"""Pruebas del servicio. Se corren desde esta carpeta con:

    pytest -v

Como en la Semana 12, las pruebas no usan el registro: CARGAR_MODELO=no
evita que el servicio lo busque al importarse (en GitHub Actions no hay
servidor de MLflow), y se reemplaza el modelo por uno que siempre estima 20
dolares, con una version inventada.
"""

import os

os.environ["CARGAR_MODELO"] = "no"

import pandas as pd
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


def modelo_de_prueba():
    viajes = agregar_features(pd.DataFrame([VIAJE, VIAJE]))
    modelo = Pipeline([("preparar", preparacion()), ("modelo", DummyRegressor(strategy="mean"))])
    modelo.fit(viajes[NUMERICAS + YA_LISTAS + CATEGORICAS], [20.0, 20.0])
    return modelo


servicio.modelo = modelo_de_prueba()
servicio.version_servida = "7"
cliente = TestClient(servicio.app)


def test_salud_dice_que_version_sirve():
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "modelo_cargado": True, "version_modelo": "7"}


def test_cada_prediccion_dice_que_version_la_calculo():
    respuesta = cliente.post("/predecir", json=VIAJE)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"tarifa_estimada": 20.0, "version_modelo": "7"}
