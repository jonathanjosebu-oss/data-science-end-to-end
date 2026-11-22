"""Comprobacion del Ejercicio 2. Correla desde esta carpeta, despues de
entrenar_fraude.py:

    python comprobar.py

Imprime OK o revisa por cada paso. No la modifiques.
"""

import ast
import os

import pandas as pd
import pytest

import puntuar_pagos


def comprobar(numero, condicion):
    if condicion:
        print(f"Paso {numero}: OK")
    else:
        print(f"Paso {numero}: revisa")


def pruebas_con_assert(ruta):
    """Cuantas funciones test_ tiene el archivo, y cuantas tienen al menos un assert."""
    with open(ruta) as archivo:
        arbol = ast.parse(archivo.read())
    pruebas = [nodo for nodo in arbol.body if isinstance(nodo, ast.FunctionDef) and nodo.name.startswith("test_")]
    con_assert = [prueba for prueba in pruebas if any(isinstance(nodo, ast.Assert) for nodo in ast.walk(prueba))]
    return len(pruebas), len(con_assert)


if not os.path.exists(puntuar_pagos.RUTA_MODELO):
    print("No existe modelo_fraude.joblib: corre primero python entrenar_fraude.py")
else:
    modelo = puntuar_pagos.cargar_modelo(puntuar_pagos.RUTA_MODELO)
    comprobar(1, hasattr(modelo, "predict_proba"))

    pagos = pd.read_csv(puntuar_pagos.RUTA_LOTE)
    puntuados = None
    if modelo is not None:
        puntuados = puntuar_pagos.puntuar_lote(modelo, pagos, "comprobacion")
    probabilidades = None
    if puntuados is not None and "probabilidad_fraude" in puntuados.columns:
        probabilidades = puntuados["probabilidad_fraude"]
    comprobar(2, probabilidades is not None and len(probabilidades) == len(pagos)
              and probabilidades.between(0, 1).all() and probabilidades.nunique() > 1)
    comprobar(3, probabilidades is not None
              and list(puntuados.columns) == ["id_pago", "probabilidad_fraude", "version_modelo"]
              and (probabilidades == probabilidades.round(4)).all())

    ejemplo = pd.DataFrame({"id_pago": [1, 2, 3, 4], "probabilidad_fraude": [0.05, 0.40, 0.10, 0.90], "version_modelo": "x"})
    cola = puntuar_pagos.a_revisar(ejemplo, 0.10)
    comprobar(4, cola is not None and list(cola["id_pago"]) == [4, 2, 3])

    total, con_assert = pruebas_con_assert("test_puntuar_pagos.py")
    resultado = pytest.main(["-q", "--no-header", "-p", "no:cacheprovider", "-W", "ignore::pytest.PytestAssertRewriteWarning", "test_puntuar_pagos.py"])
    comprobar(5, total == 4 and con_assert == 4 and resultado == 0)
