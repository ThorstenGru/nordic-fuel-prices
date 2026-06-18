import aiohttp
import asyncio
import os
from typing import List, Dict, Any
from .base import BaseScraper
from ._anwb import ANWBScraper


class _DEAnwb(ANWBScraper):
    """Fallback: ANWB POI API when Tankerkönig API key is unavailable."""
    COUNTRY    = "DE"
    ISO3       = "DEU"
    BBOX       = (47.27, 5.87, 55.06, 15.04)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90

# German fuel prices via Tankerkönig
# Distributes government-mandated MTS-K (Markttransparenzstelle für Kraftstoffe) data
# FREE — register once at https://creativecommons.tankerkoenig.de for an API key
# Set TANKERKOENIG_API_KEY as a GitHub Actions secret
#
# Grid of 40+ centre points covering all of Germany; each call fetches
# stations within 25 km radius (~400 stations max per call).

API_KEY  = os.environ.get("TANKERKOENIG_API_KEY", "")
LIST_URL = "https://creativecommons.tankerkoenig.de/json/list.php"

# ~40 centre coordinates that together blanket the country with 25 km circles
GRID = [
    (53.5753, 10.0153),  # Hamburg
    (53.0793,  8.8017),  # Bremen
    (52.3759,  9.7320),  # Hannover
    (53.1435, 11.0533),  # Lüneburg
    (54.3233, 10.1228),  # Kiel
    (54.0865, 12.1444),  # Rostock
    (53.8667, 10.6867),  # Lübeck
    (51.4556,  7.0116),  # Dortmund
    (51.2217,  6.7762),  # Düsseldorf
    (50.9333,  6.9500),  # Köln
    (50.7753,  6.0839),  # Aachen
    (50.3569,  7.5890),  # Koblenz
    (50.1109,  8.6821),  # Frankfurt
    (49.9929,  8.2473),  # Mainz
    (49.4521, 11.0767),  # Nürnberg
    (48.9667, 12.0667),  # Regensburg
    (48.5658, 13.4317),  # Passau
    (48.3717, 10.8983),  # Augsburg
    (48.1351, 11.5820),  # München
    (47.8010, 13.0452),  # Salzburg border
    (47.9990,  7.8421),  # Freiburg
    (47.5595,  9.6753),  # Lindau / Bodensee
    (48.7758,  9.1829),  # Stuttgart
    (49.0069,  8.4037),  # Karlsruhe
    (51.9607,  7.6261),  # Münster
    (51.5167,  9.9167),  # Kassel
    (51.3397, 12.3731),  # Leipzig
    (51.4818, 11.9699),  # Halle
    (51.0504, 13.7373),  # Dresden
    (51.7535, 14.6329),  # Cottbus
    (52.5200, 13.4050),  # Berlin
    (52.6367, 13.2353),  # Brandenburg / Oranienburg
    (52.1205, 11.6276),  # Magdeburg
    (50.9272, 11.5861),  # Erfurt
    (53.4285, 14.5528),  # Stettin border / Vorpommern
    (54.5086, 13.6000),  # Rügen
    (50.0755, 14.4378),  # Praha border / Sachsen east
    (51.3600, 10.0000),  # Eichsfeld
    (49.7000,  9.9500),  # Würzburg
    (50.5700,  9.6800),  # Fulda
]

FUEL_MAP = {
    "e5":     ("E5",     "L"),
    "e10":    ("E10",    "L"),
    "diesel": ("DIESEL", "L"),
}


class GermanyScraper(BaseScraper):
    COUNTRY = "DE"
    CURRENCY = "EUR"
    SOURCE = "tankerkoenig.de (MTS-K)"
    CONFIDENCE = 0.99

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        if not API_KEY:
            print("[DE] TANKERKOENIG_API_KEY not set — falling back to ANWB")
            return await _DEAnwb(self.session).fetch_stations()

        sem = asyncio.Semaphore(5)
        tasks = [self._fetch_area(lat, lon, sem) for lat, lon in GRID]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        seen: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            for s in result:
                if s["id"] not in seen:
                    seen[s["id"]] = s

        stations = list(seen.values())
        print(f"[DE] {len(stations)} stations from tankerkoenig.de")
        return stations

    async def _fetch_area(self, lat: float, lon: float, sem: asyncio.Semaphore) -> List[Dict]:
        params = {
            "lat": lat, "lng": lon,
            "rad": 25, "sort": "dist",
            "type": "all", "apikey": API_KEY,
        }
        async with sem:
            try:
                async with self.session.get(
                    LIST_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)
            except Exception as e:
                print(f"[DE] area ({lat:.2f},{lon:.2f}): {e}")
                return []

        if not data.get("ok"):
            return []

        result = []
        for s in data.get("stations", []):
            prices = []
            for field, (ft, unit) in FUEL_MAP.items():
                val = s.get(field)
                if isinstance(val, (int, float)) and val > 0:
                    prices.append(self.price_entry(ft, float(val), unit))
            if not prices:
                continue
            brand = s.get("brand", "")
            name  = s.get("name", "")
            result.append({
                "id": f"de_{s.get('id', '')}",
                "country": "DE",
                "name": f"{brand} {name}".strip() if brand else name,
                "brand": brand,
                "address": f"{s.get('street', '')} {s.get('houseNumber', '')}".strip(),
                "city": s.get("place", ""),
                "lat": s.get("lat"),
                "lon": s.get("lng"),
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        return result
