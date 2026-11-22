"""Pruebas del servicio de fraude. Se corren desde esta carpeta con:

    pytest -v
"""

import pandas as pd
from fastapi.testclient import TestClient
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

import servicio_fraude
from preparacion_pagos import agregar_features, columnas, preparacion

PAGO = {
    "fecha_hora": "2026-11-04 02:40",
    "metodo": "app",
    "monto": 41.30,
    "distancia_km": 8.6,
    "tarjeta_nueva": 1,
    "intentos_fallidos": 2,
    "viajes_previos": 0,
}


def modelo_de_prueba():
    """Un modelo que responde 0.25 para cualquier pago: un fraude de cuatro."""
    pagos = agregar_features(pd.DataFrame([PAGO, PAGO, PAGO, PAGO]))
    modelo = Pipeline([("preparar", preparacion()), ("modelo", DummyClassifier(strategy="prior"))])
    modelo.fit(columnas(pagos), [1, 0, 0, 0])
    return modelo


servicio_fraude.modelo = modelo_de_prueba()
cliente = TestClient(servicio_fraude.app)


def test_salud():
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["modelo_cargado"] is True


def test_pago_valido():
    respuesta = cliente.post("/evaluar_pago", json=PAGO)
    # TODO 3: comprueba que la respuesta tiene codigo 200 y que su JSON es
    # exactamente {"probabilidad_fraude": 0.25, "revisar": True}: con el
    # modelo de prueba, 0.25 alcanza el umbral de 0.10.


def test_pago_sin_monto_se_rechaza():
    pago = PAGO.copy()
    pago.pop("monto")
    respuesta = cliente.post("/evaluar_pago", json=pago)
    # Comprueba que el servicio rechaza el pago con codigo 422.
