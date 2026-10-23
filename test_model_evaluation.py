import unittest
from unittest.mock import patch

from scripts.evaluar_modelo import evaluate


class ModelEvaluationTests(unittest.TestCase):
    def test_metrics_count_unavailable_predictions_as_errors(self):
        cases = [
            {"case_id": "1", "text_content": "uno", "expected_sentiment": "Positivo", "expected_red_flag": False},
            {"case_id": "2", "text_content": "dos", "expected_sentiment": "Negativo", "expected_red_flag": True},
            {"case_id": "3", "text_content": "tres", "expected_sentiment": "Neutral", "expected_red_flag": True},
            {"case_id": "4", "text_content": "cuatro", "expected_sentiment": "Positivo", "expected_red_flag": False},
        ]
        outputs = [
            {"sentiment_label": "Positivo", "metadata_ai": {"risk_burnout": False}},
            {"sentiment_label": "Negativo", "metadata_ai": {"risk_burnout": True}},
            {"sentiment_label": "NO_DISPONIBLE", "metadata_ai": {"risk_burnout": False, "error_type": "TimeoutError"}},
            {"sentiment_label": "Negativo", "metadata_ai": {"risk_burnout": False}},
        ]

        with (
            patch("scripts.evaluar_modelo.sanitize_text", side_effect=lambda text: text),
            patch("scripts.evaluar_modelo.analyze_sentiment_with_ai", side_effect=outputs),
        ):
            metrics = evaluate(cases, delay_seconds=0)

        self.assertEqual(metrics["sentiment_accuracy"], 0.5)
        self.assertEqual(metrics["analysis_available"], 3)
        self.assertEqual(metrics["unavailable_or_failed"], 1)
        self.assertEqual(metrics["red_flag"]["recall"], 0.5)
        self.assertEqual(metrics["red_flag"]["false_negatives"], 1)
        self.assertEqual(metrics["per_case"][2]["unavailable_reason"], "TimeoutError")
        self.assertIn("p95", metrics["latency_seconds"])

    def test_unavailable_reason_is_recorded_when_evaluation_raises(self):
        case = {"case_id": "E127", "text_content": "texto", "expected_sentiment": "Neutral", "expected_red_flag": False}
        with (
            patch("scripts.evaluar_modelo.sanitize_text", side_effect=lambda text: text),
            patch("scripts.evaluar_modelo.analyze_sentiment_with_ai", side_effect=TimeoutError),
        ):
            metrics = evaluate([case], delay_seconds=0)

        self.assertEqual(metrics["per_case"][0]["unavailable_reason"], "TimeoutError")


if __name__ == "__main__":
    unittest.main()
