import aiohttp
import asyncio
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .base import BaseScraper

# ByVäg segment signature: starts uppercase, has 2+ consecutive lowercase, then another uppercase.
# Examples: "BollebygdKappared", "PiteaBergsviken", "GullspangOtterbacken"
# Excluded: "Circle", "K", "AB", "Express", "OKQ8", "dinX", "St1"
_BYVAEG_RE = re.compile(r'^[A-Z][a-z]{2,}[A-Z]')

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
            price_entries = []
            for ft_raw, (ft, unit) in FUEL_MAP.items():
                p = prices_by_fuel.get(ft_raw)
                if p and p > 0:
                    price_entries.append(self.price_entry(ft, p, unit))

            if not price_entries:
                continue

            name, brand, city = self._parse_station_id(station_id)
            stations.append({
                "id": f"se_{station_id}",
                "country": "SE",
                "name": name,
                "brand": brand,
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

    def _parse_station_id(self, station_id: str) -> Tuple[str, str, str]:
        """Parse station_id → (display_name, brand, city).

        Key format: {county}_{seller}_{byväg}
        where seller may contain underscores (Circle_K, Neste_Oil_Express, Borjes_Tankcenter…)
        and byväg is a CamelCase concatenation of municipality+road (e.g. BollebygdKappared).

        The ByVäg segment is detected by: starts with uppercase, has 2+ consecutive lowercase
        letters, then another uppercase — this matches "BollebygdKappared" but not "Circle",
        "K", "AB", "dinX", "OKQ8", or "Express".
        """
        parts = station_id.split("_")
        if len(parts) < 2:
            return station_id, station_id, ""

        brand_parts: list = []
        byvaeg_parts: list = []
        in_byvaeg = False
        for seg in parts[1:]:  # skip county at parts[0]
            if not in_byvaeg and _BYVAEG_RE.match(seg):
                in_byvaeg = True
            if in_byvaeg:
                byvaeg_parts.append(seg)
            else:
                brand_parts.append(seg)

        brand = "_".join(brand_parts) if brand_parts else parts[1]
        address = " ".join(byvaeg_parts) if byvaeg_parts else ""
        # city = first ByVäg segment (CamelCase city+road; best we can do without a municipality list)
        city = byvaeg_parts[0] if byvaeg_parts else ""
        display_brand = brand.replace("_", " ")
        name = f"{display_brand} · {address}".strip(" ·") if address else display_brand
        return name, brand, city
