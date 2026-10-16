import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.v1.endpoints.feedback import _safe_sentiment_distribution
from app.services.ai_engine import AIAnalysisResult, analyze_sentiment_with_ai, generate_executive_summary
from app.services.sanitization import sanitize_text


class _FakePrompt:
    def __or__(self, right):
        return _FakeChain(right)


class _FakeChain:
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, _payload):
        if isinstance(self.llm, _FakeStructuredLLM):
            return self.llm.result
        return SimpleNamespace(content=self.llm.summary)


class _FakeStructuredLLM:
    def __init__(self, result):
        self.result = result


class _FakeLLM:
    result = AIAnalysisResult(
        polarity_score=-0.7,
        sentiment_label="Negativo",
        emotions_detected=["Estrés/Burnout"],
        organizational_axes=["Carga de trabajo"],
        risk_burnout=True,
        red_flag_reason="Julio reporta agotamiento; escribir a test@empresa.com",
        key_phrases=["Julio", "test@empresa.com", "carga excesiva"],
    )
    summary = "Julio informó problemas; contactar test@empresa.com."

    def __init__(self, **_kwargs):
        pass

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self.result)


class PrivacyTests(unittest.TestCase):
    def test_pii_sanitization_and_context_preservation(self):
        original = (
            "Me contactaron al +52 55 1234 5678 y al (662) 123-4567. "
            "Mi RFC es ABCD123456XYZ y mi correo test.empresa@plurione.com.mx. "
            "Pedido 12345678 el 12/10/2026."
        )
        cleaned = sanitize_text(original)

        self.assertNotIn("+52", cleaned)
        self.assertNotIn("1234 5678", cleaned)
        self.assertNotIn("662", cleaned)
        self.assertNotIn("ABCD123456XYZ", cleaned)
        self.assertNotIn("test.empresa", cleaned)
        self.assertIn("[TELEFONO OCULTO] y al [TELEFONO OCULTO]", cleaned)
        self.assertIn("[RFC OCULTO]", cleaned)
        self.assertIn("[CORREO OCULTO]", cleaned)
        self.assertIn("Pedido 12345678", cleaned)
        self.assertIn("12/10/2026", cleaned)
        self.assertEqual(
            sanitize_text("Reunión el 12/10/2026 a las 10:30."),
            "Reunión el 12/10/2026 a las 10:30.",
        )

    def test_ai_analysis_output_is_sanitized(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key"}), \
             patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
             patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
            result = analyze_sentiment_with_ai("Comentario de prueba")

        self.assertIn("[NOMBRE OCULTO]", result["key_phrases"])
        self.assertIn("[CORREO OCULTO]", result["key_phrases"])
        self.assertNotIn("test@empresa.com", result["metadata_ai"]["red_flag_reason"])
        self.assertTrue(
            "[CORREO OCULTO]" in result["metadata_ai"]["red_flag_reason"]
            or "[UBICACION OCULTA]" in result["metadata_ai"]["red_flag_reason"]
        )

    def test_executive_summary_output_is_sanitized(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key"}), \
             patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
             patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
            summary = generate_executive_summary("Comentarios sintéticos")

        self.assertNotIn("test@empresa.com", summary)
        self.assertTrue("[CORREO OCULTO]" in summary or "[UBICACION OCULTA]" in summary)

    def test_small_sentiment_category_suppresses_entire_distribution(self):
        distribution, suppressed = _safe_sentiment_distribution(
            {"Positivo": 8, "Negativo": 3, "Neutral": 7}
        )
        self.assertTrue(suppressed)
        self.assertEqual(distribution, {})

    def test_distribution_is_returned_when_every_category_meets_k(self):
        source = {"Positivo": 8, "Negativo": 5, "Neutral": 7}
        distribution, suppressed = _safe_sentiment_distribution(source)
        self.assertFalse(suppressed)
        self.assertEqual(distribution, source)


if __name__ == "__main__":
    unittest.main()
