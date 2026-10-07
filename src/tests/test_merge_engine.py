"""Tests for src/merge_engine.py.  Run:  python -m unittest src.tests.test_merge_engine  (repo root)
or pytest src/tests/test_merge_engine.py"""
import copy
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from merge_engine import (MergeConfig, SourceResult, bucket_of, canonical_brand,  # noqa: E402
                          merge_sources, octane_of)

NOW = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
LAT0, LON0 = 55.6000, 13.0000
M = 1 / 111320.0      # degrees of latitude per metre


def iso(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def px(ft, price, ts=None, octane=None, cur="SEK"):
    p = {"fuel_type": ft, "price": price, "currency": cur, "unit": "L", "updated_at": ts}
    if octane:
        p["octane"] = octane
    return p


def st(sid, dlat_m=0.0, brand="Shell", prices=(), dlon_m=0.0, name=None):
    import math
    return {"id": sid, "country": "SE", "name": name if name is not None else (brand or "x"), "brand": brand,
            "address": "", "city": "", "lat": LAT0 + dlat_m * M,
            "lon": LON0 + dlon_m * M / math.cos(math.radians(LAT0)), "source": sid, "confidence": 0.9,
            "prices": list(prices)}


def src(sid, stations, prio, kind="official", ok=True, error=None):
    return SourceResult(sid, sid.upper(), stations, prio, kind, "SEK", ok, error)


def run(results, **kw):
    return merge_sources(results, MergeConfig(country="SE", **kw), now=NOW)


def price(station, bucket):
    for p in station["prices"]:
        if bucket_of(p) == bucket:
            return p
    return None


class Helpers(unittest.TestCase):
    def test_octane_and_bucket(self):
        self.assertEqual(octane_of({"fuel_type": "E5"}), 95)
        self.assertEqual(octane_of({"fuel_type": "E5", "octane": 98}), 98)
        self.assertEqual(bucket_of({"fuel_type": "E10"}), "95")
        self.assertEqual(bucket_of({"fuel_type": "95"}), "95")
        self.assertEqual(bucket_of({"fuel_type": "98"}), "98+")
        self.assertEqual(bucket_of({"fuel_type": "E5", "octane": 100}), "98+")
        self.assertEqual(bucket_of({"fuel_type": "diesel"}), "DIESEL")
        self.assertEqual(bucket_of({"fuel_type": "HVO100"}), "HVO100")

    def test_brand_normalisation(self):
        self.assertEqual(canonical_brand("Circle K"), canonical_brand("CIRCLEK"))
        self.assertEqual(canonical_brand("Statoil"), "circle k")
        self.assertEqual(canonical_brand("Shell Express"), "shell")
        self.assertEqual(canonical_brand("OMV Tankstelle"), "omv")
        self.assertEqual(canonical_brand("Ö Tank"), canonical_brand("O Tank"))
        self.assertEqual(canonical_brand("", "Preem Lund"), "preem")
        self.assertEqual(canonical_brand("", "Lund centrum"), "")
        self.assertEqual(canonical_brand("Unknown"), "")


class Matching(unittest.TestCase):
    def test_two_sources_agree(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.00)])], 1)
        b = src("b", [st("B1", 20, prices=[px("DIESEL", 18.05)])], 2)
        out, rep = run([a, b])
        self.assertEqual(len(out), 1)
        s = out[0]
        self.assertEqual(s["sources"], ["a", "b"])
        self.assertEqual(s["match"], {"merged": 1})
        p = price(s, "DIESEL")
        self.assertEqual((p["price"], p["source"]), (18.00, "a"))
        self.assertNotIn("alt", p)
        self.assertNotIn("disagree", p)
        self.assertEqual(rep["matched_pairs"], 1)

    def test_disagree_exposes_alt(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.00, ts=iso(5))])], 1)
        b = src("b", [st("B1", 10, prices=[px("DIESEL", 20.00, ts=iso(5))])], 2)
        out, rep = run([a, b])
        p = price(out[0], "DIESEL")
        self.assertEqual(p["price"], 18.00)
        self.assertTrue(p["disagree"])
        self.assertEqual(p["alt"], [{"price": 20.00, "source": "b", "updated_at": iso(5)}])
        self.assertEqual(rep["conflicts"], 1)
        self.assertEqual(rep["alt_values"], 1)

    def test_alt_without_disagree(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.00)])], 1)
        b = src("b", [st("B1", 10, prices=[px("DIESEL", 18.50)])], 2)       # 2.8 %
        out, _ = run([a, b])
        p = price(out[0], "DIESEL")
        self.assertEqual(len(p["alt"]), 1)
        self.assertNotIn("disagree", p)

    def test_never_averages(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.00)])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 19.00)])], 2)
        out, _ = run([a, b])
        self.assertIn(price(out[0], "DIESEL")["price"], (18.00, 19.00))

    def test_adjacent_different_brands_not_merged(self):
        a = src("a", [st("A1", brand="Shell", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 30, brand="Circle K", prices=[px("DIESEL", 18.0)])], 2)
        out, rep = run([a, b])
        self.assertEqual(len(out), 2)
        self.assertEqual(rep["matched_pairs"], 0)

    def test_brand_alias_merges(self):
        a = src("a", [st("A1", brand="Circle K", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 60, brand="Statoil", prices=[px("DIESEL", 18.0)])], 2)
        out, _ = run([a, b])
        self.assertEqual(len(out), 1)

    def test_too_far_not_merged(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 150, prices=[px("DIESEL", 18.0)])], 2)
        out, _ = run([a, b])
        self.assertEqual(len(out), 2)

    def test_ambiguous_two_candidates_not_merged(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 20, prices=[px("DIESEL", 18.1)]),
                       st("B2", 28, dlon_m=5, prices=[px("DIESEL", 18.2)])], 2)
        out, rep = run([a, b])
        self.assertEqual(len(out), 3)
        self.assertEqual(rep["matched_pairs"], 0)
        self.assertGreaterEqual(rep["ambiguous_skipped"], 1)

    def test_ambiguous_reverse_side(self):
        a = src("a", [st("A1", 0, prices=[px("DIESEL", 18.0)]),
                      st("A2", 12, dlon_m=3, prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 6, prices=[px("DIESEL", 18.1)])], 2)
        out, rep = run([a, b])
        self.assertEqual(len(out), 3)
        self.assertEqual(rep["matched_pairs"], 0)

    def test_clear_nearest_among_two_merges(self):
        a = src("a", [st("A1", 0, prices=[px("DIESEL", 18.0)]),
                      st("A2", 90, prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 3, prices=[px("DIESEL", 18.1)])], 2)
        out, rep = run([a, b])
        self.assertEqual(len(out), 2)
        self.assertEqual(rep["matched_pairs"], 1)
        self.assertEqual(out[0]["sources"], ["a", "b"])
        self.assertEqual(out[1]["sources"], ["a"])

    def test_never_two_of_same_source(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 0, prices=[px("DIESEL", 18.1)])], 2)
        c = src("c", [st("C1", 90, brand="Shell")], 3, kind="geometry")
        out, _ = run([a, b, c])
        for s in out:
            self.assertEqual(len(s["sources"]), len(set(s["sources"])))

    def test_unknown_brand_radius(self):
        a = src("a", [st("A1", brand="Shell", prices=[px("DIESEL", 18.0)])], 1)
        near = src("b", [st("B1", 30, brand="", name="Tank 1", prices=[px("DIESEL", 18.0)])], 2)
        far = src("b", [st("B1", 70, brand="", name="Tank 1", prices=[px("DIESEL", 18.0)])], 2)
        self.assertEqual(len(run([a, near])[0]), 1)
        self.assertEqual(len(run([a, far])[0]), 2)
        # known equal brand at the same 70 m still merges (match radius 100 m)
        known = src("b", [st("B1", 70, brand="Shell", prices=[px("DIESEL", 18.0)])], 2)
        self.assertEqual(len(run([a, known])[0]), 1)

    def test_unknown_brand_fills_brand_field(self):
        a = src("a", [st("A1", brand="", name="", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 10, brand="Preem", name="Preem Lund")], 2, kind="geometry")
        out, _ = run([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["brand"], "Preem")


class Selection(unittest.TestCase):
    def test_newer_timestamp_wins_over_priority(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0, ts=iso(120))])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 18.5, ts=iso(10))])], 2)
        p = price(run([a, b])[0][0], "DIESEL")
        self.assertEqual((p["price"], p["source"]), (18.5, "b"))
        self.assertEqual(p["alt"][0]["source"], "a")

    def test_small_time_difference_priority_wins(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0, ts=iso(40))])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 18.3, ts=iso(20))])], 2)     # only 20 min newer
        p = price(run([a, b])[0][0], "DIESEL")
        self.assertEqual(p["source"], "a")

    def test_timestamp_preference_can_be_disabled(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0, ts=iso(600))])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 18.3, ts=iso(1))])], 2)
        p = price(run([a, b], prefer_newer_timestamp=False)[0][0], "DIESEL")
        self.assertEqual(p["source"], "a")

    def test_missing_timestamp_falls_back_to_priority(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 18.3, ts=iso(1))])], 2)
        p = price(run([a, b])[0][0], "DIESEL")
        self.assertEqual(p["source"], "a")

    def test_priority_tie_lower_source_id(self):
        a = src("zz", [st("Z1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("aa", [st("A1", 5, prices=[px("DIESEL", 18.3)])], 1)
        out, _ = run([a, b])
        self.assertEqual(price(out[0], "DIESEL")["source"], "aa")

    def test_gap_fill_by_bucket(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 18.1), px("LPG", 9.0), px("E85", 12.0)])], 2)
        s = run([a, b])[0][0]
        self.assertEqual(price(s, "DIESEL")["source"], "a")
        self.assertEqual(price(s, "LPG")["source"], "b")
        self.assertEqual(price(s, "E85")["source"], "b")

    def test_anwb_95_not_added_next_to_e10(self):
        a = src("a", [st("A1", prices=[px("E10", 18.0, octane=95)])], 1)
        b = src("b", [st("B1", 5, prices=[px("95", 18.2)])], 2)
        s = run([a, b])[0][0]
        petrol = [p for p in s["prices"] if bucket_of(p) == "95"]
        self.assertEqual(len(petrol), 1)
        self.assertEqual(petrol[0]["fuel_type"], "E10")           # fuel_type of the winner kept
        self.assertEqual(len(s["prices"]), 1)

    def test_98_does_not_fill_95_bucket(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 5, prices=[px("98", 20.0), px("E5", 20.1, octane=98)])], 2)
        s = run([a, b])[0][0]
        self.assertIsNone(price(s, "95"))
        self.assertIsNotNone(price(s, "98+"))
        self.assertTrue(all(octane_of(p) is None or octane_of(p) >= 97 for p in s["prices"]))

    def test_95_and_98_coexist(self):
        a = src("a", [st("A1", prices=[px("E10", 18.0, octane=95), px("E5", 20.0, octane=98)])], 1)
        s = run([a])[0][0]
        self.assertEqual(len(s["prices"]), 2)

    def test_duplicate_in_bucket_keeps_lower(self):
        a = src("a", [st("A1", prices=[px("95", 19.0), px("E10", 18.0, octane=95), px("DIESEL", 17.0)])], 1)
        out, rep = run([a])
        s = out[0]
        self.assertEqual(price(s, "95")["price"], 18.0)
        self.assertEqual(rep["duplicate_prices_dropped"], 1)

    def test_regulated_cap_only_fills(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 17.0)])], 1)
        cap = src("cap", [st("C1", 5, prices=[px("DIESEL", 19.5), px("95", 20.5)])], 0, kind="regulated_cap")
        out, rep = run([a, cap])
        self.assertEqual(len(out), 1)
        s = out[0]
        d = price(s, "DIESEL")
        self.assertEqual((d["price"], d["source"]), (17.0, "a"))
        self.assertNotIn("basis", d)
        self.assertNotIn("alt", d)                                  # caps never show as alternatives
        g = price(s, "95")
        self.assertEqual((g["price"], g["basis"], g["source"]), (20.5, "regulated_max", "cap"))
        self.assertEqual(rep["regulated_fills"], 1)

    def test_regulated_cap_never_overrides_even_with_priority(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 17.0)])], 9)
        cap = src("cap", [st("C1", 5, prices=[px("DIESEL", 19.5, ts=iso(1))])], 0, kind="regulated_cap")
        out, _ = run([a, cap])
        d = price(out[0], "DIESEL")
        self.assertEqual(d["source"], "a")

    def test_cap_prices_not_outlier_checked(self):
        stations = [st(f"A{i}", i * 100, dlon_m=i * 50, prices=[px("DIESEL", 18.0)]) for i in range(8)]
        cap = src("cap", [st("C1", 250, dlon_m=900, brand="", prices=[px("95", 30.0)])], 0, kind="regulated_cap")
        out, rep = run([src("a", stations, 1), cap])
        self.assertTrue(any(price(s, "95") for s in out))


class Filters(unittest.TestCase):
    def _cluster(self, extra=None, n=7):
        sts = [st(f"A{i}", i * 150, dlon_m=i * 40, brand=f"B{i}", prices=[px("DIESEL", 18.0 + i * 0.05)])
               for i in range(n)]
        if extra:
            sts.append(extra)
        return sts

    def test_outlier_dropped(self):
        bad = st("BAD", 200, dlon_m=300, brand="Zed", prices=[px("DIESEL", 40.0), px("LPG", 9.0)])
        out, rep = run([src("a", self._cluster(bad), 1)])
        self.assertEqual(rep["outliers_dropped"], 1)
        s = [x for x in out if x["id"] == "BAD"][0]
        self.assertIsNone(price(s, "DIESEL"))
        self.assertIsNotNone(price(s, "LPG"))            # no neighbours with LPG: kept

    def test_no_outlier_check_with_few_neighbours(self):
        bad = st("BAD", 200, brand="Zed", prices=[px("DIESEL", 40.0)])
        out, rep = run([src("a", self._cluster(bad, n=3), 1)])
        self.assertEqual(rep["outliers_dropped"], 0)

    def test_far_neighbours_ignored(self):
        far = st("FAR", 20000, brand="Zed", prices=[px("DIESEL", 40.0)])       # 20 km away
        out, rep = run([src("a", self._cluster(far), 1)])
        self.assertEqual(rep["outliers_dropped"], 0)

    def test_failed_source_skipped(self):
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 99.0)])], 0, ok=False, error="HTTP 500")
        out, rep = run([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["sources"], ["a"])
        self.assertEqual(rep["failed_sources"], [{"source_id": "b", "error": "HTTP 500"}])
        self.assertEqual(rep["sources"]["b"]["stations_used"], 0)

    def test_all_failed(self):
        out, rep = run([src("a", [st("A1")], 1, ok=False, error="x")])
        self.assertEqual(out, [])
        self.assertEqual(rep["final_station_count"], 0)

    def test_future_timestamps_nulled(self):
        fut = (NOW + timedelta(minutes=45)).isoformat()
        ok_ts = (NOW + timedelta(minutes=5)).isoformat()                       # within tolerance
        a = src("a", [st("A1", prices=[px("DIESEL", 18.0, ts=fut), px("LPG", 9.0, ts=ok_ts)])], 1)
        out, rep = run([a])
        self.assertIsNone(price(out[0], "DIESEL")["updated_at"])
        self.assertEqual(price(out[0], "DIESEL")["price"], 18.0)
        self.assertEqual(price(out[0], "LPG")["updated_at"], ok_ts)
        self.assertEqual(rep["future_ts_nulled"], 1)

    def test_invalid_prices_and_stations(self):
        bad = st("A2", 500)
        bad["lat"] = None
        a = src("a", [st("A1", prices=[px("DIESEL", -1), px("LPG", "x"), px("E85", 12.0)]), bad], 1)
        out, rep = run([a])
        self.assertEqual(len(out), 1)
        self.assertEqual([p["fuel_type"] for p in out[0]["prices"]], ["E85"])
        self.assertEqual(rep["invalid_stations_dropped"], 1)


class Skeleton(unittest.TestCase):
    def test_skeleton_and_unmatched_additions(self):
        a = src("a", [st("A1", 0, prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("B1", 5, prices=[px("DIESEL", 18.0)]),
                      st("B2", 5000, brand="OMV", prices=[px("DIESEL", 18.4)])], 2)
        out, rep = run([b, a])                       # input order must not matter
        self.assertEqual([s["id"] for s in out], ["A1", "B2"])
        self.assertEqual(rep["sources"]["b"]["stations_in"], 2)
        self.assertEqual(rep["sources"]["b"]["stations_used"], 2)
        self.assertEqual(rep["sources"]["a"]["prices_won"], 1)
        self.assertEqual(rep["sources"]["b"]["prices_won"], 1)
        self.assertEqual(rep["final_station_count"], 2)
        self.assertEqual(rep["priced_station_count"], 2)

    def test_geometry_dropped_near_priced_kept_when_far(self):
        a = src("a", [st("A1", 0, prices=[px("DIESEL", 18.0)])], 1)
        g = src("osm", [st("G1", 80, brand="OMV"),               # within 100 m of priced, brand differs
                        st("G2", 3000, brand="OMV")], 0, kind="geometry")
        out, rep = run([a, g])
        self.assertEqual(sorted(s["id"] for s in out), ["A1", "G2"])
        self.assertEqual(rep["geometry_dropped"], 1)
        self.assertEqual(out[-1]["prices"], [])

    def test_geometry_comes_last_even_with_best_priority(self):
        g = src("osm", [st("G1", 0, brand="Shell")], 0, kind="geometry")
        a = src("a", [st("A1", 3000, prices=[px("DIESEL", 18.0)])], 5)
        out, _ = run([g, a])
        self.assertEqual([s["id"] for s in out], ["A1", "G1"])

    def test_geometry_matches_and_contributes_source(self):
        a = src("a", [st("A1", 0, brand="Shell", prices=[px("DIESEL", 18.0)])], 1)
        g = src("osm", [st("G1", 15, brand="Shell")], 0, kind="geometry")
        out, _ = run([a, g])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["sources"], ["a", "osm"])

    def test_id_collision_between_sources(self):
        a = src("a", [st("X", 0, prices=[px("DIESEL", 18.0)])], 1)
        b = src("b", [st("X", 5000, brand="OMV", prices=[px("DIESEL", 18.0)])], 2)
        out, _ = run([a, b])
        self.assertEqual(len({s["id"] for s in out}), 2)

    def test_output_fields_preserved(self):
        s0 = st("A1", prices=[px("DIESEL", 18.0, ts=iso(3))])
        out, _ = run([src("a", [s0], 1)])
        for k in ("id", "country", "name", "brand", "address", "city", "lat", "lon", "source", "confidence"):
            self.assertEqual(out[0][k], s0[k])
        self.assertEqual(out[0]["sources"], ["a"])
        self.assertNotIn("match", out[0])
        self.assertEqual(out[0]["prices"][0]["source"], "a")
        self.assertEqual(out[0]["prices"][0]["unit"], "L")


class Determinism(unittest.TestCase):
    def _inputs(self):
        a = src("a", [st(f"A{i}", i * 60, dlon_m=i * 20, brand=["Shell", "OMV", "Preem"][i % 3],
                         prices=[px("DIESEL", 18 + i * 0.01, ts=iso(i)), px("E10", 17.5, octane=95)])
                      for i in range(12)], 1)
        b = src("b", [st(f"B{i}", i * 60 + 5, dlon_m=i * 20, brand=["Shell", "OMV", "Preem"][i % 3],
                         prices=[px("DIESEL", 18.5 + i * 0.01), px("LPG", 9.0), px("95", 17.9)])
                      for i in range(0, 14)], 2)
        g = src("osm", [st(f"G{i}", i * 60 + 2000, brand="Shell") for i in range(5)], 3, kind="geometry")
        return [a, b, g]

    def test_same_input_same_output(self):
        r1 = run(self._inputs())
        r2 = run(self._inputs())
        self.assertEqual(r1, r2)
        self.assertEqual([s["id"] for s in r1[0]], [s["id"] for s in r2[0]])

    def test_result_list_order_irrelevant(self):
        ins = self._inputs()
        r1 = run(ins)
        r2 = run(list(reversed(self._inputs())))
        self.assertEqual(r1, r2)

    def test_inputs_not_mutated(self):
        ins = self._inputs()
        snapshot = copy.deepcopy(ins)
        run(ins)
        self.assertEqual(ins, snapshot)


if __name__ == "__main__":
    unittest.main()
