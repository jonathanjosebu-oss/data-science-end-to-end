"""Comprobacion del Ejercicio 2. Correla desde esta carpeta, despues de
entrenar_fraude.py:

    python comprobar.py

Imprime OK o revisa por cada paso. No la modifiques.
"""

import ast
import os

import pytest
from fastapi.testclient import TestClient

import servicio_fraude

RIESGOSO = {"fecha_hora": "2026-11-04 02:40", "metodo": "app", "monto": 41.30, "distancia_km": 8.6,
            "tarjeta_nueva": 1, "intentos_fallidos": 2, "viajes_previos": 0}
TRANQUILO = {"fecha_hora": "2026-11-04 14:10", "metodo": "tarjeta", "monto": 19.80, "distancia_km": 6.3,
             "tarjeta_nueva": 0, "intentos_fallidos": 0, "viajes_previos": 22}
CAMPOS = {"fecha_hora", "metodo", "monto", "distancia_km", "tarjeta_nueva", "intentos_fallidos", "viajes_previos"}


def comprobar(numero, condicion):
    if condicion:
        print(f"Paso {numero}: OK")
    else:
        print(f"Paso {numero}: revisa")


def tiene_assert(ruta, nombre):
    with open(ruta) as archivo:
        arbol = ast.parse(archivo.read())
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nombre:
            return any(isinstance(hijo, ast.Assert) for hijo in ast.walk(nodo))
    return False


def evaluar(cliente, pago):
    try:
        respuesta = cliente.post("/evaluar_pago", json=pago)
    except Exception:
        return None
    if respuesta.status_code != 200:
        return None
    return respuesta.json()


if servicio_fraude.modelo is None:
    print("No existe modelo_fraude.joblib: corre primero python entrenar_fraude.py")
else:
    cliente = TestClient(servicio_fraude.app)
    campos = servicio_fraude.Pago.model_fields
    paso_1 = set(campos) == CAMPOS and all(campo.is_required() for campo in campos.values())

    riesgoso = evaluar(cliente, RIESGOSO)
    tranquilo = evaluar(cliente, TRANQUILO)
    paso_2 = (riesgoso is not None and tranquilo is not None
              and 0 <= riesgoso["probabilidad_fraude"] <= 1
              and riesgoso["probabilidad_fraude"] > tranquilo["probabilidad_fraude"])
    paso_4 = (paso_2 and riesgoso.get("revisar") is True and tranquilo.get("revisar") is False)

    argumentos = ["-q", "--no-header", "-p", "no:cacheprovider", "-W", "ignore::pytest.PytestAssertRewriteWarning"]
    paso_3 = (tiene_assert("test_servicio_fraude.py", "test_pago_valido")
              and pytest.main(argumentos + ["test_servicio_fraude.py::test_pago_valido"]) == 0)
    paso_5 = (tiene_assert("test_servicio_fraude.py", "test_pago_sin_monto_se_rechaza")
              and pytest.main(argumentos + ["test_servicio_fraude.py::test_pago_sin_monto_se_rechaza"]) == 0)

    comprobar(1, paso_1)
    comprobar(2, paso_2)
    comprobar(3, paso_3)
    comprobar(4, paso_4)
    comprobar(5, paso_5)
