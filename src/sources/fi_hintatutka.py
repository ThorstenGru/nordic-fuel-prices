"""
Finland per-station petrol 95E10 + diesel from Hintatutka (hintatutka.net).  GRADE C - community.

Endpoint : GET http://www.hintatutka.net/about   (any page of the site embeds the same JSON blob:
           ... "stations":[{id,name,brand,address,lat,lng,price_95e10_thousandths,
           price_diesel_thousandths,latest_price_updated_at,...}] ...)
           ONE request returns every station (224 on 2026-10-07), with GPS and a per-station
           timestamp (the latest report for that station; naive time, assumed Europe/Helsinki).
Licence  : PERMISSION GRANTED by the site owner of hintatutka.net (confirmed by the EuroFuelPrices owner,
           2026-11-07). Condition: keep the attribution "Hintatutka.net" wherever these prices are shown.
           Prices are community-reported. (No ToS page exists; robots.txt only "Disallow: /admin".)
Rate     : 1 request per run (<= 1 req/s trivially). Honest User-Agent.
Refresh  : every 6 h is plenty (reports arrive a few per day; many stations are weeks old).
Fuels    : 95E10 -> E10/octane 95, Diesel -> DIESEL. (98E5 / E85 exist only on per-station pages.)
Caveat   : prices older than MAX_AGE_DAYS are dropped by default (set to None to keep all).
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp

URL = "https://www.hintatutka.net/about"
UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
SOURCE = "hintatutka.net (community)"
CONFIDENCE = 0.6
MAX_AGE_DAYS: Optional[int] = 45


def _ts(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        try:
            from zoneinfo import ZoneInfo
            dt = dt.replace(tzinfo=ZoneInfo("Europe/Helsinki"))
        except Exception:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=3)))
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def parse(html: str, max_age_days: Optional[int] = MAX_AGE_DAYS) -> List[Dict[str, Any]]:
    i = html.find('"stations":[')
    if i < 0:
        return []
    raw, _ = json.JSONDecoder().raw_decode(html[i + len('"stations":'):])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)) if max_age_days else None
    out = []
    for s in raw:
        try:
            lat, lon = float(s["lat"]), float(s["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (59.5 <= lat <= 70.2 and 19 <= lon <= 31.7):
            continue
        upd = _ts(s.get("latest_price_updated_at"))
        if cutoff and upd and datetime.fromisoformat(upd) < cutoff:
            continue
        prices = []
        for key, ft, oct_ in (("price_95e10_thousandths", "E10", 95), ("price_diesel_thousandths", "DIESEL", None)):
            v = s.get(key)
            try:
                v = int(v) if v else None
            except (TypeError, ValueError):
                continue
            if v and 1000 <= v <= 4000:
                p = {"fuel_type": ft, "price": v / 1000, "currency": "EUR", "unit": "L",
                     "updated_at": upd, "source": SOURCE}
                if oct_:
                    p["octane"] = oct_
                prices.append(p)
        if not prices:
            continue
        name = str(s.get("name") or "").strip()
        if not name or s.get("id") is None:
            continue
        brand = (s.get("brand") or name.split()[0]).strip()
        out.append({
            "id": f"fi_ht_{s['id']}", "country": "FI", "name": name, "brand": brand,
            "address": s.get("address") or "", "city": s.get("city_name") or "",
            "lat": lat, "lon": lon, "source": SOURCE, "confidence": CONFIDENCE, "prices": prices,
        })
    return out


async def fetch(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    async with session.get(URL, headers={"User-Agent": UA}, timeout=aiohttp.ClientTimeout(total=30)) as r:
        if r.status != 200:
            print(f"[FI/hintatutka] HTTP {r.status}")
            return []
        return parse(await r.text())
