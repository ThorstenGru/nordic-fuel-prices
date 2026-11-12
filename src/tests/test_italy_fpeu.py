import asyncio
import math
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers import italy  # noqa: E402


def km(a, b):
    return math.hypot((a[0] - b[0]) * 111.2, (a[1] - b[1]) * 111.2 * math.cos(math.radians(a[0])))


class Cover(unittest.TestCase):
    def test_children_cover_the_parent_square(self):
        lat, lon, r = 45.0, 9.0, 40.0
        half = r / math.sqrt(2)   # half side of the square the circle contains
        kids = italy.fpeu_split(lat, lon, r)
        self.assertEqual(len(kids), 4)
        for dy in (-1, 1):
            for dx in (-1, 1):   # the four corners of the parent square
                corner = (lat + dy * half / 111.2, lon + dx * half / (111.2 * math.cos(math.radians(lat))))
                self.assertTrue(any(km(corner, (k[0], k[1])) <= k[2] + 0.5 for k in kids))

    def test_cells_stay_within_the_api_radius_limit(self):
        self.assertTrue(all(c[2] <= 50 for c in italy.fpeu_cells()))


class Fetch(unittest.IsolatedAsyncioTestCase):
    async def test_full_answer_is_split_and_stations_are_deduped_and_mapped(self):
        sc = italy.ItalyScraper(None)
        sc.state_path = None
        calls = []

        def st(i):
            return {"id": i, "name": f"S{i}", "brand": "Eni", "address": "Via 1", "city": "ROMA", "lat": 41.9, "lng": 12.5,
                    "prices": {"diesel": {"price": 1.9, "ts": 1794242721}, "sp95": {"price": 1.7, "ts": 1794242721}, "lng": {"price": 2.0, "ts": 1}}}

        async def fake(lat, lon, r):
            calls.append(r)
            if len(calls) == 1:
                return [st(i) for i in range(italy.FPEU_CAP)]      # capped -> must be split into 4
            return [st(0), st(1)]                                  # duplicates across circles

        sc._fpeu_query = fake
        orig, italy.fpeu_cells = italy.fpeu_cells, lambda: [(41.9, 12.5, 40.0)]
        try:
            out = await sc._fetch_fpeu()
        finally:
            italy.fpeu_cells = orig
        self.assertEqual(len(calls), 5)                           # 1 capped + 4 children
        self.assertEqual(len(out), italy.FPEU_CAP)                # deduped by id
        types = {p["fuel_type"] for p in out[0]["prices"]}
        self.assertEqual(types, {"DIESEL", "E5"})                 # lng is not mapped
        self.assertIsNotNone(out[0]["prices"][0]["updated_at"])
        self.assertTrue(out[0]["id"].startswith("it_fp"))

    async def test_gives_up_after_repeated_api_failures(self):
        sc = italy.ItalyScraper(None)
        sc.state_path = None

        async def fail(lat, lon, r):
            return None

        sc._fpeu_query = fail
        self.assertEqual(await sc._fetch_fpeu(), [])

    async def test_failed_crawl_starts_a_cool_down_and_success_ends_it(self):
        import pathlib, tempfile
        sc = italy.ItalyScraper(None)
        sc.state_path = pathlib.Path(tempfile.mkdtemp()) / "it_crawl.json"
        calls = []

        async def fail(lat, lon, r):
            calls.append(1)
            return None

        sc._fpeu_query = fail
        await sc._fetch_fpeu()
        n = len(calls)
        self.assertGreater(n, 0)
        await sc._fetch_fpeu()                                  # within 3 h: no new crawl at all
        self.assertEqual(len(calls), n)
        sc._wall = lambda: time.time() + italy.FPEU_COOLDOWN_S + 60
        await sc._fetch_fpeu()                                  # cool-down over: tries again
        self.assertGreater(len(calls), n)


if __name__ == "__main__":
    unittest.main()
