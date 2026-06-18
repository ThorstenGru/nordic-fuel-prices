import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Slovenia: mandatory fuel price reporting via goriva.si (Ministry-backed portal)
# Working endpoint: /api/v1/search/ (public, no auth) — paginated DRF response
# ~550 stations with GPS, real-time prices
#
# Price fields (Slovenian keys in prices dict):
#   95               → E5 (Eurosuper 95)
#   98, 100          → E5 (premium 98/100 octane)
#   dizel            → DIESEL
#   dizel-premium    → DIESEL (premium)
#   avtoplin-lpg     → LPG
#   hvo              → HVO100
#   cng              → CNG
#   KOEL             → skip (heating/commercial oil)
#   lng              → skip (LNG — rare, different use case)

BASE_URL = "https://goriva.si/api/v1/search/"

_PRICE_MAP = {
    "95":           ("E5",     "L"),
    "98":           ("E5",     "L"),
    "100":          ("E5",     "L"),
    "dizel":        ("DIESEL", "L"),
    "dizel-premium":("DIESEL", "L"),
    "avtoplin-lpg": ("LPG",    "L"),
    "hvo":          ("HVO100", "L"),
    "cng":          ("CNG",    "kg"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://goriva.si/",
}

# Slovenia geographic bounds
_LAT_MIN, _LAT_MAX = 45.4, 46.9
_LON_MIN, _LON_MAX = 13.3, 16.7


class SloveniaScraper(BaseScraper):
    COUNTRY = "SI"
    CURRENCY = "EUR"
    SOURCE = "goriva.si"
    CONFIDENCE = 1.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        all_items: List[dict] = []
        url: Optional[str] = f"{BASE_URL}?format=json"

        while url:
            try:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers=_HEADERS,
                ) as resp:
                    if resp.status != 200:
                        print(f"[SI] HTTP {resp.status} — {url}")
                        break
                    page = await resp.json(content_type=None)
            except Exception as e:
                print(f"[SI] {e} — {url}")
                break

            results = page.get("results") if isinstance(page, dict) else None
            if not results:
                break

            all_items.extend(results)
            url = page.get("next")  # None when no more pages

            # Polite delay between pages
            if url:
                await asyncio.sleep(0.3)

        stations = []
        for item in all_items:
            if not isinstance(item, dict):
                continue

            prices_raw = item.get("prices") or {}
            prices = []
            seen: set = set()
            for key, (ft, unit) in _PRICE_MAP.items():
                if ft in seen:
                    continue
                val = prices_raw.get(key)
                if val is None:
                    continue
                try:
                    price = float(val)
                except (TypeError, ValueError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, unit))
                    seen.add(ft)

            if not prices:
                continue

            try:
                lat = float(item.get("lat") or 0)
                lon = float(item.get("lng") or 0)
                if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            name = (item.get("name") or "").strip()
            sid = item.get("pk") or len(stations)

            stations.append({
                "id":         f"si_{sid}",
                "country":    "SI",
                "name":       name,
                "brand":      name,
                "address":    (item.get("address") or "").strip(),
                "city":       (item.get("zip_code") or "").strip(),
                "lat":        lat,
                "lon":        lon,
                "source":     self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices":     prices,
            })

        print(f"[SI] {len(stations)} stations from goriva.si")
        return stations
