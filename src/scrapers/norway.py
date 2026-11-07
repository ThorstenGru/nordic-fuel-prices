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

  The SSB national monthly average is deliberately not used (a country-wide
  average would be a fake per-station price). Station markers without an ANWB
  price show with empty prices.
"""

import aiohttp
import asyncio
from typing import List, Dict, Any
from merge_engine import MergeConfig, SourceResult, merge_sources
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


class NorwayScraper(BaseScraper):
    COUNTRY    = "NO"
    CURRENCY   = "NOK"
    SOURCE     = "anwb.nl (ANWB POI API) + openstreetmap.org (locations)"
    CONFIDENCE = 0.80
    GRADE = "C"
    REFRESH_MINUTES = 55   # full ANWB crawl plus a country-wide Overpass query per run: hourly

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        anwb_res, osm_els = await asyncio.gather(
            _NOAnwb(self.session).fetch_stations(), self._fetch_osm(), return_exceptions=True)

        anwb_err = osm_err = None
        if isinstance(anwb_res, Exception):
            anwb_err = str(anwb_res)
            print(f"[NO/ANWB] failed: {anwb_res}")
            anwb_res = []
        if isinstance(osm_els, Exception):
            osm_err = str(osm_els)
            print(f"[NO/OSM] failed: {osm_els}")
            osm_els = []
        elif not osm_els:
            osm_err = "empty"

        results = [
            SourceResult("anwb", "ANWB", anwb_res, 9, "aggregator", "NOK", ok=anwb_err is None, error=anwb_err),
            SourceResult("osm", "OpenStreetMap", self._parse_osm(osm_els), 99, "geometry", "NOK",
                         ok=osm_err is None, error=osm_err),
        ]
        stations, self.merge_report = merge_sources(results, MergeConfig(country="NO"))

        if not stations:
            raise RuntimeError("Norway: no station source returned data")

        rp = self.merge_report
        print(f"[NO] {len(stations)} stations ({rp['priced_station_count']} priced; "
              f"conflicts {rp['conflicts']}, outliers {rp['outliers_dropped']}, failed {rp['failed_sources']})")
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
            print(f"[NO/OSM] {type(e).__name__}: {e}")
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
