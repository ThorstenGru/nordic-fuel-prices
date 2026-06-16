import aiohttp
import json
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

FUEL_MAP = {
    "E10":    ("E10",    "L"),
    "SP95":   ("E5",     "L"),
    "SP98":   ("E5",     "L"),
    "Gazole": ("DIESEL", "L"),
    "E85":    ("E85",    "L"),
    "GPLc":   ("LPG",    "L"),
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
                params={"limit": "-1", "timezone": "UTC"},
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                if resp.status != 200:
                    print(f"[FR] HTTP {resp.status}")
                    return []
                raw = await resp.json(content_type=None)
        except Exception as e:
            print(f"[FR] {e}")
            return []

        stations = []
        for s in raw:
            prices = self._parse_prices(s.get("prix") or s.get("fields", {}).get("prix"))
            if not prices:
                continue

            lat, lon = self._parse_coords(s)
            brand = (
                s.get("nom_marque") or s.get("nom") or
                s.get("fields", {}).get("nom_marque") or ""
            )
            stations.append({
                "id": f"fr_{s.get('id', '')}",
                "country": "FR",
                "name": brand,
                "brand": brand,
                "address": s.get("adresse") or s.get("fields", {}).get("adresse", ""),
                "city": s.get("ville") or s.get("fields", {}).get("ville", ""),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        print(f"[FR] {len(stations)} stations from data.economie.gouv.fr")
        return stations

    def _parse_prices(self, prix_raw) -> List[Dict]:
        if not prix_raw:
            return []
        if isinstance(prix_raw, str):
            try:
                prix_list = json.loads(prix_raw)
            except (json.JSONDecodeError, ValueError):
                return []
        elif isinstance(prix_raw, list):
            prix_list = prix_raw
        else:
            return []

        prices = []
        seen_types = set()
        for p in prix_list:
            # API uses either {nom, valeur} or {@nom, @valeur}
            name  = p.get("nom") or p.get("@nom", "")
            valeur = p.get("valeur") or p.get("@valeur")
            ft_info = FUEL_MAP.get(name)
            if not ft_info or not valeur:
                continue
            try:
                price = float(str(valeur).replace(",", "."))
            except (ValueError, TypeError):
                continue
            if price > 0 and ft_info[0] not in seen_types:
                prices.append(self.price_entry(ft_info[0], price, ft_info[1]))
                seen_types.add(ft_info[0])
        return prices

    def _parse_coords(self, s: dict):
        # v2 API returns decimal degrees directly; older versions × 100 000
        try:
            # GeoJSON geometry field
            geom = s.get("geom") or s.get("geo_point_2d")
            if isinstance(geom, dict):
                coords = geom.get("coordinates") or geom.get("lon", None)
                if isinstance(coords, list) and len(coords) >= 2:
                    return float(coords[1]), float(coords[0])
                # geo_point_2d format: {"lat": ..., "lon": ...}
                if "lat" in geom:
                    return float(geom["lat"]), float(geom["lon"])

            lat_raw = s.get("latitude") or s.get("fields", {}).get("latitude")
            lon_raw = s.get("longitude") or s.get("fields", {}).get("longitude")
            if lat_raw is None:
                return None, None
            lat = float(lat_raw)
            lon = float(lon_raw)
            # Old dataset stores lat/lon × 100 000
            if abs(lat) > 90:
                lat /= 100_000
                lon /= 100_000
            return lat, lon
        except (TypeError, ValueError, KeyError):
            return None, None
