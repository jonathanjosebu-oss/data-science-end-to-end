"""Offline feature-distribution monitoring metrics for numeric model inputs."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype


def _psi(
    reference: np.ndarray,
    current: np.ndarray,
    *,
    bins: int,
    epsilon: float,
) -> float:
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) == 1:
        width = max(abs(float(edges[0])) * 1e-6, 1e-6)
        edges = np.array(
            [-np.inf, edges[0] - width, edges[0] + width, np.inf],
            dtype=float,
        )
    elif len(edges) == 2:
        edges = np.array(
            [-np.inf, np.mean(edges), np.inf],
            dtype=float,
        )
    else:
        edges[0] = -np.inf
        edges[-1] = np.inf

    reference_counts = np.histogram(reference, bins=edges)[0].astype(float)
    current_counts = np.histogram(current, bins=edges)[0].astype(float)
    reference_share = (reference_counts + epsilon) / (
        reference_counts.sum() + epsilon * len(reference_counts)
    )
    current_share = (current_counts + epsilon) / (
        current_counts.sum() + epsilon * len(current_counts)
    )
    return float(
        np.sum(
            (current_share - reference_share)
            * np.log(current_share / reference_share)
        )
    )


def feature_drift_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    bins: int = 10,
    epsilon: float = 1e-6,
) -> pd.DataFrame:
    """Compare numeric feature distributions without using target labels."""
    if bins < 2:
        raise ValueError("bins must be at least 2")
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if reference.empty or current.empty:
        raise ValueError("Reference and current feature frames must not be empty")
    if set(reference.columns) != set(current.columns):
        raise ValueError("Reference and current feature columns must match")

    rows = []
    current = current.loc[:, reference.columns]
    for column in reference.columns:
        if not is_numeric_dtype(reference[column]) or not is_numeric_dtype(current[column]):
            raise TypeError(f"Feature {column!r} must be numeric")
        reference_values = pd.to_numeric(reference[column], errors="coerce").to_numpy(
            dtype=float
        )
        current_values = pd.to_numeric(current[column], errors="coerce").to_numpy(
            dtype=float
        )
        reference_finite = reference_values[np.isfinite(reference_values)]
        current_finite = current_values[np.isfinite(current_values)]
        if not len(reference_finite) or not len(current_finite):
            raise ValueError(f"Feature {column!r} needs finite values in both frames")
        rows.append(
            {
                "feature": column,
                "psi": _psi(
                    reference_finite,
                    current_finite,
                    bins=bins,
                    epsilon=epsilon,
                ),
                "reference_n": int(len(reference_values)),
                "current_n": int(len(current_values)),
                "reference_missing_fraction": float(
                    1 - len(reference_finite) / len(reference_values)
                ),
                "current_missing_fraction": float(
                    1 - len(current_finite) / len(current_values)
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("psi", ascending=False).reset_index(drop=True)
