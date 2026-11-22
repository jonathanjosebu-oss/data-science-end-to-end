"""Entrena la version 1 del modelo de la tarifa, como en la sesion pasada,
y ademas guarda la distribucion de referencia de dos features en
referencia_deriva.json: las proporciones de distancia_km en sus deciles y
de zona_origen en cada zona, calculadas con los viajes de entrenamiento.
No lo modifiques.

    python entrenar.py
"""

import json

import joblib
import numpy as np
import pandas as pd
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
joblib.dump(modelo, "modelo_tarifa.joblib")
with open("modelo_version.txt", "w") as archivo:
    archivo.write("1")

cortes = np.quantile(X_entrenamiento["distancia_km"].dropna(), np.linspace(0, 1, 11))
conteo, _ = np.histogram(X_entrenamiento["distancia_km"].dropna(), bins=[-np.inf] + list(cortes[1:-1]) + [np.inf])
zonas = sorted(X_entrenamiento["zona_origen"].unique())
proporciones_zona = X_entrenamiento["zona_origen"].value_counts(normalize=True).reindex(zonas, fill_value=0)
referencia = {
    "distancia_km": {"cortes": [float(c) for c in cortes[1:-1]], "proporciones": [float(p) for p in conteo / conteo.sum()]},
    "zona_origen": {"categorias": zonas, "proporciones": [float(p) for p in proporciones_zona]},
}
with open("referencia_deriva.json", "w") as archivo:
    json.dump(referencia, archivo, indent=2)
print("Version 1 guardada, y referencia de deriva con", len(conteo), "casillas de distancia y", len(zonas), "zonas")
