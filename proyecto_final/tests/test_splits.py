import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.splits import create_or_load_holdout


class CreateOrLoadHoldoutTests(unittest.TestCase):
    def test_nonconsecutive_input_index_keeps_grouped_holdout_aligned(self):
        frame = pd.DataFrame(
            {
                "hecho_id": [f"row-{index}" for index in range(20)],
                "inchikey": [f"compound-{index}" for index in range(20)],
            },
            index=[index * 3 + 7 for index in range(20)],
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch("src.splits.SPLIT_PATH", root / "split.csv"),
                patch(
                    "src.splits.SPLIT_METADATA_PATH",
                    root / "split.metadata.json",
                ),
            ):
                train, test, _ = create_or_load_holdout(
                    frame,
                    source_sha256="dataset-hash",
                )

        self.assertEqual(len(train) + len(test), len(frame))
        self.assertFalse(set(train["hecho_id"]) & set(test["hecho_id"]))
        self.assertFalse(set(train["inchikey"]) & set(test["inchikey"]))
        self.assertEqual(
            set(train["hecho_id"]) | set(test["hecho_id"]),
            set(frame["hecho_id"]),
        )

    def test_incomplete_saved_split_is_rejected(self):
        frame = pd.DataFrame(
            {
                "hecho_id": [f"row-{index}" for index in range(10)],
                "inchikey": [f"compound-{index}" for index in range(10)],
            }
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            split_path = root / "split.csv"
            split_path.touch()
            with (
                patch("src.splits.SPLIT_PATH", split_path),
                patch(
                    "src.splits.SPLIT_METADATA_PATH",
                    root / "missing.metadata.json",
                ),
                self.assertRaisesRegex(ValueError, "incomplete"),
            ):
                create_or_load_holdout(
                    frame,
                    source_sha256="dataset-hash",
                )


if __name__ == "__main__":
    unittest.main()
