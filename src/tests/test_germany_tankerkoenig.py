import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data_checks import quality_report, track_changes  # noqa: E402
from scrapers import germany  # noqa: E402
from scrapers.germany import GermanyScraper, GRID, RURAL, _DEAnwb, _cover_circles, accuracy_summary, accuracy_update, parse_tk_stations  # noqa: E402


class FakeResp:
    def __init__(self, status, body):
        self.status, self.body = status, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self, content_type=None):
        return self.body


class FakeSession:
    """Scripted GET: `script` is a list of (status, body) consumed in order; last one repeats."""

    def __init__(self, script=None):
        self.calls = []
        self.script = script or [(200, {"ok": True, "stations": []})]

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        i = min(len(self.calls) - 1, len(self.script) - 1)
        return FakeResp(*self.script[i])


class FakeTime:
    def __init__(self, wall=0.0):
        self.now, self.wall, self.sleeps = 0.0, wall, []

    def clock(self):
        return self.now

    async def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def anwb_station(i, lat, lon, p95=1.859, diesel=1.759, p98=None):
    prices = [{"fuel_type": "95", "price": p95, "currency": "EUR", "unit": "L", "updated_at": None, "octane": 95},
              {"fuel_type": "DIESEL", "price": diesel, "currency": "EUR", "unit": "L", "updated_at": None}]
    if p98:
        prices.append({"fuel_type": "98", "price": p98, "currency": "EUR", "unit": "L", "updated_at": None, "octane": 98})
    return {"id": f"de_{i}", "country": "DE", "name": f"A{i}", "brand": "Aral", "address": "", "city": "",
            "lat": lat, "lon": lon, "source": "anwb.nl (ANWB POI API)", "confidence": 0.85, "grade": "C",
            "prices": prices}


def tk_body(*rows):
    return {"ok": True, "stations": [dict(id=f"tk{i}", lat=r[0], lng=r[1], brand="ARAL", name="N", street="S",
                                          houseNumber="1", place="P", e5=r[2], e10=r[3], diesel=r[4])
                                     for i, r in enumerate(rows)]}


def make(mode, session, ft=None, key="k", **attrs):
    with mock.patch.dict(os.environ, {"TANKERKOENIG_MODE": mode, "TANKERKOENIG_API_KEY": key}, clear=False):
        sc = GermanyScraper(session)
    ft = ft or FakeTime()
    sc._sleep, sc._clock, sc._wall = ft.sleep, ft.clock, lambda: ft.wall
    sc.acc_path = None   # tests never write data/de_accuracy.json
    for k, v in attrs.items():
        setattr(sc, k, v)
    return sc, ft


def run(sc, baseline):
    with mock.patch.object(_DEAnwb, "fetch_stations", mock.AsyncMock(return_value=baseline)):
        return asyncio.run(sc.fetch_stations())


class Off(unittest.TestCase):
    def test_off_makes_no_requests_even_with_key(self):
        s = FakeSession()
        sc, _ = make("off", s)
        out = run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertEqual(s.calls, [])
        self.assertEqual(out[0]["prices"][0]["fuel_type"], "95")
        self.assertEqual(sc.GRADE, "C")

    def test_default_and_unknown_mode_are_off(self):
        with mock.patch.dict(os.environ, {"TANKERKOENIG_API_KEY": "k"}, clear=False):
            os.environ.pop("TANKERKOENIG_MODE", None)
            self.assertEqual(GermanyScraper(None).mode, "off")
        sc, _ = make("bogus", FakeSession())
        self.assertEqual(sc.mode, "off")


class TestMode(unittest.TestCase):
    def test_spacing_cap_and_partial_labelling(self):
        s = FakeSession([(200, tk_body((52.5, 13.4, 1.90, 1.85, 1.75)))])
        sc, ft = make("test", s)
        out = run(sc, [anwb_station(1, 52.5, 13.4), anwb_station(2, 50.0, 8.0)])
        self.assertEqual(len(s.calls), 5)                       # capped at 5 circles
        self.assertEqual(len(ft.sleeps), 4)
        self.assertTrue(all(x >= 62 for x in ft.sleeps))        # >= 62 s between requests
        self.assertEqual(sc.GRADE, "C")                         # never claims full MTS-K coverage
        self.assertIn("partial", sc.SOURCE)
        self.assertEqual(out[0]["grade"], "A")
        self.assertEqual(out[1]["grade"], "C")                  # unmatched stays ANWB
        self.assertEqual(len(out), 2)                           # no extras in test mode
        self.assertEqual({p["fuel_type"] for p in out[0]["prices"]}, {"E5", "E10", "DIESEL"})

    def test_spacing_counts_from_end_of_previous_request_not_start(self):
        s = FakeSession()
        sc, ft = make("test", s)
        orig = s.get

        def slow_get(*a, **k):
            ft.now += 10                                         # a request takes 10 s
            return orig(*a, **k)
        s.get = slow_get
        run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertTrue(all(abs(x - 62) < 1e-6 for x in ft.sleeps))   # full gap after the 10 s request ended

    def test_rotation_by_time_slot_covers_all_circles(self):
        seen = []
        for slot in range(20):
            sc, _ = make("test", FakeSession(), ft=FakeTime(wall=slot * 1800 + 5))
            c5 = sc._circles([])
            self.assertEqual(len(c5), 5)
            self.assertEqual(sum(1 for c in c5 if c in RURAL), 3)       # every run: 2 metro + 3 country-side circles
            seen += c5
        self.assertEqual(set(seen), set(GRID) | set(RURAL))
        a, _ = make("test", FakeSession(), ft=FakeTime(wall=100))
        b, _ = make("test", FakeSession(), ft=FakeTime(wall=1700))   # same slot, same circles
        c, _ = make("test", FakeSession(), ft=FakeTime(wall=1900))
        self.assertEqual(a._circles([]), b._circles([]))
        self.assertNotEqual(a._circles([]), c._circles([]))

    def test_aborts_on_first_503_without_retry(self):
        for code in (503, 429):
            s = FakeSession([(200, tk_body((52.5, 13.4, 1.90, 1.85, 1.75))), (code, {})])
            sc, _ = make("test", s)
            out = run(sc, [anwb_station(1, 52.5, 13.4)])
            self.assertEqual(len(s.calls), 2)                    # 1 ok, 1 refused, then nothing
            self.assertEqual(sc.tk_info["aborted"], f"HTTP {code}")
            self.assertEqual(out[0]["grade"], "A")               # data from before the abort is kept
            self.assertTrue(sc.merge_report["failed_sources"])

    def test_time_budget_stops_before_overrun(self):
        s = FakeSession()
        sc, ft = make("test", s, budget_s=200)
        run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertLess(len(s.calls), 5)
        self.assertEqual(sc.tk_info["stopped"], "time budget")
        self.assertLessEqual(ft.now, 200)

    def test_budget_respects_scraper_timeout(self):
        s = FakeSession()
        sc, _ = make("test", s, scraper_timeout_s=100)           # 100 - 90 < 30: skip, keep ANWB
        out = run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertEqual(s.calls, [])
        self.assertEqual(len(out), 1)


class Commercial(unittest.TestCase):
    def test_max_req_and_no_throttle(self):
        s = FakeSession([(200, tk_body((52.5, 13.4, 1.90, 1.85, 1.75)))])
        base = [anwb_station(i, 47.5 + i * 0.3, 8 + i * 0.4) for i in range(20)]
        sc, ft = make("commercial", s, max_req=7)
        run(sc, base)
        self.assertEqual(len(s.calls), 7)
        self.assertEqual(ft.sleeps, [])
        self.assertEqual(sc.tk_info["stopped"], "request budget")

    def test_abort_on_503(self):
        s = FakeSession([(503, {})])
        base = [anwb_station(i, 47.5 + i * 0.3, 8 + i * 0.4) for i in range(20)]
        sc, _ = make("commercial", s, concurrency=1)
        run(sc, base)
        self.assertEqual(len(s.calls), 1)
        self.assertEqual(sc.tk_info["aborted"], "HTTP 503")

    def test_base_url_radius_extras_and_grade(self):
        s = FakeSession([(200, tk_body((52.5, 13.4, 1.90, 1.85, 1.75), (50.0, 8.0, 1.9, 1.8, 1.7)))])
        sc, _ = make("commercial", s, max_req=1, radius_km=40, base_url="https://example.test/api")
        out = run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertEqual(s.calls[0][0], "https://example.test/api/list.php")
        self.assertEqual(s.calls[0][1]["rad"], 40)
        self.assertEqual(len(out), 2)                            # extra MTS-K station added
        self.assertEqual(sc.GRADE, "C")                          # only 2 stations: no full-coverage claim
        sc._label(12000)
        self.assertEqual(sc.GRADE, "A")

    def test_cover_circles_footprint_and_order(self):
        pts = [{"lat": 52.5 + i * 0.01, "lon": 13.4} for i in range(30)] + [{"lat": 48.1, "lon": 11.6}]
        c = _cover_circles(pts, 25)
        self.assertGreaterEqual(len(c), 2)
        self.assertLess(abs(c[0][0] - 52.6), 0.5)                # densest first
        self.assertEqual(_cover_circles([], 25), [])


class ParseAndMerge(unittest.TestCase):
    def test_parse_fields(self):
        sc, _ = make("test", None)
        st = parse_tk_stations(tk_body((52.5, 13.4, 1.9, False, 1.7)), sc.price_entry)[0]
        self.assertEqual(st["id"], "de_tk_tk0")
        self.assertEqual(st["source"], "tankerkoenig.de (MTS-K)")
        self.assertEqual(st["address"], "S 1")
        self.assertEqual({p["fuel_type"] for p in st["prices"]}, {"E5", "DIESEL"})   # closed fuel (False) skipped
        self.assertEqual(st["lng" if "lng" in st else "lon"], 13.4)

    def test_alt_reading_kept_and_98_retained(self):
        base = [anwb_station(1, 52.5, 13.4, p95=1.80, diesel=1.759, p98=2.05)]
        tk = parse_tk_stations(tk_body((52.5, 13.4, 1.95, 1.85, 1.759)), make("test", None)[0].price_entry)
        out = GermanyScraper._merge(base, tk, add_extras=False)
        by = {p["fuel_type"]: p for p in out[0]["prices"]}
        self.assertEqual(set(by), {"E5", "E10", "DIESEL", "98"})
        self.assertEqual(by["E10"]["alt"][0], {"price": 1.80, "source": "anwb", "updated_at": None})  # 2.8 % apart
        self.assertNotIn("alt", by["DIESEL"])                    # identical
        self.assertNotIn("alt", by["E5"])
        self.assertEqual(by["98"]["source"], "anwb")
        self.assertEqual(out[0]["id"], "de_1")                   # id kept for the 48 h tracker

    def test_distinct_e5_e10_activate_e10_gt_e5_check_and_tracker(self):
        sts = []
        for i in range(40):
            sts.append(anwb_station(i, 50 + i * 0.01, 8))
        tk = parse_tk_stations(tk_body(*[(50 + i * 0.01, 8, 1.90, 1.95 if i < 4 else 1.85, 1.7) for i in range(40)]),
                               make("test", None)[0].price_entry)
        GermanyScraper._merge(sts, tk)
        rep = quality_report(sts)
        self.assertEqual(rep["e10_gt_e5"], {"n": 40, "pct": 10.0})
        # tracker: stable after the one-off signature change at upgrade, flagged after 48 h
        track_changes(sts, None, 1000)
        again = [dict(s) for s in sts]
        track_changes(again, sts, 1000 + 49 * 60)
        self.assertTrue(all(s.get("ps") == 1 for s in again))


class Baseline(unittest.TestCase):
    def test_anwb_survives_tankerkoenig_failure(self):
        class Boom(FakeSession):
            def get(self, *a, **k):
                raise RuntimeError("down apikey=SECRET123")
        sc, _ = make("test", Boom(), key="SECRET123")
        base = [anwb_station(1, 52.5, 13.4)]
        out = run(sc, base)
        self.assertEqual(out, base)
        self.assertEqual(out[0]["prices"][0]["fuel_type"], "95")
        self.assertEqual(sc.GRADE, "C")

    def test_merge_exception_keeps_baseline(self):
        sc, _ = make("test", FakeSession([(200, tk_body((52.5, 13.4, 1.9, 1.85, 1.7)))]))
        with mock.patch.object(GermanyScraper, "_merge", side_effect=ValueError("x")):
            out = run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertEqual(len(out), 1)

    def test_key_not_logged(self):
        self.assertNotIn("SECRET", GermanyScraper._scrub("GET https://x/list.php?lat=1&apikey=SECRET&rad=2"))

    def test_missing_key_makes_no_requests(self):
        s = FakeSession()
        sc, _ = make("commercial", s, key="")
        run(sc, [anwb_station(1, 52.5, 13.4)])
        self.assertEqual(s.calls, [])


class AccuracyMeter(unittest.TestCase):
    def test_histograms_summary_and_pruning(self):
        store = {}
        pairs = [("petrol", "metro", "ESSO", 0.0)] * 6 + [("petrol", "rural", "ESSO", 1.0), ("diesel", "rural", "ARAL", -2.0),
                                                           ("diesel", "metro", "ARAL", 12.0), ("diesel", "metro", "ARAL", 0.4)]
        accuracy_update(store, pairs, "2026-11-11")
        sm = accuracy_summary(store)
        self.assertEqual(sm["n"], 10)
        self.assertEqual(sm["within_1ct_pct"], 80.0)         # 6 zeros + 0.4 + 1.0 within 1 ct; -2 and 12 are not
        self.assertEqual(sm["bias_median_ct"], 0.0)
        self.assertIn("80.0%", sm["line"])
        self.assertEqual(sm["by"]["petrol|rural"]["n"], 1)
        for d in range(12, 30):                                # older days fall out after 14 days
            accuracy_update(store, [("petrol", "metro", "X", 0.0)], f"2026-11-{d:02d}")
        self.assertEqual(len(store["days"]), 14)
        self.assertNotIn("2026-11-11", store["days"])

    def test_merge_records_signed_difference_and_stratum(self):
        base = [anwb_station(1, 52.5, 13.4)]
        tk = parse_tk_stations(tk_body((52.5, 13.4, 1.90, 1.85, 1.75)), GermanyScraper(FakeSession()).price_entry)
        tk[0]["_stratum"] = "rural"
        acc = []
        GermanyScraper._merge(base, tk, add_extras=False, acc=acc)
        self.assertEqual(acc, [("petrol", "rural", "ARAL", 0.9), ("diesel", "rural", "ARAL", 0.9)])   # ANWB minus official, in ct


if __name__ == "__main__":
    unittest.main()
