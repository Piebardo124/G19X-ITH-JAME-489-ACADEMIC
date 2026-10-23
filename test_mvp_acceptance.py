import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.api.v1.endpoints import feedback
from app.core.security import require_roles


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *_args, **_kwargs):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def group_by(self, *_args, **_kwargs):
        return self

    def having(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows


class _StatsDB:
    def __init__(self, rows, phrases=()):
        self.rows = rows
        self.phrases = list(phrases)
        self.query_count = 0

    def query(self, *_entities):
        self.query_count += 1
        return _Query(self.rows if self.query_count == 1 else self.phrases)


class _ForbiddenDB:
    def query(self, *_entities):
        raise AssertionError("El endpoint debe rechazar el rol antes de consultar la base")


class DashboardStatsAPITests(unittest.TestCase):
    def test_stats_returns_aggregates_after_privacy_minimum(self):
        created_at = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
        analyses = [
            SimpleNamespace(
                polarity_score=0.8,
                sentiment_label="Positivo",
                metadata_ai={"emotions": ["Satisfacción/Conformidad"], "organizational_axes": ["Ambiente laboral"]},
            )
            for _ in range(5)
        ]
        rows = [(analysis, 1, "Recursos Humanos", created_at) for analysis in analyses]
        db = _StatsDB(rows, [("colaboración", 5)])

        body = feedback.get_dashboard_stats(
            department_id=1,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            db=db,
            current_user={"role": "hr"},
        )
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["total_responses"], 5)
        self.assertEqual(body["average_polarity"], 0.8)
        self.assertEqual(body["distribution"], {"Positivo": 5})
        self.assertEqual(body["key_phrases"], [{"name": "colaboración", "count": 5}])

    def test_stats_rejects_partial_month(self):
        with self.assertRaises(HTTPException) as error:
            feedback.get_dashboard_stats(
                department_id=1,
                start_date=date(2026, 10, 2),
                end_date=date(2026, 10, 31),
                db=_ForbiddenDB(),
                current_user={"role": "hr"},
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_stats_rejects_unprivileged_role(self):
        with self.assertRaises(HTTPException) as error:
            require_roles("admin", "hr", "executive", "analyst")(
                current_user={"role": "employee"}
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_executive_is_allowed_to_read_dashboard_stats(self):
        self.assertEqual(
            require_roles("admin", "hr", "executive", "analyst")(
                current_user={"role": "executive"}
            ),
            {"role": "executive"},
        )


if __name__ == "__main__":
    unittest.main()
