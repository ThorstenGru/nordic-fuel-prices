"""
Czechia: BenzinMapa.cz (station base + REAL reported prices) with ANWB as gap filler.

BenzinMapa.cz (https://benzinmapa.cz, operator Jiri Karafiat) publishes ONE static file,
https://benzinmapa.cz/data/map_data.json (~130 KB gzip, refreshed ~daily, 3 x/day nominal), with
~3,170 OpenStreetMap-keyed stations ("osm_<node id>"), lat/lng, brand, and a price block
p = {n95, n98, naf (diesel), lpg, src, at}  (CZK per litre, 'at' = ISO-8601 UTC).
robots.txt allows /data/ (it disallows /api/ and /_next/, which we never touch).

IMPORTANT data-quality finding (2026-10-07): p.src is
  * "mbenzin-avg-offset" for ~99% of stations = an ESTIMATE (national average + brand offset), NOT a
    price anyone reported. The site's own terms say so. We NEVER publish those as station prices.
  * "tank-ono.cz"  = chain-published price (Tank ONO), real.
  * "uzivatel"     = a user-reported price with its own timestamp, real.
So only the real prices are kept; estimated stations stay as location-only (prices = []) unless
ANWB covers them, in which case ANWB supplies the price.

Licence: owner confirmed use is cleared. Attribution: "BenzinMapa.cz (community prices from
mbenzin.cz / Tank ONO; station positions (c) OpenStreetMap contributors, ODbL); ANWB for gaps".

Merge policy (same conservative approach as denmark.py): one record per physical station; two records
are the same only when within ~100 m AND the canonical brand is known and equal AND the match is
mutually unique. Fuel types are filled by priority (BenzinMapa first, ANWB last); when both have a
fuel the one with the newer per-price timestamp wins (a missing timestamp loses); nothing is averaged.
Each price carries 'source'; each station carries a 'sources' list.
"""

import math
import re
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseScraper, iso_utc
from ._anwb import ANWBScraper

BM_URL = "https://benzinmapa.cz/data/map_data.json"
USER_AGENT = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
CZ_TZ = "Europe/Prague"

MERGE_RADIUS_M = 100.0
SOURCE_PRIORITY = ["benzinmapa", "anwb"]
REAL_BM_SRC = {"tank-ono.cz", "uzivatel"}          # everything else (mbenzin-avg-offset) is an estimate
BM_FUELS = {"n95": "E10", "n98": "E5", "naf": "DIESEL", "lpg": "LPG"}   # site convention: E10=95, E5=98
CZK_BAND = (15.0, 90.0)
LPG_BAND = (10.0, 50.0)
LAT_RANGE, LON_RANGE = (48.5, 51.1), (12.0, 18.9)

BRAND_PATTERNS = [
    (re.compile(r"\bmol\b"), "mol"),
    (re.compile(r"orlen|benzina"), "orlen"),
    (re.compile(r"\bshell\b"), "shell"),
    (re.compile(r"\bomv\b"), "omv"),
    (re.compile(r"\beni\b|agip"), "eni"),
    (re.compile(r"\bono\b|tank\s*ono"), "ono"),
    (re.compile(r"euro\s*oil"), "eurooil"),
    (re.compile(r"robin\s*oil"), "robinoil"),
    (re.compile(r"\bcircle\s*k\b"), "circlek"),
    (re.compile(r"\bglobus\b"), "globus"),
    (re.compile(r"\bmakro\b"), "makro"),
    (re.compile(r"\btesco\b"), "tesco"),
    (re.compile(r"\balbert\b"), "albert"),
    (re.compile(r"\bkaufland\b"), "kaufland"),
    (re.compile(r"\bpap\s*oil\b"), "papoil"),
    (re.compile(r"\bprim\b"), "prim"),
    (re.compile(r"\bslovnaft\b"), "slovnaft"),
]


def canonical_brand(*names: str) -> Optional[str]:
    """Canonical chain id, or None when unknown (unknown brands are never merged)."""
    for n in names:
        low = (n or "").lower().strip()
        if not low:
            continue
        for rx, brand in BRAND_PATTERNS:
            if rx.search(low):
                return brand
    return None


def _dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    dlat = (b_lat - a_lat) * 111_320.0
    dlon = (b_lon - a_lon) * 111_320.0 * math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot(dlat, dlon)


def _in_cz(lat, lon) -> bool:
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1])


def _plausible(fuel: str, price: float) -> bool:
    lo, hi = LPG_BAND if fuel in ("LPG", "CNG") else CZK_BAND
    return lo <= price <= hi


class _CZAnwb(ANWBScraper):
    COUNTRY = "CZ"
    ISO3 = "CZE"
    CURRENCY = "CZK"
    BBOX = (48.55, 12.10, 51.06, 18.87)
    SOURCE = "anwb.nl (ANWB POI API)"


class CzechiaScraper(BaseScraper):
    COUNTRY = "CZ"
    CURRENCY = "CZK"
    SOURCE = ("BenzinMapa.cz (community/chain-reported prices; stations (c) OpenStreetMap contributors, ODbL)"
              " + anwb.nl (ANWB POI API) for gaps")
    CONFIDENCE = 0.75
    GRADE = "D"                    # crowd-sourced primary; ANWB aggregator fills gaps
    REFRESH_MINUTES = 60
    requests_made = 0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        by_source: Dict[str, List[Dict]] = {}
        errors = []
        try:
            bm = await self._fetch_benzinmapa()
            if bm:
                by_source["benzinmapa"] = bm
        except Exception as e:                       # 403/429 and friends surface here, source skipped
            errors.append(f"benzinmapa: {type(e).__name__}: {e}")
        try:
            anwb = await _CZAnwb(self.session).fetch_stations()
            self._clean_anwb(anwb)
            if anwb:
                by_source["anwb"] = anwb
        except Exception as e:
            errors.append(f"anwb: {type(e).__name__}: {e}")
        for er in errors:
            print(f"[CZ] source FAILED: {er}")
        if not by_source:
            raise RuntimeError("CZ: all sources failed or returned nothing: " + "; ".join(errors))

        raw_total = sum(len(v) for v in by_source.values())
        merged = self._merge(by_source)
        priced = sum(1 for s in merged if s["prices"])
        print("[CZ] sources: " + ", ".join(f"{k}={len(v)}" for k, v in by_source.items())
              + f" | before dedupe={raw_total} after={len(merged)} priced={priced}")
        return merged

    # -- BenzinMapa ----------------------------------------------------------
    async def _fetch_benzinmapa(self) -> List[Dict]:
        CzechiaScraper.requests_made += 1
        async with self.session.get(
            BM_URL, timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as resp:
            if resp.status in (403, 429):
                raise RuntimeError(f"HTTP {resp.status} (blocked / rate-limited)")
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
            data = await resp.json(content_type=None)
        return self._parse_benzinmapa(data)

    def _parse_benzinmapa(self, data: Any) -> List[Dict]:
        items = (data or {}).get("stations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise RuntimeError("unexpected BenzinMapa schema (no 'stations' list)")
        out = []
        for it in items:
            try:
                lat, lon = float(it.get("lat")), float(it.get("lng"))
            except (TypeError, ValueError):
                continue
            if not _in_cz(lat, lon):
                continue
            p = it.get("p") or {}
            prices = []
            if p.get("src") in REAL_BM_SRC:           # skip 'mbenzin-avg-offset' estimates
                ts = p.get("at")
                for key, fuel in BM_FUELS.items():
                    try:
                        val = float(p.get(key))
                    except (TypeError, ValueError):
                        continue
                    if val > 0 and _plausible(fuel, val):
                        e = self.price_entry(fuel, val, "L", updated_at=ts, tz=CZ_TZ)
                        e["source"] = "benzinmapa"
                        prices.append(e)
            city = it.get("city") or ""
            out.append({
                "id": f"cz_bm_{it.get('id', '')}",
                "country": "CZ",
                "name": it.get("name") or it.get("brand") or "",
                "address": "" if str(it.get("address", "")).startswith("GPS ") else (it.get("address") or ""),
                "city": city,
                "brand": it.get("brand") or it.get("name") or "",
                "lat": lat,
                "lon": lon,
                "source": "benzinmapa.cz",
                "confidence": self.CONFIDENCE,
                "prices": prices,                     # [] = location only (price was an estimate)
            })
        return out

    # -- ANWB cleanup --------------------------------------------------------
    def _clean_anwb(self, stations: List[Dict]) -> None:
        """ANWB sometimes returns two entries for one fuel (95 and 98 both -> E5): keep the lower
        price per fuel (never average), drop implausible values and out-of-country coordinates."""
        for st in stations[:]:
            if not _in_cz(st.get("lat"), st.get("lon")):
                stations.remove(st)
                continue
            best: Dict[str, Dict] = {}
            for p in st.get("prices", []):
                if p.get("currency") != "CZK" or not _plausible(p["fuel_type"], p["price"]):
                    continue
                cur = best.get(p["fuel_type"])
                if cur is None or p["price"] < cur["price"]:
                    best[p["fuel_type"]] = p
            st["prices"] = list(best.values())

    # -- merge ---------------------------------------------------------------
    def _merge(self, by_source: Dict[str, List[Dict]]) -> List[Dict]:
        kept: List[Dict] = []
        for src in SOURCE_PRIORITY:
            batch = by_source.get(src)
            if not batch:
                continue
            for st in batch:
                st["_brand"] = canonical_brand(st.get("brand"), st.get("name"))
                for p in st.get("prices", []):
                    p["source"] = src
                st["sources"] = [src]

            fwd: Dict[int, List[int]] = {}
            rev: Dict[int, List[int]] = {}
            near: Dict[int, int] = {}      # batch idx -> any kept station within radius (brand ignored)
            for i, st in enumerate(batch):
                for j, k in enumerate(kept):
                    if abs(k["lat"] - st["lat"]) > 0.002 or abs(k["lon"] - st["lon"]) > 0.004:
                        continue
                    if _dist_m(k["lat"], k["lon"], st["lat"], st["lon"]) > MERGE_RADIUS_M:
                        continue
                    near[i] = near.get(i, 0) + 1
                    if st["_brand"] and k["_brand"] == st["_brand"]:
                        fwd.setdefault(i, []).append(j)
                        rev.setdefault(j, []).append(i)

            add: List[Dict] = []
            for i, st in enumerate(batch):
                cands = fwd.get(i, [])
                if len(cands) == 1 and len(rev.get(cands[0], [])) == 1:
                    k = kept[cands[0]]
                    by_fuel = {p["fuel_type"]: p for p in k["prices"]}
                    for p in st.get("prices", []):
                        cur = by_fuel.get(p["fuel_type"])
                        if cur is None:
                            k["prices"].append(p)
                            by_fuel[p["fuel_type"]] = p
                        elif (p.get("updated_at") or "") > (cur.get("updated_at") or ""):
                            k["prices"][k["prices"].index(cur)] = p      # strictly newer wins
                            by_fuel[p["fuel_type"]] = p
                    k["sources"].append(src)
                elif src != "benzinmapa" or st["prices"] or not near.get(i):
                    add.append(st)
                # else: unpriced (estimated) BenzinMapa location next to an existing record: drop
            kept.extend(add)

        # Second pass: unpriced BenzinMapa locations lose to any ANWB station within radius
        # (brand-agnostic), since they carry no data the ANWB record lacks.
        anwb_pts = [k for k in kept if "anwb" in k["sources"] and "benzinmapa" not in k["sources"]]
        final = []
        for k in kept:
            if k["sources"] == ["benzinmapa"] and not k["prices"]:
                if any(abs(a["lat"] - k["lat"]) <= 0.002 and abs(a["lon"] - k["lon"]) <= 0.004
                       and _dist_m(a["lat"], a["lon"], k["lat"], k["lon"]) <= MERGE_RADIUS_M
                       for a in anwb_pts):
                    continue
            final.append(k)
        for k in final:
            k.pop("_brand", None)
        return final
