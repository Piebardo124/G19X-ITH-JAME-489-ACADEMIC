"""Pruebas de los límites de solicitudes."""
import os
import runpy
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from limits import parse
from limits.storage import MemoryStorage, RedisStorage
from limits.strategies import FixedWindowRateLimiter


def configured_storage(uri=None):
    # Mantiene cada prueba independiente.
    with patch.dict(os.environ):
        if uri is None:
            os.environ.pop("RATE_LIMIT_STORAGE_URI", None)
        else:
            os.environ["RATE_LIMIT_STORAGE_URI"] = uri
        module = runpy.run_path(str(Path(__file__).resolve().parent / "app/core/rate_limit.py"))
    return module["limiter"]._storage


class RateLimitConfigurationTests(unittest.TestCase):
    def test_default_memory_storage_keeps_a_working_request_limit(self):
        storage = configured_storage()
        self.assertIsInstance(storage, MemoryStorage)
        counter = FixedWindowRateLimiter(storage)
        item = parse("2/minute")
        scope = ("configuration-test", uuid.uuid4().hex)
        try:
            self.assertTrue(counter.hit(item, *scope))
            self.assertTrue(counter.hit(item, *scope))
            self.assertFalse(counter.hit(item, *scope))
        finally:
            storage.clear(item.key_for(*scope))

    def test_redis_url_initializes_with_the_installed_client_without_connecting(self):
        storage = configured_storage("redis://127.0.0.1:6379/9")
        try:
            self.assertIsInstance(storage, RedisStorage)
            settings = storage.storage.connection_pool.connection_kwargs
            self.assertEqual((settings["host"], settings["port"], settings["db"]), ("127.0.0.1", 6379, 9))
        finally:
            storage.storage.close()

    @unittest.skipUnless(os.getenv("TEST_REDIS_URL"), "TEST_REDIS_URL habilita la prueba con un Redis real de pruebas.")
    def test_real_redis_shares_limits_between_independent_configurations(self):
        uri = os.environ["TEST_REDIS_URL"]
        first = configured_storage(uri)
        second = configured_storage(uri)
        item = parse("2/minute")
        scope = ("configuration-test", uuid.uuid4().hex)
        try:
            self.assertTrue(first.check())
            self.assertTrue(second.check())
            self.assertTrue(FixedWindowRateLimiter(first).hit(item, *scope))
            self.assertTrue(FixedWindowRateLimiter(second).hit(item, *scope))
            self.assertFalse(FixedWindowRateLimiter(first).hit(item, *scope))
        finally:
            # Limpia únicamente los datos de esta prueba.
            first.clear(item.key_for(*scope))
            first.storage.close()
            second.storage.close()


if __name__ == "__main__":
    unittest.main()
