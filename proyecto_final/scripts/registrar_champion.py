"""Entrena y registra un modelo con el segmento de entrenamiento (PSet 4).

Uso (desde proyecto_final/, con MLflow levantado):
    python -m scripts.registrar_champion --alias challenger --motivo "..."

1. Lee el snapshot C18 de la OBT y el manifiesto de lotes por experimento.
2. Entrena con el segmento `entrenamiento` (experimentos 0006-0275) usando los
   hiperparámetros del champion del PSet 3 (sin repetir el tuning) y las
   features de src/pipeline.py.
3. Registra `qsrr-predict-modelo` con el alias indicado.
4. Si el alias es `champion`, exporta el fixture de CI (scripts/exportar_fixture.py).
"""

from __future__ import annotations

import argparse

from scripts import exportar_fixture
from src.datos import load_snapshot
from src.reentrenar import MODEL_NAME, fit_and_register
from src.splits import TRAINING_SEGMENT, create_or_load_lots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alias", default="champion", choices=["champion", "challenger"])
    parser.add_argument(
        "--motivo",
        default="champion inicial PSet 4: OBT corregida y split por experimento",
    )
    parser.add_argument("--fase", default="entrenamiento_inicial")
    args = parser.parse_args()

    frame, metadata = load_snapshot()
    frame, lots = create_or_load_lots(frame, source_sha256=metadata["sha256"])
    train = frame.loc[frame["segment"].eq(TRAINING_SEGMENT)].reset_index(drop=True)
    sample = frame.loc[frame["segment"].eq(exportar_fixture.SAMPLE_SEGMENT)].sample(
        n=exportar_fixture.SAMPLE_SIZE, random_state=42
    )
    result = fit_and_register(
        train,
        dataset_metadata=metadata,
        phase=args.fase,
        reason=args.motivo,
        alias=args.alias,
        training_segments=[TRAINING_SEGMENT],
        evaluation={"muestra_fija": sample},
        extra_tags={"corte_experimento": lots["cutoff_experiment"]},
    )
    print(
        f"{MODEL_NAME} v{result['version']} @{args.alias} run={result['run_id']} "
        f"CV RMSE={result['cv_rmse_mean']:.3f}±{result['cv_rmse_std']:.3f}"
    )
    if args.alias == "champion":
        exportar_fixture.main("champion")


if __name__ == "__main__":
    main()
