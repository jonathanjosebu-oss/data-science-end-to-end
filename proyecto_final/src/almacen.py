"""Tablas operativas en Snowflake (esquema PRODUCCION) para el PSet 4.

LOTES_ENTRADAS   lo que el laboratorio conoce al pedir la predicción (sin target)
LAB_MEDICIONES   tiempos medidos por el laboratorio (aún no visibles)
TARGETS          mediciones que ya "llegaron" (un lote después: horizonte)
PREDICCIONES     una fila por analito predicho (auditoría: versión y run_id)
SOLICITUDES      una fila por llamada a la API (métricas de sistema)
MONITOREO        métricas por lote en formato largo (sistema, modelo, datos, deriva)
ALERTAS          alertas disparadas con su plantilla (umbral, ventana, severidad...)
REENTRENAMIENTOS ciclo challenger/champion con la decisión humana
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from src.datos import _connection_settings

SCHEMA = "PRODUCCION"

DDL = {
    "LOTES_ENTRADAS": """
        LOTE INTEGER, SEMANA_PREDICCION DATE, HECHO_ID VARCHAR, EXPERIMENTO_ID VARCHAR,
        INCHIKEY VARCHAR, SMILES VARCHAR, TIPO_COLUMNA VARCHAR, FASE_MOVIL VARCHAR,
        FLUJO_ML_MIN DOUBLE, T0_MIN DOUBLE, COLUMNA_LONGITUD_MM DOUBLE, COLUMNA_DIAMETRO_MM DOUBLE,
        COLUMNA_PARTICULA_UM DOUBLE, PH_A DOUBLE, PH_B DOUBLE, GRADIENTE VARCHAR""",
    "LAB_MEDICIONES": """
        LOTE INTEGER, SEMANA_LLEGADA_TARGET DATE, HECHO_ID VARCHAR, TIEMPO_RETENCION DOUBLE,
        TIEMPO_RETENCION_ORIGINAL DOUBLE, DERIVA_INDUCIDA BOOLEAN""",
    "TARGETS": """
        LOTE INTEGER, HECHO_ID VARCHAR, TIEMPO_RETENCION DOUBLE, DERIVA_INDUCIDA BOOLEAN,
        LLEGO_EN_LOTE INTEGER, CARGADO_EN TIMESTAMP_TZ""",
    "PREDICCIONES": """
        ID_PREDICCION VARCHAR, ID_SOLICITUD VARCHAR, TS TIMESTAMP_TZ, LOTE INTEGER,
        HECHO_ID VARCHAR, EXPERIMENTO_ID VARCHAR, SMILES VARCHAR, TIPO_COLUMNA VARCHAR,
        FASE_MOVIL VARCHAR, FLUJO_ML_MIN DOUBLE, ENTRADA_METODO VARCHAR, PREDICCION_MIN DOUBLE,
        DECISION VARCHAR, FUERA_DE_DOMINIO BOOLEAN, RESPALDO_USADO BOOLEAN, MODELO VARCHAR,
        VERSION_MODELO INTEGER, ALIAS VARCHAR, RUN_ID VARCHAR, LATENCIA_MS DOUBLE,
        ADVERTENCIAS VARCHAR""",
    "SOLICITUDES": """
        ID_SOLICITUD VARCHAR, TS TIMESTAMP_TZ, LOTE INTEGER, EXPERIMENTO_ID VARCHAR,
        N_COMPUESTOS INTEGER, STATUS INTEGER, LATENCIA_MS DOUBLE, ERROR VARCHAR""",
    "MONITOREO": """
        LOTE INTEGER, LOTE_EVALUADO INTEGER, TS TIMESTAMP_TZ, TIPO VARCHAR, METRICA VARCHAR,
        FEATURE VARCHAR, VALOR DOUBLE, UMBRAL DOUBLE, SUPERA BOOLEAN, VERSION_MODELO INTEGER""",
    "ALERTAS": """
        LOTE INTEGER, LOTE_EVALUADO INTEGER, TS TIMESTAMP_TZ, ALERTA VARCHAR, METRICA VARCHAR,
        VALOR DOUBLE, UMBRAL DOUBLE, VENTANA VARCHAR, SEVERIDAD VARCHAR, RECEPTOR VARCHAR,
        ACCION VARCHAR, DIAGNOSTICO VARCHAR""",
    "REENTRENAMIENTOS": """
        TS TIMESTAMP_TZ, LOTE INTEGER, MOTIVO VARCHAR, VENTANA VARCHAR, RUN_ID VARCHAR,
        VERSION_CHALLENGER INTEGER, VERSION_CHAMPION INTEGER, LOTE_EVALUACION INTEGER,
        RMSE_CHAMPION DOUBLE, RMSE_CHALLENGER DOUBLE, CV_STD_CHAMPION DOUBLE,
        NEGOCIO_CHAMPION DOUBLE, NEGOCIO_CHALLENGER DOUBLE, REGLA_PROMUEVE BOOLEAN,
        DECISION_HUMANA VARCHAR, MOTIVO_DECISION VARCHAR, VERSION_CHAMPION_FINAL INTEGER""",
}


@contextmanager
def conexion() -> Iterator[snowflake.connector.SnowflakeConnection]:
    settings = _connection_settings()
    con = snowflake.connector.connect(**settings, schema=SCHEMA)
    try:
        yield con
    finally:
        con.close()


def asegurar_tablas() -> None:
    with conexion() as con, con.cursor() as cur:
        database = con.database
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {database}.{SCHEMA}")
        for tabla, columnas in DDL.items():
            cur.execute(f"CREATE TABLE IF NOT EXISTS {database}.{SCHEMA}.{tabla} ({columnas})")


def ejecutar(sql: str, params: tuple | None = None) -> None:
    with conexion() as con, con.cursor() as cur:
        cur.execute(sql, params)


def consultar(sql: str, params: tuple | None = None) -> pd.DataFrame:
    with conexion() as con, con.cursor() as cur:
        cur.execute(sql, params)
        frame = cur.fetch_pandas_all()
    frame.columns = [c.lower() for c in frame.columns]
    return frame


def escribir(tabla: str, frame: pd.DataFrame, *, borrar_donde: str | None = None) -> int:
    """Inserta `frame` en PRODUCCION.<tabla>; `borrar_donde` hace la carga
    idempotente (p. ej. 'LOTE = 3' antes de reinsertar un lote)."""
    if frame.empty:
        return 0
    datos = frame.copy()
    datos.columns = [c.upper() for c in datos.columns]
    with conexion() as con:
        if borrar_donde:
            with con.cursor() as cur:
                cur.execute(f"DELETE FROM {tabla} WHERE {borrar_donde}")
        ok, _, filas, _ = write_pandas(
            con, datos, tabla, schema=SCHEMA, quote_identifiers=False, use_logical_type=True
        )
    if not ok:
        raise RuntimeError(f"No se pudo escribir {tabla}")
    return int(filas)
