import aiohttp
from typing import List, Dict, Any
from .base import BaseScraper

# Icelandic fuel prices via Gasvaktin community project
# Scrapes all major Icelandic fuel station chains daily
# https://github.com/gasvaktin/gasvaktin
# Free, no API key, ~75 stations

GAS_JSON_URL = (
    "https://raw.githubusercontent.com/gasvaktin/gasvaktin/master/vaktin/gas.json"
)

FUEL_MAP = {
    "bensin95": ("E5",     "L"),
    "diesel":   ("DIESEL", "L"),
}


class IcelandScraper(BaseScraper):
    COUNTRY = "IS"
    CURRENCY = "ISK"
    SOURCE = "gasvaktin.is"
    CONFIDENCE = 0.90

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                GAS_JSON_URL,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    print(f"[IS] HTTP {resp.status}")
                    return []
                raw = await resp.json(content_type=None)
        except Exception as e:
            print(f"[IS] {e}")
            return []

        # Accept both list-at-root and {"stations": [...]} shapes
        items = raw if isinstance(raw, list) else raw.get("stations", [])

        stations = []
        for s in items:
            geo = s.get("geo") or {}
            lat = geo.get("lat") or s.get("lat")
            lon = geo.get("lon") or s.get("lon")
            try:
                lat = float(lat)
                lon = float(lon)
            except (TypeError, ValueError):
                lat = lon = None

            prices = []
            for field, (ft, unit) in FUEL_MAP.items():
                val = s.get(field)
                if isinstance(val, (int, float)) and val > 0:
                    prices.append(self.price_entry(ft, float(val), unit))

            if not prices:
                continue

            name    = (s.get("name") or "").strip()
            company = (s.get("company") or "").strip()
            stations.append({
                "id": f"is_{s.get('key', name)}",
                "country": "IS",
                "name": name or company,
                "brand": company,
                "address": "",
                "city": "",
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        print(f"[IS] {len(stations)} stations from gasvaktin.is")
        return stations
