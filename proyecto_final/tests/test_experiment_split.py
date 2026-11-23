import pandas as pd
import pytest

from src.splits import TRAINING_SEGMENT, experiment_time_split


def _frame(rows_per_experiment):
    records = []
    for number, rows in enumerate(rows_per_experiment, start=1):
        experiment = f"{number:04d}"
        records += [
            {"hecho_id": f"{experiment}_{i}", "experimento_id": experiment}
            for i in range(rows)
        ]
    return pd.DataFrame(records)


def test_training_precedes_every_lot_and_experiments_are_not_split():
    frame = _frame([10] * 30)
    manifest, metadata = experiment_time_split(frame, train_fraction=0.5, n_lots=8)

    assert manifest.groupby("experimento_id")["segment"].nunique().max() == 1
    order = manifest.assign(n=manifest["experimento_id"].astype(int))
    last_train = order.loc[order["segment"].eq(TRAINING_SEGMENT), "n"].max()
    first_lot = order.loc[order["segment"].ne(TRAINING_SEGMENT), "n"].min()
    assert last_train < first_lot
    assert metadata["cutoff_experiment"] == f"{last_train:04d}"


def test_lots_are_consecutive_and_none_is_empty():
    frame = _frame([5, 50, 3, 3, 40, 2, 2, 2, 2, 30, 1, 1, 1, 1, 1, 1, 1, 1])
    manifest, metadata = experiment_time_split(frame, train_fraction=0.3, n_lots=8)

    lots = manifest.loc[manifest["segment"].str.startswith("lote_")]
    assert metadata["n_lots"] == 8
    assert lots["segment"].nunique() == 8
    by_experiment = lots.groupby("experimento_id")["segment"].first().sort_index()
    assert by_experiment.is_monotonic_increasing


def test_rejects_too_few_experiments():
    with pytest.raises(ValueError):
        experiment_time_split(_frame([10] * 5), n_lots=8)
