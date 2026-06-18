import aiohttp
import asyncio
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .base import BaseScraper
from . import geocoder as _geo

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


def _split_byvaeg(s: str) -> Tuple[str, str]:
    """Split a CamelCase ByVäg string into (city, street).

    "SolvesborgSnapphanegatan" → ("Solvesborg", "Snapphanegatan")
    "PiteaBergsviken"          → ("Pitea", "Bergsviken")
    "GoteborgKungsbackavagen"  → ("Goteborg", "Kungsbackavagen")
    """
    words = re.findall(r'[A-Z][a-z]*', s)
    if not words:
        return s, ""
    city   = words[0]
    street = " ".join(words[1:]) if len(words) > 1 else ""
    return city, street


class SwedenScraper(BaseScraper):
    COUNTRY = "SE"
    CURRENCY = "SEK"
    SOURCE = "bensinpriser.nu (via henrikhjelm.se)"
    CONFIDENCE = 0.85  # Community-curated + station-owner reported

    BASE_URL = "https://henrikhjelm.se/api/getdata.php"
    # Limit concurrent requests — the proxy server throttles under heavy parallel load.
    _CONCURRENCY = 4

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(self._CONCURRENCY)
        tasks = [self._fetch_county_throttled(c, sem) for c in COUNTIES]
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

            name, brand, geo_key, city, street = self._parse_station_id(station_id)
            stations.append({
                "id": f"se_{station_id}",
                "country": "SE",
                "name": name,
                "brand": brand,
                "address": street,
                "city": city,
                "geo_key": geo_key,   # raw CamelCase byvaeg used as geocache key
                "county": station_county.get(station_id, ""),
                "lat": None,
                "lon": None,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": price_entries,
            })

        await _geo.apply_geocoding(
            stations, "SE", self.session,
            key_fn=lambda s: s.get("geo_key", ""),
            query_fn=lambda s: (*_split_byvaeg(s.get("geo_key", "")), ""),
        )

        for s in stations:
            s.pop("geo_key", None)

        return stations

    # ── County fetch ───────────────────────────────────────────────────────

    async def _fetch_county_throttled(
        self, county: str, sem: asyncio.Semaphore
    ) -> List[Tuple[str, str, float]]:
        async with sem:
            result = await self._fetch_county(county)
            await asyncio.sleep(0.3)
            return result

    async def _fetch_county(self, county: str) -> List[Tuple[str, str, float]]:
        """Returns list of (station_id, fuel_type_raw, price)."""
        try:
            async with self.session.get(
                self.BASE_URL,
                params={"lan": county},
                timeout=aiohttp.ClientTimeout(total=30),
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

    # ── ID parser ──────────────────────────────────────────────────────────

    def _parse_station_id(self, station_id: str) -> Tuple[str, str, str, str, str]:
        """Parse station_id → (display_name, brand, geo_key, city, street).

        Key format: {county}_{seller}_{byväg}
        ByVäg is a CamelCase city+street concat: "SolvesborgSnapphanegatan"
        → city="Solvesborg", street="Snapphanegatan"
        → display: "St1 · Snapphanegatan, Solvesborg"
        """
        parts = station_id.split("_")
        if len(parts) < 2:
            return station_id, station_id, "", "", ""

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

        brand    = "_".join(brand_parts) if brand_parts else parts[1]
        geo_key  = byvaeg_parts[0] if byvaeg_parts else ""
        city, street = _split_byvaeg(geo_key) if geo_key else ("", "")

        display_brand = brand.replace("_", " ")
        if street and city:
            name = f"{display_brand} · {street}, {city}"
        elif city:
            name = f"{display_brand} · {city}"
        else:
            name = display_brand

        return name, brand, geo_key, city, street
