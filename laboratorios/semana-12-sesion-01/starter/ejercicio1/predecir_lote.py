"""Prediccion por lotes de la tarifa de los viajes programados.

Cada noche, este script estima la tarifa de todos los viajes reservados para
el dia siguiente y deja las estimaciones en una tabla. Por la manana, la app
lee la tarifa de esa tabla: nadie espera a que el modelo responda.

    python predecir_lote.py
"""

import hashlib

import joblib
import pandas as pd

from preparacion_taxis import CATEGORICAS, NUMERICAS, YA_LISTAS

RUTA_MODELO = "modelo_tarifa.joblib"
RUTA_LOTE = "viajes_programados.csv"
RUTA_SALIDA = "tarifas_estimadas.csv"


def huella(ruta):
    """Los primeros 12 caracteres del MD5 del archivo: identifican la version
    exacta del modelo que produjo cada estimacion."""
    with open(ruta, "rb") as archivo:
        return hashlib.md5(archivo.read()).hexdigest()[:12]


def cargar_modelo(ruta):
    # TODO 1: carga el pipeline entrenado que guardo entrenar.py, con joblib.load.
    return None


def predecir_lote(modelo, viajes, version_modelo):
    """Una fila por viaje, con tres columnas: id_viaje, tarifa_estimada y
    version_modelo."""
    # TODO 2: estima la tarifa de cada viaje con el modelo, sobre las mismas
    # columnas con que se entreno.
    estimadas = None

    # TODO 3: arma la tabla de salida con las tres columnas del docstring, con
    # la tarifa redondeada a 2 decimales.
    return pd.DataFrame({"id_viaje": viajes["id_viaje"]})


if __name__ == "__main__":
    modelo = cargar_modelo(RUTA_MODELO)
    version = huella(RUTA_MODELO)
    viajes = pd.read_csv(RUTA_LOTE)

    predicciones = predecir_lote(modelo, viajes, version)
    predicciones.to_csv(RUTA_SALIDA, index=False)

    print(f"Modelo {version}: {len(viajes)} viajes leidos de {RUTA_LOTE}, {len(predicciones)} filas en {RUTA_SALIDA}")
    print(predicciones.head().to_string(index=False))
