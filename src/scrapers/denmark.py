import os
import aiohttp
from typing import List, Dict, Any
from .base import BaseScraper

# fuelprices.dk — commercial API, free tier available
# Requires API key: contact fuelprices.dk to get one
# Set env var: FUELPRICES_DK_API_KEY
API_URL = "https://fuelprices.dk/api/stations"

FUEL_MAP = {
    "Benzin 95": ("E10", "L"),
    "Benzin 98": ("E5", "L"),
    "Diesel": ("DIESEL", "L"),
    "Autogas": ("LPG", "L"),
    "El": ("DC_50KW", "kWh"),
}


class DenmarkScraper(BaseScraper):
    COUNTRY = "DK"
    CURRENCY = "DKK"
    SOURCE = "fuelprices.dk"
    CONFIDENCE = 0.95  # Commercial API covering 8 major chains

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        api_key = os.environ.get("FUELPRICES_DK_API_KEY", "")
        if not api_key:
            print("[DK] Skipping — FUELPRICES_DK_API_KEY not set")
            return []

        try:
            async with self.session.get(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    print(f"[DK] API returned {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[DK] Fetch failed: {e}")
            return []

        stations = []
        raw_list = data if isinstance(data, list) else data.get("stations", [])

        for item in raw_list:
            prices = []
            for fuel_entry in item.get("prices", []):
                fuel_name = fuel_entry.get("type", "")
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
                "id": f"dk_{item.get('id', '')}",
                "country": "DK",
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
