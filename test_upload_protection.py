"""Pruebas de protección de las cargas."""
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.core.upload_protection import CSVUploadProtectionMiddleware, CSV_UPLOAD_PATH


class UploadProtectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.endpoint_called = False

        @self.app.post(CSV_UPLOAD_PATH)
        async def upload(file: UploadFile = File(...)):
            self.endpoint_called = True
            return {"content": (await file.read()).decode()}

        self.middleware = CSVUploadProtectionMiddleware(self.app, max_request_bytes=256)
        self.body = (
            b"--qa\r\nContent-Disposition: form-data; name=\"file\"; filename=\"qa.csv\"\r\n"
            b"Content-Type: text/csv\r\n\r\ntext_content\nComentario valido\n\r\n--qa--\r\n"
        )

    async def request(self, chunks, *, token="valid-token", content_length=None, path=CSV_UPLOAD_PATH):
        headers = [(b"content-type", b"multipart/form-data; boundary=qa")]
        if token is not None:
            headers.append((b"authorization", ("Bearer " + token).encode()))
        if content_length is not None:
            headers.append((b"content-length", str(content_length).encode()))
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": headers, "client": ("127.0.0.1", 123),
            "server": ("testserver", 80), "root_path": "",
        }
        events = [
            {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
            for i, chunk in enumerate(chunks)
        ]
        self.receive_count = 0

        async def receive():
            self.receive_count += 1
            return events.pop(0) if events else {"type": "http.disconnect"}

        sent = []

        async def send(message):
            sent.append(message)

        await self.middleware(scope, receive, send)
        status = next(message["status"] for message in sent if message["type"] == "http.response.start")
        raw_body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
        return status, json.loads(raw_body) if raw_body else None

    async def test_missing_auth_does_not_read_or_spool_upload(self):
        with patch("starlette.formparsers.SpooledTemporaryFile") as spool:
            status, _ = await self.request([b"x" * 1000], token=None)
        self.assertEqual(status, 401)
        self.assertEqual(self.receive_count, 0)
        self.assertFalse(self.endpoint_called)
        spool.assert_not_called()

    async def test_invalid_token_and_forbidden_role_rejected_before_body(self):
        for status_code in (401, 403):
            with self.subTest(status=status_code), patch(
                "app.core.upload_protection.verify_csv_upload_access",
                side_effect=HTTPException(status_code, "Acceso denegado"),
            ):
                status, _ = await self.request([self.body])
                self.assertEqual(status, status_code)
                self.assertEqual(self.receive_count, 0)
                self.assertFalse(self.endpoint_called)

    async def test_declared_large_body_rejected_before_receive_or_parser(self):
        with patch("app.core.upload_protection.verify_csv_upload_access"), \
             patch("starlette.formparsers.SpooledTemporaryFile") as spool:
            status, _ = await self.request([b"x" * 1000], content_length=1000)
        self.assertEqual(status, 413)
        self.assertEqual(self.receive_count, 0)
        spool.assert_not_called()

    async def test_streaming_body_is_bounded_even_with_false_content_length(self):
        for content_length in (None, 1):
            with self.subTest(length=content_length), \
                 patch("app.core.upload_protection.verify_csv_upload_access"), \
                 patch("starlette.formparsers.SpooledTemporaryFile") as spool:
                status, _ = await self.request([b"x" * 128] * 4, content_length=content_length)
                self.assertEqual(status, 413)
                self.assertEqual(self.receive_count, 3)
                spool.assert_not_called()
        self.assertFalse(self.endpoint_called)

    async def test_valid_multipart_is_replayed_to_parser_once(self):
        with patch("app.core.upload_protection.verify_csv_upload_access") as authorize, \
             patch("starlette.formparsers.SpooledTemporaryFile", wraps=tempfile.SpooledTemporaryFile) as spool:
            status, body = await self.request([self.body[:80], self.body[80:]])
        self.assertEqual(status, 200)
        self.assertEqual(body["content"], "text_content\nComentario valido\n")
        self.assertTrue(self.endpoint_called)
        authorize.assert_called_once_with("valid-token")
        spool.assert_called_once()

    async def test_other_routes_are_not_intercepted(self):
        @self.app.post("/other")
        async def other():
            return {"ok": True}

        with patch("app.core.upload_protection.verify_csv_upload_access") as authorize:
            status, body = await self.request([b""], token=None, path="/other")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        authorize.assert_not_called()

    def test_preflight_authorization_uses_database_role_and_closes_session(self):
        from app.core.upload_protection import verify_csv_upload_access

        session = MagicMock()
        with patch("app.core.upload_protection.SessionLocal") as factory, \
             patch("app.core.upload_protection.verify_token", return_value={"email": "qa@example.test", "role": "executive"}):
            factory.return_value.__enter__.return_value = session
            with self.assertRaises(HTTPException) as error:
                verify_csv_upload_access("signed-token")
            self.assertEqual(error.exception.status_code, 403)
            factory.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
