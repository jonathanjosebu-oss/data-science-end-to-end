"""Run a target-blind, 50-compound Gemini benchmark against MLflow models."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.datos import load_local_environment, load_snapshot
from src.experiments import EXPERIMENT_NAME, WORKFLOW_VERSION, configure_tracking
from src.llm_benchmark import (
    DEFAULT_MODEL,
    PROMPT_VERSION,
    build_prediction_prompt,
    request_gemini_prediction,
)
from src.pipeline import clear_feature_caches, model_inputs, valid_smiles_mask
from src.splits import create_or_load_holdout

SEED = 42
SAMPLE_SIZE = 50
MODEL_NAME = "qsrr-predict-modelo"
REQUEST_INTERVAL_SECONDS = 4.5
PROGRESS_COLUMNS = (
    "hecho_id",
    "inchikey",
    "actual_retention_min",
    "gemini_prediction_min",
    "prompt_tokens",
    "output_tokens",
    "data_sha256",
    "holdout_split_hash",
    "model",
    "prompt_version",
)


def main() -> None:
    load_local_environment()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Configure GEMINI_API_KEY in the local environment or ignored "
            "proyecto_final/.env before running the authorized API benchmark."
        )

    frame, data_metadata = load_snapshot()
    valid = valid_smiles_mask(frame)
    modeling_data = frame.loc[
        valid & frame["inchikey"].notna()
    ].reset_index(drop=True)
    _, holdout, split_metadata = create_or_load_holdout(
        modeling_data,
        source_sha256=data_metadata["sha256"],
    )
    sample = (
        holdout.sort_values("hecho_id", kind="mergesort")
        .drop_duplicates("inchikey")
        .sample(
            n=min(SAMPLE_SIZE, holdout["inchikey"].nunique()),
            random_state=SEED,
        )
        .sort_values("hecho_id", kind="mergesort")
        .reset_index(drop=True)
    )
    if sample.empty:
        raise ValueError("The grouped holdout has no valid compounds to benchmark")

    X_sample, y_sample, _ = model_inputs(sample)
    champion = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")
    challenger = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@challenger")
    champion_predictions = champion.predict(X_sample)
    challenger_predictions = challenger.predict(X_sample)
    clear_feature_caches()

    progress_path = PROJECT_ROOT / "data" / "gemini_benchmark_progress.csv"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    if progress_path.exists():
        progress = pd.read_csv(
            progress_path,
            dtype={
                "hecho_id": "string",
                "data_sha256": "string",
                "holdout_split_hash": "string",
                "model": "string",
                "prompt_version": "string",
            },
        )
        if tuple(progress.columns) != PROGRESS_COLUMNS:
            raise ValueError(
                f"Benchmark checkpoint has unexpected columns: {progress_path}"
            )
        if progress["hecho_id"].duplicated().any():
            raise ValueError("Benchmark checkpoint contains duplicate observations")
        allowed_ids = set(sample["hecho_id"].astype(str))
        if not set(progress["hecho_id"].astype(str)).issubset(allowed_ids):
            raise ValueError("Benchmark checkpoint does not match the holdout sample")
        if not progress.empty:
            if not progress["data_sha256"].eq(data_metadata["sha256"]).all():
                raise ValueError("Benchmark checkpoint belongs to a different snapshot")
            if not progress["holdout_split_hash"].eq(
                split_metadata["model_rows_hash"]
            ).all():
                raise ValueError("Benchmark checkpoint belongs to a different split")
            if not progress["model"].eq(DEFAULT_MODEL).all():
                raise ValueError("Benchmark checkpoint belongs to a different model")
            if not progress["prompt_version"].eq(PROMPT_VERSION).all():
                raise ValueError("Benchmark checkpoint belongs to a different prompt")
            expected_targets = sample.set_index(
                sample["hecho_id"].astype(str)
            )["tiempo_retencion"]
            for _, saved in progress.iterrows():
                if not np.isclose(
                    float(saved["actual_retention_min"]),
                    float(expected_targets.loc[str(saved["hecho_id"])]),
                    rtol=0,
                    atol=1e-12,
                ):
                    raise ValueError(
                        "Benchmark checkpoint labels do not match the holdout"
                    )
    else:
        progress = pd.DataFrame(columns=PROGRESS_COLUMNS)

    completed_ids = set(progress["hecho_id"].astype(str))
    token_totals = {}
    configure_tracking()
    run_name = f"gemini-zero-shot-{DEFAULT_MODEL}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tags(
            {
                "phase": "llm_benchmark",
                "model_family": "gemini_zero_shot",
                "workflow_version": WORKFLOW_VERSION,
                "target_labels_sent_to_provider": "false",
                "external_data_authorized": "public_repoRT_holdout_sample",
            }
        )
        mlflow.log_params(
            {
                "provider": "Google Gemini API",
                "model": DEFAULT_MODEL,
                "benchmark_type": "zero-shot",
                "prompt_version": PROMPT_VERSION,
                "sample_size": len(sample),
                "unique_compounds": int(sample["inchikey"].nunique()),
                "random_state": SEED,
                "data_sha256": data_metadata["sha256"],
                "holdout_split_hash": split_metadata["model_rows_hash"],
                "target_labels_sent_to_provider": False,
            }
        )
        for _, row in sample.iterrows():
            observation_id = str(row["hecho_id"])
            if observation_id in completed_ids:
                continue
            time.sleep(REQUEST_INTERVAL_SECONDS)
            result = request_gemini_prediction(
                build_prediction_prompt(row),
                api_key=api_key,
                model=DEFAULT_MODEL,
            )
            new_progress = pd.DataFrame(
                [
                    {
                        "hecho_id": observation_id,
                        "inchikey": str(row["inchikey"]),
                        "actual_retention_min": float(row["tiempo_retencion"]),
                        "gemini_prediction_min": float(result["prediction"]),
                        "prompt_tokens": result["prompt_tokens"],
                        "output_tokens": result["output_tokens"],
                        "data_sha256": data_metadata["sha256"],
                        "holdout_split_hash": split_metadata["model_rows_hash"],
                        "model": DEFAULT_MODEL,
                        "prompt_version": PROMPT_VERSION,
                    }
                ],
                columns=PROGRESS_COLUMNS,
            )
            if progress.empty:
                progress = new_progress
            else:
                progress = pd.concat([progress, new_progress], ignore_index=True)
            temporary_path = progress_path.with_suffix(".tmp")
            progress.to_csv(temporary_path, index=False)
            temporary_path.replace(progress_path)
            completed_ids.add(observation_id)
            print(f"Gemini predictions: {len(completed_ids)}/{len(sample)}")

        if len(completed_ids) != len(sample):
            raise RuntimeError(
                f"Gemini benchmark incomplete: {len(completed_ids)}/{len(sample)}"
            )

        predictions = pd.DataFrame(
            {
                "hecho_id": sample["hecho_id"].astype(str),
                "inchikey": sample["inchikey"].astype(str),
                "actual_retention_min": y_sample.to_numpy(),
                "gemini_prediction_min": progress.set_index("hecho_id")
                .loc[sample["hecho_id"].astype(str), "gemini_prediction_min"]
                .to_numpy(),
                "champion_prediction_min": champion_predictions,
                "challenger_prediction_min": challenger_predictions,
            }
        )
        metrics = {}
        for label, column in (
            ("gemini", "gemini_prediction_min"),
            ("champion", "champion_prediction_min"),
            ("challenger", "challenger_prediction_min"),
        ):
            metrics[f"{label}_rmse_min"] = float(
                root_mean_squared_error(
                    predictions["actual_retention_min"], predictions[column]
                )
            )
            metrics[f"{label}_mae_min"] = float(
                mean_absolute_error(
                    predictions["actual_retention_min"], predictions[column]
                )
            )
        mlflow.log_metrics(metrics)
        for token_name, values in (
            ("prompt_tokens_total", progress["prompt_tokens"].dropna().tolist()),
            ("output_tokens_total", progress["output_tokens"].dropna().tolist()),
        ):
            known_values = [value for value in values if value is not None]
            token_totals[token_name] = (
                sum(known_values) if known_values else None
            )
        mlflow.log_metrics(
            {
                f"gemini_{name}": float(value)
                for name, value in token_totals.items()
                if value is not None
            }
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        predictions_path = PROJECT_ROOT / "docs" / (
            f"llm_benchmark_predictions_{timestamp}.csv"
        )
        metrics_path = PROJECT_ROOT / "docs" / (
            f"llm_benchmark_metrics_{timestamp}.json"
        )
        predictions.to_csv(predictions_path, index=False)
        report = {
            "provider": "Google Gemini API",
            "model": DEFAULT_MODEL,
            "benchmark_type": "zero-shot",
            "prompt_version": PROMPT_VERSION,
            "sample_size": len(sample),
            "unique_compounds": int(sample["inchikey"].nunique()),
            "random_state": SEED,
            "data_sha256": data_metadata["sha256"],
            "holdout_split_hash": split_metadata["model_rows_hash"],
            "target_labels_sent_to_provider": False,
            "api_calls": len(sample),
            **token_totals,
            "mlflow_run_id": run.info.run_id,
            "metrics": metrics,
        }
        metrics_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        mlflow.log_artifact(str(predictions_path), artifact_path="llm_benchmark")
        mlflow.log_artifact(str(metrics_path), artifact_path="llm_benchmark")

    progress_path.unlink(missing_ok=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
