import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import usage_export as ux  # noqa: E402


class Usage(unittest.TestCase):
    def test_roundtrip_and_refusal_of_bad_input(self):
        d = Path(tempfile.mkdtemp())
        src = d / "s.json"
        src.write_text(json.dumps({"generated": "2026-11-17T06:00:00Z", "days": 90, "events": [{"day": "2026-11-16", "name": "visit", "n": 3}, {"day": "2026-11-16", "name": "fuel_filter:diesel", "n": 1}], "poll": [{"q": "use", "a": "route", "n": 2}]}), encoding="utf-8")
        ux.write(ux.load(src), d / "usage.json", d / "events.csv")
        self.assertEqual(json.loads((d / "usage.json").read_text(encoding="utf-8"))["events"][1]["name"], "fuel_filter:diesel")
        self.assertEqual((d / "events.csv").read_text(encoding="utf-8").splitlines()[1], "2026-11-16,visit,3")
        for bad in ('<html>error</html>', '{"error":"auth"}', json.dumps({"events": [{"day": "x", "name": "y", "n": "z"}], "poll": []})):
            src.write_text(bad, encoding="utf-8")
            with self.assertRaises(ValueError):                     # an error page must never be published as the report
                ux.load(src)


if __name__ == "__main__":
    unittest.main()
