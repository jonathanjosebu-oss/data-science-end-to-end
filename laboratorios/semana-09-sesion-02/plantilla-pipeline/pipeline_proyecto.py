"""Preparacion de los datos de mi proyecto, lista para produccion.

Las features que decidiste en tu notebook de la sesion pasada viven aqui,
dentro de funciones. Desde la Semana 10, tus notebooks de experimentos
importan este archivo en vez de copiar el codigo:

    from pipeline_proyecto import cargar_y_dividir, construir_preparacion

Para comprobar que corre de principio a fin, sin notebook:

    python3 pipeline_proyecto.py
"""

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# TODO: el mismo archivo de tu notebook de features de la sesion pasada.
RUTA_DATOS = "../data/processed/TODO_archivo.csv"

OBJETIVO = "TODO_columna_objetivo"
NUMERICAS = ["TODO_numerica_1", "TODO_numerica_2"]
CATEGORICAS = ["TODO_categorica_1"]
YA_LISTAS = []


def agregar_features(datos):
    # TODO: copia aqui, desde tu notebook de la sesion pasada, solo las
    # lineas que construyen tus 2 features. Sin graficos, sin prints y sin
    # las celdas que usaste para probar.
    return datos


def cargar_y_dividir(ruta=RUTA_DATOS):
    datos = agregar_features(pd.read_csv(ruta))
    X = datos[NUMERICAS + CATEGORICAS + YA_LISTAS]
    y = datos[OBJETIVO]
    # TODO: decide como dividir. Si tus filas tienen fecha y vas a predecir
    # el futuro, divide por fecha (entrenamiento antes de una fecha de corte,
    # prueba despues) en vez de al azar.
    return train_test_split(X, y, test_size=0.2, random_state=42)


def construir_preparacion():
    return ColumnTransformer([
        ("numericas", Pipeline([
            ("imputar", SimpleImputer(strategy="median")),
            ("escalar", StandardScaler()),
        ]), NUMERICAS),
        ("categoricas", Pipeline([
            ("imputar", SimpleImputer(strategy="most_frequent")),
            ("codificar", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), CATEGORICAS),
        ("ya_listas", "passthrough", YA_LISTAS),
    ])


# Esto corre con "python3 pipeline_proyecto.py", pero no cuando un
# notebook hace "from pipeline_proyecto import ...".
if __name__ == "__main__":
    X_ent, X_prueba, y_ent, y_prueba = cargar_y_dividir()
    preparacion = construir_preparacion()
    X_ent_listo = preparacion.fit_transform(X_ent)
    X_prueba_listo = preparacion.transform(X_prueba)
    print("Entrenamiento:", X_ent_listo.shape, "Prueba:", X_prueba_listo.shape)
    print(list(preparacion.get_feature_names_out()))
