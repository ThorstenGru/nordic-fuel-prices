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

Merge: delegated to merge_engine.merge_sources. SourceResults: BenzinMapa real prices priority 1 'crowd';
BenzinMapa location-only stations as a separate 'geometry' result (they only survive where no priced
station is near); ANWB priority 9 'aggregator' (already CZK). Newer timestamp wins by >= 30 min, else
priority. A failing source is marked ok=False; raise only when all fail.
"""

import math
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseScraper, iso_utc, octane_of
from ._anwb import ANWBScraper
from merge_engine import MergeConfig, SourceResult, merge_sources

BM_URL = "https://benzinmapa.cz/data/map_data.json"
USER_AGENT = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
CZ_TZ = "Europe/Prague"

REAL_BM_SRC = {"tank-ono.cz", "uzivatel"}          # everything else (mbenzin-avg-offset) is an estimate
BM_FUELS = {"n95": "E10", "n98": "E5", "naf": "DIESEL", "lpg": "LPG"}   # site convention: E10=95, E5=98
CZK_BAND = (15.0, 90.0)
LPG_BAND = (10.0, 50.0)
LAT_RANGE, LON_RANGE = (48.5, 51.1), (12.0, 18.9)

def _dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    dlat = (b_lat - a_lat) * 111_320.0
    dlon = (b_lon - a_lon) * 111_320.0 * math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot(dlat, dlon)


def _in_cz(lat, lon) -> bool:
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1])


def _slot(p: Dict) -> str:
    """Merge slot: petrol bucketed by octane (95 / 98+), other fuels by fuel_type."""
    o = octane_of(p)
    if o is None:
        return p["fuel_type"]
    return "P98" if o >= 97 else "P95"


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
    merge_report: Dict[str, Any] = {}

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        errors: Dict[str, str] = {}
        bm: List[Dict] = []
        anwb: List[Dict] = []
        try:
            bm = await self._fetch_benzinmapa()
            if not bm:
                errors["benzinmapa"] = "0 stations"
        except Exception as e:                       # 403/429 and friends surface here, source skipped
            errors["benzinmapa"] = f"{type(e).__name__}: {e}"
        try:
            anwb = await _CZAnwb(self.session).fetch_stations()
            self._clean_anwb(anwb)
            if not anwb:
                errors["anwb"] = "0 stations"
        except Exception as e:
            errors["anwb"] = f"{type(e).__name__}: {e}"
        for src, er in errors.items():
            print(f"[CZ] source {src} FAILED: {er}")
        bm_ok, anwb_ok = "benzinmapa" not in errors, "anwb" not in errors
        results = [
            SourceResult("benzinmapa", "BenzinMapa.cz", [s for s in bm if s["prices"]], 1, "crowd", "CZK",
                         bm_ok, errors.get("benzinmapa")),
            SourceResult("benzinmapa_loc", "BenzinMapa.cz (locations)", [s for s in bm if not s["prices"]], 5,
                         "geometry", "CZK", bm_ok, errors.get("benzinmapa")),
            SourceResult("anwb", "anwb.nl", anwb, 9, "aggregator", "CZK", anwb_ok, errors.get("anwb")),
        ]
        if not any(r.ok for r in results):
            raise RuntimeError("CZ: all sources failed or returned nothing: " + "; ".join(errors.values()))
        merged, self.merge_report = merge_sources(results, MergeConfig(country="CZ"))
        for st in merged:
            st.setdefault("confidence", self.CONFIDENCE)
        rp = self.merge_report
        print(f"[CZ] bm={len(bm)} anwb={len(anwb)} | after merge={len(merged)} priced={rp['priced_station_count']}"
              f" conflicts={rp['conflicts']} outliers={rp['outliers_dropped']}")
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
                        e = self.price_entry(fuel, val, "L", updated_at=ts, tz=CZ_TZ,
                                             octane={"E10": 95, "E5": 98}.get(fuel))
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
        """ANWB may return several entries for one slot (octane bucket 95 / 98+): keep the lower
        price per fuel (never average), drop implausible values and out-of-country coordinates."""
        for st in stations[:]:
            if not _in_cz(st.get("lat"), st.get("lon")):
                stations.remove(st)
                continue
            best: Dict[str, Dict] = {}
            for p in st.get("prices", []):
                if p.get("currency") != "CZK" or not _plausible(p["fuel_type"], p["price"]):
                    continue
                cur = best.get(_slot(p))
                if cur is None or p["price"] < cur["price"]:
                    best[_slot(p)] = p
            st["prices"] = list(best.values())
