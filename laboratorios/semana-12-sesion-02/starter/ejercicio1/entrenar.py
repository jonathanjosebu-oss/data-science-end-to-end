"""Entrena el modelo final de la Semana 11 con todos los viajes y lo guarda
en un archivo, para que otro programa lo use sin volver a entrenarlo.

    python entrenar.py

En la Semana 11 elegiste la red neuronal con 2380 viajes de entrenamiento y
la mediste con los 595 de prueba. Para predecir viajes nuevos ya no hace
falta reservar una prueba: el modelo que se usa se entrena con todos.
No lo modifiques.
"""

import joblib
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline

from preparacion_taxis import CATEGORICAS, NUMERICAS, OBJETIVO, YA_LISTAS, preparacion

RUTA_MODELO = "modelo_tarifa.joblib"

viajes = pd.read_csv("viajes_features.csv")
modelo = Pipeline([
    ("preparar", preparacion()),
    ("modelo", MLPRegressor(hidden_layer_sizes=(64,), max_iter=1000, random_state=42)),
])
modelo.fit(viajes[NUMERICAS + YA_LISTAS + CATEGORICAS], viajes[OBJETIVO])

joblib.dump(modelo, RUTA_MODELO)
print(f"Modelo entrenado con {len(viajes)} viajes y guardado en {RUTA_MODELO}")
