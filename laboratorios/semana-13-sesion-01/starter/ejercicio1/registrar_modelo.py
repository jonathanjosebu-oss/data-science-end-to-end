"""Entrena el modelo de la tarifa, mide su error y lo registra en el
registro de modelos de MLflow como una version nueva de "tarifa-taxis".

    python registrar_modelo.py 64

El numero es el tamano de la capa oculta de la red neuronal. Cada vez que
lo corres, el registro guarda una version nueva, con su numero, su corrida
y su metrica: ninguna version reemplaza a otra.
"""

import logging
import sys

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline

from preparacion_taxis import dividir, preparacion

logging.getLogger("mlflow").setLevel(logging.ERROR)

NOMBRE = "tarifa-taxis"

neuronas = int(sys.argv[1])
viajes = pd.read_csv("viajes_features.csv")
X_entrenamiento, X_prueba, y_entrenamiento, y_prueba = dividir(viajes)

mlflow.set_experiment("tarifa-taxis-registro")
with mlflow.start_run(run_name=f"red-{neuronas}"):
    modelo = Pipeline([
        ("preparar", preparacion()),
        ("modelo", MLPRegressor(hidden_layer_sizes=(neuronas,), max_iter=1000, random_state=42)),
    ])
    modelo.fit(X_entrenamiento, y_entrenamiento)
    mae = mean_absolute_error(y_prueba, modelo.predict(X_prueba))
    mlflow.log_param("neuronas", neuronas)
    mlflow.log_metric("mae", mae)

    # TODO 1: guarda el modelo en la corrida (mlflow.sklearn.log_model, con
    # el nombre de artefacto "modelo") y registralo a la vez, con
    # registered_model_name=NOMBRE. log_model devuelve informacion del
    # modelo: su atributo registered_model_version es el numero de la
    # version nueva.
    version = None

print(f"Version {version} de {NOMBRE}: red de {neuronas} neuronas, MAE {mae:.4f}")
