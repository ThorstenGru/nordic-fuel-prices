import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chain_price import flag_chain_prices  # noqa: E402


def st(i, brand, price, src="anwb.nl (ANWB POI API)", ts=None, ft="DIESEL"):
    p = {"fuel_type": ft, "price": price, "updated_at": ts}
    return {"id": f"s{i}", "brand": brand, "source": src, "prices": [p]}


class Chain(unittest.TestCase):
    def test_same_price_at_many_stations_is_flagged_and_the_odd_one_is_not(self):
        s = [st(i, "ST1", 21.593) for i in range(20)] + [st(99, "ST1", 20.9)]
        self.assertEqual(flag_chain_prices(s), 20)
        self.assertTrue(all(x.get("chain_price") for x in s[:20]))
        self.assertNotIn("chain_price", s[20])

    def test_per_station_prices_are_not_flagged(self):
        s = [st(i, "ARAL", 1.80 + i / 1000) for i in range(30)]
        self.assertEqual(flag_chain_prices(s), 0)

    def test_small_brand_timestamped_and_other_sources_are_left_alone(self):
        self.assertEqual(flag_chain_prices([st(i, "X", 1.9) for i in range(14)]), 0)                         # under 15 stations
        self.assertEqual(flag_chain_prices([st(i, "X", 1.9, ts="2026-11-16T05:00:00+00:00") for i in range(20)]), 0)   # real timestamps
        self.assertEqual(flag_chain_prices([st(i, "X", 1.9, src="e-control.at") for i in range(20)]), 0)

    def test_98_octane_is_not_counted_as_petrol_and_a_rerun_clears_old_flags(self):
        s = [st(i, "X", 1.9, ft="E5") for i in range(20)]
        for x in s:
            x["prices"][0]["octane"] = 98
        self.assertEqual(flag_chain_prices(s), 0)
        t = [st(i, "ST1", 21.0) for i in range(20)]
        flag_chain_prices(t)
        for x in t:
            x["prices"][0]["price"] = 21.0 + int(x["id"][1:]) / 100
        self.assertEqual(flag_chain_prices(t), 0)
        self.assertFalse(any("chain_price" in x for x in t))


if __name__ == "__main__":
    unittest.main()
