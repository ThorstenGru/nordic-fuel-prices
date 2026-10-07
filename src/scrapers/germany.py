"""
Germany.

Baseline (no key needed): ANWB POI API, adaptively tiled — ~14.9k stations with prices (GRADE C,
no timestamps). Whole-country boxes are rejected by ANWB with ``limit_exceeded`` which is why
Germany used to publish 0 stations.

Upgrade (needs TANKERKOENIG_API_KEY): Tankerkönig serves the statutory MTS-K feed
(Bundeskartellamt: every station must report a price change within 5 minutes). Its stations
override the matching ANWB station (<=150 m) and any extra stations are added. The key is a
free registration at https://onboarding.tankerkoenig.de (owner action). Data licence: CC BY 4.0
(attribution "Tankerkönig / MTS-K, Bundeskartellamt").
"""

import asyncio
import math
import os
from collections import defaultdict
from typing import List, Dict, Any, Tuple

import aiohttp

from .base import BaseScraper
from ._anwb import ANWBScraper


class _DEAnwb(ANWBScraper):
    COUNTRY    = "DE"
    ISO3       = "DEU"
    BBOX       = (47.27, 5.87, 55.06, 15.04)
    TILE_STEP  = 2.0
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85


API_KEY  = os.environ.get("TANKERKOENIG_API_KEY", "")
LIST_URL = "https://creativecommons.tankerkoenig.de/json/list.php"

# 25 km search circles; metro areas first (where most stations are). Coverage of the whole
# country comes from the ANWB baseline, Tankerkönig upgrades what it can see.
GRID = [
    (53.5753, 10.0153), (53.0793, 8.8017), (52.3759, 9.7320), (53.1435, 11.0533),
    (54.3233, 10.1228), (54.0865, 12.1444), (53.8667, 10.6867), (51.4556, 7.0116),
    (51.2217, 6.7762), (50.9333, 6.9500), (50.7753, 6.0839), (50.3569, 7.5890),
    (50.1109, 8.6821), (49.9929, 8.2473), (49.4521, 11.0767), (48.9667, 12.0667),
    (48.5658, 13.4317), (48.3717, 10.8983), (48.1351, 11.5820), (47.8010, 13.0452),
    (47.9990, 7.8421), (47.5595, 9.6753), (48.7758, 9.1829), (49.0069, 8.4037),
    (51.9607, 7.6261), (51.5167, 9.9167), (51.3397, 12.3731), (51.4818, 11.9699),
    (51.0504, 13.7373), (51.7535, 14.6329), (52.5200, 13.4050), (52.6367, 13.2353),
    (52.1205, 11.6276), (50.9272, 11.5861), (53.4285, 14.5528), (54.5086, 13.6000),
    (50.0755, 14.4378), (51.3600, 10.0000), (49.7000, 9.9500), (50.5700, 9.6800),
]

FUEL_MAP = {"e5": ("E5", "L"), "e10": ("E10", "L"), "diesel": ("DIESEL", "L")}


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class GermanyScraper(BaseScraper):
    COUNTRY    = "DE"
    CURRENCY   = "EUR"
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
    GRADE      = "C"
    REFRESH_MINUTES = 30

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        stations = await _DEAnwb(self.session).fetch_stations()

        if API_KEY:
            tk = await self._fetch_tankerkoenig()
            if tk:
                stations = self._merge(stations, tk)
                self.SOURCE = "tankerkoenig.de (MTS-K) + anwb.nl"
                self.CONFIDENCE = 0.95
                if len(tk) >= 1000:
                    self.GRADE = "A"
        else:
            print("[DE] TANKERKOENIG_API_KEY not set — ANWB baseline only (no statutory MTS-K upgrade)")
        return stations

    # ── Tankerkönig (MTS-K) ───────────────────────────────────────────────────

    async def _fetch_tankerkoenig(self) -> List[Dict[str, Any]]:
        sem = asyncio.Semaphore(2)
        results = await asyncio.gather(*(self._fetch_area(lat, lon, sem) for lat, lon in GRID),
                                       return_exceptions=True)
        seen: Dict[str, Dict] = {}
        for r in results:
            if isinstance(r, Exception) or not r:
                continue
            for s in r:
                seen.setdefault(s["id"], s)
        print(f"[DE] {len(seen)} stations from tankerkoenig.de (statutory MTS-K)")
        return list(seen.values())

    async def _fetch_area(self, lat: float, lon: float, sem: asyncio.Semaphore) -> List[Dict]:
        params = {"lat": lat, "lng": lon, "rad": 25, "sort": "dist", "type": "all", "apikey": API_KEY}
        async with sem:
            try:
                async with self.session.get(LIST_URL, params=params,
                                            timeout=aiohttp.ClientTimeout(total=25)) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)
            except Exception as e:
                print(f"[DE] tankerkoenig ({lat:.2f},{lon:.2f}): {e}")
                return []
            await asyncio.sleep(1.0)

        if not data.get("ok"):
            print(f"[DE] tankerkoenig not ok: {data.get('message')}")
            return []

        out = []
        for s in data.get("stations", []):
            prices = []
            for field, (ft, unit) in FUEL_MAP.items():
                val = s.get(field)
                if isinstance(val, (int, float)) and val > 0:
                    prices.append(self.price_entry(ft, float(val), unit,
                                                   octane=95 if ft in ("E5", "E10") else None))
            brand, name = s.get("brand", ""), s.get("name", "")
            out.append({
                "id": f"de_tk_{s.get('id', '')}",
                "country": "DE",
                "name": f"{brand} {name}".strip() if brand else name,
                "brand": brand,
                "address": f"{s.get('street', '')} {s.get('houseNumber', '')}".strip(),
                "city": s.get("place", ""),
                "lat": s.get("lat"),
                "lon": s.get("lng"),
                "source": "tankerkoenig.de (MTS-K)",
                "confidence": 0.99,
                "grade": "A",
                "prices": prices,
            })
        return out

    @staticmethod
    def _merge(base: List[Dict], tk: List[Dict]) -> List[Dict]:
        """Statutory MTS-K stations override the matching ANWB station (<=150 m); extras are added."""
        cell = 0.002
        index: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
        for s in base:
            index[(round(s["lat"] / cell), round(s["lon"] / cell))].append(s)
        replaced = added = 0
        for t in tk:
            if t.get("lat") is None or t.get("lon") is None or not t["prices"]:
                continue
            cx, cy = round(t["lat"] / cell), round(t["lon"] / cell)
            best, best_d = None, 1e9
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for s in index.get((cx + dx, cy + dy), []):
                        d = _dist_m(t["lat"], t["lon"], s["lat"], s["lon"])
                        if d < best_d:
                            best, best_d = s, d
            if best is not None and best_d <= 150:
                best.update(prices=t["prices"], source=t["source"], confidence=t["confidence"], grade="A",
                            name=t["name"] or best["name"], brand=t["brand"] or best["brand"],
                            address=t["address"] or best["address"], city=t["city"] or best["city"])
                replaced += 1
            else:
                base.append(t)
                added += 1
        print(f"[DE] MTS-K merge: {replaced} ANWB stations upgraded, {added} added")
        return base
