import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chargers  # noqa: E402

NKEY = "test-nobil-key-fedcba9876543210"


def station(lat, lon, **kw):
    s = {"lat": lat, "lon": lon, "op": "", "kw": 11.0, "pts": 2, "flags": 0, "yr": 2024, "title": "T", "uc": "", "prov": 19, "ref": ""}
    s.update(kw)
    return s


def nobil_cs(i, lat, lon, conn="32", cap="11 kW - 400V 3-phase max 16A", **st):
    sta = {"2": {"attrvalid": "1", "trans": "Public"}}
    sta.update(st)
    return {"csmd": {"id": str(i), "International_id": f"SWE_{i}", "Street": "Kungsgatan", "House_number": "5", "City": "Lund",
                     "Owned_by": "Mer Sverige AB", "Position": f"({lat},{lon})", "Updated": "2025-03-01 10:00:00"},
            "attr": {"st": sta, "conn": {"1": {"4": {"attrvalid": conn, "trans": "Type 2"}, "5": {"attrvalid": "8", "trans": cap}}}}}


class Helpers(unittest.TestCase):
    def test_operator_alias(self):
        self.assertEqual(chargers.canon_op("Incharge (SE)"), "Vattenfall InCharge")
        self.assertEqual(chargers.canon_op("Mer Sverige AB"), "MER")
        self.assertEqual(chargers.canon_op("Unknown Op"), "Unknown Op")
        self.assertEqual(chargers.canon_op(None), "")

    def test_dedupe_keeps_richer_and_max_points(self):
        a = station(59.30000, 18.00000, pts=2)
        b = station(59.30010, 18.00000, pts=2, op="MER", flags=chargers.FLAG_COSTNOTE)       # 11 m away, richer
        c = station(59.31000, 18.00000)                                                       # far
        res, merged = chargers.dedupe([a, b, c])
        self.assertEqual((len(res), merged), (2, 1))
        self.assertEqual(res[0]["op"], "MER")
        self.assertEqual(res[0]["pts"], 2)                                                    # max, not 4


class Nobil(unittest.TestCase):
    def test_operator_is_the_network_not_the_property_owner(self):
        cs = nobil_cs(1, 55.7, 13.2)
        cs["csmd"]["Operator"] = "Vattenfall InCharge"          # who runs the post
        cs["csmd"]["Owned_by"] = "Vendelsö AB"                  # who owns it
        out, _ = chargers.reduce_nobil({"chargerstations": [cs]})
        self.assertEqual(out[0]["op"], "Vattenfall InCharge")
        out, _ = chargers.reduce_nobil({"chargerstations": [nobil_cs(2, 55.7, 13.2)]})   # no Operator field: falls back to the owner
        self.assertEqual(out[0]["op"], "MER")

    def test_reduce(self):
        doc = {"chargerstations": [
            nobil_cs(1, 55.7, 13.2, **{"7": {"attrvalid": "1", "trans": "Yes"}}),
            nobil_cs(2, 55.8, 13.2, conn="31"),                                                      # not Type 2
            nobil_cs(3, 55.9, 13.2, **{"2": {"attrvalid": "2", "trans": "Visitors"}}),               # not public
            nobil_cs(4, 56.0, 13.2, **{"21": {"attrvalid": "9", "trans": "Permanently closed"}}),    # closed
            nobil_cs(5, 56.1, 13.2, **{"19": {"attrvalid": "3", "trans": "Charging card"}})]}
        out, st = chargers.reduce_nobil(doc)
        self.assertEqual([o["ids"] for o in out], [{"1"}, {"5"}])
        self.assertEqual((st["noT2"], st["access"], st["closed"]), (1, 1, 1))
        self.assertEqual(out[0]["flags"], chargers.FLAG_NOBIL_PARK)
        self.assertEqual(out[1]["flags"], chargers.FLAG_MEMBER)
        self.assertEqual((out[0]["op"], out[0]["kw"], out[0]["yr"], out[0]["title"]), ("MER", 11.0, 2025, "Kungsgatan 5, Lund"))


class Build(unittest.TestCase):
    def test_schema(self):
        sts = [station(59.3, 18.0, op="MER", flags=32), station(59.4, 18.1, kw=None), station(10.0, 10.0)]  # last is outside SE
        f = chargers.build_file("SE", sts, date(2026, 11, 7))
        self.assertEqual((f["v"], f["cc"], f["generated"], f["n"], f["dropped_outside_box"]), (1, "SE", "2026-11-07", 2, 1))
        self.assertEqual(f["ops"], ["MER"])
        self.assertEqual(f["s"][0], [59.3, 18.0, 1, 11, 2, 32, 24, "T"])
        self.assertEqual(f["s"][1][2:4], [0, 0])
        self.assertEqual((f["sources"], f["source"], f["notes"]), (["NOBIL"], "nobil", []))
        self.assertEqual(f["medVerified"], 2024)
        self.assertTrue(any("NOBIL by Enova" in a and "CC BY 4.0" in a for a in f["attribution"]))
        self.assertFalse(any("Open Charge Map" in a for a in f["attribution"]))

    def test_guards(self):
        mk = lambda n, out=0: {"cc": "NO", "n": n, "dropped_outside_box": out, "s": []}
        prev = {"s": [0] * 2000}
        self.assertIsNone(chargers.check(mk(1900), prev, [NKEY]))
        self.assertIn("drop", chargers.check(mk(1500), prev, [NKEY]))
        self.assertIn("band", chargers.check(mk(500), None, [NKEY]))
        self.assertIn("box", chargers.check(mk(1900, 100), prev, [NKEY]))
        leaky = mk(1900)
        leaky["s"] = [[0, 0, 0, 0, 0, 0, 0, NKEY]]
        self.assertIn("key", chargers.check(leaky, prev, [NKEY]))
        self.assertIsNone(chargers.check(mk(1900), prev, ["", "short"]))                  # empty / short secrets never match

    def test_due(self):
        today = date(2026, 11, 7)
        self.assertTrue(chargers.due(None, today))
        self.assertTrue(chargers.due({}, today))
        self.assertFalse(chargers.due({"generated": "2026-11-01"}, today))              # 6 days
        self.assertTrue(chargers.due({"generated": "2026-10-31"}, today))               # 7 days
        self.assertFalse(chargers.due({"generated": "2026-10-31", "attempted": "2026-11-07"}, today))
        self.assertTrue(chargers.due({"generated": "2026-11-06"}, today, force=True))


def doc_of(n):
    return {"chargerstations": [nobil_cs(i, 56.0 + i * 0.001, 13.0 + i * 0.001) for i in range(n)]}


class Run(unittest.TestCase):
    """End to end with the network mocked: file written, key absent, last-good retained on a bad answer, frozen countries untouched."""

    def run_with(self, doc, prev_file=None, cc="SE", key=NKEY, force=True):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d)
            out = data / f"ev_{cc.lower()}.json"
            if prev_file:
                out.write_text(json.dumps(prev_file), encoding="utf-8")
            calls = []

            async def fake_prev(session, c):
                try:
                    return json.loads(out.read_text(encoding="utf-8"))
                except OSError:
                    return {}

            async def fake_get(session, url, headers, tag):
                calls.append(tag)
                return doc

            with mock.patch.object(chargers, "DATA", data), mock.patch.object(chargers, "get_json", fake_get), mock.patch.object(chargers, "fetch_prev", fake_prev), \
                    mock.patch.object(chargers, "CALL_GAP", 0), mock.patch.dict(os.environ, {"NOBIL_API_KEY": key}):
                n = asyncio.run(chargers.run([cc], force=force))
            return n, (out.read_text(encoding="utf-8") if out.exists() else None), calls

    def test_writes_clean_file(self):
        n, txt, calls = self.run_with(doc_of(2100))
        self.assertEqual((n, calls), (1, ["SE NOBIL"]))
        f = json.loads(txt)
        self.assertEqual((f["cc"], f["n"], f["sources"]), ("SE", 2100, ["NOBIL"]))
        self.assertNotIn(NKEY, txt)
        self.assertNotIn("apikey", txt.lower())
        self.assertNotIn("International_id", txt)

    def test_bad_answer_keeps_last_good(self):
        prev = {"v": 1, "cc": "SE", "generated": "2026-10-01", "s": [[56, 13, 0, 11, 2, 0, 24, "a"]] * 3000, "n": 3000}
        n, txt, _ = self.run_with(doc_of(10), prev_file=prev)                          # 10 usable stations: no usable answer
        self.assertEqual(n, 0)
        kept = json.loads(txt)
        self.assertEqual((kept["n"], len(kept["s"])), (3000, 3000))
        self.assertEqual(kept["attempted"], datetime.now(timezone.utc).date().isoformat())

    def test_shrunk_file_refused(self):
        prev = {"v": 1, "cc": "SE", "generated": "2026-10-01", "s": [[56, 13, 0, 11, 2, 0, 24, "a"]] * 4000, "n": 4000}
        n, txt, _ = self.run_with(doc_of(2100), prev_file=prev)                        # in band but 47 % lower
        self.assertEqual(n, 0)
        self.assertEqual(json.loads(txt)["n"], 4000)

    def test_not_due_republishes_without_calling_the_api(self):
        today = datetime.now(timezone.utc).date().isoformat()
        prev = {"v": 1, "cc": "SE", "generated": today, "s": [[56, 13, 0, 11, 2, 0, 24, "a"]] * 3000, "n": 3000}
        n, txt, calls = self.run_with(doc_of(2100), prev_file=prev, force=False)
        self.assertEqual((n, calls), (0, []))
        self.assertEqual(json.loads(txt)["n"], 3000)

    def test_frozen_countries_are_republished_untouched_even_when_forced(self):
        prev = {"v": 1, "cc": "DK", "generated": "2026-11-07", "s": [[55, 12, 0, 11, 2, 0, 24, "a"]] * 1500, "n": 1500}
        n, txt, calls = self.run_with(doc_of(2100), prev_file=prev, cc="DK")
        self.assertEqual((n, calls), (0, []))
        self.assertEqual(json.loads(txt), prev)                                        # no `attempted` stamp, no refresh: the old Open Charge Map file stays as published

    def test_crash_keeps_last_good_and_marks_attempt(self):
        prev = {"v": 1, "cc": "SE", "generated": "2026-10-01", "s": [[56, 13, 0, 11, 2, 0, 24, "a"]] * 3000, "n": 3000}
        with mock.patch.object(chargers, "reduce_nobil", side_effect=AttributeError("boom")):
            n, txt, _ = self.run_with(doc_of(2100), prev_file=prev)
        self.assertEqual(n, 0)
        kept = json.loads(txt)
        self.assertEqual(kept["n"], 3000)
        self.assertEqual(kept["attempted"], datetime.now(timezone.utc).date().isoformat())

    def test_no_key_changes_nothing(self):
        prev = {"v": 1, "cc": "SE", "generated": "2026-10-01", "s": [[56, 13, 0, 11, 2, 0, 24, "a"]] * 3000, "n": 3000}
        n, txt, calls = self.run_with(doc_of(2100), prev_file=prev, key="")
        self.assertEqual((n, calls), (0, []))
        self.assertEqual(json.loads(txt)["n"], 3000)

    def test_unreadable_previous_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []

            async def fake_prev(session, cc):
                return None

            async def fake_get(*a, **k):
                calls.append(a)
                return None

            with mock.patch.object(chargers, "DATA", Path(d)), mock.patch.object(chargers, "get_json", fake_get), mock.patch.object(chargers, "fetch_prev", fake_prev), \
                    mock.patch.object(chargers, "CALL_GAP", 0), mock.patch.dict(os.environ, {"NOBIL_API_KEY": NKEY}):
                n = asyncio.run(chargers.run(["SE"], force=True))
            self.assertEqual((n, calls), (0, []))
            self.assertFalse((Path(d) / "ev_se.json").exists())


if __name__ == "__main__":
    unittest.main()
