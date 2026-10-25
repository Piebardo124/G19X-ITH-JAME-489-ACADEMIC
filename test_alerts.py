import unittest
from datetime import date

from fastapi import HTTPException
from fastapi import Response

from app.api.v1.endpoints.alerts import list_alerts
from app.core.security import require_roles


class FakeQuery:
    def __init__(self):
        self.filters = []
        self.joined = False
        self.offset_value = None
        self.limit_value = None

    def filter(self, *expressions):
        self.filters.extend(expressions)
        return self

    def join(self, *_entities):
        self.joined = True
        return self

    def order_by(self, *_expressions):
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return []


class FakeDB:
    def __init__(self):
        self.query_instance = FakeQuery()

    def query(self, *_entities):
        return self.query_instance


class AlertEndpointTests(unittest.TestCase):
    def test_list_alerts_applies_date_and_other_filters(self):
        db = FakeDB()

        result = list_alerts(
            response=Response(),
            status_filter="OPEN",
            risk_level="ALTO",
            department_id=0,
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
            page=1,
            page_size=50,
            db=db,
            current_user={"role": "hr"},
        )

        self.assertEqual(result, [])
        self.assertTrue(db.query_instance.joined)
        self.assertEqual(len(db.query_instance.filters), 5)
        self.assertEqual(db.query_instance.offset_value, 0)
        self.assertEqual(db.query_instance.limit_value, 51)

    def test_list_alerts_rejects_reversed_date_range(self):
        with self.assertRaises(HTTPException) as error:
            list_alerts(
                response=Response(),
                date_from=date(2026, 10, 2),
                date_to=date(2026, 10, 1),
                db=FakeDB(),
                current_user={"role": "hr"},
            )

        self.assertEqual(error.exception.status_code, 400)

    def test_admin_can_read_alert_inbox(self):
        self.assertEqual(
            require_roles("admin", "hr", "analyst")(current_user={"role": "admin"}),
            {"role": "admin"},
        )

    def test_executive_cannot_read_alert_inbox(self):
        with self.assertRaises(HTTPException) as error:
            require_roles("admin", "hr", "analyst")(current_user={"role": "executive"})

        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
