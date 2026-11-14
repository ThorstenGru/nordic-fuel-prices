import asyncio
import json
import os
import sys
import tempfile
import unittest
import zlib
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chargefinder as cf  # noqa: E402

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover
    AESGCM = None

KEY = "k" * 32


def enc(lst, key=KEY):
    iv = os.urandom(12)
    ct = AESGCM(key.encode()).encrypt(iv, zlib.compress(json.dumps(lst).encode()), None)
    return {"i": iv.hex(), "e": ct[:-16].hex(), "a": ct[-16:].hex()}


def st(i, lat, lon, cc="DK", **kw):
    s = {"slug": f"s{i}", "location": {"latitude": lat, "longitude": lon}, "locationAddress": {"countryCode": cc, "street": "Vej 1", "city": "By"},
         "plugType2": 2, "maxCapacity": 22, "access": "Public", "operator": "Clever"}
    s.update(kw)
    return s


class Pure(unittest.TestCase):
    def test_geohash_known(self):
        self.assertEqual(cf.geohash(57.64911, 10.40744, 7), "u4pruyd")

    def test_box_url_is_ne_then_sw(self):
        u = cf.box_url(55.0, 56.0, 12.0, 13.0)
        self.assertEqual(u, f"{cf.API}/{cf.geohash(56.0, 13.0)}-{cf.geohash(55.0, 12.0)}?exact=1")

    @unittest.skipIf(AESGCM is None, "cryptography missing")
    def test_decode(self):
        self.assertEqual(cf.decode(enc([{"a": 1}]), KEY), [{"a": 1}])
        self.assertIsNone(cf.decode(enc([{"a": 1}]), "x" * 32))          # wrong key
        self.assertIsNone(cf.decode({"error": "x"}, KEY))                 # not encrypted
        self.assertIsNone(cf.decode(enc({"a": 1}), KEY))                  # not a list

    def test_reduce(self):
        r = cf.reduce_station(st(1, 55.5, 12.5, freeCharging=1, authCard=1), "DK", 2026)
        self.assertEqual((r["op"], r["kw"], r["pts"], r["flags"], r["title"]), ("Clever", 22.0, 2, 3, "Vej 1, By"))
        self.assertIsNone(cf.reduce_station(st(2, 55.5, 12.5, plugType2=0), "DK", 2026))           # no Type 2
        self.assertIsNone(cf.reduce_station(st(3, 55.5, 12.5, access="Visitors"), "DK", 2026))     # not public
        self.assertIsNone(cf.reduce_station(st(4, 55.5, 12.5, cc="SE"), "DK", 2026))               # other country

    def test_split_and_seed_cover_the_box(self):
        b = (54.5, 57.9, 7.9, 15.3)
        self.assertEqual(len(cf.split4(b)), 4)
        seeds = cf.seed_boxes(b)
        self.assertEqual((min(x[0] for x in seeds), max(x[1] for x in seeds), min(x[2] for x in seeds), max(x[3] for x in seeds)), b)


@unittest.skipIf(AESGCM is None, "cryptography missing")
class Run(unittest.TestCase):
    def go(self, answers, prev=None, force=True, key=KEY):
        """answers: function(url) -> (status, json). Returns (written, file text or None)."""
        class R:
            def __init__(self, status, body):
                self.status, self.body = status, body

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def json(self, content_type=None):
                return self.body

        class S:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            def get(self, url, **k):
                return R(*answers(url))

        async def nosleep(*a):
            return None

        with tempfile.TemporaryDirectory() as d, mock.patch.object(cf.aiohttp, "ClientSession", S), mock.patch.object(cf.asyncio, "sleep", nosleep), mock.patch.object(cf, "seed_boxes", lambda b: [b]), \
                mock.patch.dict(cf.COUNTRIES, {"DK": ("DK", (5, 50), (55.0, 56.0, 12.0, 13.0))}):
            p = Path(d) / "ev_dk.json"
            if prev:
                p.write_text(json.dumps(prev), encoding="utf-8")
            n = asyncio.run(cf.run(["DK"], Path(d), key, force))
            return n, (p.read_text(encoding="utf-8") if p.exists() else None)

    def good(self, url):
        return 200, enc([st(i, 55.1 + i * 0.01, 12.1 + i * 0.01) for i in range(10)])

    def test_writes_file_without_key(self):
        n, txt = self.go(self.good)
        self.assertEqual(n, 1)
        f = json.loads(txt)
        self.assertEqual((f["cc"], f["n"], f["sources"]), ("DK", 10, ["ChargeFinder"]))
        self.assertNotIn(KEY, txt)

    def test_403_stops_and_keeps_last_good(self):
        prev = {"v": 1, "cc": "DK", "generated": "2026-10-01", "n": 20, "s": []}
        n, txt = self.go(lambda u: (403, {}), prev=prev)
        self.assertEqual(n, 0)
        kept = json.loads(txt)
        self.assertEqual(kept["n"], 20)
        self.assertIn("attempted", kept)

    def test_decoy_answer_is_refused(self):
        far = enc([st(i, 40.0 + i * 0.01, 3.0) for i in range(10)])    # stations nowhere near the box
        self.assertEqual(self.go(lambda u: (200, far))[0], 0)            # no station in the box: nothing usable

    def test_big_drop_refused(self):
        prev = {"v": 1, "cc": "DK", "generated": "2026-10-01", "n": 40, "s": []}
        n, txt = self.go(self.good, prev=prev)                          # 10 < 80 % of 40
        self.assertEqual((n, json.loads(txt)["n"]), (0, 40))

    def test_not_due_is_left_alone(self):
        prev = {"v": 1, "cc": "DK", "generated": date.today().isoformat(), "n": 40, "s": []}
        n, txt = self.go(self.good, prev=prev, force=False)
        self.assertEqual((n, json.loads(txt)), (0, prev))


if __name__ == "__main__":
    unittest.main()
