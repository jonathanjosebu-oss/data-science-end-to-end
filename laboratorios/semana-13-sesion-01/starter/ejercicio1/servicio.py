"""Servicio de prediccion de la tarifa, ahora con el modelo del registro.

El de la Semana 12 cargaba modelo_tarifa.joblib, un archivo que se
reemplaza cada vez que se reentrena. Este carga la version de
"tarifa-taxis" que tiene el alias "produccion", y responde cual es.

    uvicorn servicio:app --port 8000
"""

import os
from datetime import datetime

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

from features_taxis import agregar_features
from preparacion_taxis import CATEGORICAS, NUMERICAS, YA_LISTAS

NOMBRE = "tarifa-taxis"
ALIAS = os.environ.get("ALIAS_MODELO", "produccion")

modelo = None
version_servida = None

# MLflow se importa solo si hay que cargar el modelo: las pruebas no lo
# necesitan, y en GitHub Actions no hay servidor de MLflow.
if os.environ.get("CARGAR_MODELO", "si") == "si":
    import mlflow.sklearn
    from mlflow import MlflowClient

    # TODO 3: busca la version con el alias ALIAS
    # (MlflowClient().get_model_version_by_alias(NOMBRE, ALIAS)), guarda su
    # numero en version_servida y carga el modelo de esa version con
    # mlflow.sklearn.load_model(f"models:/{NOMBRE}/{version_servida}").
    pass

app = FastAPI(title="Tarifa estimada de taxis")


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
    return {"estado": "ok", "modelo_cargado": modelo is not None, "version_modelo": version_servida}


@app.post("/predecir")
def predecir(viaje: Viaje):
    datos = agregar_features(pd.DataFrame([viaje.model_dump()]))
    tarifa = modelo.predict(datos[NUMERICAS + YA_LISTAS + CATEGORICAS])[0]
    # TODO 4: agrega a la respuesta "version_modelo", con version_servida: quien
    # reciba una tarifa tiene que poder saber que modelo la calculo.
    return {"tarifa_estimada": round(float(tarifa), 2)}
