"""MLflow tracking helpers for comparable, group-aware regression experiments."""

from __future__ import annotations

import os
import subprocess
import time
import gc
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.metrics import make_scorer, mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import ParameterSampler, cross_validate

from src.pipeline import clear_feature_caches, make_model_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
EXPERIMENT_NAME = "qsrr-predict-c18"
WORKFLOW_VERSION = "stratified-selection-full-final-v1"
SCORING = {
    "rmse": make_scorer(root_mean_squared_error, greater_is_better=False),
    "mae": "neg_mean_absolute_error",
}
MODEL_PIP_REQUIREMENTS = [
    "scikit-learn==1.5.2",
    "pandas==2.2.2",
    "numpy==1.26.4",
    "scipy==1.15.3",
    "rdkit==2024.9.6",
]


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "not-available"
    return result.stdout.strip()


def configure_tracking() -> str:
    mlflow.set_tracking_uri(TRACKING_URI)
    experiment = mlflow.set_experiment(EXPERIMENT_NAME)
    return experiment.experiment_id


def _log_run_context(
    *,
    phase: str,
    family: str,
    dataset_metadata: dict[str, Any],
    seed: int,
) -> None:
    mlflow.set_tags(
        {
            "phase": phase,
            "model_family": family,
            "workflow_version": WORKFLOW_VERSION,
            "git_commit": _git_commit(),
            "data_tables": dataset_metadata["source_tables"],
            "data_snapshot_read_at_utc": dataset_metadata["snapshot_read_at_utc"],
            "data_sha256": dataset_metadata["sha256"],
            "training_sample_sha256": dataset_metadata.get(
                "training_sample_sha256", dataset_metadata["sha256"]
            ),
            "sampling_method": dataset_metadata.get(
                "sampling_method", "full training partition"
            ),
            "sampling_seed": str(dataset_metadata.get("sampling_seed", seed)),
            "data_source_ref": dataset_metadata.get("source_ref", "not-recorded"),
            "validation": "GroupKFold by inchikey",
            "random_state": str(seed),
        }
    )
    mlflow.log_param("data_sha256", dataset_metadata["sha256"])
    mlflow.log_param("data_rows", int(dataset_metadata["rows"]))
    mlflow.log_param(
        "source_rows", int(dataset_metadata.get("source_rows", dataset_metadata["rows"]))
    )
    mlflow.log_param(
        "training_sample_sha256",
        dataset_metadata.get("training_sample_sha256", dataset_metadata["sha256"]),
    )


def _log_model(model: Any, X: pd.DataFrame, artifact_path: str = "model") -> None:
    example = X.head(min(5, len(X))).copy()
    predictions = model.predict(example)
    signature = infer_signature(example, predictions)
    clear_feature_caches()
    gc.collect()
    mlflow.sklearn.log_model(
        sk_model=model,
        artifact_path=artifact_path,
        signature=signature,
        input_example=example,
        code_paths=["src"],
        pip_requirements=MODEL_PIP_REQUIREMENTS,
    )


def evaluate_cv_run(
    *,
    run_name: str,
    phase: str,
    family: str,
    estimator: Any,
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    cv: Any,
    dataset_metadata: dict[str, Any],
    seed: int = 42,
    nested: bool = False,
) -> dict[str, Any]:
    """Evaluate one default model using identical grouped CV and log its artifact."""
    configure_tracking()
    with mlflow.start_run(run_name=run_name, nested=nested):
        _log_run_context(
            phase=phase,
            family=family,
            dataset_metadata=dataset_metadata,
            seed=seed,
        )
        model = (
            estimator.named_steps["regressor"]
            if hasattr(estimator, "named_steps")
            else estimator
        )
        mlflow.log_params(model.get_params(deep=False))
        started = time.perf_counter()
        scores = cross_validate(
            estimator,
            X,
            y,
            groups=groups,
            cv=cv,
            scoring=SCORING,
            return_train_score=True,
            n_jobs=1,
            error_score="raise",
        )
        cv_seconds = time.perf_counter() - started
        train_rmse = -scores["train_rmse"]
        test_rmse = -scores["test_rmse"]
        train_mae = -scores["train_mae"]
        test_mae = -scores["test_mae"]
        metrics = {
            "train_rmse_mean": float(np.mean(train_rmse)),
            "cv_rmse_mean": float(np.mean(test_rmse)),
            "cv_rmse_std": float(np.std(test_rmse, ddof=1)),
            "train_mae_mean": float(np.mean(train_mae)),
            "cv_mae_mean": float(np.mean(test_mae)),
            "cv_mae_std": float(np.std(test_mae, ddof=1)),
            "rmse_train_cv_gap": float(np.mean(test_rmse) - np.mean(train_rmse)),
            "cv_fit_seconds_total": float(cv_seconds),
            "cv_seconds_per_fold_mean": float(np.mean(scores["fit_time"])),
        }
        mlflow.log_metrics(metrics)

        clear_feature_caches()
        gc.collect()
        fitted = estimator.fit(X, y)
        train_predictions = fitted.predict(X)
        full_train_rmse = float(root_mean_squared_error(y, train_predictions))
        full_train_mae = float(mean_absolute_error(y, train_predictions))
        mlflow.log_metrics(
            {
                "full_train_rmse": full_train_rmse,
                "full_train_mae": full_train_mae,
            }
        )
        _log_model(fitted, X)
        return {
            **metrics,
            "full_train_rmse": full_train_rmse,
            "full_train_mae": full_train_mae,
            "run_id": mlflow.active_run().info.run_id,
            "family": family,
            "phase": phase,
        }


def run_nested_random_search(
    *,
    family: str,
    estimator: Any,
    search_space: dict[str, Any],
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    cv: Any,
    dataset_metadata: dict[str, Any],
    seed: int = 42,
    n_iter: int = 30,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run nested CV trials and log the best parameters on the parent run."""
    if n_iter < 30:
        raise ValueError("The assignment requires at least 30 tuning configurations")
    configure_tracking()
    configurations = list(
        ParameterSampler(search_space, n_iter=n_iter, random_state=seed)
    )
    rows = []
    best_parameters = None
    best_trial_run_id = None
    best_rmse = float("inf")

    with mlflow.start_run(run_name=f"{family}_tuning_parent"):
        parent_id = mlflow.active_run().info.run_id
        _log_run_context(
            phase="tuning",
            family=family,
            dataset_metadata=dataset_metadata,
            seed=seed,
        )
        mlflow.log_param("n_iter", n_iter)
        mlflow.log_param("cv_folds", cv.get_n_splits())

        for index, parameters in enumerate(configurations, start=1):
            trial = make_model_pipeline(estimator)
            trial.set_params(**parameters)
            with mlflow.start_run(
                run_name=f"{family}_config_{index:02d}",
                nested=True,
            ):
                _log_run_context(
                    phase="tuning",
                    family=family,
                    dataset_metadata=dataset_metadata,
                    seed=seed,
                )
                mlflow.set_tag("mlflow.parentRunId", parent_id)
                mlflow.log_param("configuration", index)
                mlflow.log_params(parameters)
                started = time.perf_counter()
                scores = cross_validate(
                    trial,
                    X,
                    y,
                    groups=groups,
                    cv=cv,
                    scoring=SCORING,
                    return_train_score=True,
                    n_jobs=1,
                    error_score="raise",
                )
                elapsed = time.perf_counter() - started
                fold_rmse = -scores["test_rmse"]
                fold_train_rmse = -scores["train_rmse"]
                mean_rmse = float(np.mean(fold_rmse))
                std_rmse = float(np.std(fold_rmse, ddof=1))
                trial_metrics = {
                    "cv_rmse_mean": mean_rmse,
                    "cv_rmse_std": std_rmse,
                    "train_rmse_mean": float(np.mean(fold_train_rmse)),
                    "rmse_train_cv_gap": float(
                        mean_rmse - np.mean(fold_train_rmse)
                    ),
                    "cv_mae_mean": float(np.mean(-scores["test_mae"])),
                    "cv_fit_seconds_total": float(elapsed),
                }
                mlflow.log_metrics(trial_metrics)

                trial_run_id = mlflow.active_run().info.run_id
                rows.append(
                    {
                        "family": family,
                        "configuration": index,
                        **parameters,
                        **trial_metrics,
                        "run_id": trial_run_id,
                    }
                )
                if mean_rmse < best_rmse:
                    best_rmse = mean_rmse
                    best_parameters = parameters.copy()
                    best_trial_run_id = trial_run_id

        if best_parameters is None or best_trial_run_id is None:
            raise RuntimeError(f"No successful tuning configurations for {family}")

        mlflow.log_param("best_trial_run_id", best_trial_run_id)
        mlflow.log_params({f"best_{name}": value for name, value in best_parameters.items()})
        mlflow.log_metric("best_cv_rmse_mean", best_rmse)

    results = pd.DataFrame(rows).sort_values("cv_rmse_mean")
    return results, best_parameters


_CV_METRIC_NAMES = (
    "train_rmse_mean", "cv_rmse_mean", "cv_rmse_std", "train_mae_mean",
    "cv_mae_mean", "cv_mae_std", "rmse_train_cv_gap", "cv_fit_seconds_total",
    "cv_seconds_per_fold_mean", "full_train_rmse", "full_train_mae",
)


def evaluate_or_reuse_cv_run(**kwargs: Any) -> dict[str, Any]:
    """Reuse a FINISHED run with the same name, phase, family and data sample.

    Re-running a notebook (Restart + Run All) then does not duplicate the
    evidence in MLflow; when no such run exists, it is trained and logged.
    """
    from mlflow.tracking import MlflowClient

    experiment_id = configure_tracking()
    metadata = kwargs["dataset_metadata"]
    sample_hash = metadata.get("training_sample_sha256", metadata["sha256"])
    runs = MlflowClient().search_runs(
        [experiment_id],
        filter_string=(
            f"attributes.run_name = '{kwargs['run_name']}' "
            f"AND tags.phase = '{kwargs['phase']}' "
            f"AND tags.model_family = '{kwargs['family']}' "
            f"AND tags.workflow_version = '{WORKFLOW_VERSION}' "
            f"AND tags.training_sample_sha256 = '{sample_hash}' "
            "AND attributes.status = 'FINISHED'"
        ),
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if runs and all(name in runs[0].data.metrics for name in _CV_METRIC_NAMES):
        run = runs[0]
        return {
            **{name: run.data.metrics[name] for name in _CV_METRIC_NAMES},
            "run_id": run.info.run_id,
            "family": kwargs["family"],
            "phase": kwargs["phase"],
            "reused_from_mlflow": True,
        }
    return {**evaluate_cv_run(**kwargs), "reused_from_mlflow": False}
