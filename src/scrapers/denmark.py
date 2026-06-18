import aiohttp
import asyncio
import re
from typing import List, Dict, Any, Tuple
from .base import BaseScraper
from ._anwb import ANWBScraper
from . import geocoder as _geo

# Free, no-auth APIs mandated by Danish law from Jan 2026
SHELL_URL = "https://shellpumpepriser.geoapp.me/v1/prices"
Q8_URL = "https://beta.q8.dk/Station/GetStationPrices?page=1&pageSize=2000"


class _DKAnwb(ANWBScraper):
    """ANWB coverage for Denmark: Circle K, Uno-X, Go'On, Oil! etc."""
    COUNTRY    = "DK"
    ISO3       = "DNK"
    CURRENCY   = "DKK"
    BBOX       = (54.80, 8.00, 57.80, 15.20)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90

# Shell: (fuelType, octane) → fuel_type
SHELL_FUEL_MAP = {
    ("Autobenzin", "95"):  "E10",
    ("Autobenzin", "98"):  "E5",
    ("Autodiesel", None):  "DIESEL",
    ("Autodiesel", ""):    "DIESEL",
}

# Q8/F24: product name keywords → fuel_type
Q8_FUEL_MAP = [
    ("95 E10",    "E10"),
    ("95 Extra",  "E5"),
    ("95",        "E10"),   # fallback
    ("Diesel Extra", "DIESEL"),
    ("Diesel",    "DIESEL"),
    ("HVO",       "HVO100"),
    ("Gas",       "LPG"),
]


class DenmarkScraper(BaseScraper):
    COUNTRY = "DK"
    CURRENCY = "DKK"
    SOURCE = "shell+q8+anwb.nl open APIs"
    CONFIDENCE = 1.0  # Mandatory government reporting

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        shell_task = self._fetch_shell()
        q8_task = self._fetch_q8()
        anwb_task = _DKAnwb(self.session).fetch_stations()
        shell, q8, anwb = await asyncio.gather(shell_task, q8_task, anwb_task, return_exceptions=True)

        stations = []
        if not isinstance(shell, Exception):
            stations.extend(shell)
        if not isinstance(q8, Exception):
            stations.extend(q8)
        if not isinstance(anwb, Exception):
            stations.extend(anwb)
        return stations

    async def _fetch_shell(self) -> List[Dict]:
        try:
            async with self.session.get(
                SHELL_URL, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status != 200:
                    print(f"[DK/Shell] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[DK/Shell] {e}")
            return []

        stations = []
        for item in data:
            coords = item.get("coordinates", {})
            try:
                lat = float(coords.get("latitude", 0)) or None
                lon = float(coords.get("longitude", 0)) or None
            except (TypeError, ValueError):
                lat = lon = None

            prices = []
            for p in item.get("prices", []):
                ft = self._map_shell_fuel(
                    p.get("fuelType", ""), p.get("octane") or ""
                )
                if not ft:
                    continue
                try:
                    price = float(p["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, "L"))

            if not prices:
                continue

            stations.append({
                "id": f"dk_shell_{item.get('stationId', '')}",
                "country": "DK",
                "name": f"Shell {item.get('city', '')}".strip(),
                "address": f"{item.get('street', '')} {item.get('houseNumber', '') or ''}".strip(),
                "city": item.get("city", ""),
                "postal_code": item.get("postalCode", ""),
                "brand": "Shell",
                "lat": lat,
                "lon": lon,
                "source": "shellpumpepriser.geoapp.me",
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        return stations

    async def _fetch_q8(self) -> List[Dict]:
        try:
            async with self.session.get(
                Q8_URL,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[DK/Q8] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[DK/Q8] {e}")
            return []

        raw = data.get("data", {}).get("stationsPrices", [])
        stations = []
        for item in raw:
            prices = []
            for p in item.get("products", []):
                ft = self._map_q8_fuel(p.get("productName", ""))
                if not ft:
                    continue
                try:
                    price = float(p["price"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price > 0:
                    prices.append(self.price_entry(ft, price, "L"))

            if not prices:
                continue

            city, postal, street = self._parse_q8_address(item.get("address", ""))
            stations.append({
                "id": f"dk_q8_{item.get('stationId', '')}",
                "country": "DK",
                "name": item.get("stationName", ""),
                "address": item.get("address", ""),
                "city": city,
                "postal_code": postal,
                "geo_street": street,   # extracted street component for geocoding
                "brand": item.get("stationName", ""),
                "lat": None,  # Q8 API doesn't include coordinates
                "lon": None,
                "source": "beta.q8.dk",
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })

        await _geo.apply_geocoding(
            stations, "DK", self.session,
            key_fn=lambda s: s["id"],
            query_fn=lambda s: (s.get("city", ""), s.get("geo_street", ""), s.get("postal_code", "")),
        )

        for s in stations:
            s.pop("geo_street", None)

        return stations

    def _map_shell_fuel(self, fuel_type: str, octane: str) -> str | None:
        key = (fuel_type, octane if octane else None)
        ft = SHELL_FUEL_MAP.get(key)
        if not ft:
            # Try without octane
            ft = SHELL_FUEL_MAP.get((fuel_type, None))
        return ft

    def _map_q8_fuel(self, product_name: str) -> str | None:
        name = product_name.lower()
        for keyword, ft in Q8_FUEL_MAP:
            if keyword.lower() in name:
                return ft
        return None

    def _parse_q8_address(self, address: str) -> Tuple[str, str, str]:
        """Parse Q8 address string → (city, postal, street).

        Format: "Street [Number] City PostalCode Danmark"
        e.g. "Dronningemaen 34 Svendborg 5700 Danmark"
        → city="Svendborg", postal="5700", street="Dronningemaen 34"
        """
        match = re.search(r'(\d{4})', address)
        postal = match.group(1) if match else ""
        street = ""
        if match:
            before_postal = address[:match.start()].strip()
            words = before_postal.split()
            city = words[-1] if words else ""
            street = " ".join(words[:-1]) if len(words) > 1 else ""
        else:
            city = ""
        return city, postal, street
