"""Entrenamiento, registro y comparación champion/challenger (PSet 4).

Lo usan el entrenamiento inicial (`scripts/registrar_champion.py`), el flujo de
Kestra `reentrenamiento.yml` y las pruebas. La preparación es la de
`src/pipeline.py` y los hiperparámetros son los del champion del PSet 3: el
reentrenamiento no repite el tuning.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import GroupKFold

from src.business_metrics import calibrate_pairwise_interval
from src.experiments import _git_commit, _log_model, configure_tracking
from src.pipeline import (
    ConditionMedianRegressor,
    chromatographic_condition_groups,
    clear_feature_caches,
    make_model_pipeline,
    model_inputs,
)

MODEL_NAME = "qsrr-predict-modelo"
RANDOM_STATE = 42
# Champion del PSet 3: HistGradientBoosting, run 04483473d3314b51b7ee40f03ca90c94
# (versión 5 del registro del Codespace), mejor configuración del tuning.
CHAMPION_PARAMS: dict[str, Any] = {
    "learning_rate": 0.18043311207136256,
    "max_iter": 200,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 10,
    "l2_regularization": 4.9352962094020985,
}
PSET3_CHAMPION_RUN_ID = "04483473d3314b51b7ee40f03ca90c94"
BASELINE_ARTIFACT = "linea_base.json"

# Restricciones de monotonía del champion: ninguna. Se evaluaron (2026-11-22)
# frente a las pruebas de comportamiento (tests/test_comportamiento.py):
#   sin restricciones          CV 2,489±0,054 | lotes 3,05 | flujo ✗ | homólogas 14/24 ✗
#   mol_logp +1                CV 2,499±0,041 | lotes 3,39 | flujo ✗ | homólogas 10/24 ✗
#   mol_logp +1, flujo -1      CV 2,581±0,055 | lotes 3,75 | flujo ✓ | homólogas 12/24 ✗
# Corregir el flujo cuesta +23 % de error en lotes nuevos porque el flujo actúa
# como proxy del método (falta el programa de gradiente) y no arregla las series
# homólogas. Se mantiene el champion sin restricciones y el defecto queda
# documentado como xfail estricto y como criterio de promoción.
MONOTONIC_CONSTRAINTS: dict[str, int] = {}


def monotonic_cst(constraints: dict[str, int] | None = None) -> list[int]:
    from src.pipeline import FEATURE_COLUMNS

    constraints = MONOTONIC_CONSTRAINTS if constraints is None else constraints
    return [int(constraints.get(column, 0)) for column in FEATURE_COLUMNS]


def build_model(
    params: dict[str, Any] | None = None,
    constraints: dict[str, int] | None = None,
):
    regressor = HistGradientBoostingRegressor(
        random_state=RANDOM_STATE,
        monotonic_cst=monotonic_cst(constraints),
        **(params or CHAMPION_PARAMS),
    )
    return make_model_pipeline(regressor)


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "rmse": float(root_mean_squared_error(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else float("nan"),
    }


def grouped_cv(
    frame: pd.DataFrame,
    params: dict[str, Any] | None = None,
    *,
    n_splits: int = 5,
    sample_weight: np.ndarray | None = None,
) -> dict[str, Any]:
    """GroupKFold by compound; returns fold RMSE mean/std and OOF predictions."""
    X, y, groups = model_inputs(frame)
    oof = np.full(len(y), np.nan)
    fold_rmse, fold_mae = [], []
    for train_idx, valid_idx in GroupKFold(n_splits=n_splits).split(X, y, groups):
        model = build_model(params)
        fit_kwargs = {}
        if sample_weight is not None:
            fit_kwargs["regressor__sample_weight"] = sample_weight[train_idx]
        model.fit(X.iloc[train_idx], y.iloc[train_idx], **fit_kwargs)
        oof[valid_idx] = model.predict(X.iloc[valid_idx])
        fold_rmse.append(root_mean_squared_error(y.iloc[valid_idx], oof[valid_idx]))
        fold_mae.append(mean_absolute_error(y.iloc[valid_idx], oof[valid_idx]))
        clear_feature_caches()
    return {
        "cv_rmse_mean": float(np.mean(fold_rmse)),
        "cv_rmse_std": float(np.std(fold_rmse, ddof=1)),
        "cv_mae_mean": float(np.mean(fold_mae)),
        "oof": oof,
    }


def fit_baseline(frame: pd.DataFrame) -> dict[str, Any]:
    """Línea base del PSet 3 (mediana por condición) en formato JSON portable.

    Es el respaldo de la API: no necesita scikit-learn ni el modelo.
    """
    X, y, _ = model_inputs(frame)
    baseline = ConditionMedianRegressor().fit(X, y)
    table = {
        "|".join("<MISSING>" if pd.isna(v) else str(v) for v in key): float(value)
        for key, value in baseline.condition_medians_.items()
    }
    return {"global_median": baseline.global_median_, "condition_medians": table}


DOMAIN_ARTIFACT = "dominio.json"


def training_domain(frame: pd.DataFrame) -> dict[str, Any]:
    """Categorías y rangos vistos en entrenamiento (advertencias, guardia de
    dominio de la API y monitoreo de valores fuera de rango)."""
    from src.pipeline import method_features

    flow = pd.to_numeric(frame["flujo_ml_min"], errors="coerce").dropna()
    features = method_features(frame.reset_index(drop=True))
    rangos = {
        column: [float(values.min()), float(values.max())]
        for column, values in features.items()
        if values.notna().any()
    }
    return {
        "tipo_columna": sorted(frame["tipo_columna"].dropna().astype(str).unique()),
        "fase_movil": sorted(frame["fase_movil"].dropna().astype(str).unique()),
        "flujo_ml_min": [float(flow.min()), float(flow.max())],
        # Rangos de los descriptores del método (features derivadas).
        "rangos_metodo": rangos,
    }


# Descriptores excluidos de la guardia (siguen en el monitoreo de rangos).
# ph_b: en entrenamiento solo varía de 2 a 3, así que casi todo método nuevo
# cae fuera, pero esas filas no tienen más error (RMSE 2,12 frente a 3,31 en
# los lotes); el pH de un eluyente orgánico es además nominal.
DOMAIN_GUARD_EXCLUDED = frozenset({"ph_b"})


def out_of_domain(features: pd.DataFrame, domain: dict[str, Any]) -> pd.Series:
    """Por fila, lista de descriptores del método fuera del rango de entrenamiento.

    Los árboles no extrapolan: un valor fuera de rango se trata como el extremo
    visto. En los lotes simulados con el champion v2, las filas marcadas (columna
    de 1 mm, gradiente de 100 min, t0 fuera de rango) tienen RMSE ~9,8 min frente
    a ~2,0 en las demás. Los nulos no cuentan (se imputan).
    """
    ranges = domain.get("rangos_metodo", {})
    flags = pd.Series([[] for _ in range(len(features))], index=features.index, dtype=object)
    for column, (low, high) in ranges.items():
        if column not in features or column in DOMAIN_GUARD_EXCLUDED:
            continue
        values = pd.to_numeric(features[column], errors="coerce")
        outside = values.notna() & ((values < low) | (values > high))
        for index in features.index[outside]:
            flags.at[index] = flags.at[index] + [column]
    return flags


def baseline_predict(baseline: dict[str, Any], frame: pd.DataFrame) -> np.ndarray:
    keys = (
        frame.loc[:, ["tipo_columna", "fase_movil", "flujo_ml_min"]]
        .astype(object)
        .where(frame.loc[:, ["tipo_columna", "fase_movil", "flujo_ml_min"]].notna(), None)
        .apply(
            lambda row: "|".join(
                "<MISSING>" if value is None else str(value) for value in row
            ),
            axis=1,
        )
    )
    table = baseline["condition_medians"]
    return np.asarray(
        [table.get(key, baseline["global_median"]) for key in keys], dtype=float
    )


def fit_and_register(
    train: pd.DataFrame,
    *,
    dataset_metadata: dict[str, Any],
    phase: str,
    reason: str,
    alias: str,
    training_segments: list[str],
    params: dict[str, Any] | None = None,
    sample_weight: np.ndarray | None = None,
    evaluation: dict[str, pd.DataFrame] | None = None,
    extra_tags: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Entrena, valida por CV, registra una versión nueva y le asigna ``alias``."""
    params = dict(params or CHAMPION_PARAMS)
    configure_tracking()
    client = MlflowClient()
    cv = grouped_cv(train, params, sample_weight=sample_weight)
    interval = calibrate_pairwise_interval(
        train["tiempo_retencion"].to_numpy(),
        cv["oof"],
        chromatographic_condition_groups(train),
        train["inchikey"].astype(str),
        random_state=RANDOM_STATE,
    )
    X, y, _ = model_inputs(train)
    model = build_model(params)
    fit_kwargs = {}
    if sample_weight is not None:
        fit_kwargs["regressor__sample_weight"] = sample_weight
    model.fit(X, y, **fit_kwargs)
    baseline = fit_baseline(train)

    with mlflow.start_run(run_name=f"{phase}-{alias}") as run:
        mlflow.set_tags(
            {
                "fase": phase,
                "motivo": reason,
                "model_family": "hist_gradient_boosting",
                "git_commit": _git_commit(),
                "validation": "GroupKFold(5) by inchikey",
                "data_tables": dataset_metadata["source_tables"],
                "obt_snapshot_dates": ",".join(dataset_metadata.get("snapshot_dates", [])),
                "obt_source_commits": ",".join(dataset_metadata.get("source_commits", [])),
                "gold_tables": "GOLD.FACT_RETENCION_CROMATOGRAFICA,GOLD.DIM_COMPUESTO,GOLD.DIM_CONDICIONES",
                "data_sha256": dataset_metadata["sha256"],
                "segmentos_entrenamiento": ",".join(training_segments),
                "hiperparametros_origen": f"champion PSet 3 ({PSET3_CHAMPION_RUN_ID})",
                **(extra_tags or {}),
            }
        )
        mlflow.log_params({f"regressor__{k}": v for k, v in params.items()})
        mlflow.log_param("monotonic_constraints", json.dumps(MONOTONIC_CONSTRAINTS))
        mlflow.log_params(
            {
                "train_rows": len(train),
                "train_compounds": train["inchikey"].nunique(),
                "train_experiments": train["experimento_id"].nunique(),
                "weighted": sample_weight is not None,
            }
        )
        mlflow.log_metrics(
            {
                "cv_rmse_mean": cv["cv_rmse_mean"],
                "cv_rmse_std": cv["cv_rmse_std"],
                "cv_mae_mean": cv["cv_mae_mean"],
                "pair_lower_error_quantile": interval["lower_error_quantile"],
                "pair_upper_error_quantile": interval["upper_error_quantile"],
                "pair_error_radius": interval["pair_error_radius"],
                "calibration_pairs": interval["calibration_pairs"],
            }
        )
        for name, frame in (evaluation or {}).items():
            pred = model.predict(model_inputs(frame)[0])
            for metric, value in regression_metrics(frame["tiempo_retencion"], pred).items():
                mlflow.log_metric(f"{name}_{metric}", value)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / BASELINE_ARTIFACT
            path.write_text(json.dumps(baseline), encoding="utf-8")
            mlflow.log_artifact(str(path))
            path = Path(tmp) / DOMAIN_ARTIFACT
            path.write_text(json.dumps(training_domain(train)), encoding="utf-8")
            mlflow.log_artifact(str(path))
        _log_model(model, X)
        run_id = run.info.run_id

    version = mlflow.register_model(f"runs:/{run_id}/model", MODEL_NAME)
    client.set_registered_model_alias(MODEL_NAME, alias, version.version)
    client.set_model_version_tag(MODEL_NAME, version.version, "fase", phase)
    client.set_model_version_tag(MODEL_NAME, version.version, "motivo", reason)
    clear_feature_caches()
    return {
        "run_id": run_id,
        "version": int(version.version),
        "model": model,
        "baseline": baseline,
        "domain": training_domain(train),
        "interval": interval,
        **{k: v for k, v in cv.items() if k != "oof"},
    }
