import aiohttp
import asyncio
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .base import BaseScraper

# Actual county slugs accepted by the API
COUNTIES = [
    "blekinge-lan", "dalarnas-lan", "gavleborgs-lan", "gotlands-lan",
    "hallands-lan", "jamtlands-lan", "jonkoping-lan", "kalmar-lan",
    "kronobergs-lan", "norrbottens-lan", "orebro-lan", "ostergotlands-lan",
    "skane-lan", "sodermanlands-lan", "stockholms-lan", "uppsala-lan",
    "varmlands-lan", "vasterbottens-lan", "vasternorrlands-lan",
    "vastmanlands-lan", "vastra-gotalands-lan",
]

# API key suffix → (fuel_type, unit)
FUEL_MAP = {
    "95":          ("E10",    "L"),
    "98":          ("E5",     "L"),
    "diesel":      ("DIESEL", "L"),
    "biodiesel":   ("HVO100", "L"),
    "etanol":      ("E85",    "L"),
    "fordonsgas":  ("CNG",    "kg"),
}


class SwedenScraper(BaseScraper):
    COUNTRY = "SE"
    CURRENCY = "SEK"
    SOURCE = "henrikhjelm.se"
    CONFIDENCE = 0.85  # Community-curated

    BASE_URL = "https://henrikhjelm.se/api/getdata.php"

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        tasks = [self._fetch_county(c) for c in COUNTIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge: station_id → {fuel_type: price, ...}
        station_prices: Dict[str, Dict[str, float]] = defaultdict(dict)
        station_county: Dict[str, str] = {}

        for county, result in zip(COUNTIES, results):
            if isinstance(result, Exception) or not result:
                continue
            for station_id, fuel_type, price in result:
                station_prices[station_id][fuel_type] = price
                station_county[station_id] = county

        stations = []
        for station_id, prices_by_fuel in station_prices.items():
            price_entries = [
                self.price_entry(ft, price, FUEL_MAP[ft_raw][1])
                for ft_raw, (ft, _) in FUEL_MAP.items()
                if (price := prices_by_fuel.get(ft)) and price > 0
            ]
            # Rebuild price entries properly
            price_entries = []
            for ft_raw, (ft, unit) in FUEL_MAP.items():
                p = prices_by_fuel.get(ft_raw)
                if p and p > 0:
                    price_entries.append(self.price_entry(ft, p, unit))

            if not price_entries:
                continue

            name, city = self._parse_name(station_id)
            stations.append({
                "id": f"se_{station_id}",
                "country": "SE",
                "name": name,
                "city": city,
                "county": station_county.get(station_id, ""),
                "lat": None,
                "lon": None,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": price_entries,
            })

        return stations

    async def _fetch_county(self, county: str) -> List[Tuple[str, str, float]]:
        """Returns list of (station_id, fuel_type_raw, price)."""
        try:
            async with self.session.get(
                self.BASE_URL,
                params={"lan": county},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        except Exception:
            return []

        if not isinstance(data, dict) or "error" in data:
            return []

        entries = []
        for key, raw_val in data.items():
            # Key format: {county}_{brand}_{address}__{fuel_type}
            if "__" not in key:
                continue
            station_id, fuel_raw = key.rsplit("__", 1)
            if fuel_raw not in FUEL_MAP:
                continue
            try:
                price = float(str(raw_val).replace(",", "."))
            except (ValueError, TypeError):
                continue
            if price > 0:
                entries.append((station_id, fuel_raw, price))

        return entries

    def _parse_name(self, station_id: str) -> Tuple[str, str]:
        """Extract readable name and city from station_id key."""
        # Format: {county}_{brand}_{cityaddress}
        parts = station_id.split("_", 2)
        if len(parts) >= 3:
            brand = parts[1]
            address = parts[2].replace("_", " ")
            # First word of address is usually the city
            words = address.split()
            city = words[0] if words else ""
            return f"{brand} {address}".strip(), city
        return station_id, ""
