import aiohttp
from typing import List, Dict, Any
from .base import BaseScraper

# Norwegian government-mandated fuel price reporting
# Source: drivstoffpriser.no (official, no API key needed)
API_URL = "https://drivstoffpriser.no/api/stations"

FUEL_MAP = {
    "Bensin 95": ("E10", "L"),
    "Diesel": ("DIESEL", "L"),
    "Autogas": ("LPG", "L"),
    "HVO100": ("HVO100", "L"),
    "Elektrisk": ("DC_50KW", "kWh"),
}


class NorwayScraper(BaseScraper):
    COUNTRY = "NO"
    CURRENCY = "NOK"
    SOURCE = "drivstoffpriser.no"
    CONFIDENCE = 1.0  # Government-mandated

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                API_URL,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        except Exception:
            return []

        stations = []
        raw_list = data if isinstance(data, list) else data.get("stations", [])

        for item in raw_list:
            prices = []
            for fuel_entry in item.get("prices", []):
                fuel_name = fuel_entry.get("name", "")
                fuel_type, unit = FUEL_MAP.get(fuel_name, (None, None))
                if not fuel_type:
                    continue
                try:
                    price = float(fuel_entry["price"])
                    if price > 0:
                        prices.append(self.price_entry(fuel_type, price, unit))
                except (KeyError, TypeError, ValueError):
                    continue

            if not prices:
                continue

            stations.append({
                "id": f"no_{item.get('id', '')}",
                "country": "NO",
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
