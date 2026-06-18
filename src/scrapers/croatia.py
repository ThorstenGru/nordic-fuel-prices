import aiohttp
from typing import List, Dict, Any
from .base import BaseScraper

# Croatia: mandatory fuel price reporting via Ministry of Economy (MZOE)
# Data published at the "GOR" (Gorivo/Fuel) portal
# Free, no API key, ~900 stations with GPS, updated daily

DATA_URL = "https://mzoe-gor.hr/data.json"

# gorivo_id → (fuel_type, unit)
FUEL_MAP = {
    1: ("E5",     "L"),   # Eurosuper 95
    2: ("E5",     "L"),   # Eurosuper 98 (premium)
    3: ("DIESEL", "L"),   # Eurodiesel
    4: ("LPG",    "L"),   # Autoplin
    5: ("CNG",    "kg"),  # Metan (compressed natural gas)
    6: ("HVO100", "L"),   # HVO100 renewable diesel
}

# Croatia geographic bounds
_LAT_MIN, _LAT_MAX = 42.3, 46.6
_LON_MIN, _LON_MAX = 13.4, 19.5


class CroatiaScraper(BaseScraper):
    COUNTRY = "HR"
    CURRENCY = "EUR"
    SOURCE = "mzoe-gor.hr"
    CONFIDENCE = 1.0  # Mandatory government reporting

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                DATA_URL, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    print(f"[HR] HTTP {resp.status}")
                    return []
                raw = await resp.json(content_type=None)
        except Exception as e:
            print(f"[HR] {e}")
            return []

        if isinstance(raw, dict):
            raw = raw.get("stations") or raw.get("data") or raw.get("results") or []

        if not isinstance(raw, list):
            print(f"[HR] Unexpected format: {type(raw)}")
            return []

        stations = []
        for item in raw:
            prices = []
            seen = set()
            for c in item.get("cjenici", []):
                gid = c.get("gorivo_id")
                ft_info = FUEL_MAP.get(gid)
                if not ft_info or ft_info[0] in seen:
                    continue
                try:
                    price = float(str(c.get("cijena", 0)).replace(",", "."))
                except (ValueError, TypeError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft_info[0], price, ft_info[1]))
                    seen.add(ft_info[0])

            if not prices:
                continue

            # "long" is Croatia's API field name for longitude
            try:
                lat = float(item.get("lat") or 0)
                lon = float(item.get("long") or item.get("lng") or item.get("lon") or 0)
                if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            brand = (item.get("brand") or item.get("naziv") or "").strip()
            sid = item.get("id") or item.get("station_id") or len(stations)

            stations.append({
                "id": f"hr_{sid}",
                "country": "HR",
                "name": brand,
                "brand": brand,
                "address": (item.get("adresa") or item.get("address") or "").strip(),
                "city": (item.get("mjesto") or item.get("city") or "").strip(),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        print(f"[HR] {len(stations)} stations from mzoe-gor.hr")
        return stations
