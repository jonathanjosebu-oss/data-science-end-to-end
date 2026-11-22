"""Manda al servicio tres semanas de viajes, una despues de otra, y despues
de cada una muestra lo que dice /deriva. No lo modifiques.

    python simular_semanas.py

- semana_normal.csv: 300 viajes como los de entrenamiento.
- semana_feriado.csv: 300 viajes de una semana de feriado, con muchos mas
  viajes al aeropuerto.
- semana_aumento.csv: 300 viajes como los de entrenamiento, de una semana
  en que la ciudad aumento 20% la tarifa por taximetro (la tarifa cobrada
  cambio; los viajes, no).

Usa TestClient, como la simulacion de la sesion pasada.
"""

import os

import pandas as pd
from fastapi.testclient import TestClient

if os.path.exists("predicciones.jsonl"):
    os.remove("predicciones.jsonl")

import servicio

cliente = TestClient(servicio.app)
for nombre in ["normal", "feriado", "aumento"]:
    viajes = pd.read_csv("semana_" + nombre + ".csv")
    for viaje in viajes.drop(columns=["tarifa_cobrada"]).to_dict("records"):
        peticion = {clave: valor for clave, valor in viaje.items() if not pd.isna(valor)}
        cliente.post("/predecir", json=peticion)
    print("Despues de la semana", nombre + ":", cliente.get("/deriva").json())
