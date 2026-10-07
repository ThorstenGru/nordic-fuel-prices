import unittest
from datetime import date

from scrapers.montenegro import parse_govme_article
from scrapers.north_macedonia import parse_gorivo_mk, validate_cap


class GovMe(unittest.TestCase):
    HTML = "<p><strong>EUROSUPER 98: 1,81 €/l (+0,02)</strong><br>EUROSUPER 95: 1,77 €/l (+0,02)<br>EURODIZEL: 1,96 €/l (+0,01)</p>"

    def test_parse(self):
        r = parse_govme_article(self.HTML, "Nove cijene goriva od 06.10.2026", date(2026, 10, 7))
        self.assertEqual(r["prices"], {"DIESEL": 1.96, "95": 1.77, "98": 1.81})
        self.assertEqual(r["date"], "2026-10-06")

    def test_stale_or_bad_title(self):
        self.assertIsNone(parse_govme_article(self.HTML, "Nove cijene goriva od 06.08.2026", date(2026, 10, 7)))
        self.assertIsNone(parse_govme_article(self.HTML, "Saopštenje", date(2026, 10, 7)))

    def test_implausible(self):
        bad = self.HTML.replace("1,77", "17,7")
        self.assertIsNone(parse_govme_article(bad, "Nove cijene goriva od 06.10.2026", date(2026, 10, 7)))


class GorivoMk(unittest.TestCase):
    HTML = ("<div>Цена на бензин 98,5 ден - 1,5 ден</div><div>Цена на бензин 98+ 100,5 ден - 1,5 ден</div>"
            "<div>Цена на дизел 97,0 ден - 3,0 ден</div>")

    def test_parse(self):
        r = parse_gorivo_mk(self.HTML, date(2026, 10, 7))
        self.assertEqual(r["prices"], {("95", 95): 98.5, ("98", 98): 100.5, ("DIESEL", None): 97.0})
        self.assertIsNone(validate_cap(r, date(2026, 10, 7)))


if __name__ == "__main__":
    unittest.main()


class IsraelCapGuard(unittest.TestCase):
    CAP = {"effective": "2026-10-05", "guard": {"excise_petrol_kl": 2809.06, "refinery_95_pipeline_kl": 3110.44}}

    def test_valid_and_invalidated(self):
        from scrapers.israel import cap_is_valid
        d = date(2026, 10, 20)
        self.assertIsNone(cap_is_valid(self.CAP, 2809.06, 3110.44, d))
        self.assertIn("excise", cap_is_valid(self.CAP, 3232.79, 3110.44, d))
        self.assertIn("refinery", cap_is_valid(self.CAP, 2809.06, 3200.0, d))
        self.assertIn("unavailable", cap_is_valid(self.CAP, None, 3110.44, d))
        self.assertIn("days old", cap_is_valid(self.CAP, 2809.06, 3110.44, date(2026, 12, 1)))


class AlbaniaCap(unittest.TestCase):
    CAP = {"decision_date": "2026-10-07", "retail_max_lek": {"DIESEL": 210, "95": 190}}

    def test_age_and_convert(self):
        from scrapers.albania import cap_age_ok, to_eur_cap
        self.assertIsNone(cap_age_ok(self.CAP, date(2026, 10, 20)))
        self.assertIn("days old", cap_age_ok(self.CAP, date(2026, 10, 25)))
        self.assertEqual(to_eur_cap(self.CAP, 100.0)["prices"], {"DIESEL": 2.1, "95": 1.9})
