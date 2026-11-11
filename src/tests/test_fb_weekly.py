import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import fb_weekly as wk  # noqa: E402


def doc(countries):
    rows = []
    for i, c in enumerate(countries):
        for fuel, base in (("p95", 1.5), ("diesel", 1.6)):
            rows.append(dict(country=c, name=c, fuel=fuel, median_eur_per_litre=base + i * 0.05, stations=500, source_grade="A"))
    return {"updated": "2026-11-11 06:30Z", "rows": rows}


class Weekly(unittest.TestCase):
    def test_four_data_scenes_with_enough_countries(self):
        sc = wk.scenes(doc(["SE", "DK", "DE", "FR", "ES", "PL", "AT", "NO", "FI", "NL"]))
        self.assertEqual(len(sc), 4)
        self.assertEqual(len(sc[0]["rows"]), 5)
        self.assertNotIn("estimates", sc[0]["note"])   # all grade A

    def test_too_little_data_gives_no_video(self):
        self.assertEqual(wk.scenes(doc(["SE", "DK", "DE"])), [])

    def test_week_key_is_iso_week(self):
        self.assertEqual(wk.week_key(date(2026, 11, 15)), "2026-W46")


if __name__ == "__main__":
    unittest.main()
