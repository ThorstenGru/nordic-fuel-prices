"""Israel - official Ministry of Energy station register (data.gov.il), locations only.

Pump prices in Israel are ONE regulated national maximum for 95 petrol (diesel is regulated only at
the refinery gate). gov.il is Cloudflare-blocked, so the figure is kept in seed/il_cap.json (from
press reports citing the Ministry; 8.27 -> 7.77 on 5 Oct 2026 corroborated by the data.gov.il
excise series). It is published ONLY while the data.gov.il excise + refinery-gate inputs it was
calibrated on are unchanged, and for at most 45 days - any monthly change switches it off.
Register: 1,255 stations with WGS84 coordinates, licence "Other (Open)".
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from .base import BaseScraper

_URL = ("https://data.gov.il/api/3/action/datastore_search"
        "?resource_id=5537a0ef-3eeb-449c-90c8-51e27564f0cb&limit=3000")
_SEED = Path(__file__).resolve().parent.parent / "seed" / "il_cap.json"
_CKAN = "https://data.gov.il/api/3/action/datastore_search?resource_id={rid}&limit=80&sort=_id%20desc"
_EXCISE_RID = "bdce45e7-9fe9-473e-bd51-cef1d787a951"
_ORL_RID = "aaa40832-ac82-4c86-bac6-0d05c83f576f"
_EXCISE_PRODUCT = "בלו בנזין (סעיף 1 לתוספת לצו)"
_REFINERY_PRODUCT = "בנזין 95 אוקטן נטול עופרת בהזרמה"
CAP_MAX_AGE_DAYS = 45
_BRANDS = {"דור-אלון": "Dor Alon", "דור אלון": "Dor Alon", "דלק": "Delek", "פז": "Paz",
           "סונול": "Sonol", "טן": "Ten", "תפוז": "Tapuz", "מיקה": "Mika", "סדש": "Sadash",
           "יעד": "Yaad"}


def _latest(records: List[dict], product: str) -> Optional[float]:
    rows = [r for r in records if (r.get("מוצר") or "").strip() == product]
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("תאריך") or "")
    try:
        return float(rows[-1]["מחיר"])
    except (KeyError, TypeError, ValueError):
        return None


def cap_is_valid(cap: dict, excise: Optional[float], refinery: Optional[float], today=None) -> Optional[str]:
    """None if the recorded cap may be published, else the reason it must not be."""
    today = today or datetime.now(timezone.utc).date()
    g = cap["guard"]
    if excise is None or refinery is None:
        return "data.gov.il guard inputs unavailable"
    if abs(excise - g["excise_petrol_kl"]) > 0.005:
        return f"petrol excise changed ({excise} != {g['excise_petrol_kl']})"
    if abs(refinery - g["refinery_95_pipeline_kl"]) > 0.005:
        return f"refinery-gate price changed ({refinery} != {g['refinery_95_pipeline_kl']})"
    age = (today - datetime.fromisoformat(cap["effective"]).date()).days
    if age > CAP_MAX_AGE_DAYS or age < -1:
        return f"cap is {age} days old"
    return None


class IsraelScraper(BaseScraper):
    COUNTRY    = "IL"
    CURRENCY   = "ILS"
    SOURCE     = "data.gov.il — Ministry of Energy station register + regulated 95 maximum"
    CONFIDENCE = 0.60
    GRADE      = "B"
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
        await self._apply_cap(stations)
        priced = sum(1 for x in stations if x["prices"])
        print(f"[IL] {len(stations)} stations, {priced} with the regulated 95 maximum")
        return stations

    async def _apply_cap(self, stations: List[Dict[str, Any]]) -> None:
        try:
            cap = json.loads(_SEED.read_text(encoding="utf-8"))
            hdr = {"User-Agent": "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"}
            vals = []
            for rid, product in ((_EXCISE_RID, _EXCISE_PRODUCT), (_ORL_RID, _REFINERY_PRODUCT)):
                async with self.session.get(_CKAN.format(rid=rid), headers=hdr,
                                            timeout=aiohttp.ClientTimeout(total=60)) as r:
                    r.raise_for_status()
                    vals.append(_latest((await r.json(content_type=None))["result"]["records"], product))
            why = cap_is_valid(cap, vals[0], vals[1])
        except Exception as e:
            why = f"{type(e).__name__}: {e}"
            cap = None
        if why:
            print(f"[IL] regulated cap NOT published: {why}")
            return
        for st in stations:
            st["prices"] = [{"fuel_type": "95", "price": cap["self_service_95"], "currency": "ILS", "unit": "L",
                             "updated_at": f"{cap['effective']}T00:00:00+00:00", "source": "regulator_cap",
                             "basis": "regulated_max", "octane": 95,
                             "note": f"self-service maximum; full service {cap['full_service_95']}"}]
