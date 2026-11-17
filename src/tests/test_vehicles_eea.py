import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "vehicles"))
import build_from_eea as b  # noqa: E402


def row(mk, cn, regs, fc=5.0, wh=None):
    return {"Mk": mk, "Cn": cn, "Ft": "petrol", "Fm": "M", "regs": regs, "fc_l100": fc, "wh_km": wh, "co2_g_km": 120}


class BuildFromEea(unittest.TestCase):
    def test_same_model_under_two_make_spellings_is_merged_and_weighted(self):
        out = b.build({"petrol": [row("VOLKSWAGEN VW", "POLO", 100, 5.0), row("VOLKSWAGEN", "POLO", 300, 6.0)]})
        (r,) = out["petrol"]
        self.assertEqual((r["make"], r["model"], r["registrations_2024"], r["cons_l100"]), ("Volkswagen", "Polo", 400, 5.75))

    def test_plug_in_hybrid_never_gets_a_charge_sustaining_consumption(self):
        out = b.build({"phev": [row("VOLVO", "XC60", 50, 1.0, 190)]})
        (r,) = out["phev"]
        self.assertIsNone(r["cons_l100"])
        self.assertEqual((r["cons_wltp_weighted"], r["ev_kwh100"]), (1.0, 19.0))

    def test_make_prefix_is_dropped_from_the_model_and_rank_follows_registrations(self):
        out = b.build({"petrol": [row("TOYOTA", "TOYOTA YARIS", 10), row("DACIA", "SANDERO", 99)]})
        self.assertEqual([r["model"] for r in out["petrol"]], ["Sandero", "Yaris"])

    def test_checked_in_file_has_100_models_per_kind(self):
        f = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eea", "co2cars_2024Fv30_top.json")
        if not os.path.exists(f):
            self.skipTest("raw EEA extract not present")
        out = b.build(json.load(open(f, encoding="utf-8")))
        self.assertEqual(b.validate(out), [])


if __name__ == "__main__":
    unittest.main()
