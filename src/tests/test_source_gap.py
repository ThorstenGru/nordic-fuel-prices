import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from source_gap import source_gap  # noqa: E402


def st(i, price=10.0, alt_price=11.0, alt_src="b", ft="E10", **flags):
    return {"id": str(i), "prices": [{"fuel_type": ft, "price": price, "octane": 95, "source": "a",
                                      "alt": [{"price": alt_price, "source": alt_src, **flags}]}]}


class SourceGap(unittest.TestCase):
    def test_median_and_buckets(self):
        r = source_gap([st(i) for i in range(30)] + [st(i, 20.0, 22.0, ft="DIESEL") for i in range(30)])
        self.assertEqual(r, [{"fuel": "diesel", "primary": "a", "other": "b", "n": 30, "median_pct": 10.0},
                             {"fuel": "p95", "primary": "a", "other": "b", "n": 30, "median_pct": 10.0}])

    def test_small_n_omitted(self):
        self.assertEqual(source_gap([st(i) for i in range(29)]), [])

    def test_flagged_ignored(self):
        S = [st(i) for i in range(29)] + [st(99, alt_price=25.0)]  # >2x outlier
        self.assertEqual(source_gap(S), [])
        bad = [st(i) for i in range(30)]
        for s in bad:
            s["prices"][0]["plausible"] = False
        self.assertEqual(source_gap(bad), [])
        reg = [st(i) for i in range(30)]
        for s in reg:
            s["prices"][0]["basis"] = "regulated_max"
        self.assertEqual(source_gap(reg), [])

    def test_third_source_separate(self):
        r = source_gap([st(i) for i in range(30)] + [st(i, alt_price=9.0, alt_src="c") for i in range(30)])
        self.assertEqual([(e["other"], e["median_pct"]) for e in r], [("b", 10.0), ("c", -10.0)])


if __name__ == "__main__":
    unittest.main()
