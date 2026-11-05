import json
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "web" / "vehicles.json"
# Shortfall: no public Europe-wide source gives 20 PHEVs (only 16 candidates found, 10 ranked).
EXPECTED = {"petrol": 20, "diesel": 20, "phev": 16}
FIELDS = {"id", "make", "model", "variant", "type", "hybrid", "rank", "tank_l", "cons_l100",
          "battery_kwh", "range_km", "ev_kwh100", "confidence", "source", "notes"}


class VehiclesJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(PATH.read_text(encoding="utf-8"))

    def test_shape(self):
        self.assertEqual(self.d["version"], 1)
        self.assertEqual(set(self.d["categories"]), set(EXPECTED))
        for e in [v for l in self.d["categories"].values() for v in l] + self.d["hyundai"]:
            self.assertEqual(set(e), FIELDS, e["id"])
            self.assertIn(e["confidence"], ("high", "medium", "low"), e["id"])

    def test_counts(self):
        for c, n in EXPECTED.items():
            self.assertEqual(len(self.d["categories"][c]), n, c)
        self.assertTrue(all(v["make"] == "Hyundai" for v in self.d["hyundai"]))

    def test_ids_unique_and_shared_identical(self):
        for l in list(self.d["categories"].values()) + [self.d["hyundai"]]:
            ids = [v["id"] for v in l]
            self.assertEqual(len(ids), len(set(ids)))
        byid = {v["id"]: v for l in self.d["categories"].values() for v in l}
        for h in self.d["hyundai"]:
            if h["id"] in byid:
                self.assertEqual(byid[h["id"]], h)

    def test_ranked_order(self):
        for l in self.d["categories"].values():
            r = [v["rank"] for v in l if v["rank"] is not None]
            self.assertEqual(r, sorted(r))

    def test_phev_nulls_flagged_low(self):
        for v in self.d["categories"]["phev"]:
            if v["battery_kwh"] is None or v["range_km"] is None:
                self.assertEqual(v["confidence"], "low", v["id"])

    def test_phev_cons_is_petrol_only(self):
        for v in self.d["categories"]["phev"] + [h for h in self.d["hyundai"] if h["type"] == "phev"]:
            if v["cons_l100"] is not None:
                self.assertGreaterEqual(v["cons_l100"], 3.5, v["id"])


if __name__ == "__main__":
    unittest.main()
