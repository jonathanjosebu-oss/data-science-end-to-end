"""Deriva de datos y deriva conceptual (PSet 4 §6.2).

Por qué los umbrales se calibran y no se toman de la literatura (PSI > 0,25):
cada lote reúne pocos experimentos de RepoRT y cada experimento es la librería
de compuestos de un laboratorio distinto. Contra el entrenamiento (58 % SMRT),
lotes sin alterar dan PSI de 0,3 a 1,8 en descriptores moleculares: el umbral
clásico alertaría todas las semanas. Se calibra con "pseudo-lotes": grupos de
experimentos del propio entrenamiento (sin SMRT) de ~3 000 filas, que
representan un lote normal de la misma población. El umbral por feature es el
percentil 99 de su PSI; el de desempeño, el percentil 95 del RMSE y del sesgo
fuera de pliegue (OOF) de esos pseudo-lotes.

Descriptores del método (flujo, gradiente, t0, columna): son constantes dentro
de un experimento, así que su PSI por lote no mide población sino cuántos
métodos hay. Se vigilan con la guardia de dominio (fracción fuera de rango),
chi-cuadrado sobre categorías (columna, fase móvil) y categorías no vistas.

    python -m monitoreo.deriva calibrar   # escribe monitoreo/referencia.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.pipeline import MOLECULE_FEATURE_COLUMNS

REFERENCIA_PATH = Path(__file__).resolve().parent / "referencia.json"
BINS = 10
EPS = 1e-6
PERCENTIL_PSI = 99
PERCENTIL_DESEMPENO = 95
FILAS_PSEUDO_LOTE = 3_000
N_PSEUDO_LOTES = 200


def bordes_cuantiles(valores: np.ndarray, bins: int = BINS) -> list[float]:
    bordes = np.unique(np.quantile(valores[np.isfinite(valores)], np.linspace(0, 1, bins + 1)))
    bordes[0], bordes[-1] = -np.inf, np.inf
    return bordes.tolist()


def proporciones(valores: np.ndarray, bordes: list[float]) -> np.ndarray:
    valores = valores[np.isfinite(valores)]
    conteo = np.histogram(valores, bins=np.asarray(bordes, dtype=float))[0].astype(float)
    return (conteo + EPS) / (conteo.sum() + EPS * len(conteo))


def psi(ref_prop: np.ndarray, cur_prop: np.ndarray) -> float:
    return float(np.sum((cur_prop - ref_prop) * np.log(cur_prop / ref_prop)))


def psi_por_feature(referencia: dict[str, Any], actual: pd.DataFrame) -> dict[str, float]:
    out = {}
    for feature, ref in referencia["psi"].items():
        valores = pd.to_numeric(actual[feature], errors="coerce").to_numpy(dtype=float)
        if np.isfinite(valores).any():
            out[feature] = psi(np.asarray(ref["proporciones"]), proporciones(valores, ref["bordes"]))
    return out


def ks_por_feature(muestra_ref: pd.DataFrame, actual: pd.DataFrame) -> dict[str, float]:
    """p-valor de Kolmogorov-Smirnov (respaldo del PSI en numéricas)."""
    out = {}
    for feature in muestra_ref.columns:
        a = pd.to_numeric(actual[feature], errors="coerce").dropna()
        if len(a):
            out[feature] = float(stats.ks_2samp(muestra_ref[feature].dropna(), a).pvalue)
    return out


def chi2_categorica(ref_frec: dict[str, float], actual: pd.Series) -> tuple[float, float, float]:
    """(p-valor chi², fracción de filas con categoría no vista, n categorías no vistas)."""
    conteo = actual.astype(str).value_counts()
    vistas = conteo[conteo.index.isin(ref_frec.keys())]
    no_vistas = conteo[~conteo.index.isin(ref_frec.keys())]
    frac_no_vista = float(no_vistas.sum() / conteo.sum()) if conteo.sum() else 0.0
    categorias = list(ref_frec)
    observado = np.array([conteo.get(c, 0) for c in categorias] + [no_vistas.sum()], dtype=float)
    esperado_p = np.array([ref_frec[c] for c in categorias] + [0.0]) * (1 - 1e-3) + 1e-3 / (len(categorias) + 1)
    esperado = esperado_p / esperado_p.sum() * observado.sum()
    p = float(stats.chisquare(observado, esperado).pvalue) if observado.sum() else 1.0
    return p, frac_no_vista, float(len(no_vistas))


def calibrar() -> dict[str, Any]:
    """Referencia de entrenamiento + umbrales calibrados con pseudo-lotes (champion vigente)."""
    import mlflow
    from mlflow.tracking import MlflowClient

    from src.datos import load_snapshot
    from src.experiments import configure_tracking
    from src.pipeline import MoleculeConditionFeatures, model_inputs
    from src.reentrenar import MODEL_NAME, grouped_cv
    from src.splits import TRAINING_SEGMENT, create_or_load_lots

    frame, metadata = load_snapshot()
    frame, _ = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    train = frame.loc[frame["segment"].eq(TRAINING_SEGMENT)].reset_index(drop=True)
    feats = MoleculeConditionFeatures().fit(model_inputs(train)[0]).transform(model_inputs(train)[0])
    mol = feats.loc[:, list(MOLECULE_FEATURE_COLUMNS)]

    referencia: dict[str, Any] = {"psi": {}, "categorias": {}}
    for feature in MOLECULE_FEATURE_COLUMNS:
        bordes = bordes_cuantiles(mol[feature].to_numpy(dtype=float))
        referencia["psi"][feature] = {
            "bordes": bordes,
            "proporciones": proporciones(mol[feature].to_numpy(dtype=float), bordes).tolist(),
        }
    for columna in ("tipo_columna", "fase_movil"):
        referencia["categorias"][columna] = train[columna].astype(str).value_counts(normalize=True).to_dict()

    # Pseudo-lotes: experimentos de entrenamiento sin SMRT (0186), ~3 000 filas.
    configure_tracking()
    mv = MlflowClient().get_model_version_by_alias(MODEL_NAME, "champion")
    params = {k.removeprefix("regressor__"): v for k, v in MlflowClient().get_run(mv.run_id).data.params.items()
              if k.startswith("regressor__")}
    params = {k: (int(v) if v.isdigit() else float(v)) for k, v in params.items()}
    cv = grouped_cv(train, params)
    residuo = cv["oof"] - train["tiempo_retencion"].to_numpy()
    tamanos = train.groupby("experimento_id").size().drop("0186", errors="ignore")
    rng = np.random.default_rng(42)
    psis, rmses, sesgos = [], [], []
    for _ in range(N_PSEUDO_LOTES):
        elegidos, n = [], 0
        for e in rng.permutation(tamanos.index):
            elegidos.append(e)
            n += tamanos[e]
            if n >= FILAS_PSEUDO_LOTE:
                break
        mascara = train["experimento_id"].isin(elegidos).to_numpy()
        psis.append(psi_por_feature(referencia, mol.loc[mascara]))
        rmses.append(float(np.sqrt(np.mean(residuo[mascara] ** 2))))
        sesgos.append(float(np.mean(residuo[mascara])))
    psis = pd.DataFrame(psis)
    referencia["umbrales"] = {
        "psi": psis.quantile(PERCENTIL_PSI / 100).to_dict(),
        "psi_features_para_alerta": 2,
        "ks_p_valor": 0.01,
        "rmse_lote": float(np.percentile(rmses, PERCENTIL_DESEMPENO)),
        "sesgo_abs_lote": float(np.percentile(np.abs(sesgos), PERCENTIL_DESEMPENO)),
        "fraccion_fuera_de_dominio": 0.20,
        "fraccion_categoria_no_vista": 0.50,
        "latencia_p95_ms": 500.0,
        "tasa_5xx": 0.01,
        "tasa_4xx": 0.05,
        "lotes_consecutivos_reentrenamiento": 2,
        "reentrenamiento_calendario_lotes": 8,  # ~2 meses; con 6 coincidía con el primer lote con deriva
    }
    referencia["cv"] = {"rmse_media": cv["cv_rmse_mean"], "rmse_de": cv["cv_rmse_std"]}
    referencia["pseudo_lotes"] = {
        "n": N_PSEUDO_LOTES, "filas_objetivo": FILAS_PSEUDO_LOTE,
        "rmse_p50": float(np.median(rmses)), "sesgo_abs_p50": float(np.median(np.abs(sesgos))),
        "psi_p50": psis.median().to_dict(),
    }
    referencia["modelo_calibrado"] = {"version": int(mv.version), "run_id": mv.run_id}
    muestra = mol.sample(min(5_000, len(mol)), random_state=0)
    referencia["muestra_ks"] = {c: muestra[c].round(6).tolist() for c in muestra.columns}
    REFERENCIA_PATH.write_text(json.dumps(referencia, ensure_ascii=False) + "\n", encoding="utf-8")
    return referencia


def cargar_referencia() -> dict[str, Any]:
    return json.loads(REFERENCIA_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["calibrar"]:
        r = calibrar()
        print(json.dumps({k: v for k, v in r["umbrales"].items()}, indent=2))
        print("CV:", r["cv"], "| pseudo-lotes:", {k: v for k, v in r["pseudo_lotes"].items() if k != "psi_p50"})
