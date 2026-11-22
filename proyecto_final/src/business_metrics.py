"""Pairwise uncertainty calibration and explicitly labeled coelution proxies."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def _sample_condition_pairs(
    condition_groups: Sequence[object],
    molecule_groups: Sequence[object],
    *,
    max_pairs: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    conditions = (
        pd.Series(condition_groups).reset_index(drop=True).fillna("<MISSING>").astype(str)
    )
    molecules = (
        pd.Series(molecule_groups).reset_index(drop=True).fillna("<MISSING>").astype(str)
    )
    rng = np.random.default_rng(random_state)
    group_indices = [
        group.index.to_numpy()
        for _, group in conditions.groupby(conditions, sort=True)
        if len(group) > 1
    ]
    if not group_indices:
        raise ValueError("No chromatographic condition has two or more observations")

    left_parts = []
    right_parts = []
    remaining = max_pairs
    pairs_per_group = max(1, max_pairs // len(group_indices))
    for indices in group_indices:
        pair_count = min(pairs_per_group, remaining)
        if len(indices) <= 2_000:
            left_positions, right_positions = np.triu_indices(len(indices), k=1)
            left_values = indices[left_positions]
            right_values = indices[right_positions]
            valid = (
                molecules.iloc[left_values].to_numpy()
                != molecules.iloc[right_values].to_numpy()
            )
            left_values = left_values[valid]
            right_values = right_values[valid]
            if len(left_values) > pair_count:
                selected = rng.choice(len(left_values), size=pair_count, replace=False)
                left_values = left_values[selected]
                right_values = right_values[selected]
        else:
            selected_pairs: set[tuple[int, int]] = set()
            attempts = 0
            while len(selected_pairs) < pair_count and attempts < 20 * pair_count:
                left = int(rng.choice(indices))
                right = int(rng.choice(indices))
                if (
                    left != right
                    and molecules.iloc[left] != molecules.iloc[right]
                ):
                    selected_pairs.add((min(left, right), max(left, right)))
                attempts += 1
            if not selected_pairs:
                continue
            left_values, right_values = map(
                np.asarray, zip(*sorted(selected_pairs), strict=True)
            )
        if len(left_values):
            left_parts.append(left_values)
            right_parts.append(right_values)
            remaining -= len(left_values)
        if remaining <= 0:
            break

    if not left_parts:
        raise ValueError("Could not sample pairs of distinct compounds by condition")
    left = np.concatenate(left_parts)[:max_pairs]
    right = np.concatenate(right_parts)[:max_pairs]
    if len(left) == 0:
        raise ValueError("No distinct-compound pairs were sampled")
    return left.astype(int), right.astype(int)


def calibrate_pairwise_interval(
    y_true: Sequence[float],
    y_oof: Sequence[float],
    condition_groups: Sequence[object],
    molecule_groups: Sequence[object],
    *,
    coverage: float = 0.95,
    max_pairs: int = 100_000,
    random_state: int = 42,
) -> dict[str, float | int]:
    """Estimate a two-sided prediction interval from out-of-fold pair errors."""
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between 0 and 1")
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_oof, dtype=float)
    if not (len(actual) == len(predicted) == len(condition_groups) == len(molecule_groups)):
        raise ValueError("Targets, predictions, and grouping arrays must align")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("OOF targets and predictions must be finite")

    left, right = _sample_condition_pairs(
        condition_groups,
        molecule_groups,
        max_pairs=max_pairs,
        random_state=random_state,
    )
    residual = actual - predicted
    pair_errors = residual[left] - residual[right]
    tail = (1 - coverage) / 2
    lower, upper = np.quantile(pair_errors, [tail, 1 - tail])
    paired_rows = np.unique(np.concatenate([left, right]))
    single_rmse = float(np.sqrt(np.mean(residual[paired_rows] ** 2)))
    pair_rmse = float(np.sqrt(np.mean(pair_errors**2)))
    return {
        "coverage": float(coverage),
        "lower_error_quantile": float(lower),
        "upper_error_quantile": float(upper),
        "pair_error_radius": float(max(abs(lower), abs(upper))),
        "calibration_pairs": int(len(pair_errors)),
        # Theory for independent errors: pair_rmse ~= sqrt(2) * single_rmse.
        "single_prediction_rmse": single_rmse,
        "pair_difference_rmse": pair_rmse,
        "pair_to_single_error_ratio": pair_rmse / single_rmse if single_rmse else float("nan"),
    }


COELUTION_WINDOW_MIN = 0.5
"""Event definition from PSet 1: two compounds whose *observed* retention times
differ by at most 0.5 min under the same condition. It is independent of the
model; the alert rule (model uncertainty) is evaluated against it."""


def _alert_scores(alerts: np.ndarray, events: np.ndarray) -> dict[str, float]:
    event_count = int(events.sum())
    alert_count = int(alerts.sum())
    recall = float(alerts[events].mean()) if event_count else float("nan")
    precision = float(events[alerts].mean()) if alert_count else float("nan")
    return {
        "alert_rate": float(alerts.mean()),
        "recall": recall,
        "false_negative_rate": 1.0 - recall if np.isfinite(recall) else float("nan"),
        "precision": precision,
        "false_alert_share": 1.0 - precision if np.isfinite(precision) else float("nan"),
    }


def coelution_proxy_metrics(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    condition_groups: Sequence[object],
    molecule_groups: Sequence[object],
    interval: dict[str, float | int],
    *,
    event_window_min: float = COELUTION_WINDOW_MIN,
    max_pairs: int = 100_000,
    random_state: int = 42,
) -> dict[str, float | int]:
    """Evaluate the interval alert rule against a model-independent proxy event.

    Event (proxy of coelution): |observed delta| <= ``event_window_min``.
    Alert: the calibrated pairwise interval around the predicted delta contains 0.
    RepoRT has no resolution/peak width, so the event is a proxy, not a
    confirmed coelution.
    """
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    if not (len(actual) == len(predicted) == len(condition_groups) == len(molecule_groups)):
        raise ValueError("Targets, predictions, and grouping arrays must align")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Holdout targets and predictions must be finite")
    if event_window_min <= 0:
        raise ValueError("event_window_min must be positive")

    left, right = _sample_condition_pairs(
        condition_groups,
        molecule_groups,
        max_pairs=max_pairs,
        random_state=random_state,
    )
    observed_delta = actual[left] - actual[right]
    predicted_delta = predicted[left] - predicted[right]
    lower = predicted_delta + float(interval["lower_error_quantile"])
    upper = predicted_delta + float(interval["upper_error_quantile"])
    alerts = (lower <= 0) & (upper >= 0)
    events = np.abs(observed_delta) <= event_window_min
    scores = _alert_scores(alerts, events)
    coverage = ((observed_delta >= lower) & (observed_delta <= upper)).mean()
    return {
        "comparison_pairs": int(len(left)),
        "event_window_min": float(event_window_min),
        "proxy_event_pairs": int(events.sum()),
        "proxy_event_base_rate": float(events.mean()),
        "coelution_proxy_recall": scores["recall"],
        "coelution_proxy_false_negative_rate": scores["false_negative_rate"],
        "coelution_proxy_precision": scores["precision"],
        "potential_coelution_alert_rate": scores["alert_rate"],
        "pairwise_prediction_interval_coverage": float(coverage),
        "coelution_labels_are_proxy": 1,
    }


def compare_alert_rules(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    condition_groups: Sequence[object],
    molecule_groups: Sequence[object],
    thresholds_min: dict[str, float],
    *,
    event_window_min: float = COELUTION_WINDOW_MIN,
    max_pairs: int = 100_000,
    random_state: int = 42,
) -> "pd.DataFrame":
    """Alert when |predicted delta| <= threshold; score every rule on the same pairs."""
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    left, right = _sample_condition_pairs(
        condition_groups, molecule_groups, max_pairs=max_pairs, random_state=random_state
    )
    events = np.abs(actual[left] - actual[right]) <= event_window_min
    predicted_gap = np.abs(predicted[left] - predicted[right])
    rows = []
    for name, threshold in thresholds_min.items():
        rows.append({
            "regla": name,
            "umbral_min": float(threshold),
            **_alert_scores(predicted_gap <= threshold, events),
        })
    return pd.DataFrame(rows).set_index("regla")
