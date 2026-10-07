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
