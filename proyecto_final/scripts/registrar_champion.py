"""Entrena y registra el champion inicial del PSet 4 y exporta el fixture de CI.

Uso (desde proyecto_final/, con MLflow levantado):
    python -m scripts.registrar_champion

1. Lee el snapshot C18 de la OBT y el manifiesto de lotes por experimento.
2. Entrena con el segmento `entrenamiento` (experimentos 0006-0275) usando los
   hiperparámetros del champion del PSet 3 (sin repetir el tuning).
3. Registra `qsrr-predict-modelo` con alias `champion`.
4. Exporta a tests/fixtures/ el modelo (mlflow.sklearn.save_model), la línea
   base de respaldo, una muestra fija y la métrica que el modelo obtuvo en ella.
"""

from __future__ import annotations

import json
import shutil

import mlflow
import mlflow.sklearn

from src.datos import load_snapshot
from src.pipeline import model_inputs
from src.reentrenar import (
    MODEL_NAME,
    fit_and_register,
    regression_metrics,
)
from src.splits import PROJECT_ROOT, TRAINING_SEGMENT, create_or_load_lots

FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
SAMPLE_SIZE = 400
SAMPLE_SEGMENT = "lote_01"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--motivo",
        default="champion inicial PSet 4: OBT corregida y split por experimento",
    )
    args = parser.parse_args()
    frame, metadata = load_snapshot()
    frame, lots = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    train = frame.loc[frame["segment"].eq(TRAINING_SEGMENT)].reset_index(drop=True)
    # Muestra fija: observaciones del primer lote posterior al corte (no vistas
    # por el modelo), con semilla fija. Se guarda en el repositorio para CI.
    sample = (
        frame.loc[frame["segment"].eq(SAMPLE_SEGMENT)]
        .sample(n=SAMPLE_SIZE, random_state=42)
        .sort_values("hecho_id")
        .reset_index(drop=True)
    )

    result = fit_and_register(
        train,
        dataset_metadata=metadata,
        phase="entrenamiento_inicial",
        reason=args.motivo,
        alias="champion",
        training_segments=[TRAINING_SEGMENT],
        evaluation={"muestra_fija": sample},
        extra_tags={"corte_experimento": lots["cutoff_experiment"]},
    )
    sample_metrics = regression_metrics(
        sample["tiempo_retencion"], result["model"].predict(model_inputs(sample)[0])
    )
    print(
        f"{MODEL_NAME} v{result['version']} run={result['run_id']} "
        f"CV RMSE={result['cv_rmse_mean']:.3f}±{result['cv_rmse_std']:.3f} "
        f"muestra fija RMSE={sample_metrics['rmse']:.4f}"
    )

    FIXTURES.mkdir(parents=True, exist_ok=True)
    model_dir = FIXTURES / "modelo"
    if model_dir.exists():
        shutil.rmtree(model_dir)
    mlflow.sklearn.save_model(
        result["model"],
        str(model_dir),
        signature=mlflow.models.get_model_info(
            f"runs:/{result['run_id']}/model"
        ).signature,
        pip_requirements=str(PROJECT_ROOT / "api" / "requirements.txt")
        if (PROJECT_ROOT / "api" / "requirements.txt").is_file()
        else None,
    )
    columns = ["hecho_id", "experimento_id", "smiles", "tipo_columna", "fase_movil",
               "flujo_ml_min", "tiempo_retencion", "inchikey"]
    sample.loc[:, columns].to_csv(FIXTURES / "muestra_fija.csv", index=False)
    (FIXTURES / "linea_base.json").write_text(
        json.dumps(result["baseline"]), encoding="utf-8"
    )
    (FIXTURES / "modelo_metadata.json").write_text(
        json.dumps(
            {
                "model_name": MODEL_NAME,
                "version": result["version"],
                "alias": "champion",
                "run_id": result["run_id"],
                "cv_rmse_mean": result["cv_rmse_mean"],
                "cv_rmse_std": result["cv_rmse_std"],
                "muestra_fija_rmse": sample_metrics["rmse"],
                "muestra_fija_mae": sample_metrics["mae"],
                "pair_lower_error_quantile": result["interval"]["lower_error_quantile"],
                "pair_upper_error_quantile": result["interval"]["upper_error_quantile"],
                "corte_experimento": lots["cutoff_experiment"],
                "dominio": result["domain"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
