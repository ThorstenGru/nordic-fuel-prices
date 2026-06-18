import aiohttp
import asyncio
from typing import List, Dict, Any
from .base import BaseScraper
from ._anwb import ANWBScraper


class _ESAnwb(ANWBScraper):
    """Fallback: ANWB POI API when MINETUR is unreachable from GH Actions."""
    COUNTRY    = "ES"
    ISO3       = "ESP"
    BBOX       = (36.00, -9.30, 43.80, 3.40)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90

# Spanish mandatory fuel price reporting via MINETUR (Ministry of Industry)
# https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/
# Free, no API key, ~12 000 stations with GPS
# Prices use comma decimal separator ("1,499")

BASE_URL = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes"
    "/PreciosCarburantes/EstacionesTerrestres/"
)

# Spanish field name → (internal fuel_type, unit)
FUEL_FIELDS = {
    "Precio Gasoleo A":                      ("DIESEL", "L"),
    "Precio Gasolina 95 E5":                 ("E5",     "L"),
    "Precio Gasolina 95 E10":                ("E10",    "L"),
    "Precio Gasolina 98 E5":                 ("E5",     "L"),  # premium 98
    "Precio Gases licuados del petroleo":    ("LPG",    "L"),
    "Precio Gas Natural Comprimido":         ("CNG",    "kg"),
    "Precio Bioetanol":                      ("E85",    "L"),
    "Precio Hidrogeno":                      ("H2",     "kg"),
}


class SpainScraper(BaseScraper):
    COUNTRY = "ES"
    CURRENCY = "EUR"
    SOURCE = "minetur.gob.es"
    CONFIDENCE = 0.95

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        # MINETUR occasionally resets connections from cloud provider IPs; retry 5×
        data = None
        for attempt in range(5):
            try:
                async with self.session.get(
                    BASE_URL,
                    timeout=aiohttp.ClientTimeout(total=90),
                    headers={
                        "Accept": "application/json",
                        "User-Agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0 Safari/537.36"
                        ),
                    },
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        break
                    print(f"[ES] HTTP {resp.status} (attempt {attempt + 1})")
            except Exception as e:
                print(f"[ES] {e} (attempt {attempt + 1})")
            if attempt < 4:
                await asyncio.sleep(10 * (attempt + 1))

        if data is None:
            print("[ES] MINETUR unavailable — falling back to ANWB")
            return await _ESAnwb(self.session).fetch_stations()

        raw_list = data.get("ListaEESSPrecio", [])
        stations = []
        for s in raw_list:
            prices = []
            seen = set()
            for field, (ft, unit) in FUEL_FIELDS.items():
                val_str = s.get(field, "").strip()
                if not val_str or ft in seen:
                    continue
                try:
                    price = float(val_str.replace(",", "."))
                except ValueError:
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, unit))
                    seen.add(ft)

            if not prices:
                continue

            try:
                lat = float(s.get("Latitud", "0").replace(",", "."))
                lon = float(s.get("Longitud (WGS84)", "0").replace(",", "."))
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180) or (lat == 0 and lon == 0):
                    lat = lon = None
            except (ValueError, TypeError):
                lat = lon = None

            stations.append({
                "id": f"es_{s.get('IDEESS', '')}",
                "country": "ES",
                "name": s.get("Rótulo", ""),
                "brand": s.get("Rótulo", ""),
                "address": s.get("Dirección", ""),
                "city": s.get("Municipio", ""),
                "lat": lat,
                "lon": lon,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        print(f"[ES] {len(stations)} stations from minetur.gob.es")
        return stations
