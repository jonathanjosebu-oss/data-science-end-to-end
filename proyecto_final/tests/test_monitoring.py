import unittest

import numpy as np
import pandas as pd

from src.monitoring import feature_drift_report


class FeatureDriftReportTests(unittest.TestCase):
    def test_detects_distribution_and_missingness_shift(self):
        reference = pd.DataFrame(
            {
                "stable": [0.0, 1.0, 2.0, 3.0],
                "shifted": [0.0, 1.0, 2.0, 3.0],
            }
        )
        current = pd.DataFrame(
            {
                "stable": [0.0, 1.0, np.nan, 3.0],
                "shifted": [20.0, 21.0, 22.0, 23.0],
            }
        )

        report = feature_drift_report(reference, current, bins=4)
        metrics = report.set_index("feature")

        self.assertGreater(metrics.loc["shifted", "psi"], metrics.loc["stable", "psi"])
        self.assertEqual(metrics.loc["stable", "current_missing_fraction"], 0.25)
        self.assertEqual(metrics.loc["stable", "reference_missing_fraction"], 0.0)

    def test_rejects_mismatched_features(self):
        with self.assertRaises(ValueError):
            feature_drift_report(
                pd.DataFrame({"first": [1.0, 2.0]}),
                pd.DataFrame({"other": [1.0, 2.0]}),
            )

    def test_detects_shift_for_binary_feature(self):
        reference = pd.DataFrame({"binary": [0.0, 0.0, 1.0, 1.0]})
        current = pd.DataFrame({"binary": [1.0, 1.0, 1.0, 1.0]})

        report = feature_drift_report(reference, current, bins=10)

        self.assertGreater(report.loc[0, "psi"], 0.0)

    def test_rejects_non_numeric_features(self):
        with self.assertRaises(TypeError):
            feature_drift_report(
                pd.DataFrame({"feature": ["a", "b"]}),
                pd.DataFrame({"feature": ["a", "c"]}),
            )


if __name__ == "__main__":
    unittest.main()
