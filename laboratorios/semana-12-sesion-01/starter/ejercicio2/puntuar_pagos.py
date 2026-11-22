"""Puntuacion por lotes de los pagos de ayer.

Cada madrugada, este script calcula la probabilidad de fraude de todos los
pagos del dia anterior y arma la cola de revision manual: los pagos que
superan el umbral elegido en la Semana 11. El equipo de revision la trabaja
durante el dia.

    python puntuar_pagos.py
"""

import hashlib

import joblib
import pandas as pd

from preparacion_pagos import agregar_features, columnas

RUTA_MODELO = "modelo_fraude.joblib"
RUTA_LOTE = "pagos_ayer.csv"
RUTA_PUNTUADOS = "pagos_puntuados.csv"
RUTA_COLA = "cola_revision.csv"
UMBRAL = 0.10


def huella(ruta):
    with open(ruta, "rb") as archivo:
        return hashlib.md5(archivo.read()).hexdigest()[:12]


def cargar_modelo(ruta):
    # TODO 1: carga el modelo que guardo entrenar_fraude.py.
    return None


def puntuar_lote(modelo, pagos, version_modelo):
    """Una fila por pago, con tres columnas: id_pago, probabilidad_fraude y
    version_modelo."""
    # TODO 2: la probabilidad de fraude de cada pago (la columna de la
    # clase 1), sobre los pagos ya preparados.
    probabilidades = None

    # TODO 3: la tabla de salida, con la probabilidad redondeada a 4 decimales.
    return pd.DataFrame({"id_pago": pagos["id_pago"]})


def a_revisar(puntuados, umbral):
    """Los pagos puntuados con probabilidad mayor o igual al umbral, del mas
    sospechoso al menos sospechoso."""
    # Deja en cola solo las filas de puntuados que alcanzan el umbral,
    # ordenadas de mayor a menor probabilidad_fraude.
    cola = puntuados
    return cola


if __name__ == "__main__":
    modelo = cargar_modelo(RUTA_MODELO)
    version = huella(RUTA_MODELO)
    pagos = pd.read_csv(RUTA_LOTE)

    puntuados = puntuar_lote(modelo, pagos, version)
    puntuados.to_csv(RUTA_PUNTUADOS, index=False)
    cola = a_revisar(puntuados, UMBRAL)
    cola.to_csv(RUTA_COLA, index=False)

    print(f"Modelo {version}: {len(pagos)} pagos leidos de {RUTA_LOTE}, {len(puntuados)} filas en {RUTA_PUNTUADOS}")
    print(f"Cola de revision (umbral {UMBRAL}): {len(cola)} pagos en {RUTA_COLA}")
    print(cola.head().to_string(index=False))
