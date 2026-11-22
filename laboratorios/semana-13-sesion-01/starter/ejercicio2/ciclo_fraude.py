"""Ejercicio 2: el ciclo de vida del modelo de fraude.

El equipo entrena modelos candidatos de fraude cada tanto. Cada candidato
se registra como una version de "fraude-pagos", con su recall y su
precision al umbral de 0.10. Una version llega a "produccion" solo si
detecta mas fraudes (mayor recall) que la que esta ahi ahora. Cada
version queda etiquetada con el resultado de esa comparacion.

    python ciclo_fraude.py

Despues de resolver, corre python comprobar.py hasta que los cinco pasos
digan OK.
"""

import logging

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from preparacion_pagos import agregar_features, columnas, preparacion

logging.getLogger("mlflow").setLevel(logging.ERROR)

NOMBRE = "fraude-pagos"
ALIAS = "produccion"
UMBRAL = 0.10


def datos():
    pagos = agregar_features(pd.read_csv("pagos_taxi.csv"))
    return train_test_split(columnas(pagos), pagos["es_fraude"], test_size=0.2, random_state=42, stratify=pagos["es_fraude"])


def evaluar(modelo, X_prueba, y_prueba):
    alertas = modelo.predict_proba(X_prueba)[:, 1] >= UMBRAL
    return {"recall": recall_score(y_prueba, alertas), "precision": precision_score(y_prueba, alertas)}


def registrar(modelo, nombre_corrida, metricas):
    """Guarda el modelo y sus metricas en una corrida nueva, lo registra
    como version nueva de NOMBRE, y devuelve el numero de version."""
    # TODO 1: abre una corrida con run_name=nombre_corrida, guarda las
    # metricas (mlflow.log_metrics) y el modelo con
    # mlflow.sklearn.log_model(modelo, "modelo", registered_model_name=NOMBRE).
    # Devuelve el numero de version, como int.
    return None


def metrica_de(version, metrica):
    """La metrica guardada en la corrida que produjo esa version."""
    # TODO 2: la version sabe de que corrida salio
    # (MlflowClient().get_model_version(NOMBRE, version).run_id), y la
    # corrida guarda sus metricas (get_run(run_id).data.metrics).
    return None


def version_en_produccion():
    """El numero de la version con el alias ALIAS, o None si ninguna lo tiene."""
    # TODO 3: get_model_version_by_alias lanza MlflowException si el alias
    # no existe todavia (o si el modelo no existe).
    return None


def promover_si_mejora(version):
    """Pone ALIAS en la version si no hay ninguna en produccion, o si su
    recall es mayor que el de la de produccion. Devuelve True si la promovio.
    En cualquier caso, etiqueta la version."""
    cliente = MlflowClient()
    actual = version_en_produccion()

    # Decide si la version mejora a la de produccion: mejora si no hay
    # ninguna, o si su recall es estrictamente mayor. Si mejora, mueve el
    # alias con set_registered_model_alias.
    mejora = False

    # Etiqueta la version (set_model_version_tag) con la clave "validacion"
    # y el valor "aprobada" o "rechazada", y con la clave "comparada_con"
    # y el numero de la version de produccion contra la que se comparo, o
    # "ninguna".
    return mejora


if __name__ == "__main__":
    mlflow.set_experiment("fraude-pagos-ciclo")
    X_entrenamiento, X_prueba, y_entrenamiento, y_prueba = datos()
    candidatos = [
        ("logistica", LogisticRegression(max_iter=1000)),
        ("gradient-boosting", GradientBoostingClassifier(random_state=42)),
        ("logistica-muy-regularizada", LogisticRegression(C=0.001, max_iter=1000)),
    ]
    for nombre, estimador in candidatos:
        modelo = Pipeline([("preparar", preparacion()), ("modelo", estimador)])
        modelo.fit(X_entrenamiento, y_entrenamiento)
        metricas = evaluar(modelo, X_prueba, y_prueba)
        version = registrar(modelo, nombre, metricas)
        promovida = promover_si_mejora(version)
        print(f"{nombre}: version {version}, recall {metricas['recall']:.3f}, precision {metricas['precision']:.3f}, promovida: {promovida}")
    print(f"En produccion: version {version_en_produccion()}")
