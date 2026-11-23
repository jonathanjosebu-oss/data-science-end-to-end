"""Leak-free feature extraction, preprocessing, model definitions, and splits."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
from scipy.stats import loguniform
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted

# Las 16 features del PSet 3 (champion v1).
LEGACY_FEATURE_COLUMNS = (
    "mol_weight",
    "mol_logp",
    "mol_tpsa",
    "mol_h_donors",
    "mol_h_acceptors",
    "mol_rotatable_bonds",
    "mol_ring_count",
    "mol_aromatic_rings",
    "mol_fraction_csp3",
    "elu_a_h2o",
    "elu_a_meoh",
    "elu_a_acn",
    "elu_b_h2o",
    "elu_b_meoh",
    "elu_b_acn",
    "flow_ml_min",
)
# PSet 4: descriptores del método conocidos antes de inyectar (dim_metodo).
METHOD_FEATURE_COLUMNS = (
    "t0_min",
    "col_length_mm",
    "col_diameter_mm",
    "col_particle_um",
    "col_volume_ml",
    "ph_a",
    "ph_b",
    "grad_org_start",
    "grad_org_max",
    "grad_time_to_max_min",
    "grad_slope_org_per_min",
    "grad_duration_min",
)
FEATURE_COLUMNS = LEGACY_FEATURE_COLUMNS + METHOD_FEATURE_COLUMNS
METHOD_RAW_COLUMNS = (
    "t0_min",
    "columna_longitud_mm",
    "columna_diametro_mm",
    "columna_particula_um",
    "ph_a",
    "ph_b",
    "gradiente",
)
MOLECULE_FEATURE_COLUMNS = (
    "mol_weight",
    "mol_logp",
    "mol_tpsa",
    "mol_h_donors",
    "mol_h_acceptors",
    "mol_rotatable_bonds",
    "mol_ring_count",
    "mol_aromatic_rings",
    "mol_fraction_csp3",
)
RAW_FEATURE_COLUMNS = (
    "smiles",
    "tipo_columna",
    "fase_movil",
    "flujo_ml_min",
) + METHOD_RAW_COLUMNS

_PHASE_PATTERN = re.compile(
    r"([AB])\[\s*H2O=([^;]+);\s*MeOH=([^;]+);\s*ACN=([^\]]+)\]",
    flags=re.IGNORECASE,
)


def _number_or_nan(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return np.nan
    return number if np.isfinite(number) else np.nan


@lru_cache(maxsize=1_000)
def _mobile_phase_features(value: Any) -> dict[str, float]:
    result = {
        f"elu_{phase.lower()}_{solvent.lower()}": np.nan
        for phase in ("a", "b")
        for solvent in ("h2o", "meoh", "acn")
    }
    if not isinstance(value, str):
        return result
    for match in _PHASE_PATTERN.finditer(value):
        phase, water, methanol, acetonitrile = match.groups()
        for solvent, raw in (
            ("h2o", water),
            ("meoh", methanol),
            ("acn", acetonitrile),
        ):
            result[f"elu_{phase.lower()}_{solvent}"] = _number_or_nan(raw)
    return result


@lru_cache(maxsize=100_000)
def _molecule_feature_values(smiles: Any) -> tuple[float, ...]:
    missing = tuple(np.nan for _ in MOLECULE_FEATURE_COLUMNS)
    if not isinstance(smiles, str) or not smiles.strip():
        return missing
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return missing
    return (
        float(Descriptors.MolWt(molecule)),
        float(Crippen.MolLogP(molecule)),
        float(rdMolDescriptors.CalcTPSA(molecule)),
        float(Lipinski.NumHDonors(molecule)),
        float(Lipinski.NumHAcceptors(molecule)),
        float(Lipinski.NumRotatableBonds(molecule)),
        float(rdMolDescriptors.CalcNumRings(molecule)),
        float(rdMolDescriptors.CalcNumAromaticRings(molecule)),
        float(rdMolDescriptors.CalcFractionCSP3(molecule)),
    )


def parse_gradient(value: Any) -> list[list[float | None]]:
    """Programa de gradiente serializado por la ingesta (JSON
    ``[[t_min, %A, %B, %C, %D, flujo], ...]``); lista vacía si no hay o es inválido."""
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        steps = json.loads(value)
    except (TypeError, ValueError):
        return []
    valid = []
    for step in steps if isinstance(steps, list) else []:
        if isinstance(step, list) and len(step) >= 3 and step[0] is not None:
            valid.append([None if v is None else float(v) for v in (step + [None] * 6)[:6]])
    return sorted(valid, key=lambda s: s[0])


def serialize_gradient(steps: list[list[float | None]]) -> str:
    """Inverso de parse_gradient (lo usa la API para armar la misma entrada)."""
    return json.dumps([[None if v is None else float(v) for v in s] for s in steps], separators=(",", ":"))


@lru_cache(maxsize=2_000)
def gradient_features(gradient: Any, mobile_phase: Any) -> tuple[float, ...]:
    """Resumen físico del gradiente en % de solvente orgánico (MeOH + ACN).

    El % orgánico de cada paso combina el %A y %B del programa con la
    composición de cada eluyente (``fase_movil``). Devuelve: % orgánico
    inicial, máximo, tiempo hasta el máximo, pendiente (%/min) y duración.
    """
    steps = parse_gradient(gradient)
    phase = _mobile_phase_features(mobile_phase)
    org_a = np.nansum([phase["elu_a_meoh"], phase["elu_a_acn"]]) / 100
    org_b = np.nansum([phase["elu_b_meoh"], phase["elu_b_acn"]]) / 100
    rows = [(s[0], s[1], s[2]) for s in steps if s[1] is not None and s[2] is not None]
    if len(rows) < 1:
        return (np.nan,) * 5
    times = np.array([r[0] for r in rows], dtype=float)
    organic = np.array([r[1] * org_a + r[2] * org_b for r in rows], dtype=float)
    start = float(organic[0])
    peak_index = int(np.argmax(organic))
    peak = float(organic[peak_index])
    time_to_max = float(times[peak_index] - times[0])
    slope = (peak - start) / time_to_max if time_to_max > 0 else 0.0
    return (start, peak, time_to_max, slope, float(times[-1] - times[0]))


def method_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Features del método; columnas ausentes en la entrada quedan como NaN."""
    def numeric(column: str) -> pd.Series:
        if column not in frame:
            return pd.Series(np.nan, index=frame.index)
        return pd.to_numeric(frame[column], errors="coerce").astype(float)

    length = numeric("columna_longitud_mm")
    diameter = numeric("columna_diametro_mm")
    gradient = frame["gradiente"] if "gradiente" in frame else pd.Series(None, index=frame.index)
    grad = pd.DataFrame(
        [gradient_features(g if isinstance(g, str) else None, p) for g, p in zip(gradient, frame["fase_movil"])],
        index=frame.index,
        columns=[
            "grad_org_start", "grad_org_max", "grad_time_to_max_min",
            "grad_slope_org_per_min", "grad_duration_min",
        ],
    )
    result = pd.DataFrame(
        {
            "t0_min": numeric("t0_min"),
            "col_length_mm": length,
            "col_diameter_mm": diameter,
            "col_particle_um": numeric("columna_particula_um"),
            # Volumen geométrico de la columna (mm³ -> mL): escala el tiempo muerto.
            "col_volume_ml": np.pi * (diameter / 2) ** 2 * length / 1000,
            "ph_a": numeric("ph_a"),
            "ph_b": numeric("ph_b"),
        },
        index=frame.index,
    )
    return pd.concat([result, grad], axis=1)


def _molecule_features(smiles: Any) -> dict[str, float]:
    values = _molecule_feature_values(smiles)
    return dict(zip(MOLECULE_FEATURE_COLUMNS, values, strict=True))


def clear_feature_caches() -> None:
    _mobile_phase_features.cache_clear()
    _molecule_feature_values.cache_clear()
    gradient_features.cache_clear()


def valid_smiles_mask(frame: pd.DataFrame) -> pd.Series:
    """Return a mask for rows whose molecule can be parsed by RDKit."""
    if "smiles" not in frame:
        raise ValueError("The dataset must include the smiles column")
    parsed = {
        smiles: isinstance(smiles, str)
        and Chem.MolFromSmiles(smiles) is not None
        for smiles in frame["smiles"].dropna().unique()
    }
    return frame["smiles"].map(lambda value: parsed.get(value, False)).astype(bool)


def model_inputs(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    required = (set(RAW_FEATURE_COLUMNS) - set(METHOD_RAW_COLUMNS)) | {"tiempo_retencion", "inchikey"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing modeling columns: {sorted(missing)}")
    # Los descriptores del método son opcionales (NaN -> imputación del pipeline).
    X = frame.reindex(columns=list(RAW_FEATURE_COLUMNS)).copy()
    y = pd.to_numeric(frame["tiempo_retencion"], errors="raise").astype(float)
    groups = frame["inchikey"].astype(str)
    return X, y, groups


def chromatographic_condition_groups(frame: pd.DataFrame) -> pd.Series:
    required = {"tipo_columna", "fase_movil", "flujo_ml_min"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing condition columns: {sorted(missing)}")
    return (
        frame.loc[:, ["tipo_columna", "fase_movil", "flujo_ml_min"]]
        .fillna("<MISSING>")
        .astype(str)
        .agg("|".join, axis=1)
    )


class MoleculeConditionFeatures(TransformerMixin, BaseEstimator):
    """Derive inference-available RDKit and mobile-phase numeric features."""

    def fit(self, X: pd.DataFrame, y: Any = None) -> MoleculeConditionFeatures:
        required = {"smiles", "fase_movil", "flujo_ml_min"}
        missing = required.difference(X.columns)
        if missing:
            raise ValueError(f"Missing raw feature columns: {sorted(missing)}")
        self.n_features_in_ = X.shape[1]
        self.feature_columns_ = FEATURE_COLUMNS
        return self

    def _output_columns(self) -> tuple[str, ...]:
        # Modelos registrados antes del PSet 4 (v1) no tienen feature_columns_:
        # siguen produciendo sus 16 columnas, así el rollback a v1 funciona.
        return getattr(self, "feature_columns_", LEGACY_FEATURE_COLUMNS)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        check_is_fitted(self)
        molecule_cache = {
            smiles: _molecule_features(smiles)
            for smiles in X["smiles"].dropna().unique()
        }
        molecule_rows = [
            molecule_cache[smiles]
            if isinstance(smiles, str) and smiles in molecule_cache
            else _molecule_features(smiles)
            for smiles in X["smiles"]
        ]
        phase_rows = [_mobile_phase_features(value) for value in X["fase_movil"]]
        result = pd.DataFrame(molecule_rows, index=X.index)
        phase_frame = pd.DataFrame(phase_rows, index=X.index)
        result = pd.concat([result, phase_frame], axis=1)
        result["flow_ml_min"] = pd.to_numeric(
            X["flujo_ml_min"], errors="coerce"
        )
        columns = self._output_columns()
        if any(c in METHOD_FEATURE_COLUMNS for c in columns):
            result = pd.concat([result, method_features(X)], axis=1)
        return result.loc[:, list(columns)]

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        return np.asarray(self._output_columns(), dtype=object)


class ConditionMedianRegressor(RegressorMixin, BaseEstimator):
    """Historical method-median baseline, fitted only on each training fold."""

    def fit(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> ConditionMedianRegressor:
        required = {"tipo_columna", "fase_movil", "flujo_ml_min"}
        missing = required.difference(X.columns)
        if missing:
            raise ValueError(f"Missing baseline columns: {sorted(missing)}")
        frame = X.loc[:, ["tipo_columna", "fase_movil", "flujo_ml_min"]].copy()
        frame["_target"] = np.asarray(y, dtype=float)
        self.global_median_ = float(np.nanmedian(frame["_target"]))
        self.condition_medians_ = (
            frame.groupby(
                ["tipo_columna", "fase_movil", "flujo_ml_min"],
                dropna=False,
                sort=False,
            )["_target"]
            .median()
            .to_dict()
        )
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        check_is_fitted(self, ("global_median_", "condition_medians_"))
        keys = zip(
            X["tipo_columna"],
            X["fase_movil"],
            X["flujo_ml_min"],
            strict=True,
        )
        return np.asarray(
            [self.condition_medians_.get(tuple(key), self.global_median_) for key in keys],
            dtype=float,
        )


def make_model_pipeline(
    regressor: Any, feature_columns: tuple[str, ...] | list[str] = FEATURE_COLUMNS
) -> Pipeline:
    """Shared preparation; ``feature_columns`` only narrows it for ablations."""
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    preprocessing = ColumnTransformer(
        transformers=[("numeric", numeric, list(feature_columns))],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("features", MoleculeConditionFeatures()),
            ("preprocessing", preprocessing),
            ("regressor", regressor),
        ]
    )


def make_default_models(random_state: int = 42) -> dict[str, Any]:
    """Five candidate families, with only deterministic seeds/parallelism set."""
    return {
        "ridge": Ridge(),
        "random_forest": RandomForestRegressor(
            random_state=random_state, n_jobs=1
        ),
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            random_state=random_state
        ),
        "mlp": MLPRegressor(random_state=random_state),
        "knn": KNeighborsRegressor(n_jobs=1),
    }


def make_baselines(random_state: int = 42) -> dict[str, Any]:
    from sklearn.dummy import DummyRegressor

    return {
        "naive_median": DummyRegressor(strategy="median"),
        "method_median_proxy": ConditionMedianRegressor(),
    }


def make_search_spaces() -> Mapping[str, dict[str, Any]]:
    return {
        "ridge": {
            "regressor__alpha": loguniform(1e-4, 1e4),
        },
        "random_forest": {
            "regressor__n_estimators": [100, 200, 300],
            "regressor__max_depth": [None, 8, 16, 24],
            "regressor__min_samples_leaf": [1, 2, 4, 8],
            "regressor__max_features": [0.5, 0.8, 1.0],
        },
        "hist_gradient_boosting": {
            "regressor__learning_rate": loguniform(0.01, 0.2),
            "regressor__max_iter": [100, 200, 300],
            "regressor__max_leaf_nodes": [15, 31, 63],
            "regressor__min_samples_leaf": [10, 20, 50],
            "regressor__l2_regularization": loguniform(1e-5, 10.0),
        },
        "mlp": {
            "regressor__hidden_layer_sizes": [(64,), (128,), (64, 32)],
            "regressor__alpha": loguniform(1e-6, 1e-1),
            "regressor__learning_rate_init": loguniform(1e-4, 1e-1),
        },
        "knn": {
            "regressor__n_neighbors": [3, 5, 7, 11, 15, 21, 31, 41],
            "regressor__weights": ["uniform", "distance"],
            "regressor__p": [1, 2],
        },
    }


def make_group_holdout(
    frame: pd.DataFrame, test_size: float = 0.2, random_state: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    if "inchikey" not in frame or frame["inchikey"].isna().any():
        raise ValueError("A non-null inchikey is required for group-aware splitting")
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=test_size, random_state=random_state
    )
    train_idx, test_idx = next(
        splitter.split(frame, groups=frame["inchikey"].astype(str))
    )
    train_groups = set(frame.iloc[train_idx]["inchikey"].astype(str))
    test_groups = set(frame.iloc[test_idx]["inchikey"].astype(str))
    if train_groups.intersection(test_groups):
        raise RuntimeError("Compound groups leaked across the holdout split")
    return train_idx, test_idx


def make_group_cv(n_splits: int = 5) -> GroupKFold:
    return GroupKFold(n_splits=n_splits)
