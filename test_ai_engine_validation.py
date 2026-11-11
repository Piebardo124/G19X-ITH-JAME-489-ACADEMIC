"""Contrato del modelo y posprocesamiento IA; no usa servicios externos."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.services import ai_engine as engine
from app.services.sanitization import SanitizationAmbiguityError


class _Prompt:
    def __init__(self, result):
        self.result = result

    def __or__(self, other):
        return self

    def invoke(self, payload):
        return self.result


class AIEngineValidationTests(unittest.TestCase):
    def payload(self, **overrides):
        return dict(emotions_detected=["Estrés/Burnout"], organizational_axes=["Carga de trabajo"],
                    risk_burnout=True, red_flag_reason="La carga de trabajo provoca agotamiento.",
                    key_phrases=["carga excesiva", "jornadas largas", "falta de descanso"]) | overrides

    def pipeline(self, sanitizer=lambda value: value, score=0.9):
        result = engine.AIQualitativeResult(**self.payload())
        with patch.dict("os.environ", {
            "AZURE_OPENAI_API_KEY": "test", "AZURE_OPENAI_ENDPOINT": "https://example.test/",
            "AZURE_LANGUAGE_KEY": "test", "AZURE_LANGUAGE_ENDPOINT": "https://example.test/",
        }), patch.object(engine, "TextAnalyticsClient") as azure, \
             patch.object(engine, "ChatOpenAI"), \
             patch.object(engine.ChatPromptTemplate, "from_messages", return_value=_Prompt(result)), \
             patch("app.services.sanitization.sanitize_text", side_effect=sanitizer):
            azure.return_value.analyze_sentiment.return_value = [SimpleNamespace(
                is_error=False, sentiment="negative",
                confidence_scores=SimpleNamespace(positive=0.01, negative=score),
            )]
            return engine.analyze_sentiment_with_ai("Comentario sintético")

    def test_valid_schema(self):
        self.assertTrue(engine.AIQualitativeResult(**self.payload()).risk_burnout)

    def test_rejects_unknown_catalogs_and_invalid_phrases(self):
        for overrides in (
            {"emotions_detected": ["Inventada"]}, {"organizational_axes": ["Inventado"]},
            {"red_flag_reason": " "}, {"key_phrases": [" ", "dos", "tres"]},
            {"key_phrases": ["Carga", "carga", "descanso"]},
            {"key_phrases": ["Carga   laboral", "carga laboral", "descanso"]},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                engine.AIQualitativeResult(**self.payload(**overrides))

    def test_privacy_collision_does_not_fabricate_phrases_or_discard_risk(self):
        phrases = self.payload()["key_phrases"]
        result = self.pipeline(lambda value: "[NOMBRE OCULTO]" if value in phrases else value)
        self.assertEqual(result["key_phrases"], ["[NOMBRE OCULTO]"])
        self.assertTrue(result["metadata_ai"]["key_phrases_suppressed"])
        self.assertTrue(result["metadata_ai"]["risk_burnout"])
        self.assertEqual(result["polarity_score"], -0.9)

    def test_case_and_whitespace_collisions_after_sanitization(self):
        mapping = dict(zip(self.payload()["key_phrases"], ["Carga  laboral", "carga laboral", "Descanso"]))
        self.assertEqual(self.pipeline(lambda value: mapping.get(value, value))["key_phrases"],
                         ["Carga laboral", "Descanso"])

    def test_ambiguous_phrase_is_omitted_without_losing_analysis(self):
        def sanitize(value):
            if value == "jornadas largas":
                raise SanitizationAmbiguityError("Entrada ambigua")
            return value
        result = self.pipeline(sanitize)
        self.assertEqual(len(result["key_phrases"]), 2)
        self.assertFalse(result["metadata_ai"]["is_simulation"])

    def test_invalid_scores_are_not_returned_as_real_analysis(self):
        for score in (float("nan"), float("inf"), 1.5):
            with self.subTest(score=score):
                result = self.pipeline(score=score)
                self.assertIsNone(result["polarity_score"])
                self.assertEqual(result["sentiment_label"], "NO_DISPONIBLE")


if __name__ == "__main__":
    unittest.main()
