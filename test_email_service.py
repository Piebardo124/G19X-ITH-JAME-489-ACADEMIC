import unittest
import ssl
from unittest.mock import patch

from app.services.email_service import send_alert_email


class _FakeSMTP:
    def __init__(self):
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self, *, context):
        self.context = context

    def login(self, *_args):
        pass

    def send_message(self, message):
        self.message = message
        # Comprueba el mensaje con acentos.
        message.as_bytes()


class EmailServiceTests(unittest.TestCase):
    def test_alert_email_serializes_spanish_accents_as_utf8(self):
        smtp = _FakeSMTP()
        with (
            patch.dict("os.environ", {
                "SMTP_EMAIL": "test@example.com",
                "SMTP_PASSWORD": "test-password",
                "SMTP_ALERT_RECIPIENT": "rh@example.com",
            }),
            patch("app.services.email_service.smtplib.SMTP", return_value=smtp),
        ):
            sent = send_alert_email(7, "Estrés y carga de trabajo elevada")

        self.assertTrue(sent)
        self.assertEqual(smtp.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(smtp.context.check_hostname)
        self.assertIsNotNone(smtp.message)
        body = smtp.message.get_payload()[0]
        self.assertEqual(body.get_content_charset(), "utf-8")
        self.assertIn("Estrés", body.get_payload(decode=True).decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
