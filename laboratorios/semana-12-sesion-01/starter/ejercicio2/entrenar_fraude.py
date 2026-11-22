"""Entrena el modelo de fraude de la Semana 11 con los 6000 pagos y lo guarda
en un archivo.

    python entrenar_fraude.py

No lo modifiques.
"""

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.pipeline import Pipeline

from preparacion_pagos import agregar_features, columnas, preparacion

RUTA_MODELO = "modelo_fraude.joblib"

pagos = agregar_features(pd.read_csv("pagos_taxi.csv"))
modelo = Pipeline([("preparar", preparacion()), ("modelo", GradientBoostingClassifier(random_state=42))])
modelo.fit(columnas(pagos), pagos["es_fraude"])

joblib.dump(modelo, RUTA_MODELO)
print(f"Modelo entrenado con {len(pagos)} pagos ({pagos['es_fraude'].sum()} fraudes) y guardado en {RUTA_MODELO}")
