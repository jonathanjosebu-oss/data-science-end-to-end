import unittest

import pandas as pd

from src.datos import canonical_data_hash


class CanonicalHashTests(unittest.TestCase):
    def test_hash_is_stable_across_row_order(self):
        frame = pd.DataFrame(
            {
                "hecho_id": ["row-b", "row-a"],
                "tiempo_retencion": [2.0, 1.0],
            }
        )

        self.assertEqual(
            canonical_data_hash(frame),
            canonical_data_hash(frame.iloc[::-1].reset_index(drop=True)),
        )

    def test_hash_requires_normalized_observation_id(self):
        with self.assertRaisesRegex(ValueError, "hecho_id"):
            canonical_data_hash(pd.DataFrame({"HECHO_ID": ["row-a"]}))


if __name__ == "__main__":
    unittest.main()
