"""Comprobacion del Ejercicio 2. Correla desde esta carpeta, con el
servidor de MLflow levantado:

    python comprobar.py

Registra dos modelos de prueba en un modelo nuevo (con un nombre distinto
cada vez, para no tocar "fraude-pagos") y revisa cada paso. Imprime OK o
revisa por cada uno. No la modifiques.
"""

import logging
import uuid

import mlflow
from mlflow import MlflowClient
from sklearn.dummy import DummyClassifier

import ciclo_fraude

logging.getLogger("mlflow").setLevel(logging.ERROR)


def comprobar(numero, condicion):
    if condicion:
        print(f"Paso {numero}: OK")
    else:
        print(f"Paso {numero}: revisa")


def intentar(funcion, *argumentos):
    try:
        return funcion(*argumentos)
    except Exception:
        return None


ciclo_fraude.NOMBRE = "comprobacion-" + uuid.uuid4().hex[:8]
mlflow.set_experiment("fraude-pagos-comprobacion")
cliente = MlflowClient()
modelo = DummyClassifier().fit([[0], [1]], [0, 1])

primera = intentar(ciclo_fraude.registrar, modelo, "prueba-1", {"recall": 0.30, "precision": 0.50})
segunda = intentar(ciclo_fraude.registrar, modelo, "prueba-2", {"recall": 0.20, "precision": 0.90})
paso_1 = primera == 1 and segunda == 2
paso_2 = paso_1 and intentar(ciclo_fraude.metrica_de, 2, "precision") == 0.90
paso_3 = paso_1 and intentar(ciclo_fraude.version_en_produccion) is None

promovida_1 = intentar(ciclo_fraude.promover_si_mejora, 1) if paso_1 else None
promovida_2 = intentar(ciclo_fraude.promover_si_mejora, 2) if paso_1 else None
paso_4 = (promovida_1 is True and promovida_2 is False
          and intentar(ciclo_fraude.version_en_produccion) == 1)

paso_5 = False
if paso_4:
    etiquetas_1 = cliente.get_model_version(ciclo_fraude.NOMBRE, 1).tags
    etiquetas_2 = cliente.get_model_version(ciclo_fraude.NOMBRE, 2).tags
    paso_5 = (etiquetas_1.get("validacion") == "aprobada" and etiquetas_1.get("comparada_con") == "ninguna"
              and etiquetas_2.get("validacion") == "rechazada" and etiquetas_2.get("comparada_con") == "1")

comprobar(1, paso_1)
comprobar(2, paso_2)
comprobar(3, paso_3)
comprobar(4, paso_4)
comprobar(5, paso_5)
