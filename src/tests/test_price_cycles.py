import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import price_cycles as pc  # noqa: E402


def U(*a):
    return datetime(*a, tzinfo=timezone.utc)


class Slots(unittest.TestCase):
    def test_local_slot_dst_and_zones(self):
        self.assertEqual(pc.local_slot("SE", U(2026, 1, 5, 23, 30)), (1, 0))      # Mon 23:30 UTC = Tue 00:30 CET
        self.assertEqual(pc.local_slot("SE", U(2026, 7, 5, 22, 30)), (0, 0))      # Sun 22:30 UTC = Mon 00:30 CEST
        self.assertEqual(pc.local_slot("FI", U(2026, 1, 5, 12, 0)), (0, 14))      # EET
        self.assertEqual(pc.local_slot("IS", U(2026, 7, 5, 12, 0)), (6, 12))      # no summer time
        self.assertEqual(pc.local_slot("GB", U(2026, 3, 29, 0, 59)), (6, 0))      # just before the switch
        self.assertEqual(pc.local_slot("GB", U(2026, 3, 29, 1, 0)), (6, 2))
        self.assertIsNone(pc.local_slot("ZZ", U(2026, 1, 1)))

    def test_codec_roundtrip_and_clip(self):
        c = pc.enc(-1.23, 7)
        self.assertEqual(len(c), 3)
        self.assertEqual(pc.dec(c * 2, 1), (-1.23, 7))
        self.assertEqual(pc.dec(pc.enc(99, 3), 0)[0], 20.47)
        self.assertEqual(pc.dec(pc.EMPTY, 167), (0.0, 0))


class Fold(unittest.TestCase):
    def test_fold_dedup_and_cap(self):
        t = U(2026, 11, 2, 8, 0)
        s = pc.fold(None, 2.0, t, (0, 9))
        self.assertEqual(pc.dec(s["c"], 9), (0.0, 1))
        self.assertIs(pc.fold(s, 2.1, t + timedelta(minutes=2), (0, 9)), s)   # re-run ignored
        s = pc.fold(s, 2.02, t + timedelta(minutes=15), (0, 9))
        lvl, n = pc.dec(s["c"], 9)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(lvl, 0.5, delta=0.05)   # mean of 0 % and about +1 %
        for k in range(60):
            s = pc.fold(s, 2.0, t + timedelta(minutes=30 + 15 * k), (0, 9))
        self.assertEqual(pc.dec(s["c"], 9)[1], pc.N_CAP)
        self.assertIsNone(pc.fold(s, 0, t, (0, 9)))
        self.assertIsNone(pc.fold(s, None, t, (0, 9)))

    def test_cheapest_windows_guard(self):
        c = pc.EMPTY
        for i in range(168):
            c = c[:i * 3] + pc.enc(1.0 if i != 30 else -2.0, 12) + c[i * 3 + 3:]   # Tue 06:00 cheapest
        st = {"c": c}
        w = pc.cheapest_windows(st, min_n=8, top=1)[0]
        self.assertEqual((w["wd"], w["hr"], w["lvl"], w["n"]), (1, 6, -2.0, 12))
        self.assertEqual(pc.cheapest_windows(st, min_n=13), [])                  # min-sample guard
        self.assertEqual(pc.cheapest_windows({"c": pc.EMPTY}), [])
        self.assertEqual(pc.cheapest_windows(None), [])
        self.assertAlmostEqual(pc.cheapest_windows(st, width=2, top=1)[0]["lvl"], -0.5)


class Build(unittest.TestCase):
    at = "2026-11-02T08:00:00+00:00"

    def meta(self, ccs):
        return {"countries": [{"country": cc, "status": "ok", "fetched_at": self.at, "stats_eur": {"p95": {"median": 1.9}, "diesel": {"median": 2.1}}}
                              for cc in ccs] + [{"country": "XX", "status": "failed"}]}

    def test_build_carries_forward_and_never_empty(self):
        t = U(2026, 11, 2, 8, 0)
        a = pc.build({}, self.meta(["SE", "DE"]), t)
        self.assertEqual(set(a["series"]), {"SE", "DE"})
        self.assertIsNone(pc.build(a, {"countries": [{"country": "SE", "status": "failed"}]}, t))
        self.assertIsNone(pc.build(a, self.meta(["SE"]), t + timedelta(minutes=15)))   # same country fetched_at: re-published data adds nothing
        m = self.meta(["SE"]); m["countries"][0]["fetched_at"] = "2026-11-02T08:15:00+00:00"
        b = pc.build(a, m, t + timedelta(minutes=15))
        self.assertIn("DE", b["series"])                    # country missing this run keeps its history
        self.assertEqual(pc.dec(b["series"]["SE"]["p95"]["c"], 9)[1], 2)

    def test_size_budget_all_countries(self):
        ccs = list(pc.TZ) + list(pc.NO_DST)
        t, d = U(2026, 1, 5, 0, 0), {}
        for k in range(672 * 2):                            # two weeks of 15-minute runs, drifting prices
            m = self.meta(ccs)
            for c in m["countries"]:
                c["fetched_at"] = (t + timedelta(minutes=15 * k)).isoformat()
                c["stats_eur"] = {"p95": {"median": 1.5 + (k % 97) / 300}, "diesel": {"median": 1.8 + (k % 89) / 250}}
            d = pc.build(d, m, t + timedelta(minutes=15 * k))
        size = len(json.dumps(d, separators=(",", ":")))
        self.assertEqual(len(d["series"]), len(ccs))
        self.assertLess(size, pc.BUDGET)
        print(f"[size] {len(ccs)} countries x 2 fuels = {size} bytes")


if __name__ == "__main__":
    unittest.main()
