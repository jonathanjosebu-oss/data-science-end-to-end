"""Pruebas de puntuar_pagos.py. Se corren desde esta carpeta con:

    pytest -v
"""

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from preparacion_pagos import agregar_features, columnas, preparacion
from puntuar_pagos import a_revisar, puntuar_lote


def pagos_de_prueba():
    """Cuatro pagos escritos a mano, uno de cada metodo y uno de madrugada."""
    return pd.DataFrame({
        "id_pago": [1, 2, 3, 4],
        "fecha_hora": ["2026-11-03 02:15", "2026-11-03 09:40", "2026-11-03 18:05", "2026-11-03 23:50"],
        "metodo": ["app", "tarjeta", "efectivo_registrado", "app"],
        "monto": [48.10, 19.75, 12.30, 33.00],
        "distancia_km": [9.2, 6.1, 3.4, 10.5],
        "tarjeta_nueva": [1, 0, 0, 0],
        "intentos_fallidos": [2, 0, 0, 1],
        "viajes_previos": [0, 25, 8, 3],
    })


def modelo_de_prueba():
    """La preparacion real con un modelo que responde la proporcion de fraude
    con que se entreno: un fraude de cuatro pagos, 0.25 para todos."""
    pagos = agregar_features(pagos_de_prueba())
    modelo = Pipeline([("preparar", preparacion()), ("modelo", DummyClassifier(strategy="prior"))])
    modelo.fit(columnas(pagos), [1, 0, 0, 0])
    return modelo


def test_columnas_de_salida():
    puntuados = puntuar_lote(modelo_de_prueba(), pagos_de_prueba(), "abc123")
    assert list(puntuados.columns) == ["id_pago", "probabilidad_fraude", "version_modelo"]


def test_una_fila_por_pago():
    pagos = pagos_de_prueba()
    puntuados = puntuar_lote(modelo_de_prueba(), pagos, "abc123")
    # Comprueba que hay una fila por pago, con los mismos id_pago y en el
    # mismo orden.


def test_probabilidades_entre_0_y_1():
    puntuados = puntuar_lote(modelo_de_prueba(), pagos_de_prueba(), "abc123")
    # Comprueba que toda probabilidad_fraude esta entre 0 y 1.


def test_cola_de_revision():
    puntuados = pd.DataFrame({
        "id_pago": [1, 2, 3, 4],
        "probabilidad_fraude": [0.05, 0.40, 0.10, 0.90],
        "version_modelo": "abc123",
    })
    cola = a_revisar(puntuados, 0.10)
    # Comprueba que en la cola quedan los pagos 4, 2 y 3, en ese orden: el
    # 0.10 entra porque el umbral incluye el limite, y el 0.05 no.
