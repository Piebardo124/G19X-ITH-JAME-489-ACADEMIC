import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.api.v1.endpoints.feedback import _safe_sentiment_distribution
from app.services.ai_engine import AIQualitativeResult, analyze_sentiment_with_ai
from app.services.sanitization import sanitize_text


class _FakePrompt:
    def __or__(self, right):
        return _FakeChain(right)


class _FakeChain:
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, _payload):
        return self.llm.result


class _FakeStructuredLLM:
    def __init__(self, result):
        self.result = result


class _FakeLLM:
    result = AIQualitativeResult(
        emotions_detected=["Estrés/Burnout"],
        organizational_axes=["Carga de trabajo"],
        risk_burnout=True,
        red_flag_reason="Julio reporta agotamiento; escribir a test@empresa.com",
        key_phrases=["Julio", "test@empresa.com", "carga excesiva"],
    )
    def __init__(self, **_kwargs):
        pass

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self.result)


class PrivacyTests(unittest.TestCase):
    def test_ai_fallback_preserves_safe_failure_type(self):
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "",
            "AZURE_OPENAI_ENDPOINT": "",
            "AZURE_LANGUAGE_KEY": "",
            "AZURE_LANGUAGE_ENDPOINT": "",
        }):
            result = analyze_sentiment_with_ai("Comentario de prueba")

        self.assertEqual(result["sentiment_label"], "NO_DISPONIBLE")
        self.assertEqual(result["metadata_ai"]["error_type"], "AzureConfigurationMissing")

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
        azure_response = SimpleNamespace(
            is_error=False,
            sentiment="negative",
            confidence_scores=SimpleNamespace(positive=0.05, negative=0.8),
        )
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://openai.example.test/",
            "AZURE_LANGUAGE_KEY": "language-test-key",
            "AZURE_LANGUAGE_ENDPOINT": "https://language.example.test/",
        }), \
             patch("app.services.ai_engine.TextAnalyticsClient") as language_client, \
             patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
             patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
            language_client.return_value.analyze_sentiment.return_value = [azure_response]
            result = analyze_sentiment_with_ai("Comentario de prueba")

        self.assertEqual(result["polarity_score"], -0.8)
        self.assertEqual(result["sentiment_label"], "Negativo")
        language_client.return_value.analyze_sentiment.assert_called_once_with(
            documents=["Comentario de prueba"]
        )
        self.assertIn("[NOMBRE OCULTO]", result["key_phrases"])
        self.assertIn("[CORREO OCULTO]", result["key_phrases"])
        self.assertNotIn("test@empresa.com", result["metadata_ai"]["red_flag_reason"])
        self.assertTrue(
            "[CORREO OCULTO]" in result["metadata_ai"]["red_flag_reason"]
            or "[UBICACION OCULTA]" in result["metadata_ai"]["red_flag_reason"]
        )

    def test_positive_azure_sentiment_uses_confidence_scores(self):
        azure_response = SimpleNamespace(
            is_error=False,
            sentiment="positive",
            confidence_scores=SimpleNamespace(positive=0.91, negative=0.02),
        )
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://openai.example.test/",
            "AZURE_LANGUAGE_KEY": "language-test-key",
            "AZURE_LANGUAGE_ENDPOINT": "https://language.example.test/",
        }), \
             patch("app.services.ai_engine.TextAnalyticsClient") as language_client, \
             patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
             patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
            language_client.return_value.analyze_sentiment.return_value = [azure_response]
            result = analyze_sentiment_with_ai("Comentario positivo")

        self.assertEqual(result["polarity_score"], 0.91)
        self.assertEqual(result["sentiment_label"], "Positivo")

    def test_contextual_names_are_removed_from_ai_output(self):
        generated = AIQualitativeResult(
            emotions_detected=["Estrés/Burnout"],
            organizational_axes=["Liderazgo y management"],
            risk_burnout=True,
            red_flag_reason="Mi jefa ana lopez me humilla. Mi correo es persona@ejemplo.com.",
            key_phrases=["Mi jefa ana lopez me humilla", "persona@ejemplo.com", "carga excesiva"],
        )
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key", "AZURE_OPENAI_ENDPOINT": "https://example.test/",
            "AZURE_LANGUAGE_KEY": "test-key", "AZURE_LANGUAGE_ENDPOINT": "https://example.test/",
        }), patch("app.services.ai_engine.TextAnalyticsClient") as azure, \
             patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
             patch.object(_FakeLLM, "result", generated), \
             patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
            azure.return_value.analyze_sentiment.return_value = [SimpleNamespace(
                is_error=False, sentiment="negative",
                confidence_scores=SimpleNamespace(positive=0.01, negative=0.9),
            )]
            result = analyze_sentiment_with_ai("Comentario previamente sanitizado")
        self.assertEqual(result["key_phrases"][0], "Mi jefa [NOMBRE OCULTO] me humilla")
        self.assertEqual(result["metadata_ai"]["red_flag_reason"],
                         "Mi jefa [NOMBRE OCULTO] me humilla. Mi correo es [CORREO OCULTO].")

    def test_small_sentiment_category_suppresses_entire_distribution(self):
        distribution, suppressed = _safe_sentiment_distribution(
            {"Positivo": 8, "Negativo": 3, "Neutral": 7}
        )
        self.assertTrue(suppressed)
        self.assertEqual(distribution, {})

    def test_ai_generated_obfuscated_identifiers_are_sanitized(self):
        generated = AIQualitativeResult(
            emotions_detected=["Estrés/Burnout"],
            organizational_axes=["Carga de trabajo"],
            risk_burnout=True,
            red_flag_reason=("Contactar a persona＠ejemplo．com o al 662\u2011123\u20114567. "
                             "El teléfono adicional es 662[TELEFONO OCULTO]123[TELEFONO OCULTO]4567."),
            key_phrases=["teléfono 55 12 34 56 78", "Correo persona\u200b@ejemplo. com", "carga excesiva",
                         "contacto 662/123/4567"],
        )
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key", "AZURE_OPENAI_ENDPOINT": "https://example.test/",
            "AZURE_LANGUAGE_KEY": "test-key", "AZURE_LANGUAGE_ENDPOINT": "https://example.test/",
        }), patch("app.services.ai_engine.TextAnalyticsClient") as azure, \
             patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
             patch.object(_FakeLLM, "result", generated), \
             patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
            azure.return_value.analyze_sentiment.return_value = [SimpleNamespace(
                is_error=False, sentiment="negative",
                confidence_scores=SimpleNamespace(positive=0.01, negative=0.9),
            )]
            result = analyze_sentiment_with_ai("Comentario previamente sanitizado")

        self.assertEqual(result["sentiment_label"], "Negativo")
        self.assertEqual(result["key_phrases"],
                         ["teléfono [TELEFONO OCULTO]", "Correo [CORREO OCULTO]", "carga excesiva",
                          "contacto [TELEFONO OCULTO]"])
        self.assertEqual(result["metadata_ai"]["red_flag_reason"],
                         "Contactar a [CORREO OCULTO] o al [TELEFONO OCULTO]. "
                         "El teléfono adicional es [TELEFONO OCULTO].")

    def test_ai_generated_null_is_never_returned_in_phrases_or_risk_reason(self):
        for reason, expect_available in (("Agotamiento persistente.", True),
                                         ("Agotamiento\x00 persistente.", False),
                                         ("Agotamiento\x01 persistente.", False)):
            with self.subTest(reason=repr(reason)):
                generated = AIQualitativeResult(
                    emotions_detected=["Estrés/Burnout"], organizational_axes=["Carga de trabajo"],
                    risk_burnout=True, red_flag_reason=reason,
                    key_phrases=["carga\x00 excesiva", "agotamiento", "falta de descanso"],
                )
                with patch.dict(os.environ, {
                    "AZURE_OPENAI_API_KEY": "test-key", "AZURE_OPENAI_ENDPOINT": "https://example.test/",
                    "AZURE_LANGUAGE_KEY": "test-key", "AZURE_LANGUAGE_ENDPOINT": "https://example.test/",
                }), patch("app.services.ai_engine.TextAnalyticsClient") as azure, \
                     patch("app.services.ai_engine.ChatOpenAI", _FakeLLM), \
                     patch.object(_FakeLLM, "result", generated), \
                     patch("app.services.ai_engine.ChatPromptTemplate.from_messages", return_value=_FakePrompt()):
                    azure.return_value.analyze_sentiment.return_value = [SimpleNamespace(
                        is_error=False, sentiment="negative",
                        confidence_scores=SimpleNamespace(positive=0.01, negative=0.9),
                    )]
                    result = analyze_sentiment_with_ai("Comentario previamente sanitizado")
                self.assertEqual(result["sentiment_label"] != "NO_DISPONIBLE", expect_available)
                self.assertNotIn("\x00", " ".join(result["key_phrases"]))
                self.assertNotIn("\x00", result["metadata_ai"]["red_flag_reason"])
                if expect_available:
                    self.assertEqual(result["key_phrases"], ["agotamiento", "falta de descanso"])
                    self.assertTrue(result["metadata_ai"]["key_phrases_suppressed"])

    def test_distribution_is_returned_when_every_category_meets_k(self):
        source = {"Positivo": 8, "Negativo": 5, "Neutral": 7}
        distribution, suppressed = _safe_sentiment_distribution(source)
        self.assertFalse(suppressed)
        self.assertEqual(distribution, source)


if __name__ == "__main__":
    unittest.main()
