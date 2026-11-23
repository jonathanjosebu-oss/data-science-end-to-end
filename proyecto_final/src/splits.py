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


TRAINING_SEGMENT = "entrenamiento"


def experiment_order(experiment_ids: pd.Series) -> pd.Series:
    """Ordinal key for RepoRT experiment IDs ("0001", "0002", ...).

    RepoRT assigns IDs sequentially as datasets are contributed, so the ID is
    the best available proxy of arrival time (the OBT has no dates).
    """
    numeric = pd.to_numeric(experiment_ids, errors="coerce")
    if numeric.isna().any():
        bad = experiment_ids[numeric.isna()].unique()[:5]
        raise ValueError(f"Non-numeric experiment IDs cannot be ordered: {list(bad)}")
    return numeric.astype(int)


def experiment_time_split(
    frame: pd.DataFrame,
    *,
    train_fraction: float = 0.75,
    n_lots: int = 10,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Split by experiment arrival order: early experiments train, later ones
    form ``n_lots`` consecutive production lots.

    Defaults chosen on the C18 OBT (219 experiments, 137 539 rows, of which
    experiment 0186/SMRT alone holds 58 %): 0.75 puts the cutoff at 0275 and
    leaves 10 lots of ~1.3k-6.5k rows; 0.80+ produces lots of <250 rows,
    too small for stable PSI/RMSE.

    Experiments are never split across segments. Lots are cut so that each one
    has roughly the same number of rows; a single experiment larger than the
    target lot size becomes its own lot.
    """
    required = {"hecho_id", "experimento_id"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing split columns: {sorted(missing)}")
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    if n_lots < 1:
        raise ValueError("n_lots must be positive")

    sizes = (
        frame.assign(_order=experiment_order(frame["experimento_id"]))
        .groupby(["_order", "experimento_id"], sort=True)
        .size()
        .reset_index(name="rows")
    )
    if len(sizes) < n_lots + 1:
        raise ValueError("Not enough experiments for the requested lots")
    total = int(sizes["rows"].sum())
    cumulative = sizes["rows"].cumsum()
    # Training: every experiment that starts before the cutoff share.
    in_training = (cumulative - sizes["rows"]) < train_fraction * total
    sizes["segment"] = np.where(in_training, TRAINING_SEGMENT, "")

    post = sizes.loc[~in_training].copy()
    if len(post) < n_lots:
        raise ValueError("Not enough post-cutoff experiments for the requested lots")
    target = post["rows"].sum() / n_lots
    lot = 1
    current = 0
    labels = []
    remaining_experiments = len(post)
    for rows in post["rows"]:
        remaining_lots = n_lots - lot
        # Close the lot when it reached its target, or when the experiments
        # left are just enough to give one to every lot still to be filled.
        if (
            remaining_lots > 0
            and current > 0
            and (current >= target or remaining_experiments <= remaining_lots)
        ):
            lot += 1
            current = 0
        labels.append(f"lote_{lot:02d}")
        current += rows
        remaining_experiments -= 1
    sizes.loc[~in_training, "segment"] = labels

    segment_by_experiment = sizes.set_index("experimento_id")["segment"]
    manifest = pd.DataFrame(
        {
            "hecho_id": frame["hecho_id"].astype(str).to_numpy(),
            "experimento_id": frame["experimento_id"].astype(str).to_numpy(),
        }
    )
    manifest["segment"] = manifest["experimento_id"].map(segment_by_experiment)
    cutoff = sizes.loc[in_training, "experimento_id"].iloc[-1]
    summary = (
        sizes.groupby("segment", sort=True)
        .agg(
            experiments=("experimento_id", "size"),
            rows=("rows", "sum"),
            first_experiment=("experimento_id", "first"),
            last_experiment=("experimento_id", "last"),
        )
        .reset_index()
    )
    metadata = {
        "method": "experiment-ID arrival order; experiments never split",
        "train_fraction": train_fraction,
        "n_lots": int(summary["segment"].str.startswith("lote_").sum()),
        "cutoff_experiment": str(cutoff),
        "segments": summary.to_dict(orient="records"),
    }
    return manifest, metadata


LOTS_PATH = PROJECT_ROOT / "data" / "lotes_manifest.csv"
LOTS_METADATA_PATH = PROJECT_ROOT / "data" / "lotes_manifest.metadata.json"
LOTS_SUMMARY_PATH = PROJECT_ROOT / "docs" / "lotes.csv"


def create_or_load_lots(
    frame: pd.DataFrame,
    *,
    source_sha256: str,
    train_fraction: float = 0.75,
    n_lots: int = 10,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Persist the experiment-order split once; refuse silent changes.

    Returns ``frame`` with a ``segment`` column ("entrenamiento", "lote_01"...).
    """
    manifest, metadata = experiment_time_split(
        frame, train_fraction=train_fraction, n_lots=n_lots
    )
    metadata = {"source_sha256": source_sha256, **metadata}
    if LOTS_PATH.is_file() and LOTS_METADATA_PATH.is_file():
        saved = json.loads(LOTS_METADATA_PATH.read_text(encoding="utf-8"))
        if saved != json.loads(json.dumps(metadata)):
            raise ValueError(
                "The saved lot manifest belongs to another dataset or setting. "
                "Remove data/lotes_manifest.* only after deciding to rebuild lots."
            )
    else:
        LOTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        manifest.sort_values("hecho_id").to_csv(LOTS_PATH, index=False)
        LOTS_METADATA_PATH.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        LOTS_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(metadata["segments"]).to_csv(LOTS_SUMMARY_PATH, index=False)

    segment = frame["hecho_id"].astype(str).map(
        manifest.set_index("hecho_id")["segment"]
    )
    if segment.isna().any():
        raise ValueError("Some observations have no segment in the lot manifest")
    return frame.assign(segment=segment.to_numpy()), metadata


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
