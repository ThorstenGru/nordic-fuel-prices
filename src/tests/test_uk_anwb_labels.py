import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers._anwb import ANWBScraper  # noqa: E402
from scrapers.united_kingdom import UnitedKingdomScraper  # noqa: E402


class UkAnwbLabels(unittest.TestCase):
    def test_95_is_e10_and_98_is_dropped(self):
        def price(ft, v, o=None):
            return {"fuel_type": ft, "price": v, "currency": "GBP", "unit": "L", "updated_at": None,
                    **({"octane": o} if o else {})}
        stub = [{"id": "gb_1", "prices": [price("95", 1.80, 95), price("98", 1.95, 98), price("DIESEL", 1.90)]}]
        with mock.patch.object(ANWBScraper, "fetch_stations", mock.AsyncMock(return_value=stub)):
            out = asyncio.run(UnitedKingdomScraper(None)._fetch_anwb())
        got = {(p["fuel_type"], p.get("octane")) for p in out[0]["prices"]}
        self.assertEqual(got, {("E10", 95), ("DIESEL", None)})


if __name__ == "__main__":
    unittest.main()
