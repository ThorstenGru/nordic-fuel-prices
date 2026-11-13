"""ChargeFinder (chargefinder.com) station list -> the same reduced ev_<cc>.json file as src/chargers.py.

Permission: ChargeFinder's written consent (docs/PERMISSIONS.md): scrapers, unlimited, "using the build in website api key ... use the app's
endpoints or key". How their app gets its data (read from their public JavaScript, 2026-11-13):
  GET https://api.chargefinder.com/stations/<geohash7 of the NE corner>-<geohash7 of the SW corner>?exact=1
answers {"i": iv hex, "e": ciphertext hex, "a": tag hex}: AES-GCM with the app's key (a 32 character string, env CHARGEFINDER_KEY, a GitHub
secret, NEVER in the repo), then zlib, then a JSON list of stations (at most ~400 per request: a full answer means "split this box").
Polite by design: an honest User-Agent, two requests at a time with a pause, one crawl a week, give up early when the API misbehaves.
Only static fields are read (position, operator, plugs, power, access, free flags); prices and live status are per-station calls and are not used.
"""
import asyncio
import json
import os
import sys
import time
import zlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

sys.path.insert(0, str(Path(__file__).parent))
import chargers  # noqa: E402

API = "https://api.chargefinder.com/stations"
UA = {"User-Agent": "EuroFuelPrices/2.0 (+https://eurofuelprices.com; ChargeFinder consent, contact via the site)"}
CAP = 380                           # an answer this long is probably cut at ~400: split the box
GAP_S = 0.5
WORKERS = 2
MIN_SPAN = 0.02                     # degrees: never split below ~2 km; a box that is still full is accepted as it is
BUDGET_S = 40 * 60                  # shortcut: one crawl per country in one go, no resume; fine while a country takes < 40 min
B32 = "0123456789bcdefghjkmnpqrstuvwxyz"

# cc -> (ChargeFinder country code, count band, (lat0, lat1, lon0, lon1))
COUNTRIES: Dict[str, Tuple[str, Tuple[int, int], Tuple[float, float, float, float]]] = {
    "DK": ("DK", (3000, 20000), (54.5, 57.9, 7.9, 15.3)),
    "DE": ("DE", (30000, 150000), (47.2, 55.2, 5.8, 15.1)),
}


def geohash(lat: float, lon: float, p: int = 7) -> str:
    la, lo, out, bit, ch, even = [-90.0, 90.0], [-180.0, 180.0], "", 0, 0, True
    while len(out) < p:
        rng, v = (lo, lon) if even else (la, lat)
        m = (rng[0] + rng[1]) / 2
        if v > m:
            ch, rng[0] = ch * 2 + 1, m
        else:
            ch, rng[1] = ch * 2, m
        even = not even
        bit += 1
        if bit == 5:
            out, bit, ch = out + B32[ch], 0, 0
    return out


def box_url(lat0: float, lat1: float, lon0: float, lon1: float) -> str:
    return f"{API}/{geohash(lat1, lon1)}-{geohash(lat0, lon0)}?exact=1"


def decode(payload: Dict[str, Any], key: str) -> Optional[List[Dict[str, Any]]]:
    """Decrypt one answer; None when it is not an encrypted list (error, wrong key)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        pt = AESGCM(key.encode()).decrypt(bytes.fromhex(payload["i"]), bytes.fromhex(payload["e"] + payload.get("a", "")), None)
        try:
            pt = zlib.decompress(pt)
        except zlib.error:
            pass
        j = json.loads(pt.decode("utf-8"))
        return j if isinstance(j, list) else None
    except Exception:  # noqa: BLE001 - type only below, never the key
        return None


def inside(s: Dict[str, Any], box: Tuple[float, float, float, float], pad: float = 0.01) -> bool:
    loc = s.get("location") or {}
    la, lo = loc.get("latitude"), loc.get("longitude")
    return isinstance(la, (int, float)) and isinstance(lo, (int, float)) and box[0] - pad <= la <= box[1] + pad and box[2] - pad <= lo <= box[3] + pad


def reduce_station(s: Dict[str, Any], cc: str, year: int) -> Optional[Dict[str, Any]]:
    """One ChargeFinder station -> the station dict of src/chargers.py, or None (not Type 2, not public, other country, no position)."""
    loc, adr = s.get("location") or {}, s.get("locationAddress") or {}
    if (adr.get("countryCode") or "").upper() != cc or not s.get("plugType2") or (s.get("access") or "Public") != "Public":
        return None
    if not isinstance(loc.get("latitude"), (int, float)) or not isinstance(loc.get("longitude"), (int, float)):
        return None
    flags = (chargers.FLAG_FREE if s.get("freeCharging") == 1 else 0) | (chargers.FLAG_MEMBER if s.get("authCard") == 1 else 0)
    kw = s.get("maxCapacity") or s.get("minCapacity") or 0
    title = ", ".join(x for x in [str(adr.get("street") or "").strip(), str(adr.get("city") or "").strip()] if x) or str(s.get("title") or "").strip()
    return {"lat": float(loc["latitude"]), "lon": float(loc["longitude"]), "op": chargers.canon_op(s.get("operator") or s.get("operatorOther")),
            "kw": float(kw) if isinstance(kw, (int, float)) and kw > 0 else None, "pts": int(s["plugType2"]), "flags": flags, "yr": year,
            "title": title, "uc": "", "prov": 0, "ref": ""}


def split4(b: Tuple[float, float, float, float]) -> List[Tuple[float, float, float, float]]:
    la, lb, oa, ob = b
    ma, mo = (la + lb) / 2, (oa + ob) / 2
    return [(la, ma, oa, mo), (la, ma, mo, ob), (ma, lb, oa, mo), (ma, lb, mo, ob)]


def seed_boxes(box: Tuple[float, float, float, float], dlat: float = 0.5, dlon: float = 0.8) -> List[Tuple[float, float, float, float]]:
    out, la = [], box[0]
    while la < box[1]:
        lo = box[2]
        while lo < box[3]:
            out.append((la, min(la + dlat, box[1]), lo, min(lo + dlon, box[3])))
            lo += dlon
        la += dlat
    return out


async def crawl(session: aiohttp.ClientSession, cc: str, key: str, sleep=asyncio.sleep, clock=time.monotonic) -> Optional[List[Dict[str, Any]]]:
    """All stations of a country, or None when the API misbehaved (3 failed boxes in a row, a decoy answer, over budget)."""
    cf_cc, _, box = COUNTRIES[cc]
    todo = seed_boxes(box)
    found: Dict[str, Dict[str, Any]] = {}
    state = {"fails": 0, "calls": 0, "stop": None}
    t0 = clock()

    async def one(b):
        for attempt in range(3):
            try:
                async with session.get(box_url(*b), headers=UA, timeout=aiohttp.ClientTimeout(total=40)) as r:
                    state["calls"] += 1
                    if r.status in (403, 429):
                        state["stop"] = f"HTTP {r.status}"          # they said no / slow down: stop, never retry around it
                        return None
                    if r.status == 200:
                        lst = decode(await r.json(content_type=None), key)
                        if lst is not None:
                            return lst
            except Exception:  # noqa: BLE001
                pass
            await sleep(3 * (attempt + 1))
        return None

    async def worker():
        while todo and not state["stop"]:
            if clock() - t0 > BUDGET_S or state["fails"] >= 3:
                state["stop"] = state["stop"] or "budget or repeated failures"
                return
            b = todo.pop()
            lst = await one(b)
            await sleep(GAP_S)
            if lst is None:
                state["fails"] += 1
                continue
            state["fails"] = 0
            if lst and not any(inside(x, b) for x in lst):          # an answer that has nothing to do with the box = the API is serving a default list
                state["stop"] = "answer does not match the requested box"
                return
            for x in lst:
                if inside(x, b) and x.get("slug"):
                    found[x["slug"]] = x
            if len(lst) >= CAP and (b[1] - b[0]) > MIN_SPAN:
                todo.extend(split4(b))

    await asyncio.gather(*(worker() for _ in range(WORKERS)))
    print(f"[chargefinder] {cc}: {len(found)} raw stations, {state['calls']} calls, stop={state['stop']}")
    if state["stop"]:
        return None
    return [x for x in found.values() if (x.get("locationAddress") or {}).get("countryCode", "").upper() == cf_cc]


def build_file(cc: str, stations: List[Dict[str, Any]], today: date) -> Dict[str, Any]:
    """Same schema as chargers.build_file, source ChargeFinder."""
    box = COUNTRIES[cc][2]
    keep = [s for s in stations if box[0] <= s["lat"] <= box[1] and box[2] <= s["lon"] <= box[3]]
    names = sorted({s["op"] for s in keep if s["op"]})
    idx = {n: i + 1 for i, n in enumerate(names)}
    rows = [[round(s["lat"], 5), round(s["lon"], 5), idx.get(s["op"], 0), int(s["kw"] + 0.5) if s["kw"] else 0, s["pts"], s["flags"],
             s["yr"] % 100, s["title"]] for s in keep]
    return {"v": 1, "cc": cc, "generated": today.isoformat(), "source": "chargefinder", "sources": ["ChargeFinder"],
            "attribution": ["Charging stations: ChargeFinder (chargefinder.com), used with permission"],
            "medVerified": today.year, "n": len(rows), "dropped_outside_box": len(stations) - len(keep),
            "ops": names, "s": rows, "notes": []}


async def run(countries: List[str], out_dir: Path, key: str, force: bool = False) -> int:
    """Weekly: a country whose file in out_dir is younger than chargers.MAX_AGE_DAYS is left as it is. Crawl, reduce, guard (count band, no big
    drop vs the previous file, no key in the output), write out_dir/ev_<cc>.json. A failed or refused try keeps the last good file and stamps
    `attempted`, so a bad day is not retried every 15 minutes. Returns files written."""
    ok, today = 0, datetime.now(timezone.utc).date()
    async with aiohttp.ClientSession() as session:
        for cc in countries:
            path = out_dir / f"ev_{cc.lower()}.json"
            try:
                prev = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                prev = None
            if prev and prev.get("v") != 1:
                prev = None
            if not (force or chargers.due(prev, today)):
                print(f"[chargefinder] {cc}: not due")
                continue
            if prev:
                chargers.write_json(path, {**prev, "attempted": today.isoformat()})
            raw = await crawl(session, cc, key)
            sts = [x for x in (reduce_station(r, COUNTRIES[cc][0], today.year) for r in raw or []) if x]
            sts, merged = chargers.dedupe(sts)
            new = build_file(cc, sts, today)
            lo, hi = COUNTRIES[cc][1]
            why = None
            if not raw:
                why = "no usable crawl"
            elif not lo <= new["n"] <= hi:
                why = f"{new['n']} stations outside the band {lo}-{hi}"
            elif prev and prev.get("n") and new["n"] < chargers.DROP_RATIO * prev["n"] and cc not in chargers.ALLOW_SHRINK:
                why = f"{new['n']} stations is a drop of more than 20 % from {prev['n']}"
            elif key in json.dumps(new, ensure_ascii=False):
                why = "the key is present in the output"
            if why:
                print(f"[chargefinder] {cc}: refused ({why}); last good file kept")
                continue
            chargers.write_json(path, new)
            ok += 1
            print(f"[chargefinder] {cc}: {new['n']} stations (dedupe merged {merged}), written")
    return ok


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    k = os.environ.get("CHARGEFINDER_KEY", "").strip()
    if not k:
        print("[chargefinder] CHARGEFINDER_KEY not set - nothing refreshed")
        sys.exit(0)
    asyncio.run(run([a.upper() for a in args[0].split(",")] if args else list(COUNTRIES), Path(os.environ.get("EV_OUT_DIR") or chargers.DATA), k,
                    "--force" in sys.argv or os.environ.get("FORCE_REFRESH") == "1"))
