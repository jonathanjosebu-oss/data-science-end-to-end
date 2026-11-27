"""Reproduce una corrida de entrenamiento desde lo que guarda MLflow (obs. PSet 3).

    python -m scripts.reproducir_corrida --run-id ac566f02...

Las corridas hijas del tuning del PSet 3 no guardaron el modelo como artefacto
(30 configuraciones x 3 familias; un Random Forest pesa ~159 MB). Lo que sí
guardan es suficiente para reconstruirlas: hiperparámetros, semilla, SHA-256
del snapshot de datos, commit de git y esquema de validación. Este script
aplica ese procedimiento a una corrida de entrenamiento inicial del PSet 4
(segmento `entrenamiento`, sin pesos) y comprueba que el modelo reconstruido
predice lo mismo que el modelo registrado.

1. Lee los parámetros y tags de la corrida en MLflow.
2. Verifica que el snapshot local tenga el mismo SHA-256 (`data_sha256`).
3. Entrena de nuevo con esos hiperparámetros y la semilla 42.
4. Compara con el artefacto `model` de la corrida en la muestra fija de 400 filas.
"""

from __future__ import annotations

import argparse
import json

import mlflow
import mlflow.sklearn
import numpy as np
from mlflow.tracking import MlflowClient

from scripts import exportar_fixture
from src.datos import load_snapshot
from src.experiments import configure_tracking
from src.pipeline import clear_feature_caches, model_inputs
from src.reentrenar import _params_registrados, build_model
from src.splits import TRAINING_SEGMENT, create_or_load_lots

TOLERANCIA_MIN = 1e-6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    configure_tracking()
    run = MlflowClient().get_run(args.run_id)
    tags, params = run.data.tags, run.data.params
    if tags.get("segmentos_entrenamiento") != TRAINING_SEGMENT or params.get("weighted") == "True":
        raise SystemExit(
            "Solo se reproducen corridas del entrenamiento inicial (segmento "
            "'entrenamiento', sin pesos). Las de reentrenamiento guardan su modelo."
        )

    frame, metadata = load_snapshot()
    if metadata["sha256"] != tags["data_sha256"]:
        raise SystemExit(
            f"El snapshot local ({metadata['sha256'][:8]}) no es el de la corrida "
            f"({tags['data_sha256'][:8]}). Restaure data/qsrr_c18.parquet de ese snapshot."
        )
    frame, _ = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    train = frame.loc[frame["segment"].eq(TRAINING_SEGMENT)].reset_index(drop=True)
    sample = frame.loc[frame["segment"].eq(exportar_fixture.SAMPLE_SEGMENT)].sample(
        n=exportar_fixture.SAMPLE_SIZE, random_state=42
    )

    hiper = _params_registrados(params)
    restricciones = json.loads(params.get("monotonic_constraints", "{}"))
    X, y, _ = model_inputs(train)
    reconstruido = build_model(hiper, restricciones).fit(X, y)
    registrado = mlflow.sklearn.load_model(f"runs:/{args.run_id}/model")

    X_muestra = model_inputs(sample)[0]
    diferencia = np.abs(reconstruido.predict(X_muestra) - registrado.predict(X_muestra))
    clear_feature_caches()
    print(f"corrida {args.run_id[:8]} · commit {tags.get('git_commit', '?')[:7]} · datos {metadata['sha256'][:8]}")
    print(f"hiperparámetros: {hiper}")
    print(f"diferencia máxima en {len(sample)} filas: {diferencia.max():.2e} min")
    if diferencia.max() > TOLERANCIA_MIN:
        raise SystemExit("NO reproducible: el modelo reconstruido difiere del registrado.")
    print("Reproducida: el modelo reconstruido predice lo mismo que el registrado.")


if __name__ == "__main__":
    main()
