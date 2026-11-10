import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import europe_index as ei  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def country(cc, p95=None, diesel=None, n=100, status="ok", age_h=1, grade="B"):
    st = {}
    if p95 is not None:
        st["p95"] = {"n": n, "median": p95}
    if diesel is not None:
        st["diesel"] = {"n": n, "median": diesel}
    return {"country": cc, "status": status, "grade": grade, "source": "x",
            "fetched_at": (NOW - timedelta(hours=age_h)).isoformat(), "stats_eur": st}


class Eligible(unittest.TestCase):
    def test_trust_filter(self):
        meta = {"countries": [country("DE", 1.9, 2.1), country("FR", 1.8, 1.9, status="stale"),
                              country("ES", 1.6, 1.7, age_h=40), country("PL", 1.5, 1.6, n=5),
                              country("ZZ", 1.0, 1.0)]}
        e = ei.eligible(meta, NOW)
        self.assertEqual(list(e), ["DE"])            # stale, too old, too few stations and unknown codes are dropped
        self.assertEqual(e["DE"]["p95"]["median"], 1.9)

    def test_fuel_missing_is_skipped_per_fuel(self):
        e = ei.eligible({"countries": [country("DE", 1.9, None)]}, NOW)
        self.assertIn("p95", e["DE"])
        self.assertNotIn("diesel", e["DE"])


class History(unittest.TestCase):
    def test_one_snapshot_per_day_and_7d_change(self):
        elig = {"DE": {"p95": {"median": 1.9}, "diesel": {"median": 2.1}}}
        h = ei.update_history([], elig, "2026-11-03")
        h = ei.update_history(h, elig, "2026-11-03")             # same day replaces, never duplicates
        self.assertEqual(len(h), 1)
        self.assertEqual(ei.change_7d_value(h, "2026-11-10", "p95", "DE", 1.95), 0.05)
        self.assertIsNone(ei.change_7d_value(h, "2026-11-05", "p95", "DE", 1.95))   # only 2 days old -> no claim
        self.assertIsNone(ei.change_7d_value(h, "2026-11-10", "p95", "FR", 1.95))   # country absent then


class Pairs(unittest.TestCase):
    def test_sentence_names_the_cheaper_country(self):
        elig = {"DE": {"p95": {"median": 2.0, "n": 9, "grade": "B"}}, "PL": {"p95": {"median": 1.5, "n": 9, "grade": "B"}}}
        s = ei.pair_sentence("DE", "PL", ei.pair_rows(elig, "DE", "PL"))
        self.assertIn("cheaper in Poland than in Germany", s)
        self.assertIn("€25.00", s)                                # 0.50 x 50 L

    def test_writes_pages_and_open_data(self):
        countries = [country(cc, 1.5 + i / 20, 1.7 + i / 20) for i, cc in
                     enumerate(["SE", "DK", "DE", "PL", "NL", "AT", "CZ", "FR", "ES", "PT"])]
        for c in countries:
            c["fetched_at"] = datetime.now(timezone.utc).isoformat()
        import json
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "meta.json").write_text(json.dumps({"countries": countries}), encoding="utf-8")
            orig = ei.load_history
            ei.load_history = lambda: []
            try:
                self.assertEqual(ei.main(d), 0)
            finally:
                ei.load_history = orig
            self.assertTrue((d / "europe" / "index.html").exists())
            self.assertTrue((d / "europe" / "fuel-prices-sweden-vs-denmark" / "index.html").exists())
            self.assertIn("country,name,fuel", (d / "open-data" / "national-averages.csv").read_text(encoding="utf-8"))

    def test_too_few_countries_keeps_previous_page(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "meta.json").write_text(json.dumps({"countries": [country("DE", 1.9, 2.1)]}), encoding="utf-8")
            self.assertEqual(ei.main(d), 0)
            self.assertFalse((d / "europe").exists())


if __name__ == "__main__":
    unittest.main()
