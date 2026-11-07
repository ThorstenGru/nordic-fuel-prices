import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers.romania import RomaniaScraper  # noqa: E402


def station(brand, seen_days_ago=None):
    s = {"id": "ro_" + brand, "country": "RO", "name": brand, "brand": brand, "lat": 46.0, "lon": 24.0, "_prices": {"DIESEL": (7.5, "L")}}
    if seen_days_ago is not None:
        s["seen_at"] = (datetime.now(timezone.utc) - timedelta(days=seen_days_ago)).isoformat()
    return s


class CarryOver(unittest.TestCase):
    def run_scraper(self, previous, fresh=None):
        sc = RomaniaScraper(None)

        async def load(): return previous

        async def county(*a, **k): return fresh or []
        sc._load_previous = load; sc._fetch_county = county
        real = asyncio.sleep
        with mock.patch("asyncio.sleep", new=lambda *_: real(0)):
            return asyncio.run(sc.fetch_stations())

    def test_station_not_seen_for_days_is_dropped_recent_one_is_kept_with_its_time(self):
        out = self.run_scraper({"old": station("Old", 5), "new": station("New", 0.5), "legacy": station("Legacy")})
        names = sorted(s["name"] for s in out)
        self.assertEqual(names, ["Legacy", "New"])                      # no seen_at yet: a full grace period, then it must be seen
        new = next(s for s in out if s["name"] == "New")
        self.assertIsNotNone(new["prices"][0]["updated_at"])            # price time = when we last saw it, so the app can judge freshness

    def test_everything_expired_is_an_error_not_an_empty_country(self):
        with self.assertRaises(RuntimeError):
            self.run_scraper({"old": station("Old", 9)})


if __name__ == "__main__":
    unittest.main()
