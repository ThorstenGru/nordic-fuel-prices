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


class MobileLayout(unittest.TestCase):
    """The video is seen on phones: the feed crops the middle 4:5 of the 9:16 frame and Reels covers the bottom. These tests draw the worst
    case (longest country names, longest notes) with the bundled DejaVu font, the one the GitHub runner draws with."""

    def _frames(self):
        import tempfile, pathlib
        from europe_index import NAMES
        longest = sorted(NAMES, key=lambda c: -len(NAMES[c]))[:5]
        note = "Median station price per litre; some figures are estimates or from unofficial sources"
        data = lambda t: dict(title=t, rows=[(NAMES[c], f"€{10.5 + i * 0.123:.2f}", 0.45 + 0.11 * i) for i, c in enumerate(longest)], note=note)   # noqa: E731
        border = dict(title="Border run of the week", border=dict(label="Petrol 95", cheap=NAMES[longest[0]], dear=NAMES[longest[1]], d=0.81), note=note)
        d = pathlib.Path(tempfile.mkdtemp())
        log = []
        for i, (k, sc, h, sub) in enumerate([("title", None, "Europe fuel prices this week", "Week 46, 11 Nov 2026"), ("data", data("Petrol 95: most expensive"), "", ""),
                                             ("data", data("Diesel: cheapest"), "", ""), ("data", border, "", ""), ("outro", None, "Full ranking and live map", "eurofuelprices.com")]):
            wk.render(sc, d / f"f{i}.png", k, h, sub, log=log)
        return log

    def test_nothing_leaves_the_safe_area(self):
        log = self._frames()
        self.assertGreater(len(log), 20)
        for t, x0, y0, x1, y1, size in log:
            self.assertGreaterEqual(x0, wk.SAFE_X - 4, t)
            self.assertLessEqual(x1, wk.W - wk.SAFE_X + 2, t)
            self.assertGreaterEqual(y0, wk.BAND_TOP - 6, t)
            self.assertLessEqual(y1, wk.BAND_BOT + 6, t)

    def test_text_stays_readable_on_a_phone(self):
        self.assertGreaterEqual(min(e[5] for e in self._frames()), wk.MIN_NOTE_PX)   # 36 px of 1080 is about 12 px on a 375 px wide phone

    def test_share_cards_never_run_off_the_right_edge(self):
        import tempfile, pathlib
        from PIL import Image
        from europe_index import NAMES, make_card
        d = pathlib.Path(tempfile.mkdtemp())
        L = sorted(NAMES, key=lambda c: -len(NAMES[c]))
        assert make_card(d / "c.png", f"Fuel prices: {NAMES[L[0]]} vs {NAMES[L[1]]}", f"Petrol 95 is €0.22/L cheaper in {NAMES[L[0]]}", "= €11.00 on a 50 L fill-up")
        im = Image.open(d / "c.png").convert("RGB")
        bg = im.getpixel((1190, 300))
        strip = [im.getpixel((x, y)) for x in range(1130, 1200) for y in range(0, 630, 3)]
        self.assertTrue(all(p == bg for p in strip))             # nothing drawn in the last 70 px: text wrapped instead of overflowing


if __name__ == "__main__":
    unittest.main()
