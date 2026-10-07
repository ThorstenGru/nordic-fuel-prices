"""
Norway fuel price scraper.

Station locations: OpenStreetMap (Overpass API) — all brands, GPS included.
Prices:           None available as free, real-time per-station data.

Why per-station prices are unavailable:
  Konkurransetilsynet (Norwegian Competition Authority) banned Circle K, YX,
  and Uno-X from publishing indicative list prices until October 2030 as an
  anti-cartel commitment. ST1/Shell also publishes nothing. ANWB POI API
  confirmed 0 Norwegian stations (tested 2026-06-18). Drivstoffappen went
  commercial. No equivalent to Denmark's mandatory reporting.

  National monthly average from SSB (Statistics Norway, table 09654) is still
  fetched and stored in meta, but it is NOT attached to individual stations
  because it is a country-wide average and would be misleading as a per-station
  price. All station markers show with empty prices.
"""

import aiohttp
import asyncio
import math
from typing import List, Dict, Any
from .base import BaseScraper
from ._anwb import ANWBScraper


class _NOAnwb(ANWBScraper):
    """ANWB now serves Norwegian stations with diesel/95 prices (0 in June 2026, ~1k by Oct 2026)."""
    COUNTRY    = "NO"
    ISO3       = "NOR"
    CURRENCY   = "NOK"
    BBOX       = (57.9, 4.3, 71.3, 31.3)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.80


def _near(lat: float, lon: float, grid: Dict, radius_m: float = 100.0) -> bool:
    """True if any point in ``grid`` (cell -> [(lat, lon)]) is within radius_m."""
    ci, cj = int(lat * 100), int(lon * 50)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for (la, lo) in grid.get((ci + di, cj + dj), ()):
                dy = (la - lat) * 111_320
                dx = (lo - lon) * 111_320 * math.cos(math.radians(lat))
                if dx * dx + dy * dy <= radius_m * radius_m:
                    return True
    return False


# ── OpenStreetMap (Overpass API) ───────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """[out:json][timeout:60];
area["ISO3166-1"="NO"]->.no;
(
  node["amenity"="fuel"](area.no);
  way["amenity"="fuel"](area.no);
);
out center tags;"""
OVERPASS_HEADERS = {
    "User-Agent": "EuroFuelPrices/1.0 (https://github.com/ThorstenGru/nordic-fuel-prices)",
}


# ── Statistics Norway (SSB) — national monthly average ────────────────────────

SSB_URL = "https://data.ssb.no/api/v0/en/table/09654"
SSB_BODY = {
    "query": [
        {"code": "PetroleumProd", "selection": {"filter": "item", "values": ["031", "035"]}},
        {"code": "ContentsCode",  "selection": {"filter": "item", "values": ["Priser"]}},
        {"code": "Tid",           "selection": {"filter": "top",  "values": ["1"]}},
    ],
    "response": {"format": "json-stat2"},
}


class NorwayScraper(BaseScraper):
    COUNTRY    = "NO"
    CURRENCY   = "NOK"
    SOURCE     = "anwb.nl (ANWB POI API) + openstreetmap.org (locations)"
    CONFIDENCE = 0.80
    GRADE = "C"

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb_res, osm_els, ssb_avg = await asyncio.gather(
            _NOAnwb(self.session).fetch_stations(), self._fetch_osm(), self._fetch_ssb(),
            return_exceptions=True)

        if isinstance(anwb_res, Exception):
            print(f"[NO/ANWB] failed: {anwb_res}")
            anwb_res = []
        if isinstance(osm_els, Exception):
            print(f"[NO/OSM] failed: {osm_els}")
            osm_els = []
        if isinstance(ssb_avg, Exception) or not ssb_avg:
            ssb_avg = []

        stations: List[Dict[str, Any]] = list(anwb_res)
        grid: Dict = {}
        for st in stations:
            grid.setdefault((int(st["lat"] * 100), int(st["lon"] * 50)), []).append((st["lat"], st["lon"]))

        # OSM adds only stations ANWB does not know (shown without prices, never invented ones)
        extra = [o for o in self._parse_osm(osm_els) if not _near(o["lat"], o["lon"], grid)]
        stations.extend(extra)

        if not stations and ssb_avg:
            stations = self._fallback_ssb_markers(ssb_avg)
        if not stations:
            raise RuntimeError("Norway: no station source returned data")

        if ssb_avg:
            print(f"[NO] SSB national avg (reference only, not attached to stations): {ssb_avg}")
        priced = sum(1 for st in stations if st.get("prices"))
        print(f"[NO] {len(stations)} stations: {len(anwb_res)} from ANWB, {len(extra)} OSM-only "
              f"({priced} priced)")
        return stations

    # ── OSM ────────────────────────────────────────────────────────────────────

    async def _fetch_osm(self) -> list:
        try:
            async with self.session.post(
                OVERPASS_URL,
                data={"data": OVERPASS_QUERY},
                headers=OVERPASS_HEADERS,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    print(f"[NO/OSM] HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
                return data.get("elements", [])
        except Exception as e:
            print(f"[NO/OSM] {e}")
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

            tags   = el.get("tags", {})
            name   = tags.get("name") or tags.get("brand") or tags.get("operator") or "Bensinstasjon"
            brand  = tags.get("brand") or tags.get("operator") or tags.get("name") or ""
            city   = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village") or ""
            street = tags.get("addr:street", "")
            housenumber = tags.get("addr:housenumber", "")
            address = f"{street} {housenumber}".strip()

            stations.append({
                "id":         f"no_osm_{eid}",
                "country":    "NO",
                "name":       name,
                "brand":      brand,
                "address":    address,
                "city":       city,
                "lat":        lat,
                "lon":        lon,
                "source":     "openstreetmap.org",
                "confidence": 0.75,
                "prices":     [],
            })
        return stations

    # ── SSB fallback ───────────────────────────────────────────────────────────

    async def _fetch_ssb(self) -> List[Dict]:
        try:
            async with self.session.post(
                SSB_URL,
                json=SSB_BODY,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        except Exception as e:
            print(f"[NO/SSB] {e}")
            return []

        values = data.get("value", [])
        if len(values) < 2:
            return []

        prices = []
        for idx, fuel_type, unit in [(0, "E10", "L"), (1, "DIESEL", "L")]:
            try:
                p = float(values[idx])
                if p > 0:
                    prices.append(self.price_entry(fuel_type, p, unit))
            except (TypeError, ValueError, IndexError):
                pass
        return prices

    def _fallback_ssb_markers(self, prices: List[Dict]) -> List[Dict]:
        """Only used when OSM returns nothing — show SSB avg at major cities."""
        cities = [
            ("Oslo",      59.9139, 10.7522),
            ("Bergen",    60.3913,  5.3221),
            ("Trondheim", 63.4305, 10.3951),
            ("Stavanger", 58.9700,  5.7331),
            ("Tromsø",    69.6496, 18.9560),
        ]
        return [
            {
                "id":         f"no_ssb_{city.lower()}",
                "country":    "NO",
                "name":       f"Norway Avg · {city}",
                "brand":      "National Average",
                "address":    "SSB Statistics Norway · monthly avg",
                "city":       city,
                "lat":        lat,
                "lon":        lon,
                "source":     "ssb.no (national monthly avg)",
                "confidence": 0.85,
                "prices":     prices,
            }
            for city, lat, lon in cities
        ]
