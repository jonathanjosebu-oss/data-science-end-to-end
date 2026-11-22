import unittest

import pandas as pd

from src.splits import stratified_compound_sample


class StratifiedCompoundSampleTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame(
            [
                {
                    "hecho_id": f"row-{compound}-{replicate}",
                    "inchikey": f"compound-{compound}",
                    "tiempo_retencion": float(compound + replicate / 10),
                }
                for compound in range(40)
                for replicate in range(2)
            ]
        )

    def test_sample_is_reproducible_grouped_and_stratified(self):
        first, first_metadata = stratified_compound_sample(
            self.frame,
            max_compounds=10,
            random_state=17,
        )
        second, second_metadata = stratified_compound_sample(
            self.frame,
            max_compounds=10,
            random_state=17,
        )

        self.assertEqual(first["hecho_id"].tolist(), second["hecho_id"].tolist())
        self.assertEqual(first_metadata, second_metadata)
        self.assertEqual(first["inchikey"].nunique(), 10)
        self.assertEqual(len(first), 20)
        self.assertTrue(first.groupby("inchikey").size().eq(2).all())

    def test_invalid_sample_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            stratified_compound_sample(self.frame, max_compounds=0)


if __name__ == "__main__":
    unittest.main()
