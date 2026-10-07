"""
Shared ANWB Points-of-Interest API scraper  (GRADE C — aggregator data, no price timestamps).

ANWB (Dutch motorist association) resells fuel-price feeds (xavvy, Appitup, ...) for most of
Europe through its Onderweg routing service. It is UNOFFICIAL and UNDOCUMENTED — treat it as a
fallback/supplement wherever a government feed exists, and as the primary only where nothing
better is available (see docs/DATA_SOURCES_AUDIT.md).

Endpoint: https://api.anwb.nl/routing/points-of-interest/v3/all
  ?type-filter=FUEL_STATION
  &bounding-box-filter={min_lat},{min_lon},{max_lat},{max_lon}

Quirks (verified 2026-10-01):
  * A bounding box that would return too many stations answers HTTP 200 with
    {"error": {"code": "limit_exceeded", ...}} and NO "value" array. Germany and Spain exceeded the
    cap as whole-country boxes (=> 0 stations for months). We therefore split a box into quadrants
    (recursively) whenever ANWB says limit_exceeded. Other countries are complete in one request.
  * The payload carries NO per-price timestamp (only value + priceTier), so every price is
    published with updated_at = null (age unknown) instead of a fake "fresh" stamp.
  * Prices come in EUR. For non-euro countries we convert with the ECB daily rate (with a
    Frankfurter fallback). If no rate exists the prices stay EUR and say so (currency field).
"""

import asyncio
import re as _re
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from .base import BaseScraper

_API_BASE = (
    "https://api.anwb.nl/routing/points-of-interest/v3/all"
    "?type-filter=FUEL_STATION"
    "&bounding-box-filter={min_lat}%2C{min_lon}%2C{max_lat}%2C{max_lon}"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest?base=EUR"
# ECB XML uses SINGLE quotes: <Cube currency='USD' rate='1.1355'/>  (the old regex only matched double)
_ECB_RE = _re.compile(r"""currency=['"]([A-Z]{3})['"]\s+rate=['"]([\d.]+)['"]""")
_FIXED_PEGS = {"BAM": 1.95583}          # Bosnian convertible mark: legally pegged to the euro
_ecb_cache: Dict[str, float] = {}       # currency_code -> units per 1 EUR
_ecb_lock: Optional[asyncio.Lock] = None


async def _ecb_rates(session: aiohttp.ClientSession) -> Dict[str, float]:
    """Return {currency: units_per_EUR}. Cached per process, concurrency-safe."""
    global _ecb_lock
    if _ecb_lock is None:
        _ecb_lock = asyncio.Lock()
    async with _ecb_lock:
        if _ecb_cache:
            return _ecb_cache
        try:
            async with session.get(_ECB_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    for m in _ECB_RE.finditer(await resp.text()):
                        _ecb_cache[m.group(1)] = float(m.group(2))
        except Exception as e:
            print(f"[ECB] rate fetch failed: {e}")
        if not _ecb_cache:
            try:
                async with session.get(_FRANKFURTER_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        _ecb_cache.update({k: float(v) for k, v in (data.get("rates") or {}).items()})
            except Exception as e:
                print(f"[ECB] frankfurter fallback failed: {e}")
        for k, v in _FIXED_PEGS.items():
            _ecb_cache.setdefault(k, v)
        print(f"[ECB] {len(_ecb_cache)} FX rates loaded")
        return _ecb_cache


# fuelType -> (fuel_type, unit)  — EURO95 handled separately (E10 if name says so)
_FUEL_MAP = {
    "EURO98":         ("E5",     "L"),
    "SUPER_E5":       ("E5",     "L"),
    "DIESEL":         ("DIESEL", "L"),
    "DIESEL_SPECIAL": ("DIESEL_SPECIAL", "L"),   # resolved per station below
    "LPG":            ("LPG",    "L"),
    "AUTOGAS":        ("LPG",    "L"),
    "CNG":            ("CNG",    "kg"),
    "E85":            ("E85",    "L"),
    "HVO":            ("HVO100", "L"),
    "HVO100":         ("HVO100", "L"),
}


def _map_fuel(fuel_type: str, fuel_name: str) -> Optional[Tuple[str, str]]:
    if fuel_type == "EURO95":
        return ("E10", "L") if "E10" in fuel_name else ("E5", "L")
    return _FUEL_MAP.get(fuel_type)


_MIN_TILE_DEG = 0.04   # never split below ~4 km; give up on that tile instead


class ANWBScraper(BaseScraper):
    """Base class for country scrapers backed by the ANWB POI API."""

    # Subclasses must set these:
    ISO3: str = ""                                          # e.g. "NLD", "BEL", "POL"
    BBOX: Tuple[float, float, float, float] = (0, 0, 0, 0)  # min_lat, min_lon, max_lat, max_lon
    CURRENCY = "EUR"   # override for non-eurozone countries (e.g. "PLN", "HUF", "CZK")
    TILE_STEP: Optional[float] = None   # pre-split the bbox into tiles of this many degrees
    GRADE = "C"
    REFRESH_MINUTES = 55                # unofficial feed: be gentle (about hourly)

    _CONCURRENCY = 8

    # ── ANWB access ───────────────────────────────────────────────────────────

    async def _query(self, bb: Tuple[float, float, float, float], sem: asyncio.Semaphore,
                     depth: int = 0) -> List[Dict[str, Any]]:
        """Fetch one bbox; on ANWB's limit_exceeded split it into 4 quadrants and recurse."""
        min_lat, min_lon, max_lat, max_lon = bb
        url = _API_BASE.format(min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon)
        data: Optional[dict] = None
        for attempt in range(3):
            try:
                async with sem:
                    async with self.session.get(url, headers=_HEADERS,
                                                timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            break
                        print(f"[{self.COUNTRY}] ANWB HTTP {resp.status} (attempt {attempt + 1})")
            except Exception as e:
                print(f"[{self.COUNTRY}] ANWB fetch error: {e} (attempt {attempt + 1})")
            await asyncio.sleep(2 * (attempt + 1))
        if not isinstance(data, dict):
            raise RuntimeError(f"ANWB bbox {bb} failed after retries")

        err = data.get("error")
        if isinstance(err, dict):
            if err.get("code") == "limit_exceeded":
                if (max_lat - min_lat) <= _MIN_TILE_DEG * 2 and (max_lon - min_lon) <= _MIN_TILE_DEG * 2:
                    print(f"[{self.COUNTRY}] ANWB tile {bb} still over limit at minimum size — skipped")
                    return []
                mid_lat, mid_lon = (min_lat + max_lat) / 2, (min_lon + max_lon) / 2
                quads = [
                    (min_lat, min_lon, mid_lat, mid_lon), (min_lat, mid_lon, mid_lat, max_lon),
                    (mid_lat, min_lon, max_lat, mid_lon), (mid_lat, mid_lon, max_lat, max_lon),
                ]
                parts = await asyncio.gather(*(self._query(q, sem, depth + 1) for q in quads))
                return [s for part in parts for s in part]
            raise RuntimeError(f"ANWB error {err.get('code')}: {err.get('message')}")
        return data.get("value", []) or []

    def _initial_tiles(self) -> List[Tuple[float, float, float, float]]:
        min_lat, min_lon, max_lat, max_lon = self.BBOX
        step = self.TILE_STEP
        if not step:
            return [self.BBOX]
        tiles = []
        lat = min_lat
        while lat < max_lat:
            lon = min_lon
            while lon < max_lon:
                tiles.append((round(lat, 4), round(lon, 4),
                              round(min(lat + step, max_lat), 4), round(min(lon + step, max_lon), 4)))
                lon += step
            lat += step
        return tiles

    # ── scraper ───────────────────────────────────────────────────────────────

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(self._CONCURRENCY)
        parts = await asyncio.gather(*(self._query(t, sem) for t in self._initial_tiles()))
        raw: Dict[str, Dict[str, Any]] = {}
        for part in parts:
            for s in part:
                sid = s.get("id")
                if sid and sid not in raw:
                    raw[sid] = s

        stations = []
        for sid, s in raw.items():
            addr = s.get("address", {}) or {}
            if addr.get("iso3CountryCode") != self.ISO3:
                continue
            coords = s.get("coordinates", {}) or {}
            lat, lon = coords.get("latitude"), coords.get("longitude")
            if lat is None or lon is None:
                continue

            prices = []
            for p in s.get("prices", []) or []:
                mapped = _map_fuel(p.get("fuelType", ""), p.get("fuelName", ""))
                if mapped is None:
                    continue
                val = p.get("value")
                if not isinstance(val, (int, float)) or val <= 0:
                    continue
                fuel_type, unit = mapped
                # EUR as delivered; converted to local currency below when a rate exists
                prices.append({"fuel_type": fuel_type, "price": float(val), "currency": "EUR",
                               "unit": unit, "updated_at": None})

            # Regular vs premium diesel: a station must never carry two DIESEL prices (benchmark
            # 2026-10-07: they differ by 7-24 ct). Prefer the regular one; use "special" only when
            # it is the only diesel the station reports (ANWB tags regular diesel as premium in HR).
            if any(p["fuel_type"] == "DIESEL" for p in prices):
                prices = [p for p in prices if p["fuel_type"] != "DIESEL_SPECIAL"]
            else:
                for p in prices:
                    if p["fuel_type"] == "DIESEL_SPECIAL":
                        p["fuel_type"] = "DIESEL"

            safe_id = str(sid).replace("|", "_").replace(" ", "_")
            stations.append({
                "id":         f"{self.COUNTRY.lower()}_{safe_id}",
                "country":    self.COUNTRY,
                "name":       s.get("title", ""),
                "brand":      s.get("title", ""),
                "address":    addr.get("streetAddress", ""),
                "city":       addr.get("city", ""),
                "lat":        lat,
                "lon":        lon,
                "source":     self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices":     prices,        # [] = known location, price unavailable
            })

        # Convert EUR -> local currency when the country doesn't use EUR
        if self.CURRENCY != "EUR" and stations:
            rates = await _ecb_rates(self.session)
            rate = rates.get(self.CURRENCY)
            if rate:
                for st in stations:
                    for p in st["prices"]:
                        p["price"] = round(p["price"] * rate, 2 if rate > 20 else 3)
                        p["currency"] = self.CURRENCY
            else:
                print(f"[{self.COUNTRY}] no FX rate for {self.CURRENCY} — prices stay in EUR")

        priced = sum(1 for st in stations if st["prices"])
        print(f"[{self.COUNTRY}] {len(stations)} stations ({priced} priced) from ANWB API")
        return stations
