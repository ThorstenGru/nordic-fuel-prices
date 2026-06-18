import aiohttp
from typing import List, Dict, Any
from .base import BaseScraper

# French mandatory fuel price reporting since 2007
# data.economie.gouv.fr — real-time prices, all ~12 000 stations, GPS per station
# Free, no API key required
# Dataset: prix-des-carburants-en-france-flux-instantane-v2

BASE_URL = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
    "/prix-des-carburants-en-france-flux-instantane-v2/exports/json"
)

# Direct numerical price fields present in the v2.1 API export (no JSON parsing needed)
# {field_name: (fuel_type, unit)}
PRICE_FIELDS = {
    "gazole_prix": ("DIESEL", "L"),
    "sp95_prix":   ("E5",     "L"),
    "sp98_prix":   ("E5",     "L"),  # premium 98 — also maps to E5, deduped via seen set
    "e10_prix":    ("E10",    "L"),
    "e85_prix":    ("E85",    "L"),
    "gplc_prix":   ("LPG",    "L"),
}


class FranceScraper(BaseScraper):
    COUNTRY = "FR"
    CURRENCY = "EUR"
    SOURCE = "data.economie.gouv.fr"
    CONFIDENCE = 0.95

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        try:
            async with self.session.get(
                BASE_URL,
                params={"timezone": "UTC"},
                timeout=aiohttp.ClientTimeout(total=300),
                headers={
                    "Accept": "application/json",
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    ),
                },
            ) as resp:
                if resp.status != 200:
                    print(f"[FR] HTTP {resp.status}")
                    return []
                raw = await resp.json(content_type=None)
        except Exception as e:
            print(f"[FR] {e}")
            return []

        # API may return a paginated wrapper or a bare array
        if isinstance(raw, dict):
            raw = raw.get("results") or raw.get("records") or raw.get("data") or []
        if not isinstance(raw, list):
            print(f"[FR] Unexpected response type: {type(raw).__name__}")
            return []

        stations = []
        for s in raw:
            if not isinstance(s, dict):
                continue

            # Use the pre-parsed direct price fields (floats) — avoids JSON string parsing
            seen: set = set()
            prices = []
            for field, (ft, unit) in PRICE_FIELDS.items():
                if ft in seen:
                    continue
                val = s.get(field)
                if val is None:
                    continue
                try:
                    price = float(val)
                except (TypeError, ValueError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, unit))
                    seen.add(ft)

            if not prices:
                continue

            lat, lon = self._coords(s)
            brand = (s.get("nom_marque") or s.get("nom") or "").strip()

            stations.append({
                "id":         f"fr_{s.get('id', '')}",
                "country":    "FR",
                "name":       brand,
                "brand":      brand,
                "address":    (s.get("adresse") or "").strip(),
                "city":       (s.get("ville") or "").strip(),
                "lat":        lat,
                "lon":        lon,
                "source":     self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices":     prices,
            })

        print(f"[FR] {len(stations)} stations from data.economie.gouv.fr")
        return stations

    def _coords(self, s: dict):
        # Prefer geom object (decimal degrees already) over raw lat/lon (×100 000)
        try:
            geom = s.get("geom")
            if isinstance(geom, dict) and geom.get("lat"):
                return float(geom["lat"]), float(geom["lon"])

            lat_raw = s.get("latitude")
            lon_raw = s.get("longitude")
            if lat_raw is None:
                return None, None
            lat = float(lat_raw)
            lon = float(lon_raw)
            if abs(lat) > 90:   # stored as integer × 100 000
                lat /= 100_000
                lon /= 100_000
            return lat, lon
        except (TypeError, ValueError, KeyError):
            return None, None
