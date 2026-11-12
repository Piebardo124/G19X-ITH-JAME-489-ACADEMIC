"""Regresiones de entradas adversas: sin PostgreSQL, Azure ni SMTP."""
import unittest
from unittest.mock import MagicMock, patch

import jwt
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1.endpoints import alerts, auth, feedback
from app.core.security import SECRET_KEY, verify_token
from app.db.database import get_db
from app import create_admin_cli


class APIHardeningTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(auth.router, prefix="/auth")
        app.include_router(alerts.router, prefix="/alerts")
        app.include_router(feedback.router, prefix="/nlp")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[verify_token] = lambda: {"role": "admin", "email": "qa@example.test"}
        self.client = TestClient(app)
        feedback.limiter.reset()

    def tearDown(self):
        self.client.close()
        feedback.limiter.reset()

    def test_nul_password_is_rejected_before_database_lookup(self):
        response = self.client.post("/auth/login", data={"username": "qa@example.test", "password": "bad\x00password"})
        self.assertEqual(response.status_code, 401)
        self.db.query.assert_not_called()

    def test_extreme_dates_and_page_return_controlled_errors(self):
        for path, expected in (
            ("/alerts/?date_to=9999-12-31", 400),
            ("/alerts/?page=1000000000000000000000000", 422),
            ("/nlp/stats?department_id=1&start_date=9999-12-01&end_date=9999-12-31", 400),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, expected)

    def test_bad_csv_headers_do_not_create_imports(self):
        for content in (b"text_content,text_content\none,two\n", b"text_content" + b"x" * 140000 + b"\n"):
            feedback.limiter.reset()
            response = self.client.post("/nlp/upload-csv", files={"file": ("bad.csv", content, "text/csv")})
            self.assertEqual(response.status_code, 400, response.text)
        self.db.add.assert_not_called()

    def test_bad_csv_structure_is_rejected_before_creating_or_processing_an_import(self):
        invalid_files = (
            b'text_content\nComentario valido\n"sin cierre\n',
            b'text_content\nComentario valido\n"texto"sobrante\n',
            b'text_content,department_id\nComentario valido,1\nFalta departamento\n',
            b'text_content\n' + b'Comentario valido\n' * 1000 + b'"sin cierre\n',
        )
        with patch.object(feedback, "process_csv_background") as process, \
             patch.object(feedback, "analyze_sentiment_with_ai") as analyze:
            for content in invalid_files:
                with self.subTest(size=len(content)):
                    feedback.limiter.reset()
                    response = self.client.post(
                        "/nlp/upload-csv", files={"file": ("bad.csv", content, "text/csv")}
                    )
                    self.assertEqual(response.status_code, 400, response.text)
            self.db.add.assert_not_called()
            self.db.commit.assert_not_called()
            process.assert_not_called()
            analyze.assert_not_called()

    def test_nul_csv_filename_is_rejected_before_database_write(self):
        body = (
            b'--csv-test\r\nContent-Disposition: form-data; name="file"; filename="bad\x00.csv"\r\n'
            b'Content-Type: text/csv\r\n\r\ntext_content\nComentario correcto\n\r\n--csv-test--\r\n'
        )
        response = self.client.post(
            "/nlp/upload-csv", content=body, headers={"Content-Type": "multipart/form-data; boundary=csv-test"}
        )
        self.assertEqual(response.status_code, 400, response.text)
        self.db.add.assert_not_called()

    def test_csv_rejects_numeric_text_and_extra_cells(self):
        for row in ({"text_content": "1234567"}, {"text_content": "Comentario válido", None: ["otra celda"]}):
            with self.subTest(row=row), self.assertRaises(feedback.CSVRowValidationError):
                feedback._validate_csv_row(row, {1})

    def test_signed_jwt_without_exp_is_rejected(self):
        token = jwt.encode({"sub": "qa@example.test"}, SECRET_KEY, algorithm="HS256")
        with self.assertRaises(HTTPException) as error:
            verify_token(token=token, db=self.db)
        self.assertEqual(error.exception.status_code, 401)
        self.db.query.assert_not_called()

    def test_admin_password_limits_and_canonical_identity(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(create_admin_cli, "SessionLocal", return_value=self.db), \
             patch("builtins.input", return_value=" QA-ADMIN@EXAMPLE.TEST "):
            for password in ("A" * 73, "A" * 12 + "\x00"):
                with patch("getpass.getpass", return_value=password):
                    self.assertFalse(create_admin_cli.init_admin())
            self.db.add.assert_not_called()
            with patch("getpass.getpass", return_value="QaTemporal-2026-Only!"):
                self.assertTrue(create_admin_cli.init_admin())
            self.assertEqual(self.db.add.call_args.args[0].email, "qa-admin@example.test")


if __name__ == "__main__":
    unittest.main()
