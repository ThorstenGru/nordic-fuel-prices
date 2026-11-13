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

KEY = "test-ocm-key-0123456789abcdef"
NKEY = "test-nobil-key-fedcba9876543210"
OPS = {1: "MER", 2: "Incharge (SE)", 3: "Some Operator AB"}
PROVS = {1: ("Open Charge Map Contributors", "CC BY 4.0"), 19: ("NOBIL by Enova", "CC BY 4.0"), 29: ("Bundesnetzagentur", "CC BY 4.0")}


def poi(lat, lon, conns=((25, 11),), **kw):
    p = {"ID": int(lat * 1e4), "DataProviderID": 1, "UsageTypeID": None, "StatusTypeID": None, "DateLastVerified": "2024-02-10T00:00:00Z",
         "AddressInfo": {"Title": "Storgatan 1", "Latitude": lat, "Longitude": lon},
         "Connections": [{"ConnectionTypeID": t, "PowerKW": k, "Quantity": 2} for t, k in conns]}
    p.update(kw)
    return p


def red(pois):
    return chargers.reduce_ocm(pois, OPS)


class OcmFilter(unittest.TestCase):
    def test_filters(self):
        pois = [poi(59.30, 18.0),                                                    # kept
                poi(59.31, 18.0, conns=((33, 50),)),                                 # CCS only
                poi(59.32, 18.0, conns=((25, 11), (33, 50)), OperatorID=1),          # kept, the CCS connector is ignored
                poi(59.33, 18.0, UsageTypeID=2),                                     # private
                poi(59.34, 18.0, StatusTypeID=150),                                  # planned
                poi(59.35, 18.0, DataProviderID=26),                                 # NonCommercial licence
                poi(59.36, 18.0, UsageTypeID=0)]                                     # unknown usage is kept
        out, st = red(pois)
        self.assertEqual(len(out), 3)
        self.assertEqual((st["noT2"], st["usage"], st["status"], st["provider"]), (1, 1, 1, 1))
        self.assertEqual(out[1]["op"], "MER")
        self.assertEqual((out[1]["kw"], out[1]["pts"]), (11, 2))

    def test_flags(self):
        f = lambda **kw: red([poi(59.3, 18.0, **kw)])[0][0]["flags"]
        self.assertEqual(f(UsageCost="Free of charge"), chargers.FLAG_FREE | chargers.FLAG_COSTNOTE)
        self.assertEqual(f(UsageCost="First hour is free, then 20 SEK"), chargers.FLAG_COSTNOTE)      # other number: not free
        for txt in ("Not free", "No free charging", "Free for customers only", "Free for customers", "Kostenlos nur für Kunden", "Gratis parkering",
                    "Ingen avgift for parkering", "Free parking, charging billed via app", "Gratis parkering, laddning kostar via app",
                    "Kostenlos parken, Laden kostenpflichtig", "Charging is not free of charge", "Free during opening hours only"):
            self.assertEqual(f(UsageCost=txt) & chargers.FLAG_FREE, 0, txt)
        for txt in ("Free", "gratis.", "Kostenlos", "Free of charge", "Ingen avgift"):
            self.assertTrue(f(UsageCost=txt) & chargers.FLAG_FREE, txt)
        self.assertEqual(f(UsageCost="0"), chargers.FLAG_COSTNOTE)                                    # bare 0 is ambiguous
        self.assertEqual(f(UsageTypeID=4), chargers.FLAG_MEMBER)
        self.assertEqual(f(UsageTypeID=7), chargers.FLAG_NOTICE)
        self.assertEqual(f(UsageTypeID=5), chargers.FLAG_PAYLOC)
        self.assertEqual(f(GeneralComments="pay parking fee"), chargers.FLAG_PARKHINT)
        self.assertEqual(f(GeneralComments="near the parking lot"), 0)
        self.assertEqual(f(UsageCost="Gratis", AddressInfo={"Latitude": 59.3, "Longitude": 18.0, "AccessComments": "Parkeringsavgift"}),
                         chargers.FLAG_FREE | chargers.FLAG_COSTNOTE | chargers.FLAG_PARKHINT)
        self.assertEqual(red([poi(59.3, 18.0, conns=((1036, 3.6),))])[0][0]["flags"], chargers.FLAG_TETHERED)

    def test_dedupe_keeps_richer_and_max_points(self):
        a = poi(59.30000, 18.00000, DataProviderID=19)
        b = poi(59.30010, 18.00000, OperatorID=1, UsageCost="2 SEK/kWh")                 # 11 m away, richer
        c = poi(59.31000, 18.00000)                                                       # far
        out, _ = red([a, b, c])
        res, merged = chargers.dedupe(out)
        self.assertEqual((len(res), merged), (2, 1))
        self.assertEqual(res[0]["op"], "MER")
        self.assertEqual(res[0]["pts"], 2)                                                # max, not 4

    def test_operator_alias(self):
        self.assertEqual(chargers.canon_op("Incharge (SE)"), "Vattenfall InCharge")
        self.assertEqual(chargers.canon_op("Mer Sverige AB"), "MER")
        self.assertEqual(chargers.canon_op("Unknown Op"), "Unknown Op")
        self.assertEqual(chargers.canon_op(None), "")


def nobil_cs(i, lat, lon, conn="32", cap="11 kW - 400V 3-phase max 16A", **st):
    sta = {"2": {"attrvalid": "1", "trans": "Public"}}
    sta.update(st)
    return {"csmd": {"id": str(i), "International_id": f"SWE_{i}", "Street": "Kungsgatan", "House_number": "5", "City": "Lund",
                     "Owned_by": "Mer Sverige AB", "Position": f"({lat},{lon})", "Updated": "2025-03-01 10:00:00"},
            "attr": {"st": sta, "conn": {"1": {"4": {"attrvalid": conn, "trans": "Type 2"}, "5": {"attrvalid": "8", "trans": cap}}}}}


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

    def test_merge(self):
        ocm, _ = red([
            poi(55.70001, 13.2, DataProviderID=19, DataProvidersReference="SWE_1", UsageCost="Free", GeneralComments=None),   # matched by id
            poi(55.90000, 13.2, DataProviderID=19, DataProvidersReference="99"),                                                  # NOBIL removed it
            poi(56.50000, 14.0, DataProviderID=1, OperatorID=3),                                                                  # contributor only
            poi(56.10001, 13.2, DataProviderID=19)])                                                                              # matched by position
        nob, _ = chargers.reduce_nobil({"chargerstations": [nobil_cs(1, 55.7, 13.2), nobil_cs(5, 56.1, 13.2), nobil_cs(7, 57.0, 13.2)]})
        res, st = chargers.merge_nobil(ocm, nob)
        self.assertEqual(st, {"matched": 2, "nobil_only": 1, "ocm_only": 1, "ocm_dropped": 1})
        self.assertEqual(len(res), 4)
        first = res[0]
        self.assertEqual((first["op"], first["uc"]), ("MER", "Free"))
        self.assertTrue(first["flags"] & chargers.FLAG_FREE)
        self.assertNotIn("ids", first)


def station(lat, lon, **kw):
    s = {"lat": lat, "lon": lon, "op": "", "kw": 11.0, "pts": 2, "flags": 0, "yr": 2024, "title": "T", "uc": "", "prov": 1, "ref": ""}
    s.update(kw)
    return s


class Build(unittest.TestCase):
    def test_schema(self):
        sts = [station(59.3, 18.0, op="MER", uc="x" * 100, flags=32), station(59.4, 18.1, kw=None, prov=19), station(10.0, 10.0)]  # last is outside SE
        f = chargers.build_file("SE", sts, date(2026, 11, 7), PROVS, nobil=True)
        self.assertEqual((f["v"], f["cc"], f["generated"], f["n"], f["dropped_outside_box"]), (1, "SE", "2026-11-07", 2, 1))
        self.assertEqual(f["ops"], ["MER"])
        self.assertEqual(f["s"][0], [59.3, 18.0, 1, 11, 2, 32, 24, "T"])
        self.assertEqual(f["s"][1][2:4], [0, 0])
        self.assertEqual(f["notes"], [[0, "x" * 80]])
        self.assertEqual(f["sources"], ["OCM", "NOBIL"])
        self.assertEqual(f["source"], "ocm+nobil")
        self.assertEqual(f["medVerified"], 2024)
        self.assertTrue(any("NOBIL by Enova" in a and "CC BY 4.0" in a for a in f["attribution"]))

    def test_guards(self):
        mk = lambda n, out=0: {"cc": "DK", "n": n, "dropped_outside_box": out, "s": []}
        prev = {"s": [0] * 2000}
        self.assertIsNone(chargers.check(mk(1900), prev, [KEY]))
        self.assertIn("drop", chargers.check(mk(1500), prev, [KEY]))
        self.assertIn("band", chargers.check(mk(500), None, [KEY]))
        self.assertIn("box", chargers.check(mk(1900, 100), prev, [KEY]))
        leaky = mk(1900)
        leaky["s"] = [[0, 0, 0, 0, 0, 0, 0, KEY]]
        self.assertIn("key", chargers.check(leaky, prev, [KEY]))
        self.assertIsNone(chargers.check(mk(1900), prev, ["", "short"]))                  # empty / short secrets never match

    def test_due(self):
        today = date(2026, 11, 7)
        self.assertTrue(chargers.due(None, today))
        self.assertTrue(chargers.due({}, today))
        self.assertFalse(chargers.due({"generated": "2026-11-01"}, today))              # 6 days
        self.assertTrue(chargers.due({"generated": "2026-10-31"}, today))               # 7 days
        self.assertFalse(chargers.due({"generated": "2026-10-31", "attempted": "2026-11-07"}, today))
        self.assertTrue(chargers.due({"generated": "2026-11-06"}, today, force=True))


class Run(unittest.TestCase):
    """End to end with the network mocked: file written, key absent, last-good retained on a bad answer."""

    def run_with(self, pois, prev_file=None, nobil_doc=None, env_nobil=""):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d)
            if prev_file:
                (data / "ev_dk.json").write_text(json.dumps(prev_file), encoding="utf-8")
            urls = []

            async def fake_prev(session, cc):
                try:
                    return json.loads((data / "ev_dk.json").read_text(encoding="utf-8"))
                except OSError:
                    return {}

            async def fake_get(session, url, headers, tag):
                urls.append(tag)
                if "referencedata" in url:
                    return {"Operators": [{"ID": 1, "Title": "MER"}], "DataProviders": [{"ID": 1, "Title": "OCM", "License": "CC BY 4.0"}]}
                return pois

            env = {"OCM_API_KEY": KEY, "NOBIL_API_KEY": env_nobil}
            with mock.patch.object(chargers, "DATA", data), mock.patch.object(chargers, "get_json", fake_get), mock.patch.object(chargers, "fetch_prev", fake_prev), \
                    mock.patch.object(chargers, "CALL_GAP", 0), mock.patch.dict(os.environ, env):
                n = asyncio.run(chargers.run(["DK"], force=True))
            out = (data / "ev_dk.json")
            return n, (out.read_text(encoding="utf-8") if out.exists() else None), urls

    def test_writes_clean_file(self):
        pois = [poi(55.0 + i * 0.001, 12.0 + i * 0.001, OperatorID=1) for i in range(1100)]
        n, txt, urls = self.run_with(pois)
        self.assertEqual(n, 1)
        f = json.loads(txt)
        self.assertEqual((f["cc"], f["n"], f["ops"]), ("DK", 1100, ["MER"]))
        self.assertNotIn(KEY, txt)
        self.assertNotIn("apikey", txt.lower())
        self.assertNotIn("International_id", txt)

    def test_bad_answer_keeps_last_good(self):
        prev = {"v": 1, "cc": "DK", "generated": "2026-10-01", "s": [[55, 12, 0, 11, 2, 0, 24, "a"]] * 1500, "n": 1500}
        n, txt, _ = self.run_with([poi(55.0, 12.0)], prev_file=prev)                   # 1 station: outside the band
        self.assertEqual(n, 0)
        kept = json.loads(txt)
        self.assertEqual(kept["n"], 1500)
        self.assertEqual(kept["attempted"], datetime.now(timezone.utc).date().isoformat())
        self.assertEqual(len(kept["s"]), 1500)

    def test_shrunk_file_refused(self):
        prev = {"v": 1, "cc": "DK", "generated": "2026-10-01", "s": [[55, 12, 0, 11, 2, 0, 24, "a"]] * 2000, "n": 2000}
        pois = [poi(55.0 + i * 0.001, 12.0 + i * 0.001) for i in range(1100)]          # in band but 45 % lower
        n, txt, _ = self.run_with(pois, prev_file=prev)
        self.assertEqual(n, 0)
        self.assertEqual(json.loads(txt)["n"], 2000)

    def test_not_due_republishes_without_calling_ocm(self):
        today = datetime.now(timezone.utc).date().isoformat()
        prev = {"v": 1, "cc": "DK", "generated": today, "s": [[55, 12, 0, 11, 2, 0, 24, "a"]] * 1500, "n": 1500}
        with tempfile.TemporaryDirectory() as d:
            data = Path(d); (data / "ev_dk.json").write_text(json.dumps(prev), encoding="utf-8"); calls = []

            async def fake_prev(session, cc):
                return prev

            async def fake_get(*a, **k):
                calls.append(a); return None

            with mock.patch.object(chargers, "DATA", data), mock.patch.object(chargers, "get_json", fake_get), mock.patch.object(chargers, "fetch_prev", fake_prev),                     mock.patch.object(chargers, "CALL_GAP", 0), mock.patch.dict(os.environ, {"OCM_API_KEY": KEY}):
                n = asyncio.run(chargers.run(["DK"]))
            self.assertEqual(n, 0); self.assertEqual(calls, [])
            self.assertEqual(json.loads((data / "ev_dk.json").read_text(encoding="utf-8"))["n"], 1500)

    def test_crash_keeps_last_good_and_marks_attempt(self):
        prev = {"v": 1, "cc": "DK", "generated": "2026-10-01", "s": [[55, 12, 0, 11, 2, 0, 24, "a"]] * 1500, "n": 1500}
        pois = [poi(55.0 + i * 0.001, 12.0 + i * 0.001, OperatorID=1) for i in range(1100)]
        with mock.patch.object(chargers, "reduce_ocm", side_effect=AttributeError("boom")):
            n, txt, _ = self.run_with(pois, prev_file=prev)
        self.assertEqual(n, 0)
        kept = json.loads(txt)
        self.assertEqual(kept["n"], 1500); self.assertEqual(kept["attempted"], datetime.now(timezone.utc).date().isoformat())

    def test_unreadable_previous_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d); calls = []

            async def fake_prev(session, cc):
                return None

            async def fake_get(*a, **k):
                calls.append(a); return None

            with mock.patch.object(chargers, "DATA", data), mock.patch.object(chargers, "get_json", fake_get), mock.patch.object(chargers, "fetch_prev", fake_prev),                     mock.patch.object(chargers, "CALL_GAP", 0), mock.patch.dict(os.environ, {"OCM_API_KEY": KEY}):
                n = asyncio.run(chargers.run(["DK"], force=True))
            self.assertEqual((n, calls), (0, [])); self.assertFalse((data / "ev_dk.json").exists())

    def test_placeholder_operator_is_unknown(self):
        pois = [poi(55.0 + i * 0.001, 12.0 + i * 0.001, OperatorID=7) for i in range(1100)]
        with tempfile.TemporaryDirectory() as d:
            async def fake_get(session, url, headers, tag):
                if "referencedata" in url:
                    return {"Operators": [{"ID": 7, "Title": "(Unknown Operator)"}], "DataProviders": [{"ID": 1, "Title": "OCM", "License": "CC BY 4.0"}]}
                return pois

            async def fake_prev(session, cc):
                return {}

            with mock.patch.object(chargers, "DATA", Path(d)), mock.patch.object(chargers, "get_json", fake_get), mock.patch.object(chargers, "fetch_prev", fake_prev),                     mock.patch.object(chargers, "CALL_GAP", 0), mock.patch.dict(os.environ, {"OCM_API_KEY": KEY}):
                asyncio.run(chargers.run(["DK"], force=True))
            self.assertEqual(json.loads((Path(d) / "ev_dk.json").read_text(encoding="utf-8"))["ops"], [])


if __name__ == "__main__":
    unittest.main()
