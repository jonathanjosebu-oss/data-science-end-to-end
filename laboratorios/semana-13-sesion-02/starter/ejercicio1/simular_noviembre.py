"""Simula noviembre: la app pide la tarifa de cada viaje de
viajes_noviembre.csv al servicio, y cuando el viaje termina, el sistema de
cobros anota la tarifa cobrada junto al id de la prediccion, en cobros.csv.
No lo modifiques.

    python simular_noviembre.py

Usa TestClient: las peticiones pasan por el servicio completo (el
middleware incluido), sin levantar uvicorn. Borra predicciones.jsonl y
cobros.csv antes de empezar.
"""

import csv
import os

import pandas as pd
from fastapi.testclient import TestClient

for ruta in ["predicciones.jsonl", "cobros.csv"]:
    if os.path.exists(ruta):
        os.remove(ruta)

import servicio

cliente = TestClient(servicio.app)
viajes = pd.read_csv("viajes_noviembre.csv")
cobros = []
for viaje in viajes.to_dict("records"):
    tarifa_real = viaje.pop("tarifa_real")
    peticion = {clave: valor for clave, valor in viaje.items() if not pd.isna(valor)}
    respuesta = cliente.post("/predecir", json=peticion).json()
    cobros.append({"id_prediccion": respuesta.get("id_prediccion"), "tarifa_cobrada": tarifa_real})

# Tres peticiones mal formadas, como las que manda una version vieja de la app.
for _ in range(3):
    cliente.post("/predecir", json={"zona_origen": "Midtown"})

with open("cobros.csv", "w", newline="") as archivo:
    escritor = csv.DictWriter(archivo, fieldnames=["id_prediccion", "tarifa_cobrada"])
    escritor.writeheader()
    escritor.writerows(cobros)

print(f"{len(viajes)} viajes simulados, del {viajes['fecha_hora_inicio'].min()[:10]} al {viajes['fecha_hora_inicio'].max()[:10]}")
print("Metricas del sistema:", cliente.get("/metricas").json())
