"""Pruebas del servicio. Se corren desde esta carpeta con:

    pytest -v

TestClient manda peticiones a la API sin levantar un servidor. Las pruebas
reemplazan el modelo guardado por uno pequeno que siempre estima 20 dolares:
revisan el contrato de la API (que acepta, que responde), no la calidad del
modelo, y no necesitan modelo_tarifa.joblib.
"""

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
cliente = TestClient(servicio.app)


def test_salud():
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "modelo_cargado": True}


def test_predecir_devuelve_tarifa():
    respuesta = cliente.post("/predecir", json=VIAJE)
    # TODO 3: comprueba que la respuesta tiene codigo 200 y que su JSON es
    # exactamente la tarifa del modelo de prueba: {"tarifa_estimada": 20.0}.


def test_viaje_sin_zona_de_origen_se_rechaza():
    viaje = VIAJE.copy()
    viaje.pop("zona_origen")
    respuesta = cliente.post("/predecir", json=viaje)
    # TODO 4: comprueba que el servicio rechaza el viaje con codigo 422, sin
    # llegar al modelo.
