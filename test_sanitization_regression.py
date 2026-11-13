"""Pruebas de ocultación de datos personales."""
import unittest
import unicodedata
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.sanitization import sanitize_text, SanitizationAmbiguityError


class SanitizationRegressionTests(unittest.TestCase):
    def test_contextual_names_preserve_the_rest_of_the_sentence(self):
        for name in ("Ana López", "ana lópez", "ana lopez", "ANA LÓPEZ", "María del Carmen López",
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
        for phone in ("+52 55 1234 5678", "(662) 123-4567", "6621234567", "662.123.4567",
                      "55 12 34 56 78", "+52 55 12 34 56 78", "662\n123\n4567",
                      "55\u00a012\u00a034\u00a056\u00a078", "662\r\n123\r\n4567"):
            with self.subTest(phone=phone):
                self.assertEqual(sanitize_text(f"Me contactan al {phone} para la reunión."),
                                 "Me contactan al [TELEFONO OCULTO] para la reunión.")

    def test_unicode_invisibles_cannot_split_identifiers(self):
        for invisible in ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad",
                          "\u202e", "\u034f", "\ufe0f", "\U000e0100"):
            for original, expected in (
                (f"Mi telefono es 662{invisible}123{invisible}4567.",
                 "Mi telefono es [TELEFONO OCULTO]."),
                (f"Mi correo es persona{invisible}@ejemplo.com.",
                 "Mi correo es [CORREO OCULTO]."),
                (f"Mi RFC es ABCD{invisible}123456XYZ.", "Mi RFC es [RFC OCULTO]."),
                (f"Mi CURP es GODE561231{invisible}HDFRRN09.", "Mi CURP es [CURP OCULTA]."),
                (f"Mi jefa Ana {invisible}López me humilla.",
                 "Mi jefa [NOMBRE OCULTO] me humilla."),
            ):
                with self.subTest(invisible=repr(invisible), original=original):
                    self.assertEqual(sanitize_text(original), expected)
                    self.assertEqual(sanitize_text(expected), expected)

    def test_unicode_width_punctuation_and_email_syntax(self):
        for original, expected in (
            *((f"Mi telefono es 662{separator}123{separator}4567.",
               "Mi telefono es [TELEFONO OCULTO].")
              for separator in ("\u2010", "\u2011", "\u2013", "\u2014", "\u2212", "/", "\u2044", "\u2215", "\\")),
            ("Mi telefono es ６６２１２３４５６７.", "Mi telefono es [TELEFONO OCULTO]."),
            ("Mi correo es persona＠ejemplo．com.", "Mi correo es [CORREO OCULTO]."),
            ("Mi correo es persona@example。com.", "Mi correo es [CORREO OCULTO]."),
            ("Mi correo es o'connor@example.com.", "Mi correo es [CORREO OCULTO]."),
            ('Mi correo es "persona ejemplo"@example.com.', "Mi correo es [CORREO OCULTO]."),
            ('Mi correo es "persona@example.com".', 'Mi correo es "[CORREO OCULTO]".'),
            ('Mi correo es "persona@example.com.', 'Mi correo es "[CORREO OCULTO].'),
            ("Mi correo es a\u0301\u0323@example.com.", "Mi correo es [CORREO OCULTO]."),
            ("Mi RFC es ＡＢＣＤ１２３４５６ＸＹＺ.", "Mi RFC es [RFC OCULTO]."),
            ("Mi CURP es ＧＯＤＥ５６１２３１ＨＤＦＲＲＮ０９.", "Mi CURP es [CURP OCULTA]."),
        ):
            with self.subTest(original=original):
                self.assertEqual(sanitize_text(original), expected)
                self.assertEqual(sanitize_text(expected), expected)

    def test_labels_cannot_hide_identifiers_or_split_name_words(self):
        for original, expected in (
            ("Mi telefono es 662[TELEFONO OCULTO]123[TELEFONO OCULTO]4567.",
             "Mi telefono es [TELEFONO OCULTO]."),
            ("Mi correo es per[CORREO OCULTO]sona@ejemplo.com.",
             "Mi correo es [CORREO OCULTO]."),
            ("Mi RFC es ABCD[RFC OCULTO]123456XYZ.", "Mi RFC es [RFC OCULTO]."),
            ("Mi CURP es GODE561231[CURP OCULTA]HDFRRN09.", "Mi CURP es [CURP OCULTA]."),
            ("Mi jefa A[NOMBRE OCULTO]na L[CORREO OCULTO]ópez me humilla.",
             "Mi jefa [NOMBRE OCULTO] me humilla."),
        ):
            with self.subTest(original=original):
                self.assertEqual(sanitize_text(original), expected)
                self.assertEqual(sanitize_text(expected), expected)

    def test_detection_normalization_does_not_rewrite_legitimate_text(self):
        for original in (
            "La herramienta ﬁnal cuesta ½ del presupuesto; versión ①.",
            "Importes 10.50, 12.30, 15.40 y 20.00.",
            "El código es 123e4567-e89b-12d3-a456-426614174000.",
            "Qué padre que el equipo coopera y escucha.",
        ):
            with self.subTest(original=original):
                self.assertEqual(sanitize_text(original), original)
        self.assertEqual(
            sanitize_text("La herramienta ﬁnal cuesta ½; correo persona＠ejemplo．com."),
            "La herramienta ﬁnal cuesta ½; correo [CORREO OCULTO].",
        )

    def test_unsafe_controls_are_rejected_before_persistence_and_ai(self):
        from app.api.v1.endpoints import feedback
        from app.db.database import get_db

        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router)
        db = MagicMock()
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client, patch.object(feedback, "analyze_sentiment_with_ai") as ai:
                for control in ("\x01", "\x08", "\x0b", "\x0c", "\x1f", "\x7f", "\x85"):
                    with self.subTest(control=repr(control)):
                        original = f"Mi telefono es 662{control}123{control}4567."
                        with self.assertRaisesRegex(SanitizationAmbiguityError, "control"):
                            sanitize_text(original)
                        feedback.limiter.reset()
                        response = client.post("/analyze-feedback", json={"text_content": original})
                        self.assertEqual(response.status_code, 422, response.text)
                        self.assertIn("control", response.json()["detail"])
                ai.assert_not_called()
                db.add.assert_not_called()
                db.commit.assert_not_called()
        finally:
            feedback.limiter.reset()

    def test_email_spaces_around_first_dot_and_following_sentence(self):
        for email in ("persona@ejemplo. com", "persona@ejemplo .com", "persona @ ejemplo . com",
                      "persona\u00a0@\u00a0ejemplo.\u202fcom", "persona@ejemplo.com.mx"):
            with self.subTest(email=email):
                expected = "Mi correo es [CORREO OCULTO]. Pedido 12345678."
                self.assertEqual(sanitize_text(f"Mi correo es {email}. Pedido 12345678."), expected)
                self.assertEqual(sanitize_text(expected), expected)

    def test_null_character_is_rejected_by_schema_and_sanitizer(self):
        from app.schemas.feedback import FeedbackCreate

        for original in ("Comentario con \x00 nulo.", "\x00Comentario de prueba."):
            with self.subTest(original=repr(original)):
                with self.assertRaisesRegex(ValueError, "carácter nulo"):
                    FeedbackCreate(text_content=original)
                with self.assertRaisesRegex(SanitizationAmbiguityError, "carácter nulo"):
                    sanitize_text(original)

    def test_email_does_not_consume_the_next_sentence(self):
        self.assertEqual(sanitize_text("Mi correo es persona@ejemplo.com. Pedido 12345678."),
                         "Mi correo es [CORREO OCULTO]. Pedido 12345678.")

    def test_rfc_does_not_consume_following_words_or_spaces(self):
        for suffix in (" y necesito ayuda.", " con datos.", " por favor.",
                       " CON DATOS.", " POR FAVOR.", " FUE RECHAZADO."):
            with self.subTest(suffix=suffix):
                self.assertEqual(sanitize_text("Mi RFC es ABCD123456" + suffix),
                                 "Mi RFC es [RFC OCULTO]" + suffix)

    def test_rfc_formats(self):
        for identifier in ("ABCD123456XYZ", "ABC123456XYZ", "abcd123456xyz"):
            with self.subTest(identifier=identifier):
                self.assertEqual(sanitize_text(f"Mi RFC es {identifier} y necesito ayuda."),
                                 "Mi RFC es [RFC OCULTO] y necesito ayuda.")

    def test_ambiguous_rfc_is_rejected_instead_of_deleting_words(self):
        for identifier in ("ABCD 123456 PAN GRATIS", "ABCD 123456 XYZ", "ABCD123456 XYZ", "ABCD123456 PAN GRATIS"):
            with self.subTest(identifier=identifier), self.assertRaises(SanitizationAmbiguityError):
                sanitize_text("Mi RFC es " + identifier)

    def test_names_without_titles_and_across_redacted_regions(self):
        for original, expected in (
            ("Me llamo ana lopez y necesito ayuda.", "Me llamo [NOMBRE OCULTO] y necesito ayuda."),
            ("Ana [CORREO OCULTO] López me humilla.", "[NOMBRE OCULTO] [CORREO OCULTO] [NOMBRE OCULTO] me humilla."),
            ("La persona Ana React López me humilla.", "La persona [NOMBRE OCULTO] React [NOMBRE OCULTO] me humilla."),
            ("Mi jefa Ana\nLópez me humilla.", "Mi jefa [NOMBRE OCULTO] me humilla."),
            ("Mi compañera Azure me humilla.", "Mi compañera [NOMBRE OCULTO] me humilla."),
        ):
            with self.subTest(original=original):
                self.assertEqual(sanitize_text(original), expected)
                self.assertEqual(sanitize_text(expected), expected)

    def test_long_folios_are_redacted_without_calling_them_phones(self):
        self.assertEqual(sanitize_text("Pedido 1234567890 entregado."), "Pedido [NUMERO OCULTO] entregado.")
        self.assertEqual(sanitize_text("Pedido 1234567890; teléfono 6621234567."),
                         "Pedido [NUMERO OCULTO]; teléfono [TELEFONO OCULTO].")

    def test_obfuscated_email(self):
        self.assertEqual(sanitize_text("Escribir a persona[arroba]ejemplo[punto]com."),
                         "Escribir a [CORREO OCULTO].")

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
        for text in ("", "Reunión el 12/10/2026 a las 10:30.", "Pedido 12345678 el 12/10/2026.",
                     "Reunión el 2026-11-12 a las 10:30.", "Pedido 12345678\nrevisado a las 10:30."):
            with self.subTest(text=text):
                self.assertEqual(sanitize_text(text), text)

    def test_buzon_rejects_null_before_persistence_and_ai(self):
        from app.api.v1.endpoints import feedback
        from app.db.database import get_db

        db = MagicMock()
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router)
        app.dependency_overrides[get_db] = lambda: db
        feedback.limiter.reset()
        try:
            with TestClient(app) as client, patch.object(feedback, "analyze_sentiment_with_ai") as ai:
                response = client.post("/analyze-feedback", json={"text_content": "Comentario con \x00 nulo."})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("carácter nulo", response.text)
                ai.assert_not_called()
                db.add.assert_not_called()
                db.commit.assert_not_called()
        finally:
            feedback.limiter.reset()

    def test_buzon_new_pii_formats_are_sanitized_before_persistence_and_ai(self):
        from app.api.v1.endpoints import feedback
        from app.db.database import get_db
        from app.db.models import FeedbackEntry

        cases = (
            ("Mi telefono es 662\u200b123\u200b4567.", "Mi telefono es [TELEFONO OCULTO]."),
            ("Mi correo es persona\u200b@ejemplo.com.", "Mi correo es [CORREO OCULTO]."),
            ("El teléfono es 55 12 34 56 78.", "El teléfono es [TELEFONO OCULTO]."),
            ("Me contactan al 662\n123\n4567.", "Me contactan al [TELEFONO OCULTO]."),
            ("Mi correo es persona@ejemplo. com.", "Mi correo es [CORREO OCULTO]."),
            ("Mi correo es persona@ejemplo .com.", "Mi correo es [CORREO OCULTO]."),
            ("Mi telefono es 662\u2011123\u20114567.", "Mi telefono es [TELEFONO OCULTO]."),
            ("Mi telefono es 662/123/4567.", "Mi telefono es [TELEFONO OCULTO]."),
            ("Mi correo es persona＠ejemplo．com.", "Mi correo es [CORREO OCULTO]."),
            ("Mi telefono es 662[TELEFONO OCULTO]123[TELEFONO OCULTO]4567.",
             "Mi telefono es [TELEFONO OCULTO]."),
        )
        db = MagicMock()
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router)
        app.dependency_overrides[get_db] = lambda: db
        result = {"polarity_score": 0.0, "sentiment_label": "Neutral", "key_phrases": [],
                  "metadata_ai": {"risk_burnout": False, "is_simulation": False}}
        try:
            with TestClient(app) as client:
                for original, expected in cases:
                    with self.subTest(original=original):
                        feedback.limiter.reset()
                        db.reset_mock()
                        with patch.object(feedback, "analyze_sentiment_with_ai", return_value=result) as ai:
                            response = client.post("/analyze-feedback", json={"text_content": original})
                            self.assertEqual(response.status_code, 200, response.text)
                            ai.assert_called_once_with(expected)
                        entries = [c.args[0].content_text for c in db.add.call_args_list
                                   if isinstance(c.args[0], FeedbackEntry)]
                        self.assertEqual(entries, [expected])
        finally:
            feedback.limiter.reset()

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

    def test_buzon_rejects_ambiguous_pii_before_persistence_and_ai(self):
        from app.api.v1.endpoints import feedback
        from app.db.database import get_db

        db = MagicMock()
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router)
        app.dependency_overrides[get_db] = lambda: db
        feedback.limiter.reset()
        try:
            with TestClient(app) as client, patch.object(feedback, "analyze_sentiment_with_ai") as ai:
                response = client.post("/analyze-feedback", json={"text_content": "Mi RFC es ABCD 123456 XYZ."})
                self.assertEqual(response.status_code, 422)
                self.assertIn("Retira", response.json()["detail"])
                ai.assert_not_called()
                db.add.assert_not_called()
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

    def test_csv_new_formats_are_sanitized_and_controls_fail_without_ai(self):
        import uuid
        from app.api.v1.endpoints import feedback
        from app.db.models import CSVImport, FeedbackEntry

        db, job = MagicMock(), CSVImport(id=uuid.uuid4(), filename="synthetic.csv", status="QUEUED")
        db.query.return_value.filter.return_value.first.return_value = job
        db.query.return_value.all.return_value = []
        result = {"polarity_score": 0.0, "sentiment_label": "Neutral", "key_phrases": [],
                  "metadata_ai": {"risk_burnout": False, "is_simulation": False}}
        with patch.object(feedback, "SessionLocal", return_value=db), \
             patch.object(feedback, "analyze_sentiment_with_ai", return_value=result) as ai:
            feedback.process_csv_background(
                "text_content\nMi telefono es 662\u2011123\u20114567.\n"
                "Mi correo es persona＠ejemplo．com.\n"
                "Mi telefono es 662[TELEFONO OCULTO]123[TELEFONO OCULTO]4567.\n"
                "Mi telefono es 662\x01123\x014567.\n", job.id,
            )
        expected = ["Mi telefono es [TELEFONO OCULTO].", "Mi correo es [CORREO OCULTO].",
                    "Mi telefono es [TELEFONO OCULTO]."]
        self.assertEqual([call.args[0] for call in ai.call_args_list], expected)
        self.assertEqual([call.args[0].content_text for call in db.add.call_args_list
                          if isinstance(call.args[0], FeedbackEntry)], expected)
        self.assertEqual((job.total_rows, job.processed_rows, job.failed_rows), (4, 3, 1))
        self.assertEqual(job.status, "COMPLETED_WITH_WARNINGS")


if __name__ == "__main__":
    unittest.main()
