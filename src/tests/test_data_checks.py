import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data_checks import median_jump, quality_report, track_changes  # noqa: E402


def st(i, price=1.8, ft="DIESEL", **kw):
    return {"id": str(i), "lat": 50 + i * 0.01, "lon": 8.0, "brand": f"b{i}",
            "prices": [{"fuel_type": ft, "price": price, "octane": 95}], **kw}


class Track(unittest.TestCase):
    def test_unchanged_flagged_changed_reset(self):
        now = 1_000_000
        prev = [dict(st(1), pc=now - 49 * 60), dict(st(2), pc=now - 49 * 60), dict(st(3), pc=now - 60)]
        cur = [st(1), st(2, 1.9), st(3), st(4)]
        r = track_changes(cur, prev, now)
        self.assertEqual(r, {"new": 1, "stale": 1})
        self.assertEqual(cur[0]["ps"], 1)
        self.assertEqual(cur[0]["pc"], now - 49 * 60)
        self.assertEqual(cur[1]["pc"], now)           # price changed
        self.assertNotIn("ps", cur[2])
        self.assertEqual(cur[3]["pc"], now)           # new station starts now

    def test_no_prev_flags_nothing(self):
        cur = [st(1)]
        self.assertEqual(track_changes(cur, None, 5), {"new": 1})
        self.assertNotIn("ps", cur[0])


class Quality(unittest.TestCase):
    def test_band_e10_dup(self):
        S = [{"id": str(i), "lat": 50 + i * 0.01, "lon": 8, "brand": "x", "pc": 1,
              "prices": [{"fuel_type": "E5", "price": 2.0, "octane": 95},
                         {"fuel_type": "E10", "price": 2.1 if i < 3 else 1.9}]} for i in range(30)]
        S.append(st(100, 0.9))
        S.append(st(101, 3.6, "95"))
        S.append(dict(S[0], id="dup"))
        r = quality_report(S)
        self.assertEqual(r["band_out"], {"DIESEL": 1, "P95": 1})
        self.assertEqual(r["e10_gt_e5"], {"n": 31, "pct": 12.9})
        self.assertEqual(r["dup_n"], 1)
        self.assertEqual(r["stale48_n"], 0)

    def test_few_pairs_omitted(self):
        self.assertNotIn("e10_gt_e5", quality_report([st(1)]))


class Jump(unittest.TestCase):
    def test_jump(self):
        r = median_jump({"p95": {"median": 1.9}, "diesel": {"median": 1.8}}, {"p95": {"median": 1.8}, "diesel": {"median": 1.8}})
        self.assertEqual(r, [{"fuel": "p95", "prev": 1.8, "now": 1.9, "pct": 5.6}])
        self.assertEqual(median_jump({"p95": {"median": 1}}, None), [])


if __name__ == "__main__":
    unittest.main()
