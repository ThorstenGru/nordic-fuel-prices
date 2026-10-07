"""
United Kingdom — open retailer fuel-price JSON feeds (CMA "Open Data" format) PRIMARY, ANWB fills gaps.

Why not the official Fuel Finder CSV?  (researched 2026-10-07)
  The statutory Fuel Finder scheme (DESNZ, Motor Fuel Price (Open Data) Regulations 2025) offers the
  latest CSV only via https://www.developer.fuel-finder.service.gov.uk/access-latest-fuelprices, which
  shows a pre-signed S3 link (valid ~12 h, one publish, updated twice daily). That page answers
  HTTP 403 (CloudFront) to every non-browser request, so there is no stable, scriptable URL.
  The API needs OAuth (not working at the moment). So the official data is NOT used here.

Retailer feeds (same schema: last_updated + stations[] with site_id, brand, address, postcode,
location{latitude,longitude}, prices{E10,E5,B7,SDV} in pence per litre). Feeds whose last_updated is
older than _MAX_AGE_DAYS are skipped (Rontec, Shell, Applegreen are stale / frozen; Morrisons only lists
Gibraltar; Tesco/BP/Co-op/Jet block bots). Timestamps are per feed ("last_updated", UK local time).

ANWB (src/scrapers/_anwb.py, ~8.6k UK stations, no timestamps) runs independently. Merging is done by the
shared engine (src/merge_engine.py): every retailer feed is its own SourceResult (priority 1, kind
"company"), ANWB is priority 9 ("aggregator", GBP). One feed failing is logged and listed in
merge_report["failed_sources"]; only all sources failing raises. Retailer prices win, ANWB fills the fuel
buckets a retailer record lacks, ANWB-only stations are added, disagreements are exposed as
price["alt"] / price["disagree"]. ANWB's "95" is really super-unleaded: relabelled E5@97 (98 stays 98).
Currency: ANWB delivers EUR; _anwb.py converts to GBP with the ECB rate (CURRENCY = "GBP"). ANWB prices
still in EUR (no rate) are dropped so GBP and EUR are never mixed.

Licence: retailer data published under the CMA/DESNZ open-data scheme; ANWB is unofficial/undocumented.
SDV (premium diesel) is not published: the site only has one DIESEL class (B7).
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from merge_engine import MergeConfig, SourceResult, merge_sources

from ._anwb import ANWBScraper
from .base import iso_utc, octane_of

_FEEDS = {
    "Asda":   "https://storelocator.asda.com/fuel_prices_data.json",
    "Esso":   "https://fuelprices.esso.co.uk/latestdata.json",
    "MFG":    "https://fuel.motorfuelgroup.com/fuel_prices_data.json",
    "Moto":   "https://moto-way.com/fuel-price/fuel_prices.json",
    "SGN":    "https://www.sgnretail.uk/files/data/SGN_daily_fuel_prices.json",
}
_MAX_AGE_DAYS = 7
_FUEL_MAP = {"E10": "E10", "E5": "E5", "B7": "DIESEL"}   # SDV (premium diesel) intentionally dropped
_FUEL_OCTANE = {"E10": 95, "E5": 97}   # UK retailer E5 = super unleaded (97+ RON); E10 = standard 95
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36", "Accept": "application/json"}
_LAT = (49.8, 60.9)
_LON = (-8.7, 1.9)


class UnitedKingdomScraper(ANWBScraper):
    COUNTRY    = "GB"
    ISO3       = "GBR"
    CURRENCY   = "GBP"
    BBOX       = (49.8, -8.7, 60.9, 1.9)
    TILE_STEP  = 3.0
    SOURCE     = "UK retailer open price feeds (Asda, Esso, MFG, Moto, SGN) + anwb.nl for remaining stations"
    CONFIDENCE = 0.85
    GRADE      = "B"
    REFRESH_MINUTES = 30

    async def _get_feed(self, name: str, url: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.session.get(url, headers=_HEADERS, timeout=40) as r:
                if r.status != 200:
                    print(f"[GB] {name}: HTTP {r.status}")
                    return None
                raw = await r.read()
            return json.loads(raw.decode("utf-8-sig"))
        except Exception as e:
            print(f"[GB] {name}: {type(e).__name__}: {e}")
            return None

    def _retailer_result(self, name: str, data: Optional[Dict[str, Any]], cutoff: datetime) -> SourceResult:
        sid = name.lower()

        def res(stations, ok=True, err=None):
            return SourceResult(source_id=sid, name=f"{name} open price feed", stations=stations,
                                priority=1, kind="company", currency=self.CURRENCY, ok=ok, error=err)

        if not isinstance(data, dict):
            return res([], False, "fetch failed")
        ts = iso_utc(data.get("last_updated"), "Europe/London")
        if not ts or datetime.fromisoformat(ts) < cutoff:
            print(f"[GB] {name}: stale/undated feed ({data.get('last_updated')}) skipped")
            return res([], False, f"stale/undated feed ({data.get('last_updated')})")
        by_id: Dict[str, Dict[str, Any]] = {}
        for s in data.get("stations") or []:
            try:
                loc = s.get("location") or {}
                lat, lon = float(loc["latitude"]), float(loc["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (_LAT[0] <= lat <= _LAT[1] and _LON[0] <= lon <= _LON[1]):
                continue
            prices = []
            for k, ft in _FUEL_MAP.items():
                try:
                    pence = float((s.get("prices") or {}).get(k))
                except (TypeError, ValueError):
                    continue
                if pence <= 0:
                    continue
                prices.append(self.price_entry(ft, round(pence / 100.0, 3), "L", ts,
                                               octane=_FUEL_OCTANE.get(ft)))
            site = str(s.get("site_id") or f"{lat:.5f}_{lon:.5f}")
            by_id[f"gb_{sid}_{site}"] = {
                "id": f"gb_{sid}_{site}",
                "country": self.COUNTRY,
                "name": s.get("brand") or "",
                "brand": s.get("brand") or "",
                "address": (s.get("address") or "").strip(),
                "city": "",
                "postcode": s.get("postcode") or "",
                "lat": lat,
                "lon": lon,
                "source": f"retailer feed [{name}]",
                "confidence": 0.90,
                "prices": prices,
            }
        print(f"[GB] {name}: {len(by_id)} stations, last_updated {data.get('last_updated')}")
        return res(list(by_id.values()))

    async def _fetch_retailers(self) -> List[SourceResult]:
        feeds = await asyncio.gather(*[self._get_feed(n, u) for n, u in _FEEDS.items()])
        cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)
        return [self._retailer_result(n, d, cutoff) for n, d in zip(_FEEDS, feeds)]

    async def _fetch_anwb(self) -> List[Dict[str, Any]]:
        out = []
        for s in await super().fetch_stations():
            ps = []
            for p in s.get("prices", []):
                if p.get("currency") != self.CURRENCY:      # unconverted EUR: never mix currencies
                    continue
                p["updated_at"] = None
                # Benchmark 2026-10-07: ANWB's UK "Euro 95 (E10)" price is really the E5 super-unleaded
                # price (85% within 1 p of the retailer E5, 8% of E10; ~17 p above true E10). Label it E5.
                # New ANWB mapping: that price arrives as fuel_type "95" (old: "E10"/"E5"); the 98 grade as
                # "98" (old: "E5"). Both are UK super-unleaded: E5, octane 97 (98 when ANWB says 98).
                if p["fuel_type"] in ("E10", "E5", "95", "98"):
                    o = octane_of(p)
                    p["octane"] = 98 if (p["fuel_type"] == "98" or (o or 0) >= 98) else 97
                    p["fuel_type"] = "E5"
                ps.append(p)
            best: Dict[str, Dict[str, Any]] = {}
            for p in ps:                       # E5 can appear twice (super + 98): keep the lower
                if p["fuel_type"] not in best or p["price"] < best[p["fuel_type"]]["price"]:
                    best[p["fuel_type"]] = p
            s["prices"] = list(best.values())
            s["source"] = "anwb.nl (ANWB POI API)"
            s["confidence"] = 0.70
            s.pop("sources", None)
            out.append(s)
        return out

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        retail, anwb = await asyncio.gather(self._fetch_retailers(), self._fetch_anwb(),
                                            return_exceptions=True)
        results: List[SourceResult] = []
        if isinstance(retail, BaseException):
            print(f"[GB] retailer feeds FAILED: {type(retail).__name__}: {retail}")
            results.append(SourceResult("retailers", "UK retailer feeds", [], 1, "company", self.CURRENCY,
                                        ok=False, error=f"{type(retail).__name__}: {retail}"))
        else:
            results.extend(retail)
        if isinstance(anwb, BaseException):
            print(f"[GB] ANWB FAILED: {type(anwb).__name__}: {anwb}")
            results.append(SourceResult("anwb", "ANWB POI API", [], 9, "aggregator", self.CURRENCY,
                                        ok=False, error=f"{type(anwb).__name__}: {anwb}"))
        else:
            results.append(SourceResult("anwb", "ANWB POI API (anwb.nl)", anwb, 9, "aggregator",
                                        self.CURRENCY))
        if not any(r.ok and r.stations for r in results):
            raise RuntimeError("GB: retailer feeds and ANWB all returned no data")
        merged, self.merge_report = merge_sources(results, MergeConfig(country="GB"))
        rep = self.merge_report
        print(f"[GB] merged {rep['final_station_count']} stations ({rep['priced_station_count']} priced) "
              f"pairs={rep['matched_pairs']} conflicts={rep['conflicts']} alt={rep['alt_values']} "
              f"outliers={rep['outliers_dropped']} failed={[f['source_id'] for f in rep['failed_sources']]}")
        return merged
