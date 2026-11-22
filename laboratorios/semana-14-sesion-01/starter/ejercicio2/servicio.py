"""Servicio de prediccion de la tarifa, instrumentado: el de la sesion
pasada (metricas del sistema en /metricas, cada prediccion en
predicciones.jsonl), con un monitor de deriva de datos en /deriva. No lo
modifiques: lo que te toca esta en deriva.py.

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

from deriva import MonitorDeDeriva
from features_taxis import agregar_features
from preparacion_taxis import CATEGORICAS, NUMERICAS, YA_LISTAS

RUTA_MODELO = "modelo_tarifa.joblib"
RUTA_VERSION = "modelo_version.txt"
RUTA_REGISTRO = os.environ.get("RUTA_REGISTRO", "predicciones.jsonl")
RUTA_REFERENCIA = "referencia_deriva.json"

modelo = None
version_modelo = None
if os.path.exists(RUTA_MODELO):
    modelo = joblib.load(RUTA_MODELO)
    with open(RUTA_VERSION) as archivo:
        version_modelo = archivo.read().strip()

monitor = None
if os.path.exists(RUTA_REFERENCIA):
    with open(RUTA_REFERENCIA) as archivo:
        monitor = MonitorDeDeriva(json.load(archivo))


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
        if not self.latencias_ms:
            p50 = p95 = None
        else:
            p50 = round(float(np.percentile(self.latencias_ms, 50)), 2)
            p95 = round(float(np.percentile(self.latencias_ms, 95)), 2)
        return {
            "peticiones": len(self.codigos),
            "errores_validacion": sum(1 for codigo in self.codigos if codigo == 422),
            "errores_servidor": sum(1 for codigo in self.codigos if codigo >= 500),
            "latencia_p50_ms": p50,
            "latencia_p95_ms": p95,
        }


metricas = Metricas()
app = FastAPI(title="Tarifa estimada de taxis")


@app.middleware("http")
async def medir(request: Request, call_next):
    """Corre alrededor de cada peticion: lo que esta antes de call_next
    pasa antes de la ruta, y lo que esta despues, cuando ya hay respuesta."""
    if request.url.path != "/predecir":
        return await call_next(request)
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    metricas.registrar((time.perf_counter() - inicio) * 1000, respuesta.status_code)
    return respuesta


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


@app.get("/deriva")
def ver_deriva():
    return monitor.estado()


@app.post("/predecir")
def predecir(viaje: Viaje):
    datos = agregar_features(pd.DataFrame([viaje.model_dump()]))
    tarifa = round(float(modelo.predict(datos[NUMERICAS + YA_LISTAS + CATEGORICAS])[0]), 2)
    id_prediccion = uuid.uuid4().hex
    registro = {"id_prediccion": id_prediccion, "momento": datetime.now().isoformat(), "version_modelo": version_modelo}
    registro.update(viaje.model_dump(mode="json"))
    registro["tarifa_estimada"] = tarifa
    with open(RUTA_REGISTRO, "a") as archivo:
        archivo.write(json.dumps(registro) + "\n")
    monitor.registrar(viaje.model_dump())
    return {"id_prediccion": id_prediccion, "tarifa_estimada": tarifa, "version_modelo": version_modelo}
