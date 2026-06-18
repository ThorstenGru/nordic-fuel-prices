"""
Sweden fuel price scraper.

Station locations: OpenStreetMap (Overpass API) — all brands, GPS included.
Prices:           bensinpriser.nu via henrikhjelm.se proxy — crowdsourced +
                  station-owner reported prices.

Strategy:
  1. Fetch all Swedish fuel station locations from OSM (one request).
  2. Fetch prices county-by-county from henrikhjelm.se (bensinpriser.nu).
  3. Match priced stations to OSM stations using normalised brand + city.
  4. Output: all OSM stations (with prices where matched) plus any priced
     stations that could not be matched but were geocoded.

Why prices are hard to get in Sweden:
  Konkurrensverket (Swedish Competition Authority) warned chains that
  publishing recommended prices online might violate antitrust law.
  Circle K removed prices; Preem, OKQ8, ST1 don't publish them either.
  Pricing is per-station (local), only visible at the physical price board.
  bensinpriser.nu is the only crowd/owner-reported free source available.
"""

import aiohttp
import asyncio
import re
import unicodedata
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from .base import BaseScraper
from . import geocoder as _geo


# ── OpenStreetMap (Overpass API) ───────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """[out:json][timeout:60];
area["ISO3166-1"="SE"]->.se;
(
  node["amenity"="fuel"](area.se);
  way["amenity"="fuel"](area.se);
);
out center tags;"""
OVERPASS_HEADERS = {
    "User-Agent": "EuroFuelPrices/1.0 (https://github.com/ThorstenGru/nordic-fuel-prices)",
}


# ── bensinpriser.nu / henrikhjelm.se ──────────────────────────────────────────

HENRIKHJELM_URL = "https://henrikhjelm.se/api/getdata.php"

COUNTIES = [
    "blekinge-lan", "dalarnas-lan", "gavleborgs-lan", "gotlands-lan",
    "hallands-lan", "jamtlands-lan", "jonkoping-lan", "kalmar-lan",
    "kronobergs-lan", "norrbottens-lan", "orebro-lan", "ostergotlands-lan",
    "skane-lan", "sodermanlands-lan", "stockholms-lan", "uppsala-lan",
    "varmlands-lan", "vasterbottens-lan", "vasternorrlands-lan",
    "vastmanlands-lan", "vastra-gotalands-lan",
]

FUEL_MAP = {
    "95":         ("E10",    "L"),
    "98":         ("E5",     "L"),
    "diesel":     ("DIESEL", "L"),
    "biodiesel":  ("HVO100", "L"),
    "etanol":     ("E85",    "L"),
    "fordonsgas": ("CNG",    "kg"),
}

# ByVäg segment: starts uppercase, 2+ lowercase, then another uppercase.
_BYVAEG_RE = re.compile(r'^[A-Z][a-z]{2,}[A-Z]')


# ── Brand/city normalisation ───────────────────────────────────────────────────

# OSM sometimes still shows the old brand name; map to current operator.
_BRAND_ALIASES: Dict[str, str] = {
    "shell":   "st1",   # St1 rebranded Shell stations in Sweden (~2024)
    "statoil": "circlek",
}


def _norm(s: str) -> str:
    """Lowercase, strip diacritics, keep alphanumerics only."""
    nfkd = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in nfkd if not unicodedata.combining(c)))


def _brand_key(raw: str) -> str:
    n = _norm(raw.split()[0] if raw.strip() else "")
    return _BRAND_ALIASES.get(n, n)


def _osm_brand_city(tags: dict) -> Tuple[str, str]:
    brand_raw = tags.get("brand") or tags.get("operator") or tags.get("name") or ""
    city_raw  = (
        tags.get("addr:city") or tags.get("addr:town") or
        tags.get("addr:village") or tags.get("addr:municipality") or ""
    )
    return _brand_key(brand_raw), _norm(city_raw)


# ── ByVäg parsing (bensinpriser.nu address format) ────────────────────────────

def _split_byvaeg(s: str) -> Tuple[str, str]:
    words = re.findall(r"[A-Z][a-z]*", s)
    if not words:
        return s, ""
    return words[0], " ".join(words[1:]) if len(words) > 1 else ""


def _parse_station_id(station_id: str) -> Tuple[str, str, str, str, str]:
    """Parse {county}_{brand}_{byvaeg} → (name, brand, geo_key, city, street)."""
    parts = station_id.split("_")
    if len(parts) < 2:
        return station_id, station_id, "", "", ""

    brand_parts: list = []
    byvaeg_parts: list = []
    in_byvaeg = False
    for seg in parts[1:]:
        if not in_byvaeg and _BYVAEG_RE.match(seg):
            in_byvaeg = True
        if in_byvaeg:
            byvaeg_parts.append(seg)
        else:
            brand_parts.append(seg)

    brand   = "_".join(brand_parts) if brand_parts else parts[1]
    geo_key = byvaeg_parts[0] if byvaeg_parts else ""
    city, street = _split_byvaeg(geo_key) if geo_key else ("", "")
    display = brand.replace("_", " ")
    if street and city:
        name = f"{display} · {street}, {city}"
    elif city:
        name = f"{display} · {city}"
    else:
        name = display
    return name, brand, geo_key, city, street


# ── Scraper ────────────────────────────────────────────────────────────────────

class SwedenScraper(BaseScraper):
    COUNTRY    = "SE"
    CURRENCY   = "SEK"
    SOURCE     = "openstreetmap.org + bensinpriser.nu"
    CONFIDENCE = 0.80

    _CONCURRENCY = 4  # max concurrent county requests to henrikhjelm.se

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        osm_task   = self._fetch_osm()
        price_task = self._fetch_all_counties()
        osm_els, priced = await asyncio.gather(osm_task, price_task, return_exceptions=True)

        if isinstance(osm_els, Exception):
            print(f"[SE/OSM] failed: {osm_els}")
            osm_els = []
        if isinstance(priced, Exception):
            print(f"[SE/bensinpriser] failed: {priced}")
            priced = []

        # Build OSM station list and a lookup index by (brand_key, city_norm)
        osm_stations = self._parse_osm(osm_els)
        osm_index: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        for s in osm_stations:
            bk, ck = s.pop("_bk", ""), s.pop("_ck", "")
            if bk and ck:
                osm_index[(bk, ck)].append(s)

        # Match priced entries → OSM stations by normalised brand + city
        unmatched: List[Dict] = []
        for p in priced:
            bk = _brand_key(p.get("brand", ""))
            ck = _norm(p.get("city", ""))
            matched = False
            for cand in osm_index.get((bk, ck), []):
                if not cand["prices"]:          # take first unpriced match
                    cand["prices"]     = p["prices"]
                    cand["source"]     = "bensinpriser.nu"
                    cand["confidence"] = 0.85
                    matched = True
                    break
            if not matched:
                unmatched.append(p)

        # Geocode unmatched priced stations so they still appear on the map
        await _geo.apply_geocoding(
            unmatched, "SE", self.session,
            key_fn=lambda s: s.get("geo_key", ""),
            query_fn=lambda s: (*_split_byvaeg(s.get("geo_key", "")), ""),
        )
        for s in unmatched:
            s.pop("geo_key", None)

        # Combine: all OSM stations + unmatched priced stations that have GPS
        all_stations = osm_stations + [s for s in unmatched if s.get("lat") is not None]
        with_prices  = sum(1 for s in all_stations if s["prices"])
        print(f"[SE] {len(all_stations)} stations total, {with_prices} with prices")
        return all_stations

    # ── OSM fetch ──────────────────────────────────────────────────────────────

    async def _fetch_osm(self) -> list:
        try:
            async with self.session.post(
                OVERPASS_URL,
                data={"data": OVERPASS_QUERY},
                headers=OVERPASS_HEADERS,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    print(f"[SE/OSM] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
                return data.get("elements", [])
        except Exception as e:
            print(f"[SE/OSM] {e}")
            return []

    def _parse_osm(self, elements: list) -> List[Dict]:
        stations = []
        seen: set = set()
        for el in elements:
            eid = el.get("id")
            if eid in seen:
                continue
            seen.add(eid)

            if el["type"] == "node":
                lat, lon = el.get("lat"), el.get("lon")
            else:
                c = el.get("center", {})
                lat, lon = c.get("lat"), c.get("lon")
            if lat is None or lon is None:
                continue

            tags = el.get("tags", {})
            name  = tags.get("name") or tags.get("brand") or tags.get("operator") or "Bränslestation"
            brand = tags.get("brand") or tags.get("operator") or tags.get("name") or ""
            city  = (tags.get("addr:city") or tags.get("addr:town")
                     or tags.get("addr:village") or "")
            street     = tags.get("addr:street", "")
            housenumber = tags.get("addr:housenumber", "")
            address    = f"{street} {housenumber}".strip()

            bk, ck = _osm_brand_city(tags)
            stations.append({
                "id":         f"se_osm_{eid}",
                "country":    "SE",
                "name":       name,
                "brand":      brand,
                "address":    address,
                "city":       city,
                "lat":        lat,
                "lon":        lon,
                "source":     "openstreetmap.org",
                "confidence": 0.75,
                "prices":     [],
                "_bk":        bk,
                "_ck":        ck,
            })

        print(f"[SE/OSM] {len(stations)} stations")
        return stations

    # ── bensinpriser.nu (via henrikhjelm.se) ──────────────────────────────────

    async def _fetch_all_counties(self) -> List[Dict]:
        sem   = asyncio.Semaphore(self._CONCURRENCY)
        tasks = [self._fetch_county_throttled(c, sem) for c in COUNTIES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        station_prices: Dict[str, Dict[str, float]] = defaultdict(dict)
        station_county: Dict[str, str] = {}

        for county, result in zip(COUNTIES, results):
            if isinstance(result, Exception) or not result:
                continue
            for station_id, fuel_raw, price in result:
                station_prices[station_id][fuel_raw] = price
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
            name, brand, geo_key, city, street = _parse_station_id(station_id)
            stations.append({
                "id":         f"se_{station_id}",
                "country":    "SE",
                "name":       name,
                "brand":      brand,
                "address":    street,
                "city":       city,
                "geo_key":    geo_key,
                "county":     station_county.get(station_id, ""),
                "lat":        None,
                "lon":        None,
                "source":     "bensinpriser.nu",
                "confidence": 0.85,
                "prices":     price_entries,
            })

        print(f"[SE/bensinpriser] {len(stations)} priced stations")
        return stations

    async def _fetch_county_throttled(
        self, county: str, sem: asyncio.Semaphore
    ) -> List[Tuple[str, str, float]]:
        async with sem:
            result = await self._fetch_county(county)
            await asyncio.sleep(0.3)
            return result

    async def _fetch_county(self, county: str) -> List[Tuple[str, str, float]]:
        try:
            async with self.session.get(
                HENRIKHJELM_URL,
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
