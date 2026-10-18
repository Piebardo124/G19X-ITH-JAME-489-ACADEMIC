import unittest
from datetime import date

from fastapi import HTTPException

from app.api.v1.endpoints.alerts import list_alerts


class FakeQuery:
    def __init__(self):
        self.filters = []
        self.joined = False

    def filter(self, *expressions):
        self.filters.extend(expressions)
        return self

    def join(self, *_entities):
        self.joined = True
        return self

    def order_by(self, *_expressions):
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
            status_filter="OPEN",
            risk_level="ALTO",
            department_id=0,
            date_from=date(2026, 10, 1),
            date_to=date(2026, 10, 31),
            db=db,
            current_user={"role": "hr"},
        )

        self.assertEqual(result, [])
        self.assertTrue(db.query_instance.joined)
        self.assertEqual(len(db.query_instance.filters), 5)

    def test_list_alerts_rejects_reversed_date_range(self):
        with self.assertRaises(HTTPException) as error:
            list_alerts(
                date_from=date(2026, 10, 2),
                date_to=date(2026, 10, 1),
                db=FakeDB(),
                current_user={"role": "hr"},
            )

        self.assertEqual(error.exception.status_code, 400)

    def test_executive_cannot_read_alert_inbox(self):
        class NoQueryDB:
            def query(self, *_entities):
                raise AssertionError("No debe consultar la DB para un rol denegado")

        with self.assertRaises(HTTPException) as error:
            list_alerts(db=NoQueryDB(), current_user={"role": "executive"})

        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
