import unittest
from unittest.mock import patch

from src.llm_benchmark import (
    build_prediction_prompt,
    parse_prediction_response,
    request_gemini_prediction,
)


class LlmBenchmarkTests(unittest.TestCase):
    def test_prompt_uses_features_without_target_or_identifiers(self):
        prompt = build_prediction_prompt(
            {
                "smiles": "CCO",
                "tipo_columna": "C18",
                "fase_movil": "A[H2O=95;MeOH=5;ACN=0]",
                "flujo_ml_min": 1.0,
                "tiempo_retencion": 7.5,
                "hecho_id": "private-row-id",
            }
        )

        self.assertIn("SMILES: CCO", prompt)
        self.assertIn("Flow rate (mL/min): 1.0", prompt)
        self.assertNotIn("7.5", prompt)
        self.assertNotIn("private-row-id", prompt)

    def test_parses_valid_numeric_response(self):
        self.assertEqual(
            parse_prediction_response('{"predicted_retention_min": 4.25}'),
            4.25,
        )

    def test_rejects_missing_or_nonfinite_prediction(self):
        for response in (
            '{"other": 1}',
            '{"predicted_retention_min": "not a number"}',
            '{"predicted_retention_min": NaN}',
        ):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    parse_prediction_response(response)

    @patch("src.llm_benchmark.urlopen")
    def test_api_request_uses_header_and_parses_usage(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = (
            b'{"candidates":[{"content":{"parts":[{"text":'
            b'"{\\"predicted_retention_min\\": 3.5}"}]}}],'
            b'"usageMetadata":{"promptTokenCount":12,"candidatesTokenCount":4}}'
        )

        result = request_gemini_prediction(
            "target-free prompt",
            api_key="test-only-key",
            model="gemini-test",
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("X-goog-api-key"), "test-only-key")
        self.assertNotIn("test-only-key", request.full_url)
        self.assertEqual(result["prediction"], 3.5)
        self.assertEqual(result["prompt_tokens"], 12)
        self.assertEqual(result["output_tokens"], 4)


if __name__ == "__main__":
    unittest.main()
