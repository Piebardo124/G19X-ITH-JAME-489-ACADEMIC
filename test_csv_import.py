import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.api.v1.endpoints import feedback
from app.db.models import CSVImport, Department


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
        self.closed = False

    def query(self, model):
        return _Query(model, self.job, self.departments)

    def add(self, item):
        self.pending.append(item)

    def commit(self):
        self.committed.extend(self.pending)
        self.pending.clear()

    def rollback(self):
        self.pending.clear()

    def flush(self):
        pass

    def close(self):
        self.closed = True


class CSVImportTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
