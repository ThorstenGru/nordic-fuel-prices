import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseScraper

# Austrian mandatory fuel price reporting via e-Control API
# https://api.e-control.at/sprit/1.0/
# Free, no API key required, real-time per-station GPS prices
# 9 federal states (Bundesländer), codes 1-9:
#   1=Burgenland 2=Kärnten 3=Niederösterreich 4=Oberösterreich
#   5=Salzburg 6=Steiermark 7=Tirol 8=Vorarlberg 9=Wien

BASE_URL = "https://api.e-control.at/sprit/1.0/search/gas-stations/by-region"

FUEL_MAP = {
    "DIE":   ("DIESEL", "L"),
    "SUP":   ("E5",     "L"),
    "SUP98": ("E5",     "L"),
    "GAS":   ("CNG",    "kg"),
    "LPG":   ("LPG",    "L"),
}

REGIONS = list(range(1, 10))


class AustriaScraper(BaseScraper):
    COUNTRY = "AT"
    CURRENCY = "EUR"
    SOURCE = "e-control.at"
    CONFIDENCE = 1.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(8)
        tasks = [
            self._fetch(region, fuel, sem)
            for region in REGIONS
            for fuel in FUEL_MAP
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            for s in result:
                sid = s["id"]
                if sid not in merged:
                    merged[sid] = s
                else:
                    existing = {p["fuel_type"] for p in merged[sid]["prices"]}
                    for p in s["prices"]:
                        if p["fuel_type"] not in existing:
                            merged[sid]["prices"].append(p)

        stations = list(merged.values())
        print(f"[AT] {len(stations)} stations from e-control.at")
        return stations

    async def _fetch(self, region: int, fuel: str, sem: asyncio.Semaphore) -> List[Dict]:
        params = {
            "regionType": "BL",
            "code": region,
            "fuelType": fuel,
            "includeClosed": "false",
        }
        async with sem:
            try:
                async with self.session.get(
                    BASE_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={"Accept": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        return []
                    raw = await resp.json(content_type=None)
            except Exception as e:
                print(f"[AT] region={region} fuel={fuel}: {e}")
                return []

        ft, unit = FUEL_MAP[fuel]
        result = []
        for s in raw:
            price_val = None
            for p in s.get("prices", []):
                if p.get("fuelType") == fuel and p.get("amount"):
                    try:
                        price_val = float(p["amount"])
                    except (TypeError, ValueError):
                        pass
                    break
            if not price_val or price_val <= 0:
                continue

            addr = s.get("address") or {}
            loc  = s.get("location") or {}
            result.append({
                "id": f"at_{s.get('id', '')}",
                "country": "AT",
                "name": s.get("name", ""),
                "brand": s.get("name", "").split(",")[0].strip(),
                "address": f"{addr.get('street', '')} {addr.get('streetnumber', '')}".strip(),
                "city": addr.get("city", ""),
                "lat": loc.get("latitude"),
                "lon": loc.get("longitude"),
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": [self.price_entry(ft, price_val, unit)],
            })
        return result
