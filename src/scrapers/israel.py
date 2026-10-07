"""Israel - official Ministry of Energy station register (data.gov.il), locations only.

Pump prices in Israel are ONE regulated national maximum per month (gov.il publishes it behind
Cloudflare; no open feed). Research 2026-10-07 found conflicting secondary figures (8.03 vs 8.27
ILS/L for 95 self-service), so no price is published until a primary source is confirmed.
Register: 1,255 stations with WGS84 coordinates, licence "Other (Open)".
"""
from typing import Any, Dict, List

import aiohttp

from .base import BaseScraper

_URL = ("https://data.gov.il/api/3/action/datastore_search"
        "?resource_id=5537a0ef-3eeb-449c-90c8-51e27564f0cb&limit=3000")
_BRANDS = {"דור-אלון": "Dor Alon", "דור אלון": "Dor Alon", "דלק": "Delek", "פז": "Paz",
           "סונול": "Sonol", "טן": "Ten", "תפוז": "Tapuz", "מיקה": "Mika", "סדש": "Sadash",
           "יעד": "Yaad"}


class IsraelScraper(BaseScraper):
    COUNTRY    = "IL"
    CURRENCY   = "ILS"
    SOURCE     = "data.gov.il — Ministry of Energy station register (locations only)"
    CONFIDENCE = 0.60
    GRADE      = "L"
    REFRESH_MINUTES = 24 * 60

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        async with self.session.get(_URL, timeout=aiohttp.ClientTimeout(total=60),
                                    headers={"User-Agent": "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"}) as r:
            r.raise_for_status()
            recs = (await r.json(content_type=None))["result"]["records"]
        stations = []
        for x in recs:
            lat, lon = x.get("נ.צ. רוחב"), x.get("נ.צ. אורך")
            try:
                lat, lon = float(lat), float(lon)
            except (TypeError, ValueError):
                continue
            if not (29.3 <= lat <= 33.5 and 34.1 <= lon <= 35.95):
                continue
            raw = (x.get("חברה") or "").strip()
            brand = _BRANDS.get(raw, raw)
            stations.append({
                "id": f"il_{x.get('מס_מינהל_הדלק') or x['_id']}", "country": "IL",
                "name": (x.get("שם_תחנה") or brand).strip(), "brand": brand,
                "address": (x.get("כתובת") or "").strip(), "city": (x.get("רשות_מקומית") or "").strip(),
                "lat": round(lat, 5), "lon": round(lon, 5),
                "source": self.SOURCE, "confidence": self.CONFIDENCE, "prices": [],
            })
        print(f"[IL] {len(stations)} stations (locations only)")
        return stations
