"""Pruebas del servicio. Se corren desde esta carpeta con:

    pytest -v

Usan un modelo de prueba que siempre estima 20 dolares, y un archivo de
registro temporal (tmp_path, una carpeta que pytest crea para cada prueba).
"""

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.dummy import DummyRegressor
from sklearn.pipeline import Pipeline

import servicio
from features_taxis import agregar_features
from preparacion_taxis import CATEGORICAS, NUMERICAS, YA_LISTAS, preparacion

VIAJE = {
    "fecha_hora_inicio": "2026-11-05 08:30",
    "zona_origen": "Midtown",
    "zona_destino": "JFK Airport",
    "distancia_km": 26.4,
    "pasajeros": 2,
    "metodo_pago": "tarjeta",
}


@pytest.fixture
def cliente(tmp_path):
    viajes = agregar_features(pd.DataFrame([VIAJE, VIAJE]))
    modelo = Pipeline([("preparar", preparacion()), ("modelo", DummyRegressor(strategy="mean"))])
    servicio.modelo = modelo.fit(viajes[NUMERICAS + YA_LISTAS + CATEGORICAS], [20.0, 20.0])
    servicio.version_modelo = "7"
    servicio.RUTA_REGISTRO = str(tmp_path / "predicciones.jsonl")
    servicio.metricas = servicio.Metricas()
    return TestClient(servicio.app)


def test_cada_prediccion_queda_registrada(cliente):
    respuesta = cliente.post("/predecir", json=VIAJE).json()
    with open(servicio.RUTA_REGISTRO) as archivo:
        lineas = [json.loads(linea) for linea in archivo]
    assert len(lineas) == 1
    assert lineas[0]["id_prediccion"] == respuesta["id_prediccion"]
    assert lineas[0]["tarifa_estimada"] == 20.0
    assert lineas[0]["version_modelo"] == "7"
    assert lineas[0]["zona_origen"] == "Midtown"


def test_metricas_cuentan_peticiones_y_errores(cliente):
    cliente.post("/predecir", json=VIAJE)
    cliente.post("/predecir", json={"zona_origen": "Midtown"})
    resumen = cliente.get("/metricas").json()
    assert resumen["peticiones"] == 2
    assert resumen["errores_validacion"] == 1
    assert resumen["errores_servidor"] == 0
    assert resumen["latencia_p95_ms"] > 0
