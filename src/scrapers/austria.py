import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseScraper

# Austrian mandatory fuel price reporting via e-Control API
# https://api.e-control.at/sprit/1.0/
# Free, no API key required, real-time per-station GPS prices
# Strategy: fetch all PB (Bezirk/district) codes from /regions, then query
# each district × each fuel type for comprehensive geographic coverage.

REGIONS_URL = "https://api.e-control.at/sprit/1.0/regions"
BY_REGION_URL = "https://api.e-control.at/sprit/1.0/search/gas-stations/by-region"

FUEL_MAP = {
    "DIE": ("DIESEL", "L"),
    "SUP": ("E5",     "L"),
    "LPG": ("LPG",    "L"),
}

# Fallback BL (Bundesland) codes if district fetch fails
BL_CODES = list(range(1, 10))


class AustriaScraper(BaseScraper):
    COUNTRY = "AT"
    CURRENCY = "EUR"
    SOURCE = "e-control.at"
    CONFIDENCE = 1.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        pb_codes = await self._fetch_pb_codes()

        sem = asyncio.Semaphore(12)
        if pb_codes:
            tasks = [
                self._fetch("PB", code, fuel, sem)
                for code in pb_codes
                for fuel in FUEL_MAP
            ]
        else:
            tasks = [
                self._fetch("BL", code, fuel, sem)
                for code in BL_CODES
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
        print(f"[AT] {len(stations)} stations from e-control.at ({len(pb_codes)} districts)")
        return stations

    async def _fetch_pb_codes(self) -> List[int]:
        try:
            async with self.session.get(
                REGIONS_URL,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[AT] regions HTTP {resp.status} — falling back to BL")
                    return []
                regions = await resp.json(content_type=None)
        except Exception as e:
            print(f"[AT] regions fetch: {e} — falling back to BL")
            return []

        codes = []
        for bl in regions:
            for pb in bl.get("subRegions", []):
                code = pb.get("code")
                if code is not None:
                    try:
                        codes.append(int(code))
                    except (TypeError, ValueError):
                        pass
        return codes

    async def _fetch(self, region_type: str, code: int, fuel: str, sem: asyncio.Semaphore) -> List[Dict]:
        params = {
            "type": region_type,
            "code": code,
            "fuelType": fuel,
            "includeClosed": "false",
        }
        async with sem:
            try:
                async with self.session.get(
                    BY_REGION_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={"Accept": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        return []
                    raw = await resp.json(content_type=None)
            except Exception as e:
                print(f"[AT] {region_type}={code} fuel={fuel}: {e}")
                return []

        if not isinstance(raw, list):
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
                "brand": (s.get("name", "") or "").split(",")[0].strip(),
                "address": f"{addr.get('street', '')} {addr.get('streetnumber', '')}".strip(),
                "city": addr.get("city", ""),
                "lat": loc.get("latitude"),
                "lon": loc.get("longitude"),
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": [self.price_entry(ft, price_val, unit)],
            })
        return result
