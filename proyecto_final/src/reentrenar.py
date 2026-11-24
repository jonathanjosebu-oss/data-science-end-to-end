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
                "gold_tables": "GOLD.FACT_RETENCION_CROMATOGRAFICA,GOLD.DIM_COMPUESTO,GOLD.DIM_CONDICIONES,GOLD.DIM_METODO",
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


# ---------------------------------------------------------------------------
# Ciclo de reentrenamiento (kestra/reentrenamiento.yml, PSet 4 §7.2)
# ---------------------------------------------------------------------------
PESO_LOTES_RECIENTES = 10.0
"""Ventana: todo el histórico (peso 1) + los lotes etiquetados (peso 10).
Se comparó con histórico sin pesos, pesos exponenciales y una ventana móvil
(20 % del histórico + lotes): peso 10 fue el mejor en los lotes 07-08 sin
perder el 09. El histórico completo conserva la cobertura química (SMRT)."""


def _lotes_etiquetados(hasta_lote: int) -> pd.DataFrame:
    """Entradas + targets que ya llegaron, de los lotes 1..hasta_lote."""
    from src import almacen

    return almacen.consultar(
        """SELECT e.*, t.TIEMPO_RETENCION FROM LOTES_ENTRADAS e
           JOIN TARGETS t ON e.HECHO_ID = t.HECHO_ID AND e.LOTE = t.LOTE
           WHERE e.LOTE <= %s""",
        (hasta_lote,),
    )


def _params_registrados(run_params: dict[str, str]) -> dict[str, Any]:
    def convertir(valor: str) -> Any:
        try:
            return int(valor)
        except ValueError:
            return float(valor)

    return {k.removeprefix("regressor__"): convertir(v) for k, v in run_params.items() if k.startswith("regressor__")}


def entrenar_challenger(semana: int, motivo: str) -> dict[str, Any]:
    """Arma la ventana, reentrena con los hiperparámetros del champion (sin
    tuning) y registra la versión con alias 'challenger' y tag fase=reentrenamiento."""
    from mlflow.tracking import MlflowClient

    from src.datos import load_snapshot
    from src.experiments import configure_tracking
    from src.splits import TRAINING_SEGMENT, create_or_load_lots

    configure_tracking()
    client = MlflowClient()
    champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
    params = _params_registrados(client.get_run(champion.run_id).data.params)
    lote_evaluacion = semana - 1  # el más reciente con target: ninguno de los dos lo ve
    frame, metadata = load_snapshot()
    frame, _ = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    historico = frame.loc[frame["segment"].eq(TRAINING_SEGMENT)]
    recientes = _lotes_etiquetados(lote_evaluacion - 1)
    columnas = [c for c in historico.columns if c in recientes.columns]
    ventana = pd.concat([historico[columnas], recientes[columnas]], ignore_index=True)
    pesos = np.r_[np.ones(len(historico)), np.full(len(recientes), PESO_LOTES_RECIENTES)]
    lotes = sorted(int(x) for x in recientes["lote"].unique()) if len(recientes) else []
    descripcion = f"histórico 0006-0275 (peso 1) + lotes {lotes} (peso {PESO_LOTES_RECIENTES:g})"
    resultado = fit_and_register(
        ventana,
        dataset_metadata={**metadata, "rows": len(ventana)},
        phase="reentrenamiento",
        reason=motivo,
        alias="challenger",
        training_segments=[TRAINING_SEGMENT, *[f"lote_{k:02d}" for k in lotes]],
        params=params,
        sample_weight=pesos,
        extra_tags={"ventana": descripcion, "semana_disparo": str(semana),
                    "lote_evaluacion": str(lote_evaluacion), "champion_previo": str(champion.version)},
    )
    print(f"Challenger v{resultado['version']} registrado ({descripcion}); CV {resultado['cv_rmse_mean']:.3f}")
    return {"version_challenger": resultado["version"], "run_id": resultado["run_id"],
            "version_champion": int(champion.version), "lote_evaluacion": lote_evaluacion,
            "ventana": descripcion, "cv_rmse": resultado["cv_rmse_mean"]}


def comparar(semana: int, motivo: str) -> dict[str, Any]:
    """Champion vs challenger en el lote etiquetado más reciente y regla de promoción.

    Regla (PSet 4 §4): se promueve si el RMSE del challenger es menor que el del
    champion en más de una desviación estándar de la CV del champion, y su
    métrica de negocio (corridas evitadas netas) no es peor; ambos evaluados en
    el mismo lote, que ninguno vio. Las pruebas de comportamiento (xfail) son
    criterio de preferencia, no de bloqueo."""
    import mlflow
    from mlflow.tracking import MlflowClient

    from src import almacen
    from src.business_metrics import corridas_evitadas
    from src.experiments import configure_tracking
    from src.pipeline import model_inputs

    configure_tracking()
    client = MlflowClient()
    lote = semana - 1
    datos = _lotes_etiquetados(lote)
    datos = datos[datos["lote"] == lote].reset_index(drop=True)
    y = datos["tiempo_retencion"].to_numpy()
    resultados = {}
    for alias in ("champion", "challenger"):
        mv = client.get_model_version_by_alias(MODEL_NAME, alias)
        metricas = client.get_run(mv.run_id).data.metrics
        modelo = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{mv.version}")
        pred = modelo.predict(model_inputs(datos)[0])
        negocio = corridas_evitadas(
            y, pred, datos["experimento_id"],
            (metricas["pair_lower_error_quantile"], metricas["pair_upper_error_quantile"]),
        )
        resultados[alias] = {"version": int(mv.version), "rmse": float(np.sqrt(np.mean((pred - y) ** 2))),
                             "negocio": float(negocio["neto"]), "cv_de": metricas["cv_rmse_std"], "run_id": mv.run_id}
    ch, cl = resultados["champion"], resultados["challenger"]
    margen = ch["rmse"] - cl["rmse"]
    promueve = bool(margen > ch["cv_de"] and cl["negocio"] >= ch["negocio"])
    explicacion = (
        f"RMSE lote {lote}: champion v{ch['version']} {ch['rmse']:.3f} vs challenger v{cl['version']} "
        f"{cl['rmse']:.3f} (mejora {margen:.3f}; umbral 1 DE CV = {ch['cv_de']:.3f}); "
        f"negocio {ch['negocio']:.3f} vs {cl['negocio']:.3f} -> "
        + ("la regla RECOMIENDA promover" if promueve else "la regla NO recomienda promover")
    )
    tags = client.get_run(cl["run_id"]).data.tags
    almacen.escribir(
        "REENTRENAMIENTOS",
        pd.DataFrame([{
            "ts": pd.Timestamp.now(tz="UTC"), "lote": semana, "motivo": motivo,
            "ventana": tags.get("ventana"), "run_id": cl["run_id"],
            "version_challenger": cl["version"], "version_champion": ch["version"],
            "lote_evaluacion": lote, "rmse_champion": ch["rmse"], "rmse_challenger": cl["rmse"],
            "cv_std_champion": ch["cv_de"], "negocio_champion": ch["negocio"],
            "negocio_challenger": cl["negocio"], "regla_promueve": promueve,
            "decision_humana": "pendiente", "motivo_decision": None, "version_champion_final": ch["version"],
        }]),
        borrar_donde=f"LOTE = {semana}",
    )
    for clave, valor in (("rmse_lote_evaluacion", cl["rmse"]), ("rmse_champion_lote_evaluacion", ch["rmse"]),
                         ("negocio_lote_evaluacion", cl["negocio"])):
        client.log_metric(cl["run_id"], clave, valor)
    client.set_tag(cl["run_id"], "regla_promueve", str(promueve))
    print(explicacion)
    return {"promueve": promueve, "explicacion": explicacion,
            "rmse_champion": ch["rmse"], "rmse_challenger": cl["rmse"],
            "version_champion": ch["version"], "version_challenger": cl["version"]}


def decidir(semana: int, aprobar: bool, motivo: str) -> dict[str, Any]:
    """Aplica la decisión humana: si se aprueba, el alias 'champion' pasa al
    challenger (la API lo toma sin reconstruir la imagen); si no, el champion
    queda intacto y se registra el motivo."""
    from mlflow.tracking import MlflowClient

    from src import almacen
    from src.experiments import configure_tracking

    configure_tracking()
    client = MlflowClient()
    champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
    challenger = client.get_model_version_by_alias(MODEL_NAME, "challenger")
    decision = "aprobado" if aprobar else "rechazado"
    if aprobar:
        client.set_registered_model_alias(MODEL_NAME, "champion", challenger.version)
        client.set_model_version_tag(MODEL_NAME, champion.version, "estado", "champion anterior (rollback)")
    client.delete_registered_model_alias(MODEL_NAME, "challenger")
    client.set_model_version_tag(MODEL_NAME, challenger.version, "decision_humana", decision)
    client.set_model_version_tag(MODEL_NAME, challenger.version, "motivo_decision", motivo)
    client.set_tag(challenger.run_id, "decision_humana", decision)
    client.set_tag(challenger.run_id, "motivo_decision", motivo)
    final = int(challenger.version if aprobar else champion.version)
    almacen.ejecutar(
        "UPDATE REENTRENAMIENTOS SET DECISION_HUMANA = %s, MOTIVO_DECISION = %s, VERSION_CHAMPION_FINAL = %s WHERE LOTE = %s",
        (decision, motivo, final, semana),
    )
    print(f"Decisión humana: {decision} ({motivo}). Champion vigente: v{final}")
    return {"decision": decision, "version_champion": final}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Ciclo de reentrenamiento (PSet 4 §7.2)")
    sub = parser.add_subparsers(dest="accion", required=True)
    for nombre in ("entrenar", "comparar"):
        p = sub.add_parser(nombre)
        p.add_argument("--semana", type=int, required=True)
        p.add_argument("--motivo", required=True)
    p = sub.add_parser("decidir")
    p.add_argument("--semana", type=int, required=True)
    p.add_argument("--aprobar", choices=["true", "false"], required=True)
    p.add_argument("--motivo", default="")
    args = parser.parse_args()
    if args.accion == "entrenar":
        salida = entrenar_challenger(args.semana, args.motivo)
    elif args.accion == "comparar":
        salida = comparar(args.semana, args.motivo)
    else:
        salida = decidir(args.semana, args.aprobar == "true", args.motivo)
    print("::" + json.dumps({"outputs": salida}, default=str) + "::")


if __name__ == "__main__":
    main()
