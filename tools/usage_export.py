"""Writes the weekly usage report from the Worker's counter export (GET /api/stats, see worker/route/index.mjs `stats`).

    python tools/usage_export.py STATS.json

web/usage.json   {generated, days, events:[{day,name,n}], poll:[{q,a,n}]}  - read by the Usage panel in admin.html
docs/usage/events.csv   day,name,n  - the same counts as a table (history in git)
Counts only: no IP, no user agent, no identifiers, no search text. Fails (exit 1) if the file is not what the Worker sends, so an error page is never published.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or not isinstance(d.get("events"), list) or not isinstance(d.get("poll"), list):
        raise ValueError("unexpected answer from /api/stats")
    for e in d["events"]:
        if not (isinstance(e.get("day"), str) and isinstance(e.get("name"), str) and isinstance(e.get("n"), int)):
            raise ValueError(f"bad event row: {e!r}")
    return d


def write(d: dict, out_json: Path, out_csv: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"generated": d.get("generated"), "days": d.get("days"), "events": d["events"], "poll": d["poll"]}, separators=(",", ":")), encoding="utf-8")
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["day", "name", "n"])
        w.writerows((e["day"], e["name"], e["n"]) for e in d["events"])


if __name__ == "__main__":
    try:
        write(load(Path(sys.argv[1])), ROOT / "web" / "usage.json", ROOT / "docs" / "usage" / "events.csv")
    except (OSError, ValueError, IndexError) as e:
        print(f"usage_export: {type(e).__name__}: {e}")
        sys.exit(1)
    print("usage_export: written")
