"""Lista las versiones registradas de "tarifa-taxis", con la corrida de
cada una, su metrica y sus alias. No lo modifiques.

    python versiones.py
"""

import logging

from mlflow import MlflowClient

logging.getLogger("mlflow").setLevel(logging.ERROR)

NOMBRE = "tarifa-taxis"

cliente = MlflowClient()
versiones = cliente.search_model_versions(f"name='{NOMBRE}'")
for version in sorted(versiones, key=lambda v: int(v.version)):
    corrida = cliente.get_run(version.run_id)
    neuronas = corrida.data.params.get("neuronas")
    mae = corrida.data.metrics.get("mae")
    aliases = cliente.get_model_version(NOMBRE, version.version).aliases
    alias = ", ".join(aliases) if aliases else "-"
    print(f"Version {version.version}: red de {neuronas} neuronas, MAE {mae:.4f}, alias: {alias}")
