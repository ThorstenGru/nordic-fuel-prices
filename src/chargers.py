"""Type 2 charging stations -> data/ev_<cc>.json (SE, NO, DK, DE).  See docs/CHARGERS_PIPELINE.md.

Source: Open Charge Map (OCM_API_KEY, header X-API-Key), optionally merged with NOBIL for SE/NO (NOBIL_API_KEY).
Weekly cadence without a scheduler: every run re-publishes the previous file (data/ is rebuilt on every CI run) and
only calls the APIs when that file is older than MAX_AGE_DAYS. A refused or failed refresh keeps the last good file.
Only a reduced tuple file is published: no OCM or NOBIL ids, no raw NOBIL fields, never a key.
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
OCM = "https://api.openchargemap.io/v3"
NOBIL_URL = "https://nobil.no/api/server/datadump.php"
MAX_AGE_DAYS = 6
CALL_GAP = 1.5                      # seconds between API calls (politeness)
T2 = {25, 1036}                     # Type 2 socket, Type 2 tethered (CCS 33 is DC and excluded)
BAD_STATUS = {100, 150, 200, 210}   # not operational, planned, removed, removed duplicate
PRIVATE_USAGE = {2, 3, 6}
DROP_PROVIDERS = {26}               # Oplaadpalen.nl: NonCommercial licence
DROP_RATIO = 0.8                    # fewer than 80 % of the previous count: refuse
ALLOW_SHRINK = {c.strip().upper() for c in os.environ.get("ALLOW_SHRINK", "").split(",") if c.strip()}   # same workflow input as the fuel pipeline: one run, listed countries may shrink
MAX_OUTLIER_SHARE = 0.02            # more than 2 % of stations outside the country box: refuse

# cc -> (OCM countrycode, NOBIL countrycode or None, count band, (lat0, lat1, lon0, lon1))
COUNTRIES = {
    "SE": ("SE", "SWE", (2000, 6000), (55.0, 69.2, 10.8, 24.3)),
    "NO": ("NO", "NOR", (1500, 8000), (57.5, 81.0, 4.0, 35.0)),
    "DK": ("DK", None, (1000, 4000), (54.5, 57.9, 7.9, 15.3)),
    "DE": ("DE", None, (10000, 40000), (47.2, 55.2, 5.8, 15.1)),
}
FLAG_FREE, FLAG_MEMBER, FLAG_NOTICE, FLAG_PAYLOC, FLAG_PARKHINT, FLAG_COSTNOTE, FLAG_TETHERED, FLAG_NOBIL_PARK = 1, 2, 4, 8, 16, 32, 64, 128

# Free only when the WHOLE note is one of these phrases; any qualifier ("not free", "free parking", "for customers") is not free.
FREE = re.compile(r"(free|free of charge|gratis|kostenlos|kostenfrei|umsonst|avgiftsfri|ingen avgift|no charge)[.!]?", re.I)
PARK = re.compile(r"(parking fee|parkeringsavgift|parkgeb|parkplatzgeb|parking cost)", re.I)
# Short names shown for providers; the licence text comes from OCM reference data.
PROVIDER_SHORT = {1: "OCM", 19: "NOBIL", 29: "Bundesnetzagentur"}
# Operator aliases (normalised name -> display name) so OCM and NOBIL share one key space for the later price table. Extend as needed.
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


def reduce_ocm(pois: List[Dict[str, Any]], ops: Dict[int, str]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """OCM compact POIs -> station dicts (lat, lon, op, kw, pts, flags, yr, title, uc, prov, ref). Applies the design filter."""
    st = {"in": len(pois), "noT2": 0, "usage": 0, "status": 0, "provider": 0, "nopos": 0}
    out: List[Dict[str, Any]] = []
    for p in pois:
        ai = p.get("AddressInfo") or {}
        t2 = [c for c in (p.get("Connections") or []) if c.get("ConnectionTypeID") in T2 and c.get("StatusTypeID") not in BAD_STATUS]
        if not t2:
            st["noT2"] += 1
        elif p.get("UsageTypeID") in PRIVATE_USAGE:
            st["usage"] += 1
        elif p.get("StatusTypeID") in BAD_STATUS:
            st["status"] += 1
        elif p.get("DataProviderID") in DROP_PROVIDERS:
            st["provider"] += 1
        elif not isinstance(ai.get("Latitude"), (int, float)) or not isinstance(ai.get("Longitude"), (int, float)):
            st["nopos"] += 1
        else:
            kws = [c["PowerKW"] for c in t2 if isinstance(c.get("PowerKW"), (int, float)) and c["PowerKW"] > 0]
            uc = (p.get("UsageCost") or "").strip()
            use = p.get("UsageTypeID")
            flags = 0
            if uc and FREE.fullmatch(uc):
                flags |= FLAG_FREE                                    # the whole note says free, nothing else
            flags |= {4: FLAG_MEMBER, 7: FLAG_NOTICE, 5: FLAG_PAYLOC}.get(use, 0)
            if PARK.search(" ".join(filter(None, [uc, p.get("GeneralComments"), ai.get("AccessComments")]))):
                flags |= FLAG_PARKHINT                                # weak text hint only
            if uc:
                flags |= FLAG_COSTNOTE
            if all(c.get("ConnectionTypeID") == 1036 for c in t2):
                flags |= FLAG_TETHERED
            out.append({"lat": ai["Latitude"], "lon": ai["Longitude"], "op": canon_op(ops.get(p.get("OperatorID"))),
                        "kw": max(kws) if kws else None, "pts": sum(int(c.get("Quantity") or 1) for c in t2), "flags": flags,
                        "yr": _year(p.get("DateLastVerified")), "title": (ai.get("Title") or "").strip(), "uc": uc,
                        "prov": p.get("DataProviderID"), "ref": re.sub(r"\D", "", str(p.get("DataProvidersReference") or ""))})
    st["kept"] = len(out)
    return out, st


def dedupe(stations: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Merge records within 30 m (grid 0.0005 deg, then metric check): keep the one with more information, points = max, never the sum."""
    grid: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    res: List[Dict[str, Any]] = []
    merged = 0

    def score(s: Dict[str, Any]) -> float:
        return (2 if s["op"] else 0) + (3 if s["flags"] & FLAG_COSTNOTE else 0) + s["yr"] / 10000 + (0 if s["prov"] == 19 else 1)

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
    """NOBIL v3 datadump -> station dicts in the OCM shape. Public Type 2 (connector value 32) only. The layout was taken from the
    NOBIL v3 documentation and has NOT been seen live; every access is defensive and a doc that yields nothing is treated as a failure upstream."""
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
            out.append({"lat": float(m.group(1)), "lon": float(m.group(2)), "op": canon_op(md.get("Owned_by")),
                        "kw": max(kws) if kws else None, "pts": len(conns), "flags": flags, "yr": _year(md.get("Updated")),
                        "title": title or str(md.get("name") or "").strip(), "uc": "", "prov": 19, "ref": "", "ids": ids})
    st["kept"] = len(out)
    return out, st


def merge_nobil(ocm: List[Dict[str, Any]], nob: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """NOBIL wins for the stations it lists (operator, points, kW, parking, year); OCM adds cost text, usage flags and contributor-only stations.
    OCM stations from provider 19 that NOBIL no longer lists are dropped (removed upstream)."""
    by_ref: Dict[str, Dict[str, Any]] = {}
    for o in ocm:
        if o["prov"] == 19 and o["ref"]:
            by_ref.setdefault(o["ref"], o)
    used: set = set()
    res: List[Dict[str, Any]] = []
    st = {"matched": 0, "nobil_only": 0, "ocm_only": 0, "ocm_dropped": 0}
    pool = [o for o in ocm if o["prov"] == 19]                         # spatial fallback only against NOBIL-derived OCM rows
    for n in nob:
        o = next((by_ref[i] for i in n["ids"] if i in by_ref and id(by_ref[i]) not in used), None)
        if o is None:
            o = next((c for c in pool if id(c) not in used and dist_m((n["lat"], n["lon"]), (c["lat"], c["lon"])) <= 30), None)
        m = {k: v for k, v in n.items() if k != "ids"}
        if o is not None:
            used.add(id(o))
            st["matched"] += 1
            m["uc"] = o["uc"]
            m["flags"] |= o["flags"] & (FLAG_FREE | FLAG_COSTNOTE | FLAG_PARKHINT | FLAG_NOTICE | FLAG_PAYLOC | FLAG_MEMBER | FLAG_TETHERED)
            m["op"] = m["op"] or o["op"]
        else:
            st["nobil_only"] += 1
        res.append(m)
    for o in ocm:
        if id(o) in used:
            continue
        if o["prov"] == 19:
            st["ocm_dropped"] += 1
        else:
            st["ocm_only"] += 1
            res.append(o)
    return res, st


def build_file(cc: str, stations: List[Dict[str, Any]], today: date, providers: Dict[int, Tuple[str, str]], nobil: bool) -> Dict[str, Any]:
    """Final reduced file. providers = {id: (title, licence)} from OCM reference data (only used for the attribution text)."""
    box = COUNTRIES[cc][3]
    keep = [s for s in stations if box[0] <= s["lat"] <= box[1] and box[2] <= s["lon"] <= box[3]]
    names = sorted({s["op"] for s in keep if s["op"]})
    idx = {n: i + 1 for i, n in enumerate(names)}
    rows, notes = [], []
    for i, s in enumerate(keep):
        rows.append([round(s["lat"], 5), round(s["lon"], 5), idx.get(s["op"], 0), int(s["kw"] + 0.5) if s["kw"] else 0, s["pts"], s["flags"],
                     s["yr"] % 100, s["title"]])
        if s["uc"]:
            notes.append([i, s["uc"][:80]])
    present = {s["prov"] for s in keep if s["prov"] is not None}
    if nobil:
        present.add(19)
    sources, attribution = [], []
    for pid in sorted(present, key=lambda x: (x not in PROVIDER_SHORT, x)):
        title, lic = providers.get(pid, (f"provider {pid}", ""))
        lic = "CC BY 4.0" if "CC BY 4.0" in lic else "CC0" if "CC0" in lic else lic[:60]
        short, text = PROVIDER_SHORT.get(pid, title), " ".join(x for x in [title, f"({lic})" if lic else ""] if x)
        if short not in sources:                                  # several provider ids share a title (PowerGo)
            sources.append(short)
        if text not in attribution:
            attribution.append(text)
    yrs = sorted(s["yr"] for s in keep if s["yr"])
    return {"v": 1, "cc": cc, "generated": today.isoformat(), "source": "ocm+nobil" if nobil else "ocm", "sources": sources,
            "attribution": ["Open Charge Map contributors and data providers (CC BY 4.0 unless stated)"] + attribution,
            "medVerified": yrs[len(yrs) // 2] if yrs else 0, "n": len(rows), "dropped_outside_box": len(stations) - len(keep),
            "ops": names, "s": rows, "notes": notes}


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
    lo, hi = COUNTRIES[new["cc"]][2]
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


async def refresh(session: aiohttp.ClientSession, cc: str, ocm_key: str, nobil_key: str, ref: Dict[str, Any],
                  prev: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    ocm_cc, nobil_cc, _, _ = COUNTRIES[cc]
    pois = await get_json(session, f"{OCM}/poi?output=json&countrycode={ocm_cc}&connectiontypeid=25,1036&compact=true&verbose=false"
                          f"&includecomments=false&maxresults=100000", {"X-API-Key": ocm_key}, f"{cc} OCM")
    if not isinstance(pois, list) or not pois:
        return None
    ops = {o["ID"]: ("" if (o.get("Title") or "").strip().startswith("(") else o.get("Title") or "") for o in ref.get("Operators") or [] if "ID" in o}   # "(Unknown Operator)" and the like are placeholders, not operators
    provs = {d["ID"]: (d.get("Title") or "", d.get("License") or "") for d in ref.get("DataProviders") or [] if "ID" in d}
    stations, st = reduce_ocm(pois, ops)
    used_nobil = False
    if nobil_key and nobil_cc:
        await asyncio.sleep(CALL_GAP)
        doc = await get_json(session, f"{NOBIL_URL}?apikey={nobil_key}&countrycode={nobil_cc}&fromdate=2005-01-01&format=json&file=false",
                             {}, f"{cc} NOBIL")
        nob, nst = reduce_nobil(doc) if isinstance(doc, dict) else ([], {})
        if len(nob) < 500:                              # unusable answer: keep last good rather than silently downgrade to OCM-only
            print(f"[chargers] {cc} NOBIL gave {len(nob)} usable stations: keeping the last good file")
            return None
        stations, mst = merge_nobil(stations, nob)
        used_nobil = True
        print(f"[chargers] {cc} NOBIL {nst}, merge {mst}")
    stations, merged = dedupe(stations)
    print(f"[chargers] {cc} OCM filter {st}, dedupe merged {merged}")
    return build_file(cc, stations, datetime.now(timezone.utc).date(), provs, used_nobil)


async def run(countries: Optional[List[str]] = None, force: bool = False) -> int:
    """Returns the number of country files refreshed. Never raises, never publishes an empty or shrunken file."""
    ocm_key, nobil_key = os.environ.get("OCM_API_KEY", "").strip(), os.environ.get("NOBIL_API_KEY", "").strip()
    today = datetime.now(timezone.utc).date()
    ok = 0
    async with aiohttp.ClientSession() as session:
        ref: Optional[Dict[str, Any]] = None
        for cc in countries or list(COUNTRIES):
            out = DATA / f"ev_{cc.lower()}.json"
            prev = await fetch_prev(session, cc)
            if prev is None:                            # could not be read (Pages hiccup): unknown is not "no file", so no blind refresh; the curl step restores the live file
                print(f"[chargers] {cc}: previous file unreadable, skipped this run")
                continue
            if prev and prev.get("v") != 1:
                prev = None
            if not due(prev, today, force):
                write_json(out, prev)                   # re-publish: gh-pages deploy deletes files absent from data/
                print(f"[chargers] {cc}: previous file is {prev['generated']}, not due")
                continue
            if not ocm_key:
                print(f"[chargers] {cc}: OCM_API_KEY not set, nothing refreshed")
                if prev:
                    write_json(out, prev)
                continue
            if ref is None:
                ref = await get_json(session, f"{OCM}/referencedata/", {"X-API-Key": ocm_key}, "referencedata") or {}
                await asyncio.sleep(CALL_GAP)
            if prev:
                write_json(out, {**prev, "attempted": today.isoformat()})   # written BEFORE the pull: a crash or the step timeout must not mean a retry every 15 minutes
            try:
                new = await refresh(session, cc, ocm_key, nobil_key, ref, prev) if ref else None
                why = "no usable data" if new is None else check(new, prev, [ocm_key, nobil_key])
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
