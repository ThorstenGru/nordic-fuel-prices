import asyncio
import re
import json
import aiohttp
from typing import List, Dict, Any, Optional
from .base import BaseScraper

# Romania: peco-online.ro — server-side rendered map with embedded JSON
# Fuel price data from ANPC mandatory price reporting
# ~1200+ stations with GPS, prices in RON/L
#
# Strategy: POST index.php per county × fuel type, parse embedded JSON.
# Response embeds: var rezultate = JSON.parse('[["Brand",lat,lon,"City","Address",price], ...]')

BASE_URL = "https://www.peco-online.ro/index.php"

# All 42 Romanian counties (judete) + Ilfov
_COUNTIES = [
    "Alba", "Arad", "Arges", "Bacau", "Bihor", "Bistrita-Nasaud",
    "Botosani", "Braila", "Brasov", "Buzau", "Calarasi", "Cluj",
    "Constanta", "Covasna", "Dambovita", "Dolj", "Galati", "Giurgiu",
    "Gorj", "Harghita", "Hunedoara", "Ialomita", "Iasi", "Ilfov",
    "Maramures", "Mehedinti", "Mures", "Neamt", "Olt", "Prahova",
    "Salaj", "Satu Mare", "Sibiu", "Suceava", "Teleorman", "Timis",
    "Tulcea", "Vaslui", "Valcea", "Vrancea", "Municipiul Bucuresti",
]

# Station chains with reported prices (send all as retele[] to include everyone)
_RETELE = [
    "Gazprom", "Lukoil", "Mol", "OMV", "Petrom", "Rompetrol", "Socar",
    "ALD", "BLKOil", "CellyRo", "Dacma", "DHR", "Metropoli", "Ozana",
    "Petrolium", "Petromar", "RST", "TEAutohof", "VhExtraOil",
]

# Fuel types to query → internal fuel_type
_FUELS = {
    "Benzina_Regular":  ("E5",     "L"),
    "Motorina_Regular": ("DIESEL", "L"),
    "GPL":              ("LPG",    "L"),
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.peco-online.ro/index.php",
    "Origin": "https://www.peco-online.ro",
}

_LAT_MIN, _LAT_MAX = 43.5, 48.4
_LON_MIN, _LON_MAX = 22.0, 30.2

_REZULTATE_RE = re.compile(r"var rezultate\s*=\s*JSON\.parse\('(\[.*?\])'\)", re.DOTALL)


class RomaniaScraper(BaseScraper):
    COUNTRY = "RO"
    CURRENCY = "RON"
    SOURCE = "peco-online.ro"
    CONFIDENCE = 0.90

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        # station_key → {id, name, brand, address, city, lat, lon, prices_dict}
        stations_by_key: Dict[str, dict] = {}

        for fuel_key, (ft, unit) in _FUELS.items():
            for county in _COUNTIES:
                entries = await self._fetch_county(county, fuel_key)
                for entry in entries:
                    brand, lat, lon, city, address, price = entry
                    key = f"{brand}|{round(lat, 4)}|{round(lon, 4)}"
                    if key not in stations_by_key:
                        idx = len(stations_by_key)
                        stations_by_key[key] = {
                            "id":         f"ro_{idx}",
                            "country":    "RO",
                            "name":       brand,
                            "brand":      brand,
                            "address":    address,
                            "city":       city,
                            "lat":        lat,
                            "lon":        lon,
                            "source":     self.SOURCE,
                            "confidence": self.CONFIDENCE,
                            "_prices":    {},
                        }
                    # Only update price if not already set (first county wins)
                    if ft not in stations_by_key[key]["_prices"]:
                        stations_by_key[key]["_prices"][ft] = (price, unit)

                await asyncio.sleep(0.15)

        # Convert to final format
        result = []
        for s in stations_by_key.values():
            prices = [
                self.price_entry(ft, pr, unit)
                for ft, (pr, unit) in s.pop("_prices").items()
                if pr > 0
            ]
            if prices:
                s["prices"] = prices
                result.append(s)

        print(f"[RO] {len(result)} stations from peco-online.ro")
        return result

    async def _fetch_county(self, county: str, carburant: str) -> list:
        post_data = {
            "carburant": carburant,
            "locatie": "Judet",
            "nume_locatie": county,
        }
        # Add all station chain checkboxes
        retele_str = "&".join(f"retele[]={r}" for r in _RETELE)
        form_body = "&".join(f"{k}={v}" for k, v in post_data.items()) + "&" + retele_str

        try:
            async with self.session.post(
                BASE_URL,
                data=form_body,
                timeout=aiohttp.ClientTimeout(total=20),
                headers=_HEADERS,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        m = _REZULTATE_RE.search(html)
        if not m:
            return []

        try:
            raw = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            return []

        entries = []
        for item in raw:
            if not isinstance(item, list) or len(item) < 6:
                continue
            brand = str(item[0]).strip()
            try:
                lat = float(item[1])
                lon = float(item[2])
            except (TypeError, ValueError):
                continue
            if not (_LAT_MIN <= lat <= _LAT_MAX) or not (_LON_MIN <= lon <= _LON_MAX):
                continue
            city = str(item[3]).strip()
            address = str(item[4]).strip()
            try:
                price = float(item[5])
            except (TypeError, ValueError):
                continue
            if price > 0:
                entries.append((brand, lat, lon, city, address, price))

        return entries
