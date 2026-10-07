"""Greenland - station LOCATIONS from OpenStreetMap (ODbL), no prices.

Research 2026-10-07: no per-station price feed exists. The only price is Polaroil's national list
price page, which sits behind a WAF (HTTP 455 to scripts), carries no date and was not confirmed
to be uniform for every settlement or operator - so it is NOT published. Many OSM features are
unnamed and some are tank depots rather than retail pumps; this is a rough location layer.
Live Overpass query with mirrors; falls back to the bundled snapshot ``seed/gl_stations.json``.
"""
import json
from pathlib import Path
from typing import Any, Dict, List

from .base import BaseScraper

_UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
_MIRRORS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter"]
_QUERY = '[out:json][timeout:90];nwr["amenity"="fuel"](59.5,-74,83.7,-11.3);out center tags;'
_SEED = Path(__file__).resolve().parent.parent / "seed" / "gl_stations.json"


def _is_greenland(lat: float, lon: float) -> bool:
    if lat < 59.7:
        return False
    if lon > -25.5 and lat < 67.5:      # Iceland
        return False
    if lon < -58 and lat < 67:          # Baffin Island (Canada)
        return False
    return True


class GreenlandScraper(BaseScraper):
    COUNTRY    = "GL"
    CURRENCY   = "DKK"
    SOURCE     = "OpenStreetMap (ODbL) — locations only"
    CONFIDENCE = 0.40
    GRADE      = "L"
    REFRESH_MINUTES = 24 * 60

    async def _live(self) -> List[Dict[str, Any]]:
        for url in _MIRRORS:
            try:
                async with self.session.post(url, data={"data": _QUERY}, headers={"User-Agent": _UA},
                                             timeout=__import__("aiohttp").ClientTimeout(total=100)) as r:
                    if r.status != 200:
                        continue
                    els = (await r.json(content_type=None)).get("elements", [])
            except Exception as e:
                print(f"[GL] overpass {url}: {e}")
                continue
            out = []
            for e in els:
                lat = e.get("lat") or (e.get("center") or {}).get("lat")
                lon = e.get("lon") or (e.get("center") or {}).get("lon")
                if lat is None or lon is None or not _is_greenland(lat, lon):
                    continue
                t = e.get("tags", {})
                out.append({"osm": f"{e['type'][0]}{e['id']}", "lat": lat, "lon": lon,
                            "name": t.get("name", ""), "brand": t.get("brand") or t.get("operator") or ""})
            if out:
                return out
        return []

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        rows = await self._live()
        if not rows:
            print("[GL] Overpass unavailable - using bundled snapshot")
            rows = json.loads(_SEED.read_text(encoding="utf-8"))
        stations = []
        for r in rows:
            label = r["name"] or r["brand"] or "Fuel (OSM)"
            stations.append({
                "id": f"gl_{r['osm']}", "country": "GL", "name": label, "brand": r["brand"] or r["name"],
                "address": "", "city": "", "lat": round(r["lat"], 5), "lon": round(r["lon"], 5),
                "source": self.SOURCE, "confidence": self.CONFIDENCE, "prices": [],
            })
        print(f"[GL] {len(stations)} stations (locations only)")
        return stations
