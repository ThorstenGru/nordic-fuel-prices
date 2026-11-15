import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import wob_history as w  # noqa: E402


def rows(n=110):
    head = ["Consumer prices", "CTR", "EU_price_with_tax_euro95", "EU_price_with_tax_diesel", "SE_price_with_tax_euro95", "SE_price_with_tax_diesel",
            "UK_price_with_tax_euro95", "UK_price_with_tax_diesel", "XX_price_with_tax_euro95", "XX_price_with_tax_diesel"]
    out = [head, [None, None, "name"], ["Date", None, "1000 l"]]
    for i in range(n):                                   # newest first, like the workbook
        serial = 46000 - i * 7
        out.append([float(serial), "SE", 1700.0, 1900.0, 1500.0 + i, 1800.0 + i, 1600.0, 1700.0, 100.0, 5000.0])
    return out


class Wob(unittest.TestCase):
    def test_build(self):
        d = w.build(rows(), date(2026, 11, 15))
        self.assertEqual(len(d["dates"]), w.WEEKS)
        self.assertEqual(d["dates"], sorted(d["dates"]))                  # oldest first
        self.assertEqual(sorted(d["c"]), ["GB", "SE"])                    # UK renamed; EU aggregate dropped; XX has impossible prices
        self.assertEqual(d["c"]["SE"]["p"][-1], 1.5)                      # newest row i=0: 1500 EUR/1000 l = 1.5 EUR/l
        self.assertEqual(d["c"]["SE"]["p"][0], round((1500 + w.WEEKS - 1) / 1000, 3))

    def test_fresh(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "x.json"
            self.assertFalse(w.fresh(p, date(2026, 11, 15)))
            p.write_text(json.dumps({"updated": "2026-11-12"}), encoding="utf-8")
            self.assertTrue(w.fresh(p, date(2026, 11, 15)))
            self.assertFalse(w.fresh(p, date(2026, 11, 18)))


if __name__ == "__main__":
    unittest.main()
