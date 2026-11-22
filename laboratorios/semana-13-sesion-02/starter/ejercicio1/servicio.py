"""Servicio de prediccion de la tarifa, instrumentado.

Ademas de responder la tarifa, mide cuanto tarda cada prediccion y con
que codigo responde (las metricas del sistema, en /metricas), y guarda
cada prediccion en predicciones.jsonl, para medir despues cuanto se
equivoco el modelo cuando llegue la tarifa cobrada (desempeno.py).

    uvicorn servicio:app --port 8000
"""

import json
import os
import time
import uuid
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from pydantic import BaseModel

from features_taxis import agregar_features
from preparacion_taxis import CATEGORICAS, NUMERICAS, YA_LISTAS

RUTA_MODELO = "modelo_tarifa.joblib"
RUTA_VERSION = "modelo_version.txt"
RUTA_REGISTRO = os.environ.get("RUTA_REGISTRO", "predicciones.jsonl")

modelo = None
version_modelo = None
if os.path.exists(RUTA_MODELO):
    modelo = joblib.load(RUTA_MODELO)
    with open(RUTA_VERSION) as archivo:
        version_modelo = archivo.read().strip()


class Metricas:
    """Las metricas del sistema, en memoria: una latencia y un codigo por
    cada peticion a /predecir."""

    def __init__(self):
        self.latencias_ms = []
        self.codigos = []

    def registrar(self, latencia_ms, codigo):
        self.latencias_ms.append(latencia_ms)
        self.codigos.append(codigo)

    def resumen(self):
        # TODO 2: devuelve un diccionario con "peticiones" (cuantas hubo),
        # "errores_validacion" (cuantas respondieron 422), "errores_servidor"
        # (cuantas respondieron 500 o mas), y "latencia_p50_ms" y
        # "latencia_p95_ms" (np.percentile, redondeadas a 2 decimales).
        # Sin peticiones, las dos latencias son None.
        return {}


metricas = Metricas()
app = FastAPI(title="Tarifa estimada de taxis")


@app.middleware("http")
async def medir(request: Request, call_next):
    """Corre alrededor de cada peticion: lo que esta antes de call_next
    pasa antes de la ruta, y lo que esta despues, cuando ya hay respuesta."""
    if request.url.path != "/predecir":
        return await call_next(request)
    # TODO 1: toma el tiempo antes y despues de call_next con time.perf_counter(),
    # y registra en metricas la latencia en milisegundos y el codigo de la
    # respuesta (respuesta.status_code).
    return await call_next(request)


class Viaje(BaseModel):
    """Lo que la app sabe de un viaje antes de que empiece."""
    fecha_hora_inicio: datetime
    zona_origen: str
    zona_destino: str
    distancia_km: float | None = None
    pasajeros: float | None = None
    metodo_pago: str | None = None


@app.get("/salud")
def salud():
    return {"estado": "ok", "modelo_cargado": modelo is not None, "version_modelo": version_modelo}


@app.get("/metricas")
def ver_metricas():
    return metricas.resumen()


@app.post("/predecir")
def predecir(viaje: Viaje):
    datos = agregar_features(pd.DataFrame([viaje.model_dump()]))
    tarifa = round(float(modelo.predict(datos[NUMERICAS + YA_LISTAS + CATEGORICAS])[0]), 2)
    id_prediccion = uuid.uuid4().hex
    # TODO 3: agrega una linea a RUTA_REGISTRO (abre el archivo con "a") con
    # json.dumps de un diccionario con id_prediccion, "momento"
    # (datetime.now().isoformat()), version_modelo, los campos del viaje
    # (viaje.model_dump(mode="json")) y "tarifa_estimada".
    return {"id_prediccion": id_prediccion, "tarifa_estimada": tarifa, "version_modelo": version_modelo}
