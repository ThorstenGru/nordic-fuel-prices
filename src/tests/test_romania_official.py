import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers import romania_official as ro  # noqa: E402
from scrapers.romania import RomaniaScraper  # noqa: E402


def station(i, lat=46.77, lon=23.59, upd="05/11/2026 14:30 "):
    return {"id": i, "name": f"S{i}", "updatedate": upd, "network": {"id": 1, "name": "Petrom"},
            "addr": {"addrstring": "Str. X 1", "location": {"Lat": lat, "Lon": lon}}, "uatid": 7}


def payload(n=1, price=7.5, lat=46.77, lon=23.59):
    sts = [station(i, lat + i * 1e-5, lon) for i in range(n)]
    return {"Stations": sts, "Products": [{"stationid": s["id"], "price": price} for s in sts]}


class Fixture(ro.MonitorulSource):
    """Replays canned replies instead of calling the network."""
    def __init__(self, replies, **kw):
        super().__init__(None, pace_s=0, **kw)
        self.replies, self.calls = replies, []

    async def _get(self, lat, lon, buffer, product):
        self.requests += 1
        self.calls.append((buffer, product, round(lat, 4)))
        return self.replies(lat, lon, buffer, product)


class Parse(unittest.TestCase):
    def test_row_and_bucharest_time(self):
        r = ro.parse_gas(payload(), "E5", "L")[0]
        self.assertEqual((r["brand"], r["price"], r["ft"]), ("Petrom", 7.5, "E5"))
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(ro.TZ)
            self.assertEqual(r["updated_at"], "2026-11-05T12:30:00+00:00")     # EET (UTC+2) in November
        except Exception:                                    # bare Windows without tzdata: iso_utc falls back to UTC
            self.assertEqual(r["updated_at"], "2026-11-05T14:30:00+00:00")

    def test_bad_rows_skipped(self):
        p = payload(2)
        p["Products"].pop()                                  # no price for station 1
        p["Stations"].append({"id": 9, "addr": {}})          # no location
        p["Stations"].append(station(10, lat=10.0))          # outside Romania
        p["Products"].append({"stationid": 10, "price": 7})
        self.assertEqual([r["sid"] for r in ro.parse_gas(p, "E5", "L")], [0])
        self.assertEqual(ro.parse_gas({}, "E5", "L"), [])
        self.assertEqual(ro.parse_gas(None, "E5", "L"), [])


class Tiling(unittest.TestCase):
    def test_cells_are_deduplicated_and_seeded(self):
        self.assertEqual(len(ro.plan_tiles([(46.77, 23.59), (46.7701, 23.5901)])), 1)
        self.assertGreater(len(ro.plan_tiles([])), 5)        # empty start -> county-seat seeds

    def test_budget_and_one_product_per_call(self):
        src = Fixture(lambda *a: payload(), budget=6)
        out = asyncio.run(src.fetch([(46.77 + 0.1 * k, 23.59) for k in range(10)], slot=0))
        self.assertEqual(src.requests, 6)
        self.assertTrue(all(p in ro.PRODUCTS for _, p, _ in src.calls))
        self.assertTrue(out)

    def test_cap_is_split_once_into_smaller_circles(self):
        def reply(lat, lon, buffer, product):
            return payload(50) if buffer == ro.BUFFER_M and product == "11" else payload(1)
        src = Fixture(reply, budget=100)
        asyncio.run(src.fetch([(46.77, 23.59)], slot=0))
        self.assertEqual(sum(1 for b, p, _ in src.calls if b == ro.BUFFER_M // 2), 4)

    def test_slices_rotate(self):
        known = [(44.0 + 0.1 * k, 25.0) for k in range(30)]
        a, b = Fixture(lambda *x: payload(), budget=9), Fixture(lambda *x: payload(), budget=9)
        seen = []
        for src, slot in ((a, 0), (b, 1)):
            asyncio.run(src.fetch(known, slot))
            seen.append(src.calls)
        self.assertEqual(len(ro.plan_tiles(known)), 30)
        self.assertNotEqual(seen[0], seen[1])


class Switch(unittest.TestCase):
    def run_mode(self, mode, peco_entries, official):
        sc = RomaniaScraper(None)

        async def load(): return {}

        async def county(*a, **k): return peco_entries

        class Src:
            def __init__(self, *a, **k): pass
            async def fetch(self, known, slot): return official
        sc._load_previous, sc._fetch_county = load, county
        real = asyncio.sleep
        env = {} if mode is None else {"ROMANIA_SOURCE": mode}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch("scrapers.romania.MonitorulSource", Src), \
                mock.patch("asyncio.sleep", new=lambda *_: real(0)):
            if mode is None:
                os.environ.pop("ROMANIA_SOURCE", None)
            return asyncio.run(sc.fetch_stations())

    PECO = [("Petrom", 46.7700, 23.5900, "Cluj", "Str A", 7.4)]
    OFFICIAL = {"1": {"name": "Petrom 1", "brand": "Petrom", "address": "Str A", "lat": 46.7701, "lon": 23.5901,
                      "prices": {"DIESEL": (7.6, "L", "2026-11-05T12:30:00+00:00")}}}

    def test_default_is_peco_and_never_touches_official(self):
        out = self.run_mode(None, self.PECO, self.OFFICIAL)
        self.assertEqual({s["source"] for s in out}, {"peco-online.ro"})

    def test_official_only_uses_its_own_timestamp(self):
        out = self.run_mode("official", self.PECO, self.OFFICIAL)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "monitorulpreturilor.info")
        self.assertEqual(out[0]["prices"][0]["updated_at"], "2026-11-05T12:30:00+00:00")

    def test_both_prefers_official_within_150m(self):
        out = self.run_mode("both", self.PECO, self.OFFICIAL)
        self.assertEqual([s["source"] for s in out], ["monitorulpreturilor.info"])

    def test_unknown_value_falls_back_to_peco(self):
        out = self.run_mode("bogus", self.PECO, self.OFFICIAL)
        self.assertEqual({s["source"] for s in out}, {"peco-online.ro"})


if __name__ == "__main__":
    unittest.main()
