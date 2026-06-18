import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseScraper

# Norway has NO public per-station consumer fuel price API as of 2026.
# Circle K (~450), YX/Prio (~300), Uno-X (~150), ST1/Shell (~264) — none expose
# free real-time price APIs. Konkurransetilsynet banned Circle K, YX, and Uno-X
# from publishing indicative list prices until October 2030 (anti-cartel commitment).
# ANWB POI API confirmed: 0 Norwegian stations in database (tested 2026-06-18).
# Drivstoffappen went commercial. No equivalent to Denmark/Austria mandatory reporting.
#
# Source used: Statistics Norway (SSB) — official monthly national average.
# Table 09654: Prices on engine fuel (NOK per litres)
#   031 = Motor gasoline, leadfree 95 octane (E10)
#   035 = Dutiable diesel
# Updated monthly with ~6-week lag. Free, no auth required.

SSB_URL = "https://data.ssb.no/api/v0/en/table/09654"
SSB_BODY = {
    "query": [
        {"code": "PetroleumProd", "selection": {"filter": "item", "values": ["031", "035"]}},
        {"code": "ContentsCode", "selection": {"filter": "item", "values": ["Priser"]}},
        {"code": "Tid", "selection": {"filter": "top", "values": ["1"]}},
    ],
    "response": {"format": "json-stat2"},
}

# Major Norwegian cities with coordinates for map visibility
CITIES = [
    ("Oslo",      59.9139, 10.7522),
    ("Bergen",    60.3913,  5.3221),
    ("Trondheim", 63.4305, 10.3951),
    ("Stavanger", 58.9700,  5.7331),
    ("Tromsø",    69.6496, 18.9560),
]


class NorwayScraper(BaseScraper):
    COUNTRY = "NO"
    CURRENCY = "NOK"
    SOURCE = "ssb.no (national monthly avg)"
    CONFIDENCE = 0.85  # Official government source, but monthly national average

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        prices = await self._fetch_ssb()
        if not prices:
            print("[NO] SSB fetch failed — no data")
            return []

        stations = []
        for city, lat, lon in CITIES:
            stations.append({
                "id": f"no_ssb_{city.lower()}",
                "country": "NO",
                "name": f"Norway Avg · {city}",
                "brand": "National Average",
                "address": "SSB Statistics Norway · monthly avg",
                "city": city,
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        print(f"[NO] {len(stations)} national-average markers from SSB")
        return stations

    async def _fetch_ssb(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.post(
                SSB_URL,
                json=SSB_BODY,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[NO/SSB] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[NO/SSB] {e}")
            return []

        # json-stat2 format: values array ordered by dimensions
        # Dims: PetroleumProd(2) × ContentsCode(1) × Tid(1)
        # [031/E10, 035/Diesel] with top-1 month each
        values = data.get("value", [])
        if len(values) < 2:
            return []

        prices = []
        fuel_map = [(0, "E10", "L"), (1, "DIESEL", "L")]
        for idx, fuel_type, unit in fuel_map:
            try:
                price = float(values[idx])
                if price > 0:
                    prices.append(self.price_entry(fuel_type, price, unit))
            except (TypeError, ValueError, IndexError):
                pass

        return prices
