import aiohttp
import asyncio
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .base import BaseScraper

# ByVäg segment signature: starts uppercase, has 2+ consecutive lowercase, then another uppercase.
# Examples: "BollebygdKappared", "PiteaBergsviken", "GullspangOtterbacken"
# Excluded: "Circle", "K", "AB", "Express", "OKQ8", "dinX", "St1"
_BYVAEG_RE   = re.compile(r'^[A-Z][a-z]{2,}[A-Z]')
_CAMEL_RE    = re.compile(r'[A-Z][a-z]+|[A-Z]+(?=[A-Z][a-z])|[A-Z]+$|[a-z]+')

# Geocoding — Nominatim (OpenStreetMap), free, 1 req/s limit
_DATA_DIR     = Path(__file__).parent.parent.parent / "data"
_GEOCACHE_PATH = _DATA_DIR / "se_geocache.json"
_GEOCACHE_URL  = "https://thorstengru.github.io/nordic-fuel-prices/se_geocache.json"
_NOMINATIM    = "https://nominatim.openstreetmap.org/search"
_UA           = "EuroFuelPrices/1.0 (https://github.com/ThorstenGru/nordic-fuel-prices)"
GEOCODE_LIMIT = 300   # max new geocoding calls per scrape run (~5 min at 1 req/s)

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

        await self._apply_geocoding(stations)

        # Strip internal field before returning
        for s in stations:
            s.pop("geo_key", None)

        return stations

    # ── Geocoding ──────────────────────────────────────────────────────────

    async def _apply_geocoding(self, stations: List[Dict]) -> None:
        geocache = await self._load_geocache()

        # 1. Apply cached coords
        for s in stations:
            entry = geocache.get(s.get("geo_key", ""))
            if entry:
                s["lat"] = entry["lat"]
                s["lon"] = entry["lon"]

        # 2. Collect unique uncached byvaeg keys
        seen: set = set()
        to_geocode: List[Dict] = []
        for s in stations:
            k = s.get("geo_key", "")
            if k and k not in geocache and k not in seen:
                seen.add(k)
                to_geocode.append(s)

        if not to_geocode:
            geocoded = sum(1 for s in stations if s["lat"] is not None)
            print(f"[SE] {geocoded}/{len(stations)} stations with GPS (cache: {len(geocache)})")
            return

        # 3. Geocode new stations sequentially (rate-limit: 1 req/s per Nominatim policy)
        new_count = 0
        for s in to_geocode[:GEOCODE_LIMIT]:
            k = s.get("geo_key", "")
            city, street = _split_byvaeg(k)
            lat, lon = await self._geocode_one(city, street)
            geocache[k] = {"lat": lat, "lon": lon}   # store even if None (avoids re-querying)
            if lat is not None:
                s["lat"] = lat
                s["lon"] = lon
                new_count += 1
            await asyncio.sleep(1.1)

        # 4. Save updated cache
        _DATA_DIR.mkdir(exist_ok=True)
        try:
            with open(_GEOCACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(geocache, f, separators=(",", ":"))
        except OSError as e:
            print(f"[SE] geocache save failed: {e}")

        geocoded = sum(1 for s in stations if s["lat"] is not None)
        remaining = len([s for s in to_geocode[GEOCODE_LIMIT:] if s.get("geo_key")])
        print(
            f"[SE] {geocoded}/{len(stations)} stations with GPS "
            f"(+{new_count} new, cache: {len(geocache)}, "
            f"{remaining} still pending)"
        )

    async def _load_geocache(self) -> Dict:
        """Load geocache from local file or previous GitHub Pages deploy."""
        if _GEOCACHE_PATH.exists():
            try:
                with open(_GEOCACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass

        # Fall back to last deployed version on GitHub Pages
        try:
            async with self.session.get(
                _GEOCACHE_URL,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict):
                        print(f"[SE] Loaded geocache from GitHub Pages ({len(data)} entries)")
                        return data
        except Exception:
            pass

        return {}

    async def _geocode_one(self, city: str, street: str) -> Tuple:
        """Geocode a city+street in Sweden via Nominatim. Returns (lat, lon) or (None, None)."""
        params: Dict[str, Any] = {"countrycodes": "se", "format": "json", "limit": 1}
        if street:
            params["street"] = street
            params["city"] = city
        else:
            params["q"] = f"{city}, Sweden"
        try:
            async with self.session.get(
                _NOMINATIM, params=params,
                headers={"User-Agent": _UA},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if data:
                        return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass
        return None, None

    # ── County fetch ───────────────────────────────────────────────────────

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
