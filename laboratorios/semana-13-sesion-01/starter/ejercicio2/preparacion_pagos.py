"""Preparacion de los pagos de la app de taxis: la misma de la Semana 11,
Sesion 2, como modulo que importan el entrenamiento y la puntuacion.

    from preparacion_pagos import agregar_features, columnas, preparacion

No lo modifiques: si el entrenamiento y la puntuacion preparan los pagos de
forma distinta, el modelo recibe columnas que no son las que aprendio.
"""

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERICAS = ["monto", "distancia_km", "monto_por_km", "hora", "tarjeta_nueva", "intentos_fallidos", "viajes_previos"]
CATEGORICAS = ["metodo"]


def agregar_features(pagos):
    """Devuelve una copia de los pagos con las dos columnas derivadas."""
    pagos = pagos.copy()
    pagos["hora"] = pd.to_datetime(pagos["fecha_hora"]).dt.hour
    pagos["monto_por_km"] = pagos["monto"] / pagos["distancia_km"]
    return pagos


def columnas(pagos):
    """Las columnas que recibe el modelo, en el orden con que se entreno."""
    return pagos[NUMERICAS + CATEGORICAS]


def preparacion():
    return ColumnTransformer([
        ("numericas", StandardScaler(), NUMERICAS),
        ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS),
    ])
