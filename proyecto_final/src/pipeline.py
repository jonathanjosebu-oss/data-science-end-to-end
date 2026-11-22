"""Leak-free feature extraction, preprocessing, model definitions, and splits."""

from __future__ import annotations

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

FEATURE_COLUMNS = (
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
)

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


def _molecule_features(smiles: Any) -> dict[str, float]:
    values = _molecule_feature_values(smiles)
    return dict(zip(MOLECULE_FEATURE_COLUMNS, values, strict=True))


def clear_feature_caches() -> None:
    _mobile_phase_features.cache_clear()
    _molecule_feature_values.cache_clear()


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
    required = set(RAW_FEATURE_COLUMNS) | {"tiempo_retencion", "inchikey"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing modeling columns: {sorted(missing)}")
    X = frame.loc[:, RAW_FEATURE_COLUMNS].copy()
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
        return self

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
        return result.loc[:, FEATURE_COLUMNS]

    def get_feature_names_out(self, input_features: Any = None) -> np.ndarray:
        return np.asarray(FEATURE_COLUMNS, dtype=object)


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
