"""Persist and validate the single compound-group holdout split."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.datos import canonical_data_hash
from src.pipeline import make_group_holdout

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPLIT_PATH = PROJECT_ROOT / "data" / "holdout_split.csv"
SPLIT_METADATA_PATH = PROJECT_ROOT / "data" / "holdout_split.metadata.json"


def stratified_compound_sample(
    frame: pd.DataFrame,
    *,
    max_compounds: int = 12_000,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Sample whole compound groups proportionally across retention quintiles."""
    required = {"hecho_id", "inchikey", "tiempo_retencion"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing sampling columns: {sorted(missing)}")
    if max_compounds < 1:
        raise ValueError("max_compounds must be positive")
    if frame["inchikey"].isna().any():
        raise ValueError("A non-null inchikey is required for stratified sampling")

    compound_medians = frame.groupby("inchikey", sort=True)["tiempo_retencion"].median()
    if compound_medians.empty or not np.isfinite(compound_medians.to_numpy()).all():
        raise ValueError("Compound-level retention medians must be non-empty and finite")

    sample_size = min(max_compounds, len(compound_medians))
    bin_count = min(5, sample_size, len(compound_medians))
    bins = pd.qcut(
        compound_medians.rank(method="first"),
        q=bin_count,
        labels=False,
    ).astype(int)
    bin_sizes = bins.value_counts().sort_index()
    exact_allocations = bin_sizes / len(compound_medians) * sample_size
    allocations = np.floor(exact_allocations).astype(int)
    remainder = sample_size - int(allocations.sum())
    remainder_order = (
        (exact_allocations - allocations)
        .sort_values(ascending=False, kind="mergesort")
        .index[:remainder]
    )
    allocations.loc[remainder_order] += 1

    rng = np.random.default_rng(random_state)
    selected_compounds = []
    for bin_id, allocation in allocations.items():
        candidates = bins.index[bins.eq(bin_id)].to_numpy()
        selected_compounds.extend(
            rng.choice(candidates, size=int(allocation), replace=False).tolist()
        )

    sample = frame.loc[frame["inchikey"].isin(selected_compounds)].copy()
    sample = sample.sort_values("hecho_id", kind="mergesort").reset_index(drop=True)
    metadata = {
        "rows": int(len(sample)),
        "compounds": int(sample["inchikey"].nunique()),
        "method": "whole-compound sample stratified by compound-median retention quintile",
        "random_state": random_state,
        "sha256": canonical_data_hash(sample),
    }
    return sample, metadata


def create_or_load_holdout(
    frame: pd.DataFrame,
    *,
    source_sha256: str,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Create the grouped holdout once and reject mismatched future datasets."""
    if "hecho_id" not in frame or frame["hecho_id"].duplicated().any():
        raise ValueError("hecho_id must be present and unique for the split")
    if "inchikey" not in frame or frame["inchikey"].isna().any():
        raise ValueError("A non-null inchikey is required for grouped splitting")

    split_hash = pd.util.hash_pandas_object(
        frame.sort_values("hecho_id").loc[:, ["hecho_id", "inchikey"]],
        index=False,
    ).sum()
    signature = {
        "source_sha256": source_sha256,
        "model_rows_hash": str(int(split_hash)),
        "test_size": test_size,
        "random_state": random_state,
        "rows": int(len(frame)),
    }
    SPLIT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if SPLIT_PATH.is_file() != SPLIT_METADATA_PATH.is_file():
        raise ValueError(
            "The saved holdout split is incomplete; restore both split files "
            "or remove both before starting a new experiment."
        )

    if SPLIT_PATH.is_file():
        saved = json.loads(SPLIT_METADATA_PATH.read_text(encoding="utf-8"))
        if saved != signature:
            raise ValueError(
                "The saved holdout split belongs to another dataset or seed. "
                "Do not replace it silently; remove the local split only after "
                "deciding to start a new experiment."
            )
        manifest = pd.read_csv(SPLIT_PATH, dtype={"hecho_id": "string"})
        if set(manifest["hecho_id"]) != set(frame["hecho_id"].astype(str)):
            raise ValueError("Saved holdout IDs do not match the current dataset")
    else:
        train_idx, test_idx = make_group_holdout(
            frame,
            test_size=test_size,
            random_state=random_state,
        )
        manifest = pd.DataFrame(
            {
                "hecho_id": frame["hecho_id"].astype(str),
                "split": "train",
            }
        )
        manifest.iloc[
            test_idx, manifest.columns.get_loc("split")
        ] = "test"
        manifest.sort_values("hecho_id").to_csv(SPLIT_PATH, index=False)
        SPLIT_METADATA_PATH.write_text(
            json.dumps(signature, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    split_by_id = manifest.set_index("hecho_id")["split"]
    split = frame["hecho_id"].astype(str).map(split_by_id)
    if split.isna().any():
        raise ValueError("The holdout manifest is missing some observation IDs")
    train = frame.loc[split.eq("train")].copy()
    test = frame.loc[split.eq("test")].copy()
    overlap = set(train["inchikey"].astype(str)) & set(test["inchikey"].astype(str))
    if overlap:
        raise RuntimeError("Compound groups leaked across the persisted holdout")
    return train, test, signature
