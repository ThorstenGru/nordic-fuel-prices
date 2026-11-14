"""Type 2 charging stations -> data/ev_<cc>.json.  See docs/CHARGERS_PIPELINE.md.

Source: NOBIL (Enova, the official Nordic charging register, CC BY 4.0; NOBIL_API_KEY) for SE and NO. Open Charge Map was dropped on
2026-11-13 as not good enough (old, operator names missing). DK, DE, NL, BE, IE, IS are FROZEN here: refreshed by src/chargefinder.py (ChargeFinder); this file only re-publishes them.
Weekly cadence without a scheduler: every run re-publishes the previous file (data/ is rebuilt on every CI run) and
only calls the API when that file is older than MAX_AGE_DAYS. A refused or failed refresh keeps the last good file.
Only a reduced tuple file is published: no NOBIL ids, no raw NOBIL fields, never a key.
"""
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from math import cos, radians, hypot
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
UA = {"User-Agent": "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"}
NOBIL_URL = "https://nobil.no/api/server/datadump.php"
MAX_AGE_DAYS = 6
CALL_GAP = 1.5                      # seconds between API calls (politeness)
DROP_RATIO = 0.8                    # fewer than 80 % of the previous count: refuse
ALLOW_SHRINK = {c.strip().upper() for c in os.environ.get("ALLOW_SHRINK", "").split(",") if c.strip()}   # same workflow input as the fuel pipeline: one run, listed countries may shrink
MAX_OUTLIER_SHARE = 0.02            # more than 2 % of stations outside the country box: refuse

# cc -> (NOBIL countrycode, count band, (lat0, lat1, lon0, lon1)). The key the owner holds answers only SWE and NOR.
COUNTRIES = {
    "SE": ("SWE", (2000, 12000), (55.0, 69.2, 10.8, 24.3)),
    "NO": ("NOR", (1500, 8000), (57.5, 81.0, 4.0, 35.0)),
}
FROZEN = ("DK", "DE", "NL", "BE", "IE", "IS", "FR", "GB")   # not refreshed here: src/chargefinder.py owns these; this only re-publishes the last published file (data/ is rebuilt every run)
FLAG_FREE, FLAG_MEMBER, FLAG_NOTICE, FLAG_PAYLOC, FLAG_PARKHINT, FLAG_COSTNOTE, FLAG_TETHERED, FLAG_NOBIL_PARK = 1, 2, 4, 8, 16, 32, 64, 128

# Operator aliases (normalised name -> display name) so every source shares one key space for the price table. Extend as needed.
ALIAS = {"mer": "MER", "recharge": "Recharge", "fortum charge drive": "Recharge", "incharge": "Vattenfall InCharge",
         "vattenfall incharge": "Vattenfall InCharge", "vattenfall": "Vattenfall InCharge", "eon drive": "E.ON Drive",
         "eon": "E.ON Drive", "circle k": "Circle K", "ionity": "Ionity", "tesla": "Tesla"}


# -- pure helpers (tested offline) ---------------------------------------------------------------

def norm_op(name: str) -> str:
    s = re.sub(r"\(.*?\)", " ", name.lower().replace("&", " ").replace(".", ""))
    s = re.sub(r"[^a-z0-9åäöæøü ]+", " ", s)
    s = re.sub(r"\b(sverige|sweden|norge|norway|danmark|deutschland|germany|ab|as|asa|a s|gmbh|se|no)\b", " ", s)
    return " ".join(s.split())


def canon_op(name: Optional[str]) -> str:
    n = (name or "").strip()
    return ALIAS.get(norm_op(n), n) if n else ""


def dist_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * cos(radians(a[0])))


def _year(s: Any) -> int:
    m = re.match(r"(\d{4})", str(s or ""))
    return int(m.group(1)) if m else 0


def dedupe(stations: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Merge records within 30 m (grid 0.0005 deg, then metric check): keep the one with more information, points = max, never the sum."""
    grid: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    res: List[Dict[str, Any]] = []
    merged = 0

    def score(s: Dict[str, Any]) -> float:
        return (2 if s["op"] else 0) + (3 if s["flags"] & FLAG_COSTNOTE else 0) + s["yr"] / 10000 + 0

    for s in stations:
        gx, gy = int(s["lat"] // 0.0005), int(s["lon"] // 0.0005)
        hit = next((o for i in (-1, 0, 1) for j in (-1, 0, 1) for o in grid.get((gx + i, gy + j), [])
                    if dist_m((s["lat"], s["lon"]), (o["lat"], o["lon"])) <= 30), None)
        if hit is None:
            grid.setdefault((gx, gy), []).append(s)
            res.append(s)
            continue
        merged += 1
        pts = max(hit["pts"], s["pts"])
        if score(s) > score(hit):
            hit.update(s)
        hit["pts"] = pts
    return res, merged


def _nobil_attr(d: Dict[str, Any], key: str) -> Tuple[str, str]:
    a = (d or {}).get(key) or {}
    return str(a.get("attrvalid", "")), str(a.get("trans") or a.get("attrval") or "")


def reduce_nobil(doc: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """NOBIL v3 datadump -> station dicts. Public Type 2 (connector value 32) only. The layout was taken from the
    NOBIL v3 documentation and checked against live datadump.php (SWE, 2026-11-10: 10006 in, 7469 kept); every access is defensive and a doc that yields nothing is treated as a failure upstream."""
    st = {"in": 0, "noT2": 0, "access": 0, "closed": 0, "nopos": 0}
    out: List[Dict[str, Any]] = []
    for cs in (doc.get("chargerstations") or []):
        st["in"] += 1
        md, attr = cs.get("csmd") or {}, cs.get("attr") or {}
        sta = attr.get("st") or {}
        conns = [c for c in (attr.get("conn") or {}).values() if isinstance(c, dict) and _nobil_attr(c, "4")[0] == "32"]
        m = re.match(r"\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)", str(md.get("Position") or ""))
        avail = _nobil_attr(sta, "2")[0]
        closed = re.search(r"remov|closed|planned|construct|nedlagt|permanent", _nobil_attr(sta, "21")[1], re.I)
        if not conns:
            st["noT2"] += 1
        elif avail not in ("", "1"):
            st["access"] += 1                                         # visitors / members only
        elif closed:
            st["closed"] += 1
        elif not m:
            st["nopos"] += 1
        else:
            kws = [float(x.replace(",", ".")) for c in conns for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*kW", _nobil_attr(c, "5")[1], re.I)]
            pay = _nobil_attr(sta, "19")[1].lower()
            flags = 0
            if _nobil_attr(sta, "7")[0] == "1" or _nobil_attr(sta, "7")[1].strip().lower() in ("yes", "ja"):
                flags |= FLAG_NOBIL_PARK
            if re.search(r"charging card|ladekort|laddkort", pay) and not re.search(r"phone|bank|sms|telefon|mobil", pay):
                flags |= FLAG_MEMBER
            title = ", ".join(x for x in [" ".join(filter(None, [str(md.get("Street") or "").strip(), str(md.get("House_number") or "").strip()])),
                                          str(md.get("City") or "").strip()] if x)
            ids = {re.sub(r"\D", "", str(md.get(k) or "")) for k in ("id", "International_id")} - {""}
            out.append({"lat": float(m.group(1)), "lon": float(m.group(2)), "op": canon_op(md.get("Operator") or md.get("Owned_by")),   # the network that runs the post (Vattenfall InCharge), not the property owner (a landlord or a local utility)
                        "kw": max(kws) if kws else None, "pts": len(conns), "flags": flags, "yr": _year(md.get("Updated")),
                        "title": title or str(md.get("name") or "").strip(), "uc": "", "prov": 19, "ref": "", "ids": ids})
    st["kept"] = len(out)
    return out, st


def build_file(cc: str, stations: List[Dict[str, Any]], today: date) -> Dict[str, Any]:
    """Final reduced file for a NOBIL country."""
    box = COUNTRIES[cc][2]
    keep = [s for s in stations if box[0] <= s["lat"] <= box[1] and box[2] <= s["lon"] <= box[3]]
    names = sorted({s["op"] for s in keep if s["op"]})
    idx = {n: i + 1 for i, n in enumerate(names)}
    rows = [[round(s["lat"], 5), round(s["lon"], 5), idx.get(s["op"], 0), int(s["kw"] + 0.5) if s["kw"] else 0, s["pts"], s["flags"],
             s["yr"] % 100, s["title"]] for s in keep]
    yrs = sorted(s["yr"] for s in keep if s["yr"])
    return {"v": 1, "cc": cc, "generated": today.isoformat(), "source": "nobil", "sources": ["NOBIL"],
            "attribution": ["NOBIL by Enova (CC BY 4.0)"],
            "medVerified": yrs[len(yrs) // 2] if yrs else 0, "n": len(rows), "dropped_outside_box": len(stations) - len(keep),
            "ops": names, "s": rows, "notes": []}


def due(prev: Optional[Dict[str, Any]], today: date, force: bool = False) -> bool:
    """Refresh when forced, when there is no readable previous file, or when it is older than MAX_AGE_DAYS and not already attempted today."""
    if force or not prev or "generated" not in prev:
        return True
    try:
        age = (today - date.fromisoformat(prev["generated"])).days
    except ValueError:
        return True
    return age > MAX_AGE_DAYS and prev.get("attempted") != today.isoformat()


def check(new: Dict[str, Any], prev: Optional[Dict[str, Any]], secrets: List[str]) -> Optional[str]:
    """Guards. Returns the reason to refuse the new file, or None."""
    lo, hi = COUNTRIES[new["cc"]][1]
    n = new["n"]
    if not lo <= n <= hi:
        return f"{n} stations outside the sanity band {lo}-{hi}"
    pn = len((prev or {}).get("s") or [])
    if pn and n < DROP_RATIO * pn and new["cc"] not in ALLOW_SHRINK:
        return f"{n} stations is a drop of more than 20 % from {pn}"
    if new["dropped_outside_box"] > MAX_OUTLIER_SHARE * (n + new["dropped_outside_box"]):
        return f"{new['dropped_outside_box']} stations outside the country box"
    txt = json.dumps(new, ensure_ascii=False)
    if any(k and len(k) >= 8 and k in txt for k in secrets):
        return "a key string is present in the output"
    return None


# -- I/O ----------------------------------------------------------------------------------------

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


async def fetch_prev(session: aiohttp.ClientSession, cc: str) -> Optional[Dict[str, Any]]:
    """Local data/ev_<cc>.json, else the live file. {} = none exists yet, None = could not be read."""
    out = DATA / f"ev_{cc.lower()}.json"
    try:
        return json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    from scrapers.geocoder import PAGES_BASES
    clean_404 = True                                    # a deploy gap must not look like "no file yet"
    for attempt in range(3):
        for base in PAGES_BASES:
            try:
                async with session.get(f"{base}/ev_{cc.lower()}.json", headers={**UA, "Cache-Control": "no-cache"},
                                       timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
                    if r.status != 404:
                        clean_404 = False
            except Exception as e:  # noqa: BLE001
                clean_404 = False
                print(f"[chargers] {cc} no previous file ({base}, try {attempt + 1}): {type(e).__name__}")
        await asyncio.sleep(1 + attempt * 2)
    return {} if clean_404 else None


async def get_json(session: aiohttp.ClientSession, url: str, headers: Dict[str, str], tag: str) -> Optional[Any]:
    """GET with 3 tries. Never prints the URL or the exception text (both can carry a key)."""
    for attempt in range(3):
        try:
            async with session.get(url, headers={**UA, **headers}, timeout=aiohttp.ClientTimeout(total=180)) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
                print(f"[chargers] {tag}: HTTP {r.status} (try {attempt + 1})")
        except Exception as e:  # noqa: BLE001
            print(f"[chargers] {tag}: {type(e).__name__} (try {attempt + 1})")
        await asyncio.sleep(CALL_GAP * (attempt + 1))
    return None


async def refresh(session: aiohttp.ClientSession, cc: str, nobil_key: str, prev: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    nobil_cc = COUNTRIES[cc][0]
    doc = await get_json(session, f"{NOBIL_URL}?apikey={nobil_key}&countrycode={nobil_cc}&fromdate=2005-01-01&format=json&file=false", {}, f"{cc} NOBIL")
    stations, st = reduce_nobil(doc) if isinstance(doc, dict) else ([], {})
    if len(stations) < 500:                             # unusable answer: keep the last good file
        print(f"[chargers] {cc} NOBIL gave {len(stations)} usable stations: keeping the last good file")
        return None
    stations = [{k: v for k, v in x.items() if k != "ids"} for x in stations]
    stations, merged = dedupe(stations)
    print(f"[chargers] {cc} NOBIL filter {st}, dedupe merged {merged}")
    return build_file(cc, stations, datetime.now(timezone.utc).date())


async def run(countries: Optional[List[str]] = None, force: bool = False) -> int:
    """Returns the number of country files refreshed. Never raises, never publishes an empty or shrunken file."""
    nobil_key = os.environ.get("NOBIL_API_KEY", "").strip()
    today = datetime.now(timezone.utc).date()
    ok = 0
    async with aiohttp.ClientSession() as session:
        for cc in countries or [*COUNTRIES, *FROZEN]:
            out = DATA / f"ev_{cc.lower()}.json"
            prev = await fetch_prev(session, cc)
            if prev is None:                            # could not be read (Pages hiccup): unknown is not "no file", so no blind refresh; the curl step restores the live file
                print(f"[chargers] {cc}: previous file unreadable, skipped this run")
                continue
            if prev and prev.get("v") != 1:
                prev = None
            if cc in FROZEN or not (force or due(prev, today)):
                if prev:
                    write_json(out, prev)               # re-publish: gh-pages deploy deletes files absent from data/
                print(f"[chargers] {cc}: " + ("owned by chargefinder.py, re-published" if cc in FROZEN else f"previous file is {prev['generated']}, not due"))
                continue
            if not nobil_key:
                print(f"[chargers] {cc}: NOBIL_API_KEY not set, nothing refreshed")
                if prev:
                    write_json(out, prev)
                continue
            if prev:
                write_json(out, {**prev, "attempted": today.isoformat()})   # written BEFORE the pull: a crash or the step timeout must not mean a retry every 15 minutes
            try:
                new = await refresh(session, cc, nobil_key, prev)
                why = "no usable data" if new is None else check(new, prev, [nobil_key])
            except Exception as e:  # noqa: BLE001  (type only: messages can carry URLs)
                new, why = None, f"error {type(e).__name__}"
            if why:
                print(f"[chargers] {cc}: refresh refused ({why}); last good file kept")
                await asyncio.sleep(CALL_GAP)
                continue
            write_json(out, new)
            ok += 1
            print(f"[chargers] {cc}: {new['n']} stations, {out.stat().st_size} bytes, sources {new['sources']}")
            await asyncio.sleep(CALL_GAP)
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    asyncio.run(run([a.upper() for a in args[0].split(",")] if args else None,
                    "--force" in sys.argv or os.environ.get("FORCE_REFRESH") == "1"))
