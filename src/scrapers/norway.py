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
from typing import List, Dict, Any
from .base import BaseScraper


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
    SOURCE     = "openstreetmap.org (locations) + ssb.no (national avg)"
    CONFIDENCE = 0.75  # Locations from OSM, no per-station prices available

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        osm_task, ssb_task = self._fetch_osm(), self._fetch_ssb()
        osm_els, ssb_avg = await asyncio.gather(osm_task, ssb_task, return_exceptions=True)

        if isinstance(osm_els, Exception):
            print(f"[NO/OSM] failed: {osm_els}")
            osm_els = []
        if isinstance(ssb_avg, Exception) or not ssb_avg:
            print("[NO/SSB] failed or no data")
            ssb_avg = []

        stations = self._parse_osm(osm_els)

        # SSB price is a national average — store it only if no OSM data came back,
        # so the map isn't completely empty.
        if not stations and ssb_avg:
            stations = self._fallback_ssb_markers(ssb_avg)

        if ssb_avg:
            print(f"[NO] SSB national avg: {ssb_avg}")
        print(f"[NO] {len(stations)} stations from OSM (no per-station prices available)")
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
