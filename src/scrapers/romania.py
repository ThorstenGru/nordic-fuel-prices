import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Romania: mandatory fuel price reporting via ANPC (National Consumer Protection Authority)
# Data mirrored at peco-online.ro (updated every ~2h from ANPC feed)
# Free, no API key required, ~1500 stations with GPS

# Primary: ANPC Transparent Prices portal
PRIMARY_URL = "https://www.peco-online.ro/index.php"
PRIMARY_PARAMS = {"action": "getStationsJson", "tip_carburant": "0"}

# Fallback: goriva-style endpoint (try if primary fails)
FALLBACK_URL = "https://carburanti.raa.ro/api/statii"

# Map Romanian fuel type strings → internal types
_FUEL_KEYWORDS = [
    ("hvo",       "HVO100", "L"),
    ("e85",       "E85",    "L"),
    ("gpl",       "LPG",    "L"),
    ("gaz petrol","LPG",    "L"),
    ("gaz natur", "CNG",    "kg"),
    ("cng",       "CNG",    "kg"),
    ("premium 98","E5",     "L"),
    ("super 98",  "E5",     "L"),
    ("benzina 98","E5",     "L"),
    ("98",        "E5",     "L"),
    ("benzina",   "E5",     "L"),  # catch-all petrol
    ("motorina",  "DIESEL", "L"),
    ("diesel",    "DIESEL", "L"),
]

_LAT_MIN, _LAT_MAX = 43.5, 48.4
_LON_MIN, _LON_MAX = 22.0, 30.2


def _map_fuel(name: str) -> Optional[tuple]:
    n = name.lower()
    for kw, ft, unit in _FUEL_KEYWORDS:
        if kw in n:
            return ft, unit
    return None


class RomaniaScraper(BaseScraper):
    COUNTRY = "RO"
    CURRENCY = "RON"
    SOURCE = "peco-online.ro"
    CONFIDENCE = 0.90

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        stations = await self._try_primary()
        if not stations:
            stations = await self._try_fallback()
        if stations:
            print(f"[RO] {len(stations)} stations")
        return stations

    async def _try_primary(self) -> List[Dict]:
        """peco-online.ro JSON endpoint."""
        try:
            async with self.session.get(
                PRIMARY_URL,
                params=PRIMARY_PARAMS,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "application/json, text/javascript, */*"},
            ) as resp:
                if resp.status != 200:
                    return []
                raw = await resp.json(content_type=None)
        except Exception:
            return []

        if isinstance(raw, dict):
            items = raw.get("stations") or raw.get("data") or raw.get("results") or []
        elif isinstance(raw, list):
            items = raw
        else:
            return []

        return self._parse_items(items, "peco-online.ro")

    async def _try_fallback(self) -> List[Dict]:
        """RAA (Registrul Auto Român) fallback endpoint."""
        try:
            async with self.session.get(
                FALLBACK_URL,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return []
                raw = await resp.json(content_type=None)
        except Exception:
            return []

        if isinstance(raw, dict):
            items = (
                raw.get("statii") or raw.get("stations") or
                raw.get("data") or raw.get("results") or []
            )
        elif isinstance(raw, list):
            items = raw
        else:
            return []

        return self._parse_items(items, "raa.ro")

    def _parse_items(self, items: list, source: str) -> List[Dict]:
        stations = []
        for item in items:
            prices = self._parse_prices(item)
            if not prices:
                continue

            try:
                lat = float(item.get("lat") or item.get("latitude") or 0)
                lon = float(
                    item.get("lng") or item.get("lon") or
                    item.get("longitude") or item.get("long") or 0
                )
                if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            name = (
                item.get("station_name") or item.get("denumire") or
                item.get("name") or item.get("naziv") or ""
            ).strip()
            sid = item.get("id") or item.get("station_id") or len(stations)

            stations.append({
                "id": f"ro_{sid}",
                "country": "RO",
                "name": name,
                "brand": (item.get("brand") or item.get("marca") or name).strip(),
                "address": (item.get("adresa") or item.get("address") or "").strip(),
                "city": (
                    item.get("localitate") or item.get("oras") or
                    item.get("city") or item.get("town") or ""
                ).strip(),
                "lat": lat,
                "lon": lon,
                "source": source,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        return stations

    def _parse_prices(self, item: dict) -> List[Dict]:
        prix = (
            item.get("carburanti") or item.get("prices") or
            item.get("preturi") or item.get("price_list") or []
        )
        seen = set()
        prices = []

        if isinstance(prix, list):
            for p in prix:
                if not isinstance(p, dict):
                    continue
                fname = (
                    p.get("fuel_type") or p.get("tip") or
                    p.get("tip_carburant") or p.get("name") or ""
                )
                val = p.get("price") or p.get("pret") or p.get("valoare")
                ft_info = _map_fuel(str(fname))
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
