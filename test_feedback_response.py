"""Pruebas de las respuestas del buzón."""
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import feedback
from app.db.database import get_db


class FeedbackResponseTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        app = FastAPI()
        app.state.limiter = feedback.limiter
        app.include_router(feedback.router)
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        feedback.limiter.reset()

    def tearDown(self):
        self.client.close()
        feedback.limiter.reset()

    def test_analysis_availability_matches_result(self):
        for label, simulation, available in [
            ('Positivo', False, True),
            ('NO_DISPONIBLE', False, False),
            ('Positivo', True, False),
        ]:
            with self.subTest(label=label, simulation=simulation):
                result = {
                    'polarity_score': 0.8 if available else None,
                    'sentiment_label': label,
                    'metadata_ai': {'risk_burnout': False, 'is_simulation': simulation},
                    'key_phrases': [],
                }
                with patch.object(feedback, 'sanitize_text', return_value='Comentario de prueba'), \
                     patch.object(feedback, 'analyze_sentiment_with_ai', return_value=result):
                    response = self.client.post('/analyze-feedback', json={
                        'text_content': 'Comentario de prueba',
                    })
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body['analysis_available'], available)
                self.assertEqual(body['status'], 'success')
                self.assertEqual('no fue analizado' in body['message'], not available)
                self.assertIn('entry_id', body)
        self.assertEqual(self.db.commit.call_count, 3)


if __name__ == '__main__':
    unittest.main()
