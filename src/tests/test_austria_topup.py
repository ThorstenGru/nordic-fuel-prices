import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers.austria import AustriaScraper  # noqa: E402


def st(i, lat, lon, price, ft="DIESEL"):
    return {"id": f"at_{i}", "lat": lat, "lon": lon, "brand": "X", "prices": [{"fuel_type": ft, "price": price}]}


class TopUp(unittest.TestCase):
    def test_only_places_not_yet_seen_are_asked_and_new_stations_are_added(self):
        sc = AustriaScraper(None)
        merged = {"at_1": st(1, 48.2, 16.3, 1.9)}
        anwb = [{"lat": 48.2, "lon": 16.3}, {"lat": 47.1, "lon": 15.4}]          # the first is seen already, the second is not
        asked = []

        async def near(lat, lon, fuel, sem):
            asked.append((round(lat, 1), fuel))
            return [st(2, 47.1, 15.4, 1.8)] if fuel == "DIE" else [st(2, 47.1, 15.4, 1.7, "E5")]
        with mock.patch.object(AustriaScraper, "_near", side_effect=near):
            asyncio.run(sc._top_up(merged, anwb, asyncio.Semaphore(2)))
        self.assertEqual({a[0] for a in asked}, {47.1})                        # no request for the place that is covered
        self.assertEqual(sorted(merged), ["at_1", "at_2"])
        self.assertEqual({p["fuel_type"] for p in merged["at_2"]["prices"]}, {"DIESEL", "E5"})   # both fuels end up on one station

    def test_failed_request_does_not_stop_the_rest(self):
        sc = AustriaScraper(None)
        merged = {}
        async def near(lat, lon, fuel, sem):
            raise RuntimeError("down")
        with mock.patch.object(AustriaScraper, "_near", side_effect=near):
            asyncio.run(sc._top_up(merged, [{"lat": 47.1, "lon": 15.4}], asyncio.Semaphore(2)))
        self.assertEqual(merged, {})


if __name__ == "__main__":
    unittest.main()
