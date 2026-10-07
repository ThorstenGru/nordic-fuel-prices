"""Tests for the regulated-maximum fill in MK / LU scrapers.  Run: python -m unittest src.tests.test_cap_mk_lu"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from merge_engine import MergeConfig, merge_sources  # noqa: E402
from scrapers import luxembourg as lu, north_macedonia as mk  # noqa: E402

TODAY = date(2026, 10, 7)
CY = "ЕУРОСУПЕР БС - "
HTML = ("<div id='CeniLista'><table><tr><td> " + CY + "95</td><td>98.5 ден/л</td></tr>"
        "<tr><td> ЕУРОДИЗЕЛ БС (Д-Е V)</td>"
        "<td>97 ден/л</td></tr><tr><td> " + CY + "98 </td><td>100.5 ден/л</td></tr>"
        "</table></div><a href='odluki/22026.10.05-Odluka za ceni na ND.pdf'>x</a>"
        "<a href='odluki/2026.09.28 Odluka za ceni na ND.pdf'>y</a>")


class _S:      # minimal stand-in for scraper instance (price_entry only)
    CURRENCY = "MKD"
    CONFIDENCE = 0.9
    price_entry = mk.NorthMacedoniaScraper.price_entry
    build_cap_result = mk.NorthMacedoniaScraper.build_cap_result

    def __init__(self, cur="MKD"):
        self.CURRENCY = cur


class MKTests(unittest.TestCase):
    def test_parse_and_validate(self):
        p = mk.parse_erc_homepage(HTML)
        self.assertEqual(p["prices"], {("95", 95): 98.5, ("DIESEL", None): 97.0, ("98", 98): 100.5})
        self.assertEqual(p["date"], date(2026, 10, 5))
        self.assertIsNone(mk.validate_cap(p, TODAY))

    def test_rejections(self):
        p = mk.parse_erc_homepage(HTML)
        self.assertIn("30 days", mk.validate_cap(p, date(2026, 12, 1)))
        p2 = dict(p, prices=dict(p["prices"], **{}))
        p2["prices"][("DIESEL", None)] = 5.0
        self.assertIn("band", mk.validate_cap(p2, TODAY))
        self.assertIn("missing", mk.validate_cap({"prices": {}, "date": TODAY}, TODAY))
        self.assertIn("no effective date", mk.validate_cap(dict(p, date=None), TODAY))

    def test_fill_only_missing(self):
        anwb = [{"id": "a", "country": "MK", "name": "X", "brand": "X", "lat": 42.0, "lon": 21.5, "prices": [
                    {"fuel_type": "DIESEL", "price": 1.5, "currency": "EUR", "unit": "L", "updated_at": None}]},
                {"id": "b", "country": "MK", "name": "Y", "brand": "Y", "lat": 41.5, "lon": 21.0, "prices": []}]
        cap = mk.parse_erc_homepage(HTML)
        res = _S("EUR").build_cap_result(anwb, cap)
        self.assertEqual(res.kind, "regulated_cap")
        self.assertEqual(res.priority, 20)
        from merge_engine import SourceResult
        merged, rep = merge_sources([SourceResult("anwb", "ANWB", anwb, 9, "aggregator", "EUR"), res], MergeConfig(country="MK"))
        by = {s["id"]: s for s in merged}
        d = [p for p in by["a"]["prices"] if p["fuel_type"] == "DIESEL"][0]
        self.assertEqual(d["price"], 1.5)
        self.assertNotIn("basis", d)
        f = [p for p in by["a"]["prices"] if p["fuel_type"] == "95"][0]
        self.assertEqual(f["basis"], "regulated_max")
        self.assertAlmostEqual(f["price"], 1.602, places=3)
        self.assertEqual(f["currency"], "EUR")
        self.assertEqual(len(by["b"]["prices"]), 3)


LU_CSV = ("DATAFLOW,MEASURE,UNIT_MEASURE,FREQ,MOTOR_ENERGY,TIME_PERIOD,OBS_VALUE\n"
          "x,PRIX,EUR_LI,I,SP98,2026-10-02,2.015\nx,PRIX,EUR_LI,I,SP98,2026-10-03,2.049\n"
          "x,PRIX,EUR_LI,I,SP95,2026-10-03,1.837\nx,PRIX,EUR_LI,I,DIE,2026-10-06,1.995\n")


class LUTests(unittest.TestCase):
    def test_lustat_parse(self):
        s = lu.parse_lustat_csv(LU_CSV)
        self.assertEqual(s[("98", 98)], (2.049, date(2026, 10, 3)))
        self.assertEqual(s[("DIESEL", None)], (1.995, date(2026, 10, 6)))
        self.assertIsNone(lu.validate_cap(s, TODAY))

    def test_stale_and_band(self):
        s = lu.parse_lustat_csv(LU_CSV)
        self.assertIn("30 days", lu.validate_cap(s, date(2026, 11, 20)))
        s[("95", 95)] = (9.0, date(2026, 10, 3))
        self.assertIn("band", lu.validate_cap(s, TODAY))

    def test_spritpreise(self):
        html = ("Diesel 1,995 € par litre Super 95 (E10) 1,837 € par litre Super 98 (Super Plus) 2,049 € "
                "Prix en vigueur depuis le 06/10/2026")
        s = lu.parse_spritpreise(html)
        self.assertEqual(s[("95", 95)], (1.837, date(2026, 10, 6)))
        self.assertEqual(s[("DIESEL", None)][0], 1.995)


if __name__ == "__main__":
    unittest.main()
