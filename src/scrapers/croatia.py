import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Croatia: mandatory fuel price reporting via Ministry of Economy (MZOE)
# Data published at the "GOR" (Gorivo/Fuel) portal: mzoe-gor.hr/data.json
# Free, no API key, ~900 stations with GPS, updated daily
#
# The data.json contains:
#   postajas  — station list with cjenici (price entries) per station
#   gorivos   — product definitions: {id, vrsta_goriva_id, naziv}
#   vrsta_gorivas — fuel category definitions: {id, vrsta_goriva}
#
# vrsta_goriva_id → fuel type (from vrsta_gorivas table in the JSON):
#   1,2 → E5 (Eurosuper 95, with/without additives)
#   5,6 → E5 (Eurosuper 100, premium 100-octane)
#   7,8 → DIESEL (Eurodizel, with/without additives)
#   9   → LPG (UNP/Autoplin)
#   10  → heating oil (lož ulje) — SKIP
#   11  → off-road blue diesel (plavi dizel) — SKIP
#   12  → E85 (Bioetanol)
#   13  → HVO100/Biodiesel
#   20-22→ bottled LPG — SKIP
#   23-25→ electric — SKIP
#   26  → CNG (Stlačeni prirodni plin)

DATA_URL = "https://mzoe-gor.hr/data.json"

# vrsta_goriva_id → (fuel_type, unit)
_VRSTA_MAP = {
    1:  ("E5",     "L"),
    2:  ("E5",     "L"),
    5:  ("E5",     "L"),
    6:  ("E5",     "L"),
    7:  ("DIESEL", "L"),
    8:  ("DIESEL", "L"),
    9:  ("LPG",    "L"),
    12: ("E85",    "L"),
    13: ("HVO100", "L"),
    26: ("CNG",    "kg"),
}

# Croatia geographic bounds
_LAT_MIN, _LAT_MAX = 42.3, 46.9
_LON_MIN, _LON_MAX = 13.4, 19.5


class CroatiaScraper(BaseScraper):
    COUNTRY = "HR"
    CURRENCY = "EUR"
    SOURCE = "mzoe-gor.hr"
    CONFIDENCE = 1.0

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                DATA_URL,
                timeout=aiohttp.ClientTimeout(total=60),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    ),
                    "Accept": "application/json, */*",
                    "Accept-Language": "hr-HR,hr;q=0.9,en;q=0.8",
                    "Referer": "https://mzoe-gor.hr/",
                },
            ) as resp:
                if resp.status != 200:
                    print(f"[HR] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[HR] {e}")
            return []

        if not isinstance(data, dict):
            print(f"[HR] Unexpected format: {type(data)}")
            return []

        # Build gorivo_id → vrsta_goriva_id lookup from the gorivos array
        gorivo_lookup: Dict[int, int] = {}
        for g in data.get("gorivos", []):
            if isinstance(g, dict) and g.get("id") and g.get("vrsta_goriva_id"):
                gorivo_lookup[int(g["id"])] = int(g["vrsta_goriva_id"])

        postajas = data.get("postajas", [])
        if not isinstance(postajas, list):
            print(f"[HR] No postajas array")
            return []

        stations = []
        for item in postajas:
            if not isinstance(item, dict):
                continue

            prices = []
            seen: set = set()
            for c in item.get("cjenici", []):
                gid = c.get("gorivo_id")
                if gid is None:
                    continue
                vrsta_id = gorivo_lookup.get(int(gid))
                if vrsta_id is None:
                    continue
                ft_info = _VRSTA_MAP.get(vrsta_id)
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

            lat, lon = self._coords(item)
            brand = (item.get("naziv") or item.get("brand") or "").strip()

            stations.append({
                "id":         f"hr_{item.get('id', len(stations))}",
                "country":    "HR",
                "name":       brand,
                "brand":      brand,
                "address":    (item.get("adresa") or "").strip(),
                "city":       (item.get("mjesto") or "").strip(),
                "lat":        lat,
                "lon":        lon,
                "source":     self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices":     prices,
            })

        print(f"[HR] {len(stations)} stations from mzoe-gor.hr")
        return stations

    def _coords(self, item: dict) -> tuple:
        # The API inconsistently uses lat/long/lng with swapped values on some records.
        # Strategy: read both candidate values, identify which is latitude by range.
        raw = {}
        for key in ("lat", "lng", "long", "lon"):
            val = item.get(key)
            if val is None:
                continue
            try:
                raw[key] = float(str(val).replace(",", "."))
            except (ValueError, TypeError):
                pass

        candidates = list(raw.values())
        if len(candidates) < 2:
            return None, None

        # Identify lat (42-47) and lon (13-20)
        lat_vals = [v for v in candidates if _LAT_MIN <= v <= _LAT_MAX]
        lon_vals = [v for v in candidates if _LON_MIN <= v <= _LON_MAX]

        if lat_vals and lon_vals:
            return lat_vals[0], lon_vals[0]
        return None, None
