"""Servicio de evaluacion de pagos: decide, en el momento del pago, si va a
revision manual. Para levantarlo desde esta carpeta, despues de
python entrenar_fraude.py:

    uvicorn servicio_fraude:app --port 8000
"""

import os
from datetime import datetime

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

from preparacion_pagos import agregar_features, columnas

RUTA_MODELO = os.environ.get("RUTA_MODELO", "modelo_fraude.joblib")
UMBRAL = 0.10

modelo = None
if os.path.exists(RUTA_MODELO):
    modelo = joblib.load(RUTA_MODELO)

app = FastAPI(title="Evaluacion de pagos")


class Pago(BaseModel):
    """Lo que la app sabe de un pago en el momento de cobrarlo."""
    # TODO 1: declara cada dato del pago con su tipo (la fecha, como
    # datetime); todos son obligatorios.
    metodo: str
    monto: float


@app.get("/salud")
def salud():
    return {"estado": "ok", "modelo_cargado": modelo is not None}


@app.post("/evaluar_pago")
def evaluar_pago(pago: Pago):
    # TODO 2: la probabilidad de fraude del pago (la columna de la clase 1),
    # sobre el pago ya preparado, como numero de Python (float).
    probabilidad = 0.0

    # Decide si el pago va a revision: revisar vale True cuando la
    # probabilidad alcanza UMBRAL.
    revisar = False

    return {"probabilidad_fraude": round(probabilidad, 4), "revisar": revisar}
