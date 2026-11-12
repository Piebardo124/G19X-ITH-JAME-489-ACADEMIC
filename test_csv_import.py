import asyncio
import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI

from app.api.v1.endpoints import feedback
from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import CSVImport, Department, FeedbackEntry


class _Query:
    def __init__(self, model, job, departments):
        self.model = model
        self.job = job
        self.departments = departments

    def filter(self, *_expressions):
        return self

    def first(self):
        return self.job

    def all(self):
        return self.departments


class _Session:
    def __init__(self, job, departments):
        self.job = job
        self.departments = departments
        self.pending = []
        self.committed = []
        self.progress_snapshots = []
        self.closed = False

    def query(self, model):
        return _Query(model, self.job, self.departments)

    def add(self, item):
        self.pending.append(item)

    def commit(self):
        self.committed.extend(self.pending)
        self.pending.clear()
        self.progress_snapshots.append({
            key: getattr(self.job, key)
            for key in ("status", "total_rows", "processed_rows", "skipped_rows", "failed_rows", "error_summary")
        })

    def rollback(self):
        self.pending.clear()

    def flush(self):
        pass

    def close(self):
        self.closed = True


class CSVImportTests(unittest.TestCase):
    def setUp(self):
        self.job = SimpleNamespace(
            status="QUEUED", total_rows=0, processed_rows=0,
            skipped_rows=0, failed_rows=0, error_summary=None, finished_at=None,
        )
        self.db = _Session(self.job, [Department(id=1, name="Recursos Humanos")])
        self.ai_result = {
            "polarity_score": 0.0, "sentiment_label": "Neutral", "key_phrases": [],
            "metadata_ai": {"risk_burnout": False},
        }

    def run_import(self, content, db=None, ai_side_effect=None):
        with patch.object(feedback, "SessionLocal", return_value=db or self.db), \
             patch.object(feedback, "sanitize_text", side_effect=lambda value: value), \
             patch.object(feedback, "analyze_sentiment_with_ai", return_value=self.ai_result, side_effect=ai_side_effect):
            feedback.process_csv_background(content, uuid.uuid4())

    def test_validation_reports_missing_department_and_accepts_anonymous_row(self):
        parsed = feedback._validate_csv_row(
            {"text_content": "Comentario válido", "is_anonymous": "true", "department_id": "1"},
            {1, 2, 3, 4},
        )
        self.assertEqual(parsed, ("Comentario válido", 1))

        with self.assertRaisesRegex(feedback.CSVRowValidationError, "department_id 5 no existe"):
            feedback._validate_csv_row(
                {"text_content": "Comentario válido", "is_anonymous": "true", "department_id": "5"},
                {1, 2, 3, 4},
            )

    def test_structure_accepts_quoted_commas_multiline_text_and_blank_lines(self):
        rows, truncated = feedback._validate_csv_structure(
            'text_content,department_id\r\n\r\n"La carga,\r\nha mejorado",1\r\n'
        )
        self.assertEqual(rows, [{"text_content": "La carga,\r\nha mejorado", "department_id": "1"}])
        self.assertFalse(truncated)

    def test_ai_unavailable_is_counted_as_saved_not_failed(self):
        job = SimpleNamespace(
            status="QUEUED", total_rows=0, processed_rows=0,
            skipped_rows=0, failed_rows=0, error_summary=None, finished_at=None,
        )
        db = _Session(job, [Department(id=1, name="Recursos Humanos")])
        import_id = uuid.uuid4()
        ai_result = {
            "polarity_score": None,
            "sentiment_label": "NO_DISPONIBLE",
            "key_phrases": [],
            "metadata_ai": {
                "risk_burnout": False,
                "is_simulation": True,
            },
        }
        csv_content = (
            "text_content,is_anonymous,department_id\n"
            "Comentario correcto,true,1\n"
            "Otro comentario,true,5\n"
        )

        with patch.object(feedback, "SessionLocal", return_value=db), \
             patch.object(feedback, "sanitize_text", side_effect=lambda value: value), \
             patch.object(feedback, "analyze_sentiment_with_ai", return_value=ai_result):
            feedback.process_csv_background(csv_content, import_id)

        self.assertEqual(job.total_rows, 2)
        self.assertEqual(job.processed_rows, 1)
        self.assertEqual(job.failed_rows, 1)
        self.assertEqual(job.status, "COMPLETED_WITH_WARNINGS")
        self.assertIn("comentario guardado; análisis de IA pendiente", job.error_summary)
        self.assertIn("department_id 5 no existe", job.error_summary)
        self.assertTrue(db.closed)

    def test_malformed_later_row_never_imports_an_earlier_valid_row(self):
        for content in (
            'text_content\nComentario valido\n"sin cierre\n',
            'text_content\nComentario valido\n"texto"sobrante\n',
            'text_content\nComentario valido\notro,celda extra\n',
        ):
            with self.subTest(content=content), \
                 patch.object(feedback, "SessionLocal", return_value=self.db), \
                 patch.object(feedback, "analyze_sentiment_with_ai") as analyze:
                feedback.process_csv_background(content, uuid.uuid4())
            self.assertEqual(self.job.status, "FAILED")
            self.assertEqual(self.job.processed_rows, 0)
            self.assertFalse(any(isinstance(item, FeedbackEntry) for item in self.db.committed))
            analyze.assert_not_called()

    def test_progress_of_saved_skipped_and_failed_rows_is_committed_before_next_call(self):
        observed = []
        def analyze(_text):
            observed.append(dict(self.db.progress_snapshots[-1]))
            return self.ai_result
        self.run_import(
            "text_content,department_id\n"
            "abc,1\n"
            "Comentario correcto,1\n"
            "Departamento inexistente,9\n"
            "Otro comentario correcto,1\n",
            ai_side_effect=analyze,
        )
        self.assertEqual(len(observed), 2)
        self.assertEqual((observed[0]["total_rows"], observed[0]["skipped_rows"]), (1, 1))
        self.assertEqual(
            tuple(observed[1][key] for key in ("total_rows", "processed_rows", "skipped_rows", "failed_rows")),
            (3, 1, 1, 1),
        )
        self.assertEqual((self.job.total_rows, self.job.processed_rows, self.job.failed_rows), (4, 2, 1))

    def test_general_failure_preserves_counts_of_already_committed_rows(self):
        class FinalQueryFailure(_Session):
            failed_once = False
            def query(self, model):
                if model is CSVImport and self.committed and not self.failed_once:
                    self.failed_once = True
                    raise RuntimeError("simulated final query failure")
                return super().query(model)
        db = FinalQueryFailure(self.job, self.db.departments)
        self.run_import("text_content\nComentario valido\n", db=db)
        self.assertEqual(self.job.status, "FAILED")
        self.assertEqual((self.job.total_rows, self.job.processed_rows, self.job.failed_rows), (1, 1, 0))
        self.assertEqual(sum(isinstance(item, FeedbackEntry) for item in db.committed), 1)
        self.assertIn("Error general: RuntimeError", self.job.error_summary)

    def test_failed_row_commit_is_not_reported_as_saved(self):
        class RowCommitFailure(_Session):
            failed_once = False
            def commit(self):
                if any(isinstance(item, FeedbackEntry) for item in self.pending) and not self.failed_once:
                    self.failed_once = True
                    raise RuntimeError("simulated row commit failure")
                super().commit()
        db = RowCommitFailure(self.job, self.db.departments)
        self.run_import("text_content\nComentario valido\n", db=db)
        self.assertEqual(self.job.status, "COMPLETED_WITH_WARNINGS")
        self.assertEqual((self.job.total_rows, self.job.processed_rows, self.job.failed_rows), (1, 0, 1))
        self.assertFalse(any(isinstance(item, FeedbackEntry) for item in db.committed))

    def test_row_limit_preserves_warning_and_counts(self):
        with patch.object(feedback, "MAX_CSV_ROWS", 2):
            self.run_import("text_content\nPrimer comentario\nSegundo comentario\nTercer comentario\n")
        self.assertEqual((self.job.total_rows, self.job.processed_rows), (2, 2))
        self.assertEqual(self.job.status, "COMPLETED_WITH_WARNINGS")
        self.assertIn("limite de 2 filas", self.job.error_summary)


class CSVUploadConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_commit_does_not_block_the_event_loop(self):
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router, prefix="/nlp")
        db = MagicMock()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[verify_token] = lambda: {"role": "admin", "email": "qa@example.test"}
        started = threading.Event()
        finished = threading.Event()
        release = threading.Event()
        def commit():
            started.set()
            release.wait(2)
            finished.set()
        db.commit.side_effect = commit
        db.refresh.side_effect = lambda job: setattr(job, "id", uuid.uuid4())
        feedback.limiter.reset()
        try:
            with patch.object(feedback, "process_csv_background"):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    upload = asyncio.create_task(client.post(
                        "/nlp/upload-csv", files={"file": ("test.csv", b"text_content\nComentario correcto\n", "text/csv")}
                    ))
                    await asyncio.wait_for(asyncio.to_thread(started.wait, 2), timeout=3)
                    event_loop_was_responsive = started.is_set() and not finished.is_set()
                    release.set()
                    response = await upload
            self.assertTrue(event_loop_was_responsive)
            self.assertEqual(response.status_code, 202)
        finally:
            release.set()
            feedback.limiter.reset()


if __name__ == "__main__":
    unittest.main()
