import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import seo_pages as sp  # noqa: E402

sp.TREND_BASE = None   # tests never touch the network


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


class TownPageUpgrade(unittest.TestCase):
    def _build(self, trend=None):
        import json, tempfile, pathlib
        from datetime import datetime, timezone
        st = [dict(id=f"b{i}", lat=50.8 + i * 0.001, lon=4.4, city="Brussel", brand="X", address="Rue 1",
                   prices=[dict(fuel_type="95", octane=95, price=1.70 + i * 0.01, currency="EUR", unit="L"),
                           dict(fuel_type="DIESEL", price=1.90 + i * 0.01, currency="EUR", unit="L")]) for i in range(6)]
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "be.json").write_text(json.dumps(dict(meta=dict(source="ANWB", fetched_at="2026-11-11T08:00:00+00:00"), stations=st)))
        old_dir, old_load = sp.DATA_DIR, sp.load_trend
        sp.DATA_DIR, sp.load_trend = d, lambda cc: trend or {}
        try:
            sp.build_country("be", dict(sp.COUNTRIES["be"], ceiling_share=0), datetime(2026, 11, 11, 9, tzinfo=timezone.utc))
        finally:
            sp.DATA_DIR, sp.load_trend = old_dir, old_load
        return d / "be"

    def test_title_has_prices_faq_trust_line_and_trend_file(self):
        import json
        out = self._build()
        html = (out / "brussel" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Diesel Brussel: vanaf 1,900 €/L · benzine vanaf 1,700 €/L", html)
        self.assertIn("FAQPage", html)
        self.assertIn("Gecontroleerd", html)
        t = json.loads((out / "trend.json").read_text())
        self.assertEqual(t["d"]["brussel"]["2026-11-11"]["DIESEL"], 1.925)

    def test_change_since_previous_day_is_shown(self):
        out = self._build({"brussel": {"2026-11-10": {"DIESEL": 1.90, "P95": 1.70}}})
        html = (out / "brussel" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Verandering sinds 10 nov: +0,025 €/L", html)

    def test_no_history_means_no_change_line(self):
        html = (self._build() / "brussel" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Verandering sinds", html)


class GermanAccuracyLine(unittest.TestCase):
    def test_footer_shows_measured_accuracy_when_the_file_exists(self):
        import json, tempfile, pathlib
        from datetime import datetime, timezone
        d = pathlib.Path(tempfile.mkdtemp())
        st = [dict(id=f"d{i}", lat=52.5 + i * 0.001, lon=13.4, city="Berlin", brand="X", address="Str 1",
                   prices=[dict(fuel_type="E10", octane=95, price=1.80, currency="EUR", unit="L"), dict(fuel_type="DIESEL", price=1.90, currency="EUR", unit="L")]) for i in range(5)]
        (d / "de.json").write_text(json.dumps(dict(meta=dict(source="anwb + tankerkoenig", fetched_at="2026-11-11T08:00:00+00:00"), stations=st)))
        (d / "de_accuracy.json").write_text(json.dumps({"summary": {"n": 26209, "within_1ct_pct": 85.3, "days": 2, "abs_p90_ct": 4.0}}))
        old_dir, old_load = sp.DATA_DIR, sp.load_trend
        sp.DATA_DIR, sp.load_trend = d, lambda cc: {}
        try:
            sp.build_country("de", dict(sp.COUNTRIES["de"]), datetime(2026, 11, 11, 9, tzinfo=timezone.utc))
        finally:
            sp.DATA_DIR, sp.load_trend = old_dir, old_load
        html = (d / "de" / "berlin" / "index.html").read_text(encoding="utf-8")
        self.assertIn("85,3 % von 26209 Stichproben", html)


if __name__ == "__main__":
    unittest.main()
