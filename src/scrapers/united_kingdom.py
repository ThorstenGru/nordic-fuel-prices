"""
United Kingdom — open retailer fuel-price JSON feeds (CMA "Open Data" format) PRIMARY, ANWB fills gaps.

Why not the official Fuel Finder CSV?  (researched 2026-10-07)
  The statutory Fuel Finder scheme (DESNZ, Motor Fuel Price (Open Data) Regulations 2025) offers the
  latest CSV only via https://www.developer.fuel-finder.service.gov.uk/access-latest-fuelprices, which
  shows a pre-signed S3 link (valid ~12 h, one publish, updated twice daily). That page answers
  HTTP 403 (CloudFront) to every non-browser request, so there is no stable, scriptable URL.
  The API needs OAuth (not working at the moment). So the official data is NOT used here.

Retailer feeds (same schema: last_updated + stations[] with site_id, brand, address, postcode,
location{latitude,longitude}, prices{E10,E5,B7,SDV} in pence per litre). Feeds whose last_updated is
older than _MAX_AGE_DAYS are skipped (Rontec, Shell, Applegreen are stale / frozen; Morrisons only lists
Gibraltar; Tesco/BP/Co-op/Jet block bots). Timestamps are per feed ("last_updated", UK local time).

ANWB (src/scrapers/_anwb.py, ~8.6k UK stations, no timestamps) runs independently; one source failing is
logged, only both failing raises. Merge (see _merge): a retailer and an ANWB station are the same only if
within 100 m, with recognised compatible brands, and mutually unique. Retailer prices win; ANWB only fills
fuel types the retailer record lacks. ANWB-only stations are added with source "anwb" and updated_at null.
Currency: ANWB delivers EUR; _anwb.py converts to GBP with the ECB rate (CURRENCY = "GBP"), each price keeps
its own currency field. ANWB prices still in EUR (no rate) are dropped so GBP and EUR are never mixed.

Licence: retailer data published under the CMA/DESNZ open-data scheme; ANWB is unofficial/undocumented.
SDV (premium diesel) is not published: the site only has one DIESEL class (B7).
"""

import asyncio
import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ._anwb import ANWBScraper
from .base import iso_utc, octane_of

_FEEDS = {
    "Asda":   "https://storelocator.asda.com/fuel_prices_data.json",
    "Esso":   "https://fuelprices.esso.co.uk/latestdata.json",
    "MFG":    "https://fuel.motorfuelgroup.com/fuel_prices_data.json",
    "Moto":   "https://moto-way.com/fuel-price/fuel_prices.json",
    "SGN":    "https://www.sgnretail.uk/files/data/SGN_daily_fuel_prices.json",
}
_MAX_AGE_DAYS = 7
_MERGE_RADIUS_M = 100.0
_FUEL_MAP = {"E10": "E10", "E5": "E5", "B7": "DIESEL"}   # SDV (premium diesel) intentionally dropped
_FUEL_OCTANE = {"E10": 95, "E5": 97}   # UK retailer E5 = super unleaded (97+ RON); E10 = standard 95
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36", "Accept": "application/json"}
_LAT = (49.8, 60.9)
_LON = (-8.7, 1.9)


class UnitedKingdomScraper(ANWBScraper):
    COUNTRY    = "GB"
    ISO3       = "GBR"
    CURRENCY   = "GBP"
    BBOX       = (49.8, -8.7, 60.9, 1.9)
    TILE_STEP  = 3.0
    SOURCE     = "UK retailer open price feeds (Asda, Esso, MFG, Moto, SGN) + anwb.nl for remaining stations"
    CONFIDENCE = 0.85
    GRADE      = "B"
    REFRESH_MINUTES = 30

    async def _get_feed(self, name: str, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.session.get(url, headers=_HEADERS, timeout=40) as r:
                if r.status != 200:
                    print(f"[GB] {name}: HTTP {r.status}")
                    return None
                raw = await r.read()
            return json.loads(raw.decode("utf-8-sig"))
        except Exception as e:
            print(f"[GB] {name}: {type(e).__name__}: {e}")
            return None

    async def _fetch_retailers(self) -> List[Dict[str, Any]]:
        feeds = await asyncio.gather(*[self._get_feed(n, u) for n, u in _FEEDS.items()])
        cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)
        by_id: Dict[str, Dict[str, Any]] = {}

        for (name, _), data in zip(_FEEDS.items(), feeds):
            if not isinstance(data, dict):
                continue
            ts = iso_utc(data.get("last_updated"), "Europe/London")
            if not ts or datetime.fromisoformat(ts) < cutoff:
                print(f"[GB] {name}: stale/undated feed ({data.get('last_updated')}) skipped")
                continue
            n = 0
            for s in data.get("stations") or []:
                try:
                    loc = s.get("location") or {}
                    lat, lon = float(loc["latitude"]), float(loc["longitude"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not (_LAT[0] <= lat <= _LAT[1] and _LON[0] <= lon <= _LON[1]):
                    continue
                prices = []
                for k, ft in _FUEL_MAP.items():
                    try:
                        pence = float((s.get("prices") or {}).get(k))
                    except (TypeError, ValueError):
                        continue
                    if pence <= 0:
                        continue
                    e = self.price_entry(ft, round(pence / 100.0, 3), "L", ts, octane=_FUEL_OCTANE.get(ft))
                    e["source"] = "retailer"
                    prices.append(e)
                sid = str(s.get("site_id") or f"{lat:.5f}_{lon:.5f}")
                st = {
                    "id": f"gb_{sid}",
                    "country": self.COUNTRY,
                    "name": s.get("brand") or "",
                    "brand": s.get("brand") or "",
                    "address": (s.get("address") or "").strip(),
                    "city": "",
                    "postcode": s.get("postcode") or "",
                    "lat": lat,
                    "lon": lon,
                    "source": f"retailer feed [{name}]",
                    "confidence": 0.90,
                    "prices": prices,
                    "sources": ["retailer"],
                }
                prev = by_id.get(st["id"])
                if prev is None or (prices and (not prev["prices"] or
                                    prices[0]["updated_at"] > prev["prices"][0]["updated_at"])):
                    by_id[st["id"]] = st
                n += 1
            print(f"[GB] {name}: {n} stations, last_updated {data.get('last_updated')}")
        return list(by_id.values())

    async def _fetch_anwb(self) -> List[Dict[str, Any]]:
        out = []
        for s in await super().fetch_stations():
            ps = []
            for p in s.get("prices", []):
                if p.get("currency") != self.CURRENCY:      # unconverted EUR: never mix currencies
                    continue
                p["source"] = "anwb"
                p["updated_at"] = None
                # Benchmark 2026-10-07: ANWB's UK "Euro 95 (E10)" price is really the E5 super-unleaded
                # price (85% within 1 p of the retailer E5, 8% of E10; ~17 p above true E10). Label it E5.
                # New ANWB mapping: that price arrives as fuel_type "95" (old: "E10"/"E5"); the 98 grade as
                # "98" (old: "E5"). Both are UK super-unleaded: E5, octane 97 (98 when ANWB says 98).
                if p["fuel_type"] in ("E10", "E5", "95", "98"):
                    o = octane_of(p)
                    p["octane"] = 98 if (p["fuel_type"] == "98" or (o or 0) >= 98) else 97
                    p["fuel_type"] = "E5"
                ps.append(p)
            best: Dict[str, Dict[str, Any]] = {}
            for p in ps:                       # E5 can appear twice (super + 98): keep the lower
                if p["fuel_type"] not in best or p["price"] < best[p["fuel_type"]]["price"]:
                    best[p["fuel_type"]] = p
            ps = list(best.values())
            s["prices"] = ps
            s["source"] = "anwb.nl (ANWB POI API)"
            s["confidence"] = 0.70
            s["sources"] = ["anwb"]
            out.append(s)
        return out

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        retail, anwb = await asyncio.gather(self._fetch_retailers(), self._fetch_anwb(),
                                            return_exceptions=True)
        if isinstance(retail, BaseException):
            print(f"[GB] retailer feeds FAILED: {type(retail).__name__}: {retail}")
            retail = []
        if isinstance(anwb, BaseException):
            print(f"[GB] ANWB FAILED: {type(anwb).__name__}: {anwb}")
            anwb = []
        if not retail and not anwb:
            raise RuntimeError("GB: retailer feeds and ANWB both returned no data")
        n_r, n_a = len(retail), len(anwb)
        merged, pairs = _merge(retail, anwb)
        self.merge_stats = {"retailer": n_r, "anwb": n_a, "pairs": pairs, "final": len(merged)}
        print(f"[GB] retailer={n_r} anwb={n_a} merged_pairs={pairs} final={len(merged)}")
        return merged


_BRAND_PATTERNS = [
    (re.compile(r"\bbp\b"), "bp"), (re.compile(r"\besso\b"), "esso"),
    (re.compile(r"\bshell\b"), "shell"), (re.compile(r"\basda\b"), "asda"),
    (re.compile(r"\btesco\b"), "tesco"), (re.compile(r"sainsbury"), "sainsburys"),
    (re.compile(r"morrisons?"), "morrisons"), (re.compile(r"\bmoto\b"), "moto"),
    (re.compile(r"\btexaco\b"), "texaco"), (re.compile(r"\bjet\b"), "jet"),
    (re.compile(r"\bgulf\b"), "gulf"), (re.compile(r"\bmurco\b"), "murco"),
    (re.compile(r"\bapplegreen\b"), "applegreen"), (re.compile(r"\brontec\b"), "rontec"),
    (re.compile(r"\bco-?op\b"), "coop"), (re.compile(r"\bharvest\b"), "harvest"),
    (re.compile(r"\bcostco\b"), "costco"), (re.compile(r"\bwaitrose\b"), "waitrose"),
    (re.compile(r"\bsgn\b"), "sgn"), (re.compile(r"\bmfg\b|motor fuel group"), "mfg"),
]
# Operator names that run forecourts under third-party fuel brands.
_OPERATORS = {"mfg", "sgn"}
_OPERATED = {"bp", "esso", "shell", "texaco", "gulf", "jet", "murco"}


def _brands(*names: Any) -> frozenset:
    out = set()
    for n in names:
        low = str(n or "").lower()
        for rx, b in _BRAND_PATTERNS:
            if rx.search(low):
                out.add(b)
    return frozenset(out)


def _compatible(a: frozenset, b: frozenset) -> bool:
    if not a or not b:
        return False          # unknown brand => never merge
    if a & b:
        return True
    return any((x in _OPERATORS and y in _OPERATED) or (y in _OPERATORS and x in _OPERATED)
               for x in a for y in b)


def _dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    dlat = (b_lat - a_lat) * 111_320.0
    dlon = (b_lon - a_lon) * 111_320.0 * math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot(dlat, dlon)


def _slot(p: Dict) -> str:
    """Merge slot: petrol bucketed by octane (95 / 97+), other fuels by fuel_type."""
    o = octane_of(p)
    if o is None:
        return p["fuel_type"]
    return "P97" if o >= 97 else "P95"


def _merge(retail: List[Dict], anwb: List[Dict]):
    """Mutually-unique <=100 m + compatible-brand match; retailer prices win, ANWB fills missing fuels."""
    for s in retail + anwb:
        s["_b"] = _brands(s.get("brand"), s.get("name"))
    grid: Dict[tuple, List[int]] = {}
    for j, r in enumerate(retail):
        grid.setdefault((int(r["lat"] * 100), int(r["lon"] * 100)), []).append(j)
    fwd: Dict[int, List[int]] = {}
    rev: Dict[int, List[int]] = {}
    for i, a in enumerate(anwb):
        if not a["_b"]:
            continue
        ci, cj = int(a["lat"] * 100), int(a["lon"] * 100)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for j in grid.get((ci + di, cj + dj), []):
                    r = retail[j]
                    if _compatible(a["_b"], r["_b"]) and \
                            _dist_m(a["lat"], a["lon"], r["lat"], r["lon"]) <= _MERGE_RADIUS_M:
                        fwd.setdefault(i, []).append(j)
                        rev.setdefault(j, []).append(i)
    pairs = 0
    extra = []
    for i, a in enumerate(anwb):
        c = fwd.get(i, [])
        if len(c) == 1 and len(rev.get(c[0], [])) == 1:
            r = retail[c[0]]
            have = {_slot(p) for p in r["prices"]}
            filled = False
            for p in a["prices"]:
                if _slot(p) not in have:
                    r["prices"].append(p)
                    have.add(_slot(p))
                    filled = True
            if filled:
                r["sources"].append("anwb")
            pairs += 1
        else:
            extra.append(a)
    out = retail + extra
    for s in out:
        s.pop("_b", None)
    return out, pairs
