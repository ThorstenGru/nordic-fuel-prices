import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from plausibility import mark_implausible  # noqa: E402


def st(i, **prices):
    return {"id": str(i), "prices": [{"fuel_type": ft, "price": v, "currency": "EUR", "octane": 95 if ft in ("E10", "E5") else None}
                                     for ft, v in prices.items()]}


def crowd(n=60):
    return [st(i, E10=1.80 + (i % 7) * 0.01, DIESEL=1.90 + (i % 5) * 0.01) for i in range(n)]


def st98(i, p95, p98):
    return {"id": str(i), "prices": [
        {"fuel_type": "E10", "price": p95, "octane": 95, "source": "anwb"},
        {"fuel_type": "98", "price": p98, "octane": 98, "source": "anwb"}]}


class Plausibility(unittest.TestCase):
    def test_octane_order_country_level_slot(self):
        # one source's 98 has no 95 at the same station but sits below the country 95 median
        S = crowd() + [{"id": f"x{i}", "prices": [{"fuel_type": "98", "price": 1.50, "octane": 98, "source": "a"}]}
                       for i in range(25)]
        self.assertEqual(mark_implausible(S, "EUR"), {"octane_order": 25})
        S = crowd() + [{"id": f"x{i}", "prices": [{"fuel_type": "98", "price": 1.95, "octane": 98, "source": "a"}]}
                       for i in range(25)]
        self.assertEqual(mark_implausible(S, "EUR"), {})

    def test_octane_order_flags_stale_95_when_98_newer(self):
        ok = [st98(i, 1.80 + i % 5 * .01, 1.95 + i % 5 * .01) for i in range(30)]
        s = st98(900, 1.95, 1.90)
        s["prices"][0]["updated_at"], s["prices"][1]["updated_at"] = "2026-10-01T00:00:00+00:00", "2026-10-09T00:00:00+00:00"
        mark_implausible(ok + [s], "EUR")
        self.assertEqual([p.get("plausible") for p in s["prices"]], [False, None])

    def test_octane_order_station_and_slot(self):
        ok = [st98(i, 1.80 + i % 5 * .01, 1.95 + i % 5 * .01) for i in range(30)]
        self.assertEqual(mark_implausible(ok + [st98(900, 1.80, 1.70)], "EUR"), {"octane_order": 1})
        bad = [st98(i, 1.80 + i % 5 * .01, 1.80 + i % 5 * .01) for i in range(30)]
        self.assertEqual(mark_implausible(bad, "EUR"), {"octane_order": 30})

    def test_normal_prices_untouched(self):
        S = crowd()
        self.assertEqual(mark_implausible(S, "EUR"), {})
        self.assertTrue(all("plausible" not in p for s in S for p in s["prices"]))

    def test_far_from_median_flagged_not_deleted(self):
        S = crowd() + [st(900, E10=4.49), st(901, E10=0.95)]
        c = mark_implausible(S, "EUR")
        self.assertEqual(S[-2]["prices"][0]["plausible"], False)
        self.assertEqual(S[-1]["prices"][0]["implausible_reason"], "far_from_country")
        self.assertEqual(len(S[-2]["prices"]), 1)           # still there
        self.assertEqual(sum(c.values()), 2)

    def test_absolute_band_for_small_countries(self):
        S = [st(1, E10=5.2)]
        self.assertEqual(mark_implausible(S, "EUR")["outside_eur_band"], 1)

    def test_non_eur_needs_fx(self):
        S = [{"id": "1", "prices": [{"fuel_type": "E10", "price": 25.0, "currency": "SEK", "octane": 95}]}]
        self.assertEqual(mark_implausible(S, "SEK", {}), {})                 # no rate -> no absolute check
        self.assertEqual(mark_implausible(S, "SEK", {"SEK": 11.0}), {})       # 2.27 EUR is fine
        S[0]["prices"][0]["price"] = 90.0
        self.assertEqual(mark_implausible(S, "SEK", {"SEK": 11.0})["outside_eur_band"], 1)

    def test_regulated_max_skips_median_rule(self):
        S = crowd() + [{"id": "r", "prices": [{"fuel_type": "E10", "price": 1.2, "currency": "EUR", "octane": 95, "basis": "regulated_max"}]}]
        mark_implausible(S, "EUR")
        self.assertNotIn("plausible", S[-1]["prices"][0])

    def test_inconsistent_fuels_flags_the_deviating_one(self):
        S = crowd() + [st(500, E10=1.83, DIESEL=2.7)]    # diesel 2.7 vs ~1.9 median; within 1.6x so only the ratio catches it
        mark_implausible(S, "EUR")
        bad = S[-1]["prices"]
        self.assertEqual(bad[1].get("implausible_reason"), "inconsistent_fuels")
        self.assertNotIn("plausible", bad[0])


if __name__ == "__main__":
    unittest.main()
