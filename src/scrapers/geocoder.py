"""
Shared Nominatim geocoding utility for scrapers that lack GPS data in their source.

Each country gets a persistent cache file (data/{cc}_geocache.json) that is:
  - Read from disk at the start of each run (if the scraper wrote it previously)
  - Fetched from the GitHub Pages deployment if no local file exists
  - Written back to disk after new geocoding, then deployed by the gh-pages action

This means geocoding accumulates across runs and never re-queries the same address.
Rate limit: 1 request per second (Nominatim policy).
"""

import asyncio
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import aiohttp

NOMINATIM_URL  = "https://nominatim.openstreetmap.org/search"
NOMINATIM_UA   = "EuroFuelPrices/1.0 (https://github.com/ThorstenGru/nordic-fuel-prices)"
PAGES_BASE     = "https://thorstengru.github.io/nordic-fuel-prices"
_DATA_DIR      = Path(__file__).parent.parent.parent / "data"
GEOCODE_LIMIT  = 250   # max new Nominatim calls per country per scrape run
GLOBAL_BUDGET  = 150   # max new Nominatim calls per run across ALL countries (keeps runs short)
_used = 0
_MIN_INTERVAL  = 1.1   # Nominatim policy: max 1 request/second for the WHOLE process
_rl_lock: Optional[asyncio.Lock] = None
_rl_last = 0.0


async def _throttle() -> None:
    """Process-wide rate limit shared by all countries geocoding concurrently."""
    global _rl_lock, _rl_last
    if _rl_lock is None:
        _rl_lock = asyncio.Lock()
    async with _rl_lock:
        loop = asyncio.get_running_loop()
        wait = _rl_last + _MIN_INTERVAL - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        _rl_last = loop.time()


# ── Cache I/O ─────────────────────────────────────────────────────────────────

async def _load_cache(country_code: str, session: aiohttp.ClientSession) -> Dict:
    """Load geocache from local file, then fall back to the previous GitHub Pages deploy."""
    path = _DATA_DIR / f"{country_code.lower()}_geocache.json"

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    url = f"{PAGES_BASE}/{country_code.lower()}_geocache.json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if isinstance(data, dict):
                    print(f"[{country_code}] Loaded geocache from GitHub Pages ({len(data)} entries)")
                    _save_cache(country_code, data)   # re-publish: gh-pages deploy deletes files absent from data/
                    return data
    except Exception:
        pass

    return {}


def _save_cache(country_code: str, cache: Dict) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    path = _DATA_DIR / f"{country_code.lower()}_geocache.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"))
    except OSError as e:
        print(f"[{country_code}] geocache save failed: {e}")


# ── Single geocode call ────────────────────────────────────────────────────────

async def _geocode_one(
    session: aiohttp.ClientSession,
    city: str,
    street: str,
    postal: str,
    country_code: str,
) -> Tuple[Optional[float], Optional[float], bool]:
    """Nominatim structured search → (lat, lon, definitive).

    ``definitive`` is False for transient failures (timeout, 429, 5xx) so they are not cached
    as "address does not exist" and get retried on a later run.
    """
    params: Dict = {"format": "json", "limit": 1}
    if country_code:
        params["countrycodes"] = country_code.lower()
    if street:
        params["street"] = street
    if city:
        params["city"] = city
    if postal and not city:
        params["postalcode"] = postal
    # Need at least street or city to make a meaningful query
    if not params.get("street") and not params.get("city"):
        return None, None, True
    await _throttle()
    try:
        async with session.get(
            NOMINATIM_URL, params=params,
            headers={"User-Agent": NOMINATIM_UA},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"]), True
                return None, None, True          # Nominatim answered: no such address
            return None, None, False              # 429 / 5xx — try again next run
    except Exception:
        return None, None, False


# ── Main entry point ──────────────────────────────────────────────────────────

async def apply_geocoding(
    stations: List[Dict],
    country_code: str,
    session: aiohttp.ClientSession,
    *,
    key_fn: Callable[[Dict], str],
    query_fn: Callable[[Dict], Tuple[str, str, str]],
    limit: int = GEOCODE_LIMIT,
) -> None:
    """Geocode stations in-place that have lat=None.

    key_fn(station)   → stable string used as the geocache key (e.g. station id, or address key)
    query_fn(station) → (city, street, postal) tuple for the Nominatim query
    limit             → max new geocoding calls this run
    """
    global _used
    cache = await _load_cache(country_code, session)

    # 1. Apply already-cached coordinates
    for s in stations:
        k = key_fn(s)
        if not k:
            continue
        entry = cache.get(k)
        if entry and entry.get("lat") is not None:
            s["lat"] = entry["lat"]
            s["lon"] = entry["lon"]

    # 2. Collect unique keys that have never been geocoded (not in cache at all)
    seen: set = set()
    to_geocode: List[Dict] = []
    for s in stations:
        k = key_fn(s)
        if not k or s["lat"] is not None or k in cache or k in seen:
            continue
        seen.add(k)
        to_geocode.append(s)

    if not to_geocode:
        geocoded = sum(1 for s in stations if s["lat"] is not None)
        print(f"[{country_code}] {geocoded}/{len(stations)} with GPS (cache: {len(cache)})")
        return

    # 3. Geocode sequentially — 1 req/s per Nominatim usage policy
    new_count = 0
    for s in to_geocode[:limit]:
        if _used >= GLOBAL_BUDGET:
            break
        _used += 1
        k = key_fn(s)
        city, street, postal = query_fn(s)
        lat, lon, definitive = await _geocode_one(session, city, street, postal, country_code)
        if definitive:
            cache[k] = {"lat": lat, "lon": lon}     # None/None = Nominatim says it does not exist
        if lat is not None:
            s["lat"] = lat
            s["lon"] = lon
            new_count += 1

    # 4. Persist updated cache
    _save_cache(country_code, cache)

    geocoded  = sum(1 for s in stations if s["lat"] is not None)
    pending   = max(0, len(to_geocode) - limit)
    print(
        f"[{country_code}] {geocoded}/{len(stations)} with GPS "
        f"(+{new_count} new, cache: {len(cache)}, {pending} pending next run)"
    )
