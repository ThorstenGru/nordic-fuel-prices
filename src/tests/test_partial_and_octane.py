import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers.spain import SpainScraper  # noqa: E402
from scrapers.portugal import PortugalScraper  # noqa: E402
from scrapers.slovenia import SloveniaScraper  # noqa: E402


class Resp:
    def __init__(self, status, body=None): self.status, self.body = status, body
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def json(self, content_type=None): return self.body


class Sess:
    def __init__(self, fn): self.fn = fn
    def get(self, url, **k): return self.fn(url, k)


ES = {"Fecha": "07/11/2026 10:00:00", "ListaEESSPrecio": [{
    "IDEESS": "1", "Rótulo": "X", "Dirección": "a", "Municipio": "m", "Provincia": "p", "C.P.": "1",
    "Latitud": "40,4", "Longitud (WGS84)": "-3,7", "Precio Gasoleo A": "1,50", "Precio Gasolina 95 E5": "1,60",
    "Precio Gasolina 98 E5": "1,80"}]}


class Octane(unittest.TestCase):
    def test_spain_keeps_95_and_98(self):
        sc = SpainScraper(Sess(lambda u, k: Resp(200, ES)))
        out = asyncio.run(sc.fetch_stations())
        octs = sorted(p.get("octane") for p in out[0]["prices"] if p["fuel_type"] == "E5")
        self.assertEqual(octs, [95, 98])


class Partial(unittest.TestCase):
    def test_portugal_core_fuel_failure_raises(self):
        def fn(url, k):
            return Resp(500) if k["params"]["idsTiposComb"] == 2101 else Resp(200, {"status": True, "resultado": []})
        with self.assertRaises(RuntimeError):
            asyncio.run(PortugalScraper(Sess(fn)).fetch_stations())

    def test_slovenia_error_between_pages_raises(self):
        calls = []

        def fn(url, k):
            calls.append(url)
            return Resp(200, {"results": [{"id": 1}], "next": "http://next"}) if len(calls) == 1 else Resp(500)
        with mock.patch("scrapers.slovenia.asyncio.sleep", new=lambda *_: asyncio.sleep(0)):
            with self.assertRaises(RuntimeError):
                asyncio.run(SloveniaScraper(Sess(fn)).fetch_stations())


if __name__ == "__main__":
    unittest.main()
