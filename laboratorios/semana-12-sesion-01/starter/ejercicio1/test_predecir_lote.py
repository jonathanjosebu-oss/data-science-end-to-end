"""Pruebas de predecir_lote.py. Se corren desde esta carpeta con:

    pytest -v

No leen viajes_programados.csv ni el modelo guardado: cada prueba arma sus
propios viajes y un modelo pequeno. Asi prueban el codigo y no los datos, y
corren igual en cualquier maquina, tambien en GitHub Actions.
"""

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.pipeline import Pipeline

from predecir_lote import predecir_lote
from preparacion_taxis import CATEGORICAS, NUMERICAS, YA_LISTAS, preparacion


def viajes_de_prueba():
    """Tres viajes escritos a mano: uno normal, uno sin pasajeros y uno
    desde el aeropuerto."""
    return pd.DataFrame({
        "id_viaje": [11, 12, 13],
        "zona_origen": ["Midtown", "Brooklyn", "JFK Airport"],
        "zona_destino": ["Harlem", "Midtown", "Midtown"],
        "distancia_km": [8.1, 10.4, 26.0],
        "pasajeros": [1.0, np.nan, 2.0],
        "metodo_pago": ["tarjeta", "efectivo", "tarjeta"],
        "hora_sin": [0.5, -0.5, 0.0],
        "hora_cos": [0.866, 0.866, -1.0],
        "es_fin_de_semana": [0, 0, 1],
        "es_hora_pico": [1, 0, 0],
        "es_tarifa_fija": [0, 0, 1],
    })


def modelo_de_prueba():
    """La preparacion real con un modelo que siempre estima 20 dolares. Estas
    pruebas revisan la forma de la salida, no la calidad de la estimacion."""
    viajes = viajes_de_prueba()
    modelo = Pipeline([("preparar", preparacion()), ("modelo", DummyRegressor(strategy="mean"))])
    modelo.fit(viajes[NUMERICAS + YA_LISTAS + CATEGORICAS], [20.0, 20.0, 20.0])
    return modelo


def test_columnas_de_salida():
    predicciones = predecir_lote(modelo_de_prueba(), viajes_de_prueba(), "abc123")
    assert list(predicciones.columns) == ["id_viaje", "tarifa_estimada", "version_modelo"]


def test_una_prediccion_por_viaje():
    viajes = viajes_de_prueba()
    predicciones = predecir_lote(modelo_de_prueba(), viajes, "abc123")
    # TODO 4: comprueba que hay una fila por viaje, con los mismos id_viaje y
    # en el mismo orden.


def test_viaje_incompleto_tambien_se_estima():
    predicciones = predecir_lote(modelo_de_prueba(), viajes_de_prueba(), "abc123")
    # TODO 5: el viaje 12 llega sin pasajeros. Comprueba que ningun viaje se
    # queda sin tarifa estimada, y que todas las filas llevan la version
    # del modelo que se paso.
