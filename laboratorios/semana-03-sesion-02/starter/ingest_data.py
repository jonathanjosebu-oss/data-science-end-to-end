"""
Ingesta de viajes de taxi de Nueva York (NYC TLC, Yellow Taxi) hacia Postgres.

Descarga los archivos parquet de 3 meses desde la fuente pública de la TLC
(https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) y carga los
primeros 300.000 viajes de cada uno en una sola tabla de Postgres, un mes a la vez, en bloques (chunks) para no
cargar los 3 meses completos en memoria de una sola vez.

Variables de ambiente esperadas (las mismas que defino en docker-compose.yml
y en main.tf, para que el contenedor de ingesta se conecte al mismo Postgres
sea cual sea la herramienta que lo haya creado):

    PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD, PG_TABLE
"""

import os
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

MESES = ["2023-01", "2023-02", "2023-03"]
URL_BASE = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{mes}.parquet"
CARPETA_DESCARGA = Path("/tmp/datos_taxis")
TAMANO_BLOQUE = 100_000
# Los primeros 300.000 viajes de cada mes: la carga completa (unos 3 millones
# por mes) tarda mas de 15 minutos, y la sesion es sobre la infraestructura,
# no sobre el volumen. Con None se carga el mes completo.
FILAS_POR_MES = 300_000


def esperar_postgres(engine, intentos=10, espera_segundos=3):
    """Reintenta la conexión hasta que Postgres acepta conexiones.

    depends_on en docker-compose (y el meta-argumento depends_on de Terraform)
    solo esperan a que el contenedor de Postgres arranque, no a que Postgres
    ya esté listo para aceptar conexiones. Ese segundo tiempo de espera lo
    resuelve el propio script, reintentando en vez de asumir que ya está listo.
    """
    for intento in range(1, intentos + 1):
        try:
            with engine.connect():
                print(f"Conexión a Postgres lista (intento {intento}).")
                return
        except OperationalError:
            print(f"Postgres todavía no acepta conexiones (intento {intento}/{intentos}), espero {espera_segundos}s.")
            time.sleep(espera_segundos)
    raise RuntimeError("Postgres no aceptó conexiones después de varios intentos.")


def descargar_mes(mes):
    """Descarga el parquet de un mes si todavía no existe localmente."""
    CARPETA_DESCARGA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA_DESCARGA / f"yellow_tripdata_{mes}.parquet"
    if destino.exists():
        print(f"{mes}: ya está descargado en {destino}, no lo vuelvo a bajar.")
        return destino

    url = URL_BASE.format(mes=mes)
    print(f"{mes}: descargando desde {url}")
    with requests.get(url, stream=True, timeout=60) as respuesta:
        respuesta.raise_for_status()
        with open(destino, "wb") as archivo:
            for bloque in respuesta.iter_content(chunk_size=1024 * 1024):
                archivo.write(bloque)
    print(f"{mes}: descarga completa ({destino.stat().st_size / 1_000_000:.1f} MB).")
    return destino


def cargar_mes_en_bloques(engine, ruta_parquet, mes, tabla, es_primer_mes):
    """Lee el parquet del mes en bloques y los agrega (append) a la tabla.

    Solo el primer bloque del primer mes usa if_exists="replace" (crea la
    tabla desde cero); todo lo demás usa "append", para que los 3 meses
    terminen en la misma tabla en vez de sobreescribirse entre sí.
    """
    archivo_parquet = pq.ParquetFile(ruta_parquet)
    total_filas = 0
    primer_bloque_del_mes = True

    for lote in archivo_parquet.iter_batches(batch_size=TAMANO_BLOQUE):
        if FILAS_POR_MES is not None and total_filas >= FILAS_POR_MES:
            break
        df = lote.to_pandas()
        if FILAS_POR_MES is not None:
            df = df.head(FILAS_POR_MES - total_filas)
        # La TLC no escribe igual el nombre de algunas columnas en todos los
        # meses (Airport_fee en uno, airport_fee en otro): en minusculas, los
        # tres meses entran en la misma tabla.
        df.columns = [columna.lower() for columna in df.columns]
        df["mes_origen"] = mes

        reemplazar_tabla = es_primer_mes and primer_bloque_del_mes
        df.to_sql(
            tabla,
            engine,
            if_exists="replace" if reemplazar_tabla else "append",
            index=False,
        )
        primer_bloque_del_mes = False
        total_filas += len(df)

    print(f"{mes}: {total_filas:,} filas cargadas en la tabla '{tabla}'.")
    return total_filas


def main():
    host = os.environ["PG_HOST"]
    port = os.environ.get("PG_PORT", "5432")
    database = os.environ["PG_DATABASE"]
    usuario = os.environ["PG_USER"]
    password = os.environ["PG_PASSWORD"]
    tabla = os.environ.get("PG_TABLE", "viajes_taxi")

    url_conexion = f"postgresql://{usuario}:{password}@{host}:{port}/{database}"
    engine = create_engine(url_conexion)

    esperar_postgres(engine)

    total_general = 0
    for indice, mes in enumerate(MESES):
        ruta = descargar_mes(mes)
        total_general += cargar_mes_en_bloques(engine, ruta, mes, tabla, es_primer_mes=(indice == 0))

    print(f"Ingesta completa: {total_general:,} filas en total, tabla '{tabla}', meses {', '.join(MESES)}.")


if __name__ == "__main__":
    main()
