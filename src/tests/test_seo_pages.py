import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import seo_pages as sp  # noqa: E402


class JsonLd(unittest.TestCase):
    def test_script_end_in_a_name_cannot_close_the_block(self):
        cfg = sp.COUNTRIES["se"]
        html = sp.page(cfg, "T", "d", "https://x/", "H", "<p>b</p>", [{"name": "</script><b>x"}], "", "2026-11-07", "f")
        self.assertNotIn("</script><b>", html)
        self.assertIn("<\\/script>", html)


class NewCountries(unittest.TestCase):
    def test_every_country_has_its_language_texts(self):
        for cc, cfg in sp.COUNTRIES.items():
            self.assertIn(cfg["lang"], sp.TXT, cc)
            self.assertIn(cfg["lang"], sp.MONTHS, cc)
            sp.slugify("Łódź", cfg["lang"])   # must not raise

    def test_belgium_drops_the_legal_maximum_but_keeps_real_prices(self):
        import json, tempfile, pathlib
        from datetime import datetime, timezone
        st = [dict(id=f"b{i}", lat=50.8 + i * 0.001, lon=4.4, city="Brussel", brand="X",
                   prices=[dict(fuel_type="95", octane=95, price=1.842 if i else 1.70, currency="EUR", unit="L")]) for i in range(6)]
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "be.json").write_text(json.dumps(dict(meta=dict(source="ANWB", fetched_at="2026-11-11T08:00:00+00:00"), stations=st)))
        old = sp.DATA_DIR
        sp.DATA_DIR = d
        try:
            sp.build_country("be", dict(sp.COUNTRIES["be"]), datetime(2026, 11, 11, 9, tzinfo=timezone.utc))
        finally:
            sp.DATA_DIR = old
        html = (d / "be" / "brussel" / "index.html").read_text(encoding="utf-8")
        self.assertIn("1,700", html)
        self.assertNotIn("1,842", html)


if __name__ == "__main__":
    unittest.main()
