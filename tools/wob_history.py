"""EU Weekly Oil Bulletin price history -> data/wob_history.json (national average pump prices incl. taxes, weekly, last two years).

Source: European Commission, Directorate-General for Energy, "Weekly Oil Bulletin - price developments 2005 onwards" (xlsx).
Reuse: the workbook states "Reproduction is authorised provided the source is acknowledged", so every page that shows the chart names it.
The workbook is read with the standard library only (an xlsx is a zip of XML files), so CI needs no extra package.
Refreshed at most every 6 days: the bulletin is weekly and the file is 4.5 MB.

    python tools/wob_history.py [--force]        # writes data/wob_history.json
"""
import json
import re
import subprocess
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "wob_history.json"
URL = "https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx"
WEEKS = 104
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ISO = {"UK": "GB"}                    # the bulletin writes UK, we write GB
MIN_COUNTRIES = 20                    # fewer than this and the sheet changed shape: write nothing


def col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_sheet(path: Path) -> list:
    """First worksheet ("Prices with taxes") as a list of rows (lists of str / float / None)."""
    z = zipfile.ZipFile(path)
    shared = []
    for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
        shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    rows = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter("{%s}row" % NS["m"]):
        cells = {}
        for c in row.findall("m:c", NS):
            v = c.find("m:v", NS)
            if v is None or v.text is None:
                continue
            cells[col_index(c.get("r"))] = shared[int(v.text)] if c.get("t") == "s" else float(v.text)
        if cells:
            r = [None] * (max(cells) + 1)
            for i, v in cells.items():
                r[i] = v
            rows.append(r)
    return rows


def build(rows: list, today: date) -> dict:
    """Pure: workbook rows -> {"v":1, "dates":[...], "c":{cc:{"p":[eur/L], "d":[eur/L]}}} for the last WEEKS weeks, oldest first."""
    head = {str(h): i for i, h in enumerate(rows[0]) if h}
    countries = sorted({k.split("_")[0] for k in head if k.endswith("_price_with_tax_euro95")} - {"EU", "EUR"})
    data = [r for r in rows if r and isinstance(r[0], float) and r[0] > 40000]          # Excel date serials (after 2009)
    data.sort(key=lambda r: r[0])
    data = data[-WEEKS:]
    base = date(1899, 12, 30)
    dates = [(base + timedelta(days=int(r[0]))).isoformat() for r in data]
    out = {}
    for cc in countries:
        pi, di = head.get(f"{cc}_price_with_tax_euro95"), head.get(f"{cc}_price_with_tax_diesel")
        if pi is None or di is None:
            continue
        def col(i):
            return [round(r[i] / 1000, 3) if i < len(r) and isinstance(r[i], float) and 300 < r[i] < 4000 else None for r in data]
        p, d = col(pi), col(di)
        if sum(v is not None for v in p) >= WEEKS // 2 and sum(v is not None for v in d) >= WEEKS // 2:
            out[ISO.get(cc, cc)] = {"p": p, "d": d}
    return {"v": 1, "source": "European Commission, Weekly Oil Bulletin", "unit": "EUR/L, national average incl. taxes", "updated": today.isoformat(),
            "dates": dates, "c": out}


def fresh(path: Path, today: date, days: int = 6) -> bool:
    try:
        return (today - date.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["updated"])).days < days
    except (OSError, ValueError, KeyError):
        return False


def main(force: bool = False) -> int:
    today = datetime.now(timezone.utc).date()
    if not force and fresh(OUT, today):
        print("[wob] history is fresh, nothing to do")
        return 0
    tmp = ROOT / "data" / "wob.xlsx"
    tmp.parent.mkdir(exist_ok=True)
    r = subprocess.run(["curl", "-sSL", "-f", "-m", "120", "-A", "EuroFuelPrices/2.0 (+https://eurofuelprices.com)", "-o", str(tmp), URL], capture_output=True)
    try:
        if r.returncode != 0:
            print("[wob] download failed, keeping the previous file")
            return 0
        doc = build(read_sheet(tmp), today)
    except Exception as e:  # noqa: BLE001 - a changed workbook must never break the scrape run
        print(f"[wob] could not read the workbook ({type(e).__name__}), keeping the previous file")
        return 0
    finally:
        tmp.unlink(missing_ok=True)
    if len(doc["c"]) < MIN_COUNTRIES or len(doc["dates"]) < WEEKS // 2:
        print(f"[wob] only {len(doc['c'])} countries / {len(doc['dates'])} weeks: refusing to write")
        return 0
    OUT.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(f"[wob] {len(doc['c'])} countries, {len(doc['dates'])} weeks to {doc['dates'][-1]}, {OUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main("--force" in sys.argv))
