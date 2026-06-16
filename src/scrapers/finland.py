import aiohttp
from typing import List, Dict, Any
from .base import BaseScraper

# polttoaine.net — community source, user-reported prices
# No API key needed, but data quality varies
API_URL = "https://www.polttoaine.net/api/stations"

FUEL_MAP = {
    "95E10": ("E10", "L"),
    "98E5": ("E5", "L"),
    "Diesel": ("DIESEL", "L"),
    "Autogas": ("LPG", "L"),
}


class FinlandScraper(BaseScraper):
    COUNTRY = "FI"
    CURRENCY = "EUR"
    SOURCE = "polttoaine.net"
    CONFIDENCE = 0.70  # Community, user-reported

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                API_URL,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[FI] API returned {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[FI] Fetch failed: {e}")
            return []

        stations = []
        raw_list = data if isinstance(data, list) else data.get("stations", [])

        for item in raw_list:
            prices = []
            for fuel_name, raw_price in item.get("prices", {}).items():
                fuel_type, unit = FUEL_MAP.get(fuel_name, (None, None))
                if not fuel_type:
                    continue
                try:
                    price = float(raw_price)
                    if price > 0:
                        prices.append(self.price_entry(fuel_type, price, unit))
                except (TypeError, ValueError):
                    continue

            if not prices:
                continue

            stations.append({
                "id": f"fi_{item.get('id', '')}",
                "country": "FI",
                "name": item.get("name", ""),
                "address": item.get("address", ""),
                "city": item.get("city", ""),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "brand": item.get("brand", ""),
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        return stations
