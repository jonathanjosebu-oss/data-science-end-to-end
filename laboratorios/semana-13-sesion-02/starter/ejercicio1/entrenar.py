"""Entrena la version 1 del modelo de la tarifa (la red de 64 neuronas de
la sesion pasada, con los 2380 viajes de entrenamiento) y la guarda con su
numero de version. No lo modifiques.

    python entrenar.py

Como en el Ejercicio 3 de la sesion pasada, el servicio no consulta el
registro: carga el modelo exportado y su numero de version.
"""

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline

from preparacion_taxis import dividir, preparacion

viajes = pd.read_csv("viajes_features.csv")
X_entrenamiento, X_prueba, y_entrenamiento, y_prueba = dividir(viajes)
modelo = Pipeline([
    ("preparar", preparacion()),
    ("modelo", MLPRegressor(hidden_layer_sizes=(64,), max_iter=1000, random_state=42)),
])
modelo.fit(X_entrenamiento, y_entrenamiento)
mae = mean_absolute_error(y_prueba, modelo.predict(X_prueba))

joblib.dump(modelo, "modelo_tarifa.joblib")
with open("modelo_version.txt", "w") as archivo:
    archivo.write("1")
print(f"Version 1 guardada en modelo_tarifa.joblib, MAE en prueba {mae:.4f}")
