import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseScraper

# Swedish county codes
COUNTIES = [
    "AB", "C", "D", "E", "F", "G", "H", "I", "K",
    "M", "N", "O", "S", "T", "U", "W", "X", "Y", "Z", "AC", "BD",
]

FUEL_MAP = {
    "95": ("E10", "L"),
    "98": ("E5", "L"),
    "diesel": ("DIESEL", "L"),
    "lpg": ("LPG", "L"),
    "hvo": ("HVO100", "L"),     # Renewable diesel
    "ev_ac": ("AC_22KW", "kWh"),
    "ev_dc": ("DC_50KW", "kWh"),
}


class SwedenScraper(BaseScraper):
    COUNTRY = "SE"
    CURRENCY = "SEK"
    SOURCE = "henrikhjelm.se"
    CONFIDENCE = 0.85  # Community-curated from official sources

    BASE_URL = "https://henrikhjelm.se/api/getdata.php"

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        stations = []
        tasks = [self._fetch_county(county) for county in COUNTIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            stations.extend(result)

        return stations

    async def _fetch_county(self, county: str) -> List[Dict]:
        try:
            async with self.session.get(
                self.BASE_URL,
                params={"lan": county},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        except Exception:
            return []

        stations = []
        for station_key, price_data in data.items():
            if not isinstance(price_data, dict):
                continue

            name = station_key.split("__")[0].replace("_", " ").strip()
            location_part = station_key.split("__")[1] if "__" in station_key else ""
            lat, lon = self._parse_coords(location_part)

            prices = []
            for raw_key, (fuel_type, unit) in FUEL_MAP.items():
                raw_val = price_data.get(raw_key)
                if raw_val is None:
                    continue
                try:
                    price = float(str(raw_val).replace(",", ".")) / 10
                    if price > 0:
                        prices.append(self.price_entry(fuel_type, price, unit))
                except (ValueError, TypeError):
                    continue

            if not prices:
                continue

            stations.append({
                "id": f"se_{station_key}",
                "country": "SE",
                "name": name,
                "county": county,
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        return stations

    def _parse_coords(self, location_str: str):
        try:
            parts = location_str.split("_")
            return float(parts[0]), float(parts[1])
        except Exception:
            return None, None
