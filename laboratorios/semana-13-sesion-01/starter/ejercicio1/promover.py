"""Pone el alias "produccion" en una version de "tarifa-taxis": la version
que el servicio tiene que cargar.

    python promover.py 2

Mover el alias a otra version es todo lo que hace falta para cambiar de
modelo, o para volver al anterior: el servicio lo lee al arrancar.
"""

import logging
import sys

from mlflow import MlflowClient

logging.getLogger("mlflow").setLevel(logging.ERROR)

NOMBRE = "tarifa-taxis"
ALIAS = "produccion"

version = sys.argv[1]
cliente = MlflowClient()

# TODO 2: pon el alias ALIAS en esa version del modelo NOMBRE, con
# cliente.set_registered_model_alias(nombre, alias, version).

actual = cliente.get_model_version_by_alias(NOMBRE, ALIAS)
print(f"{NOMBRE}@{ALIAS} es ahora la version {actual.version} (corrida {actual.run_id[:12]})")
