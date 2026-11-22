"""Preparacion de viajes_features.csv: el pipeline de la Semana 9, Sesion 2,
como modulo que los notebooks de esta semana importan en vez de copiarlo.

    from preparacion_taxis import dividir, preparacion

No lo modifiques: si cambia la preparacion, cambia para todos los
experimentos que la importan, y sus resultados dejan de ser comparables.
"""

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERICAS = ["distancia_km", "pasajeros"]
YA_LISTAS = ["hora_sin", "hora_cos", "es_fin_de_semana", "es_hora_pico", "es_tarifa_fija"]
CATEGORICAS = ["zona_origen", "zona_destino", "metodo_pago"]
OBJETIVO = "tarifa"


def dividir(viajes, columnas_extra=()):
    """Entrenamiento (80%) y prueba (20%), siempre con la misma semilla.
    columnas_extra se agregan a X pero la preparacion las descarta."""
    X = viajes[NUMERICAS + YA_LISTAS + CATEGORICAS + list(columnas_extra)]
    y = viajes[OBJETIVO]
    return train_test_split(X, y, test_size=0.2, random_state=42)


def preparacion():
    return ColumnTransformer([
        ("numericas", Pipeline([
            ("imputar", SimpleImputer(strategy="median")),
            ("escalar", StandardScaler()),
        ]), NUMERICAS),
        ("ya_listas", "passthrough", YA_LISTAS),
        ("categoricas", Pipeline([
            ("imputar", SimpleImputer(strategy="most_frequent")),
            ("codificar", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), CATEGORICAS),
    ])
