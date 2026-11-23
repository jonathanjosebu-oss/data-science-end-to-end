"""Exporta el champion vigente del Model Registry a tests/fixtures/ para CI.

Uso (desde proyecto_final/, con MLflow levantado):
    python -m scripts.exportar_fixture

Escribe el modelo (mlflow.sklearn.save_model), la línea base y el dominio del
run, la muestra fija (400 filas del lote_01, semilla 42) y la métrica que el
modelo obtiene en ella, que test_modelo.py debe reproducir. Se ejecuta después
de cada promoción o rollback que deba reflejarse en CI.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from src.datos import load_snapshot
from src.experiments import configure_tracking
from src.pipeline import RAW_FEATURE_COLUMNS, model_inputs
from src.reentrenar import BASELINE_ARTIFACT, DOMAIN_ARTIFACT, MODEL_NAME, regression_metrics
from src.splits import PROJECT_ROOT, create_or_load_lots

FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
SAMPLE_SIZE = 400
SAMPLE_SEGMENT = "lote_01"


def main(alias: str = "champion") -> dict:
    configure_tracking()
    client = MlflowClient()
    mv = client.get_model_version_by_alias(MODEL_NAME, alias)
    model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{mv.version}")
    run = client.get_run(mv.run_id)

    frame, metadata = load_snapshot()
    frame, lots = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    sample = (
        frame.loc[frame["segment"].eq(SAMPLE_SEGMENT)]
        .sample(n=SAMPLE_SIZE, random_state=42)
        .sort_values("hecho_id")
        .reset_index(drop=True)
    )
    metrics = regression_metrics(sample["tiempo_retencion"], model.predict(model_inputs(sample)[0]))

    FIXTURES.mkdir(parents=True, exist_ok=True)
    model_dir = FIXTURES / "modelo"
    if model_dir.exists():
        shutil.rmtree(model_dir)
    mlflow.sklearn.save_model(
        model,
        str(model_dir),
        signature=mlflow.models.get_model_info(f"models:/{MODEL_NAME}/{mv.version}").signature,
    )
    columns = ["hecho_id", "experimento_id", *RAW_FEATURE_COLUMNS, "tiempo_retencion", "inchikey"]
    sample.loc[:, columns].to_csv(FIXTURES / "muestra_fija.csv", index=False)
    artefactos = {}
    for name in (BASELINE_ARTIFACT, DOMAIN_ARTIFACT):
        artefactos[name] = json.loads(Path(client.download_artifacts(mv.run_id, name)).read_text("utf-8"))
    (FIXTURES / "linea_base.json").write_text(json.dumps(artefactos[BASELINE_ARTIFACT]), encoding="utf-8")
    info = {
        "model_name": MODEL_NAME,
        "version": int(mv.version),
        "alias": alias,
        "run_id": mv.run_id,
        "cv_rmse_mean": run.data.metrics["cv_rmse_mean"],
        "cv_rmse_std": run.data.metrics["cv_rmse_std"],
        "muestra_fija_rmse": metrics["rmse"],
        "muestra_fija_mae": metrics["mae"],
        "pair_lower_error_quantile": run.data.metrics["pair_lower_error_quantile"],
        "pair_upper_error_quantile": run.data.metrics["pair_upper_error_quantile"],
        "corte_experimento": lots["cutoff_experiment"],
        "dominio": artefactos[DOMAIN_ARTIFACT],
    }
    (FIXTURES / "modelo_metadata.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(f"Fixture: {MODEL_NAME} v{mv.version} ({alias}) muestra fija RMSE={metrics['rmse']:.4f}")
    return info


if __name__ == "__main__":
    main()
