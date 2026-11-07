import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers import geocoder  # noqa: E402


class Resp:
    def __init__(self, status, body=None): self.status, self.body = status, body
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def json(self, content_type=None): return self.body


class Sess:
    def __init__(self, answers): self.answers, self.calls = list(answers), 0
    def get(self, *a, **k):
        self.calls += 1
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception): raise a
        return Resp(*a)


class LoadCache(unittest.TestCase):
    def load(self, answers):
        async def base(*a, **k): return "x"
        d = Path(tempfile.mkdtemp()); s = Sess(answers)
        with mock.patch.object(geocoder, "_DATA_DIR", d), mock.patch.object(geocoder, "resolve_pages_base", base), mock.patch.object(geocoder, "_CACHE_RETRY_SLEEP", 0):
            return asyncio.run(geocoder._load_cache("SE", s)), s.calls

    def test_clean_404_means_no_cache_yet(self):
        self.assertEqual(self.load([(404,)]), ({}, 1))

    def test_unreadable_is_none_not_empty(self):
        self.assertEqual(self.load([OSError("net")]), (None, 3))
        self.assertEqual(self.load([(503,)]), (None, 3))

    def test_retry_then_data(self):
        self.assertEqual(self.load([(500,), (200, {"a": {"lat": 1, "lon": 2}})])[0], {"a": {"lat": 1, "lon": 2}})


class ApplyGeocoding(unittest.TestCase):
    def test_unreadable_cache_neither_geocodes_nor_overwrites(self):
        async def none(*a, **k): return None
        saved = []
        stations = [{"id": "a", "lat": None, "lon": None}]
        with mock.patch.object(geocoder, "_load_cache", none), mock.patch.object(geocoder, "_save_cache", lambda *a: saved.append(a)):
            asyncio.run(geocoder.apply_geocoding(stations, "SE", None, key_fn=lambda s: s["id"], query_fn=lambda s: ("c", "s", "p")))
        self.assertEqual(saved, []); self.assertIsNone(stations[0]["lat"])


if __name__ == "__main__":
    unittest.main()
