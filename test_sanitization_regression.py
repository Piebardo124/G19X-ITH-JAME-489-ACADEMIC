"""Regresiones de privacidad con el modelo real; sin red ni escritura en BD."""
import unittest
import unicodedata
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.sanitization import sanitize_text


class SanitizationRegressionTests(unittest.TestCase):
    def test_contextual_names_preserve_the_rest_of_the_sentence(self):
        for name in ("Ana López", "ana lópez", "ANA LÓPEZ", "María del Carmen López",
                     "Ana-María López", "Ana O’Connor", "Juan Pérez"):
            with self.subTest(name=name):
                self.assertEqual(
                    sanitize_text(f"Mi jefa {name} me humilla en las juntas."),
                    "Mi jefa [NOMBRE OCULTO] me humilla en las juntas.",
                )

    def test_colon_and_honorifics(self):
        for title in ("Mi jefa:", "La Sra.", "El Sr.", "Mi supervisora", "Mi líder"):
            with self.subTest(title=title):
                self.assertEqual(sanitize_text(f"{title} Ana López me humilla."),
                                 f"{title} [NOMBRE OCULTO] me humilla.")

    def test_common_words_after_job_titles_are_preserved(self):
        for text in (
            "Mi jefa organiza reuniones y escucha propuestas.",
            "El gerente siempre escucha las propuestas del equipo.",
            "El director de operaciones escucha al equipo.",
            "Mi jefe de turno escucha al equipo.",
        ):
            with self.subTest(text=text):
                self.assertEqual(sanitize_text(text), text)

    def test_technology_names_do_not_bypass_person_redaction(self):
        self.assertEqual(sanitize_text("Mi jefa Ana López trabaja con React."),
                         "Mi jefa [NOMBRE OCULTO] trabaja con React.")
        self.assertEqual(sanitize_text("Usamos React, Python, Azure y PostgreSQL."),
                         "Usamos React, Python, Azure y PostgreSQL.")

    def test_unicode_and_ascii_emails(self):
        for email in ("test.empresa+qa@plurione.com.mx", "PRUEBA@EMPRESA.COM",
                      "josé@ejemplo.com", "prueba@mañana.mx", "persona @ ejemplo.com",
                      "persona @ ejemplo . com"):
            with self.subTest(email=email):
                self.assertEqual(sanitize_text(f"Mi correo es {email}."),
                                 "Mi correo es [CORREO OCULTO].")

    def test_phone_separators(self):
        for phone in ("+52 55 1234 5678", "(662) 123-4567", "6621234567", "662.123.4567"):
            with self.subTest(phone=phone):
                self.assertEqual(sanitize_text(f"Me contactan al {phone} para la reunión."),
                                 "Me contactan al [TELEFONO OCULTO] para la reunión.")

    def test_email_does_not_consume_the_next_sentence(self):
        self.assertEqual(sanitize_text("Mi correo es persona@ejemplo.com. Pedido 12345678."),
                         "Mi correo es [CORREO OCULTO]. Pedido 12345678.")

    def test_rfc_does_not_consume_following_words_or_spaces(self):
        for suffix in (" y necesito ayuda.", " con datos.", " por favor.",
                       " CON DATOS.", " POR FAVOR.", " FUE RECHAZADO.", " PAN GRATIS."):
            with self.subTest(suffix=suffix):
                self.assertEqual(sanitize_text("Mi RFC es ABCD123456" + suffix),
                                 "Mi RFC es [RFC OCULTO]" + suffix)

    def test_rfc_formats(self):
        for identifier in ("ABCD123456XYZ", "ABC123456XYZ", "ABCD 123456 XYZ", "abcd123456xyz"):
            with self.subTest(identifier=identifier):
                self.assertEqual(sanitize_text(f"Mi RFC es {identifier} y necesito ayuda."),
                                 "Mi RFC es [RFC OCULTO] y necesito ayuda.")

    def test_curp(self):
        self.assertEqual(sanitize_text("Mi CURP es GODE561231HDFRRN09 y necesito ayuda."),
                         "Mi CURP es [CURP OCULTA] y necesito ayuda.")

    def test_existing_labels_are_preserved(self):
        text = ("Mi jefa [NOMBRE OCULTO] usa [CORREO OCULTO], [TELEFONO OCULTO], "
                "[RFC OCULTO], [CURP OCULTA] en [UBICACION OCULTA].")
        self.assertEqual(sanitize_text(text), text)

    def test_idempotence_for_combined_pii(self):
        text = ("Mi jefa Ana López me humilla. Mi correo es persona@ejemplo.com "
                "y mi teléfono 6621234567.")
        expected = ("Mi jefa [NOMBRE OCULTO] me humilla. Mi correo es [CORREO OCULTO] "
                    "y mi teléfono [TELEFONO OCULTO].")
        self.assertEqual(sanitize_text(text), expected)
        self.assertEqual(sanitize_text(expected), expected)

    def test_normalizes_decomposed_accents(self):
        self.assertEqual(sanitize_text(unicodedata.normalize("NFD", "Mi jefa Ana López me humilla.")),
                         "Mi jefa [NOMBRE OCULTO] me humilla.")

    def test_names_interrupted_by_labels_or_technology_are_not_partially_exposed(self):
        for middle in ("[CORREO OCULTO]", "React", "persona@ejemplo.com"):
            with self.subTest(middle=middle):
                expected_middle = "[CORREO OCULTO]" if "@" in middle else middle
                expected = f"Mi jefa [NOMBRE OCULTO] {expected_middle} [NOMBRE OCULTO] me humilla."
                self.assertEqual(sanitize_text(f"Mi jefa Ana {middle} López me humilla."), expected)
                self.assertEqual(sanitize_text(expected), expected)

    def test_dates_short_folios_and_empty_text(self):
        for text in ("", "Reunión el 12/10/2026 a las 10:30.", "Pedido 12345678 el 12/10/2026."):
            with self.subTest(text=text):
                self.assertEqual(sanitize_text(text), text)

    def test_buzon_sanitizes_before_persistence_and_ai(self):
        from app.api.v1.endpoints import feedback
        from app.db.database import get_db
        from app.db.models import FeedbackEntry

        db = MagicMock()
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router)
        app.dependency_overrides[get_db] = lambda: db
        result = {"polarity_score": 0.0, "sentiment_label": "Neutral", "key_phrases": [],
                  "metadata_ai": {"risk_burnout": False, "is_simulation": False}}
        expected = "Mi jefa [NOMBRE OCULTO] me humilla. Mi correo es [CORREO OCULTO]."
        feedback.limiter.reset()
        try:
            with TestClient(app) as client, patch.object(feedback, "analyze_sentiment_with_ai", return_value=result) as ai:
                response = client.post("/analyze-feedback", json={
                    "text_content": "Mi jefa Ana López me humilla. Mi correo es persona@ejemplo.com.",
                })
                self.assertEqual(response.status_code, 200, response.text)
                ai.assert_called_once_with(expected)
            entries = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], FeedbackEntry)]
            self.assertEqual([entry.content_text for entry in entries], [expected])
        finally:
            feedback.limiter.reset()

    def test_csv_sanitizes_before_persistence_and_ai(self):
        import uuid
        from app.api.v1.endpoints import feedback
        from app.db.models import CSVImport, Department, FeedbackEntry

        db, job = MagicMock(), CSVImport(id=uuid.uuid4(), filename="synthetic.csv", status="QUEUED")
        db.query.return_value.filter.return_value.first.return_value = job
        db.query.return_value.all.return_value = [Department(id=1, name="Recursos Humanos")]
        result = {"polarity_score": 0.0, "sentiment_label": "Neutral", "key_phrases": [],
                  "metadata_ai": {"risk_burnout": False, "is_simulation": False}}
        with patch.object(feedback, "SessionLocal", return_value=db), \
             patch.object(feedback, "analyze_sentiment_with_ai", return_value=result) as ai:
            feedback.process_csv_background("text_content\nMi jefa Ana López me humilla.\n", job.id)
            ai.assert_called_once_with("Mi jefa [NOMBRE OCULTO] me humilla.")
        entries = [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], FeedbackEntry)]
        self.assertEqual([entry.content_text for entry in entries], ["Mi jefa [NOMBRE OCULTO] me humilla."])
        self.assertEqual(job.processed_rows, 1)
        self.assertEqual(job.status, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
