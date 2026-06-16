import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import List, Dict, Any


class BaseScraper:
    COUNTRY: str = ""
    CURRENCY: str = ""
    SOURCE: str = ""
    CONFIDENCE: float = 1.0  # 1.0 = official gov, <1.0 = community

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.fetched_at = datetime.now(timezone.utc).isoformat()

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def build_output(self, stations: List[Dict]) -> Dict:
        return {
            "meta": {
                "country": self.COUNTRY,
                "currency": self.CURRENCY,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "fetched_at": self.fetched_at,
                "station_count": len(stations),
            },
            "stations": stations,
        }

    def price_entry(self, fuel_type: str, price: float, unit: str = "L") -> Dict:
        return {
            "fuel_type": fuel_type,
            "price": price,
            "currency": self.CURRENCY,
            "unit": unit,
            "updated_at": self.fetched_at,
        }
