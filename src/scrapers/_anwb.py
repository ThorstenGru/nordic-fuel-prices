"""
Shared ANWB Points-of-Interest API scraper.

ANWB (Dutch motorist association) aggregates real-time fuel prices for stations
across most of Europe via their Onderweg routing service.

Endpoint: https://api.anwb.nl/routing/points-of-interest/v3/all
  ?type-filter=FUEL_STATION
  &bounding-box-filter={min_lat},{min_lon},{max_lat},{max_lon}

ANWB always returns prices in EUR. For countries that use a different local
currency, the scraper fetches the ECB daily exchange rate and converts
automatically. Set CURRENCY to the ISO 4217 code of the local currency in
each subclass; leave it as "EUR" for eurozone countries.
"""

import re as _re
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from .base import BaseScraper

_API_BASE = (
    "https://api.anwb.nl/routing/points-of-interest/v3/all"
    "?type-filter=FUEL_STATION"
    "&bounding-box-filter={min_lat}%2C{min_lon}%2C{max_lat}%2C{max_lon}"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ECB daily XML exchange rates (base: EUR)
_ECB_URL   = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_ecb_cache: Dict[str, float] = {}   # currency_code → rate (how many units per 1 EUR)


async def _ecb_rates(session: aiohttp.ClientSession) -> Dict[str, float]:
    """Return {currency: units_per_EUR} from ECB daily feed. Cached per process."""
    if _ecb_cache:
        return _ecb_cache
    try:
        async with session.get(_ECB_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                text = await resp.text()
                for m in _re.finditer(r'currency="([A-Z]{3})"\s+rate="([\d.]+)"', text):
                    _ecb_cache[m.group(1)] = float(m.group(2))
    except Exception as e:
        print(f"[ECB] rate fetch failed: {e}")
    return _ecb_cache


# fuelType → (fuel_type, unit)  — EURO95 handled separately (E10 if name says so)
_FUEL_MAP = {
    "EURO98":         ("E5",     "L"),
    "SUPER_E5":       ("E5",     "L"),
    "DIESEL":         ("DIESEL", "L"),
    "DIESEL_SPECIAL": ("DIESEL", "L"),
    "LPG":            ("LPG",    "L"),
    "AUTOGAS":        ("LPG",    "L"),
    "CNG":            ("CNG",    "kg"),
    "E85":            ("E85",    "L"),
    "HVO":            ("HVO100", "L"),
    "HVO100":         ("HVO100", "L"),
}


def _map_fuel(fuel_type: str, fuel_name: str) -> Optional[Tuple[str, str]]:
    if fuel_type == "EURO95":
        return ("E10", "L") if "E10" in fuel_name else ("E5", "L")
    return _FUEL_MAP.get(fuel_type)


class ANWBScraper(BaseScraper):
    """Base class for country scrapers backed by the ANWB POI API."""

    # Subclasses must set these:
    ISO3: str = ""                                          # e.g. "NLD", "BEL", "POL"
    BBOX: Tuple[float, float, float, float] = (0, 0, 0, 0) # min_lat, min_lon, max_lat, max_lon
    CURRENCY = "EUR"   # override for non-eurozone countries (e.g. "PLN", "HUF", "CZK")

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        min_lat, min_lon, max_lat, max_lon = self.BBOX
        url = _API_BASE.format(
            min_lat=min_lat, min_lon=min_lon,
            max_lat=max_lat, max_lon=max_lon,
        )
        try:
            async with self.session.get(
                url,
                headers=_HEADERS,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    print(f"[{self.COUNTRY}] ANWB HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[{self.COUNTRY}] ANWB fetch error: {e}")
            return []

        stations = []
        for s in data.get("value", []):
            addr = s.get("address", {})
            if addr.get("iso3CountryCode") != self.ISO3:
                continue

            coords = s.get("coordinates", {})
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is None or lon is None:
                continue

            raw_prices = s.get("prices", [])
            prices = []
            for p in raw_prices:
                mapped = _map_fuel(p.get("fuelType", ""), p.get("fuelName", ""))
                if mapped is None:
                    continue
                val = p.get("value")
                if not isinstance(val, (int, float)) or val <= 0:
                    continue
                fuel_type, unit = mapped
                # Store in EUR; converted to local currency below if needed
                prices.append({
                    "fuel_type":  fuel_type,
                    "price":      float(val),
                    "currency":   "EUR",
                    "unit":       unit,
                    "updated_at": self.fetched_at,
                })

            if not prices:
                continue

            sid = s.get("id", "").replace("|", "_").replace(" ", "_")
            stations.append({
                "id":         f"{self.COUNTRY.lower()}_{sid}",
                "country":    self.COUNTRY,
                "name":       s.get("title", ""),
                "brand":      s.get("title", ""),
                "address":    addr.get("streetAddress", ""),
                "city":       addr.get("city", ""),
                "lat":        lat,
                "lon":        lon,
                "source":     self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices":     prices,
            })

        # Convert EUR → local currency when the country doesn't use EUR
        if self.CURRENCY != "EUR" and stations:
            rates = await _ecb_rates(self.session)
            rate  = rates.get(self.CURRENCY)
            if rate:
                for s in stations:
                    for p in s["prices"]:
                        p["price"]    = round(p["price"] * rate, 3)
                        p["currency"] = self.CURRENCY
            else:
                print(f"[{self.COUNTRY}] ECB rate not found for {self.CURRENCY} — keeping EUR")

        print(f"[{self.COUNTRY}] {len(stations)} stations from ANWB API")
        return stations
