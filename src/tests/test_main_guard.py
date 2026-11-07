import asyncio
import json
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


def st(i, price=1.8, **kw):
    return {"id": f"s{i}", "country": "DE", "lat": 50 + i * 0.001, "lon": 10, "name": f"n{i}",
            "prices": [{"fuel_type": "95", "price": price, "currency": "EUR", "unit": "L"}], **kw}


def good_scraper(n, price=1.8, error=None):
    class G:
        COUNTRY, CURRENCY, SOURCE, CONFIDENCE, REFRESH_MINUTES, GRADE = "XX", "EUR", "t", 1, 1, "C"

        def __init__(self, session):
            self.fetched_at = "2026-10-09T00:00:00+00:00"

        async def fetch_stations(self):
            if error:
                raise RuntimeError(error)
            return [st(i, price) for i in range(n)]
    return G


def run_one_with(scraper, old=None, prev_meta=None, allow=()):
    async def fj(*a, **k):
        return old

    async def base(*a, **k):
        return "x"

    out = Path(tempfile.mkdtemp())
    with mock.patch.object(main, "fetch_json", fj), mock.patch.object(main, "resolve_pages_base", base),             mock.patch.object(main, "OUTPUT_DIR", out), mock.patch.object(main, "ALLOW_SHRINK", set(allow)), mock.patch.object(main, "FORCE_REFRESH", True):
        r = asyncio.run(main.run_one(scraper, None, prev_meta or {}))
    return r, json.loads((out / "xx.json").read_text(encoding="utf-8"))


class CleanStations(unittest.TestCase):
    def test_drops_bad_values_and_keeps_good(self):
        far = st(9); far["lat"] = 10.0                              # outside Europe
        future = st(8); future["prices"][0]["updated_at"] = "2099-01-01T00:00:00+00:00"
        out, dropped = main.clean_stations([st(1, 99.0), st(2, 0.05), st(3), st(3), far, future, "junk", {"id": "x", "lat": None, "lon": 1}])
        ids = [s["id"] for s in out]
        self.assertEqual(sorted(ids), ["s1", "s2", "s3", "s8"])
        self.assertEqual([len(s["prices"]) for s in out if s["id"] in ("s1", "s2")], [0, 0])    # EUR band 0.4-4.5: 99 and 0.05 dropped, station kept
        self.assertIsNone(next(s for s in out if s["id"] == "s8")["prices"][0]["updated_at"])  # never publish a timestamp from the future
        self.assertEqual((dropped["price_outlier"], dropped["duplicate_id"], dropped["coords_outside_europe"], dropped["not_a_dict"], dropped["no_coords"]), (2, 1, 1, 1, 1))


class Retention(unittest.TestCase):
    OLD = {"meta": {"currency": "EUR", "station_count": 30, "priced_count": 30, "fetched_at": "2026-10-01T00:00:00+00:00"},
           "stations": [st(i) for i in range(30)]}

    def test_scraper_error_keeps_last_good_as_stale(self):
        r, f = run_one_with(good_scraper(0, error="boom"), old=self.OLD)
        self.assertEqual(f["meta"]["status"], "stale"); self.assertEqual(len(f["stations"]), 30)
        self.assertIn("boom", f["meta"]["last_error"])

    def test_error_without_previous_file_is_failed_and_empty(self):
        r, f = run_one_with(good_scraper(0, error="boom"), old=None)
        self.assertEqual(f["meta"]["status"], "failed"); self.assertEqual(f["stations"], [])

    def test_shrink_below_ratio_is_refused(self):
        pm = {"XX": {"station_count": 100, "priced_count": 100, "status": "ok", "fetched_at": "2026-10-01T00:00:00+00:00"}}
        r, f = run_one_with(good_scraper(10), old=self.OLD, prev_meta=pm)
        self.assertEqual(f["meta"]["status"], "stale"); self.assertEqual(len(f["stations"]), 30)
        self.assertIn("regressed", f["meta"]["last_error"])

    def test_allow_shrink_publishes_the_smaller_file(self):
        pm = {"XX": {"station_count": 100, "priced_count": 100, "status": "ok", "fetched_at": "2026-10-01T00:00:00+00:00"}}
        r, f = run_one_with(good_scraper(10), old=self.OLD, prev_meta=pm, allow=("XX",))
        self.assertEqual(f["meta"]["status"], "ok"); self.assertEqual(len(f["stations"]), 10)


class FetchPrev(unittest.TestCase):
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
            return FetchPrev.Resp(*a)

    def run_fp(self, answers):
        s = self.Sess(answers)
        with mock.patch.object(main, "RETRY_SLEEP", 0):
            return asyncio.run(main.fetch_prev_json(s, "u")), s.calls

    def test_retries_then_succeeds(self):
        (data, clean), calls = self.run_fp([(500,), (200, {"a": 1})])
        self.assertEqual((data, clean, calls), ({"a": 1}, True, 2))

    def test_404_is_clean_and_not_retried(self):
        (data, clean), calls = self.run_fp([(404,)])
        self.assertEqual((data, clean, calls), (None, True, 1))

    def test_unknown_after_three_failures(self):
        (data, clean), calls = self.run_fp([OSError("net")])
        self.assertEqual((data, clean, calls), (None, False, 3))


class RunAllGuards(unittest.TestCase):
    def go(self, meta_answer, statuses):
        async def base(*a, **k):
            return "x"

        async def fp(*a, **k):
            return meta_answer

        async def ro(sc, session, pm):
            st_ = statuses.pop(0)
            return {"cc": f"C{sc}", "meta": {"status": st_, "station_count": 0, "currency": "EUR"}, "health": {}}

        out = Path(tempfile.mkdtemp())
        with mock.patch.object(main, "resolve_pages_base", base), mock.patch.object(main, "fetch_prev_json", fp), mock.patch.object(main, "run_one", ro),                 mock.patch.object(main, "ALL_SCRAPERS", list(range(len(statuses)))), mock.patch.object(main, "OUTPUT_DIR", out):
            try:
                asyncio.run(main.run_all())
            except SystemExit as e:
                return e.code, out
        return 0, out

    def test_unreadable_meta_stops_the_run(self):
        code, out = self.go((None, False), ["ok"])
        self.assertEqual(code, 1); self.assertFalse((out / "meta.json").exists())

    def test_too_many_failed_countries_stop_the_run(self):
        code, out = self.go(({}, True), ["failed"] * 6 + ["ok"])
        self.assertEqual(code, 1); self.assertFalse((out / "meta.json").exists())

    def test_few_failed_countries_still_publish(self):
        code, out = self.go(({}, True), ["failed"] * 2 + ["ok"] * 5)
        self.assertEqual(code, 0); self.assertTrue((out / "meta.json").exists())


class IsoUtc(unittest.TestCase):
    def test_timezones_epoch_and_junk(self):
        from scrapers.base import iso_utc
        try:
            from zoneinfo import ZoneInfo; ZoneInfo("Europe/Lisbon")
        except Exception:
            self.skipTest("no tz database on this machine (CI has one)")
        self.assertEqual(iso_utc("2026-10-01T10:45:01+02:00"), "2026-10-01T08:45:01+00:00")        # offset honoured
        self.assertEqual(iso_utc("2026-10-01 10:45:01", "Europe/Lisbon"), "2026-10-01T09:45:01+00:00")   # naive local time, summer
        self.assertEqual(iso_utc("2026-12-01 10:45:01", "Europe/Stockholm"), "2026-12-01T09:45:01+00:00")  # naive local time, winter
        self.assertEqual(iso_utc("2026-10-01 10:45:01"), "2026-10-01T10:45:01+00:00")                 # no tz given: UTC
        self.assertEqual(iso_utc(1790000000), iso_utc(1790000000000))                                  # seconds and milliseconds agree
        self.assertIsNone(iso_utc("not a date")); self.assertIsNone(iso_utc(""))


class PricedRegression(unittest.TestCase):
    def test_priced_station_drop_is_refused(self):
        def priced_scraper():
            class G(good_scraper(60)):
                async def fetch_stations(self):
                    return [st(i) if i < 10 else {**st(i), "prices": []} for i in range(60)]
            return G
        old = {"meta": {"currency": "EUR", "station_count": 60, "priced_count": 60, "fetched_at": "2026-10-01T00:00:00+00:00"}, "stations": [st(i) for i in range(60)]}
        pm = {"XX": {"station_count": 60, "priced_count": 60, "status": "ok", "fetched_at": "2026-10-01T00:00:00+00:00"}}
        r, f = run_one_with(priced_scraper(), old=old, prev_meta=pm)
        self.assertEqual(f["meta"]["status"], "stale"); self.assertIn("priced stations regressed", f["meta"]["last_error"])


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
