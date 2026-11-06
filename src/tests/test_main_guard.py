import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main  # noqa: E402


class Bad:
    COUNTRY, CURRENCY, SOURCE, CONFIDENCE, REFRESH_MINUTES, GRADE = "XX", "EUR", "t", 1, 1, "C"

    def __init__(self, session):
        self.fetched_at = "2026-10-09T00:00:00+00:00"

    async def fetch_stations(self):
        return [{"id": "a", "country": "DE", "lat": 50, "lon": 10, "prices": ["not a dict"]}]


class RunOneGuard(unittest.TestCase):
    def test_bad_data_fails_one_country_not_the_run(self):
        async def none(*a, **k):
            return None

        async def base(*a, **k):
            return "x"

        with mock.patch.object(main, "fetch_json", none), mock.patch.object(main, "resolve_pages_base", base), \
                mock.patch.object(main, "OUTPUT_DIR", Path(tempfile.mkdtemp())):
            r = asyncio.run(main.run_one(Bad, None, {}))
        self.assertEqual(r["meta"]["status"], "failed")
        self.assertIn("post-processing", r["meta"]["last_error"])


class FxBlock(unittest.TestCase):
    def test_only_published_non_euro_currencies(self):
        fx = {"SEK": 10.99, "PLN": 4.22, "CHF": 0.93, "USD": 1.1}
        b = main.fx_block(fx, "2026-11-05", ["SEK", "EUR", "PLN", "SEK", None, "XXX"])
        self.assertEqual(b, {"rates": {"PLN": 4.22, "SEK": 10.99}, "date": "2026-11-05", "source": "ECB"})

    def test_none_without_rates_or_date(self):
        self.assertIsNone(main.fx_block({}, "2026-11-05", ["SEK"]))
        self.assertIsNone(main.fx_block({"SEK": 10.99}, None, ["SEK"]))


if __name__ == "__main__":
    unittest.main()
