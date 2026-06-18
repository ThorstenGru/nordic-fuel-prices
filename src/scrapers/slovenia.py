import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Slovenia: mandatory fuel price reporting via goriva.si (Ministry-backed portal)
# Free REST API, ~550 stations with GPS, updated in near real-time
# Backup raw data: github.com/stefanb/goriva-data

API_URL = "https://goriva.si/api/v1/stations/?format=json&page_size=2000"

# Map Slovenian fuel names (case-insensitive substrings) to internal types
_FUEL_KEYWORDS = [
    ("hvo",        "HVO100", "L"),
    ("e85",        "E85",    "L"),
    ("cng",        "CNG",    "kg"),
    ("zemeljski",  "CNG",    "kg"),  # zemeljski plin = natural gas
    ("autoplin",   "LPG",    "L"),
    ("avtoplin",   "LPG",    "L"),
    ("plin",       "LPG",    "L"),   # plin = gas (catch-all for LPG after CNG)
    ("100",        "E5",     "L"),   # Eurosuper 100 → E5 premium
    ("98",         "E5",     "L"),   # UNL 98
    ("95",         "E5",     "L"),   # Eurosuper 95 (Slovenia uses E5 label)
    ("super",      "E5",     "L"),   # catch-all for petrol
    ("diesel",     "DIESEL", "L"),
    ("dizel",      "DIESEL", "L"),   # Slovenian spelling
    ("bencin",     "E5",     "L"),   # bencin = petrol
]

# Slovenia geographic bounds
_LAT_MIN, _LAT_MAX = 45.4, 46.9
_LON_MIN, _LON_MAX = 13.3, 16.7


def _map_fuel(name: str) -> Optional[tuple]:
    n = name.lower()
    for kw, ft, unit in _FUEL_KEYWORDS:
        if kw in n:
            return ft, unit
    return None


class SloveniaScraper(BaseScraper):
    COUNTRY = "SI"
    CURRENCY = "EUR"
    SOURCE = "goriva.si"
    CONFIDENCE = 1.0  # Government-mandated data

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                API_URL,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[SI] HTTP {resp.status}")
                    return []
                raw = await resp.json(content_type=None)
        except Exception as e:
            print(f"[SI] {e}")
            return []

        # DRF pagination: {"count":..., "results":[...]} or raw list
        if isinstance(raw, dict):
            items = raw.get("results") or raw.get("stations") or raw.get("data") or []
        elif isinstance(raw, list):
            items = raw
        else:
            print(f"[SI] Unexpected format: {type(raw)}")
            return []

        stations = []
        for item in items:
            prices = self._parse_prices(item)
            if not prices:
                continue

            try:
                lat = float(item.get("lat") or item.get("latitude") or 0)
                lon = float(item.get("lng") or item.get("lon") or item.get("longitude") or 0)
                if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            name = (item.get("name") or item.get("title") or item.get("naziv") or "").strip()
            brand = (item.get("brand") or item.get("group") or item.get("skupina") or name).strip()
            sid = item.get("id") or item.get("pk") or len(stations)

            stations.append({
                "id": f"si_{sid}",
                "country": "SI",
                "name": name,
                "brand": brand,
                "address": (item.get("address") or item.get("naslov") or "").strip(),
                "city": (
                    item.get("municipality") or item.get("town") or
                    item.get("mesto") or item.get("obcina") or ""
                ).strip(),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        print(f"[SI] {len(stations)} stations from goriva.si")
        return stations

    def _parse_prices(self, item: dict) -> List[Dict]:
        """Handle both list-of-dicts and dict-of-values price formats."""
        prix = item.get("prices") or item.get("cene") or item.get("price_list") or []
        seen = set()
        prices = []

        if isinstance(prix, list):
            for p in prix:
                if isinstance(p, dict):
                    # {fuel_type: {name: "..."}, price: "1.389"}
                    fuel_obj = p.get("fuel_type") or p.get("fuel") or {}
                    if isinstance(fuel_obj, dict):
                        fname = fuel_obj.get("name") or fuel_obj.get("naziv") or ""
                    else:
                        fname = str(fuel_obj)
                    fname = fname or p.get("name") or p.get("naziv") or ""
                    val = p.get("price") or p.get("cena")
                elif isinstance(p, str):
                    # plain string — shouldn't happen but guard it
                    continue
                else:
                    continue

                ft_info = _map_fuel(fname)
                if not ft_info or ft_info[0] in seen:
                    continue
                try:
                    price = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft_info[0], price, ft_info[1]))
                    seen.add(ft_info[0])

        elif isinstance(prix, dict):
            # {"Eurosuper 95": 1.389, "Diesel": 1.289, ...}
            for fname, val in prix.items():
                ft_info = _map_fuel(fname)
                if not ft_info or ft_info[0] in seen:
                    continue
                try:
                    price = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft_info[0], price, ft_info[1]))
                    seen.add(ft_info[0])

        return prices
