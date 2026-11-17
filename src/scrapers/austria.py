import aiohttp
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from .base import BaseScraper, dist_m
from ._anwb import ANWBScraper

# Austrian mandatory fuel price reporting via e-Control API
# https://api.e-control.at/sprit/1.0/
# Free, no API key required, real-time per-station GPS prices
# Strategy: fetch all PB (Bezirk/district) codes from /regions, then query
# each district × each fuel type for comprehensive geographic coverage.

REGIONS_URL = "https://api.e-control.at/sprit/1.0/regions"
BY_REGION_URL = "https://api.e-control.at/sprit/1.0/search/gas-stations/by-region"
BY_ADDRESS_URL = "https://api.e-control.at/sprit/1.0/search/gas-stations/by-address"
# e-control answers at most 10 stations per request, and by-region returns the 10 CHEAPEST of a district: a plain district crawl
# covers about a quarter of the ~2,900 Austrian stations and is biased to cheap ones. So the by-region result is topped up by
# asking by-address (the 10 NEAREST) at every place ANWB lists a station that e-control has not shown us yet. ANWB is used only
# as a list of places; every price still comes from e-control.
SEED_MAX = 1500                 # seed places per run (x 2 fuels = at most 3,000 polite requests, 6 at a time)
SEED_MATCH_M = 150
SEED_BUDGET_S = 420


class _ATAnwb(ANWBScraper):
    COUNTRY = "AT"
    ISO3 = "AUT"
    BBOX = (46.37, 9.53, 49.02, 17.16)
    SOURCE = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85

# e-control only accepts fuelType DIE | SUP | GAS (LPG returns HTTP 400!). GAS is an umbrella for
# autogas AND CNG: the price's ``label`` tells which ("CNG" -> per kg, anything else -> LPG per litre).
FUEL_MAP = {
    "DIE": ("DIESEL", "L"),
    "SUP": ("E5",     "L"),
    "GAS": ("LPG",    "L"),
}

# Fallback BL (Bundesland) codes if district fetch fails
BL_CODES = list(range(1, 10))


class AustriaScraper(BaseScraper):
    COUNTRY = "AT"
    CURRENCY = "EUR"
    SOURCE = "e-control.at"
    CONFIDENCE = 1.0
    GRADE = "A"   # statutory: price changes reported to E-Control within 30 minutes
    REFRESH_MINUTES = 60   # 2026-11-17: the top-up asks e-control about a thousand times per run; once an hour is polite enough for a public API without written terms

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        pb_codes = await self._fetch_pb_codes()

        sem = asyncio.Semaphore(12)
        if pb_codes:
            tasks = [
                self._fetch("PB", code, fuel, sem)
                for code in pb_codes
                for fuel in FUEL_MAP
            ]
        else:
            tasks = [
                self._fetch("BL", code, fuel, sem)
                for code in BL_CODES
                for fuel in FUEL_MAP
            ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        failed = sum(1 for r in results if isinstance(r, Exception))
        if failed > max(2, 0.02 * len(results)):   # a few lost districts are tolerated; more means the file would silently miss regions or a fuel
            raise RuntimeError(f"{failed} of {len(results)} e-control requests failed; not publishing a partial country")

        merged: Dict[str, Dict] = {}
        for result in results:
            if isinstance(result, Exception) or not result:
                continue
            for s in result:
                sid = s["id"]
                if sid not in merged:
                    merged[sid] = s
                else:
                    existing = {(p["fuel_type"], p.get("octane")) for p in merged[sid]["prices"]}
                    for p in s["prices"]:
                        if (p["fuel_type"], p.get("octane")) not in existing:
                            merged[sid]["prices"].append(p)

        by_region = len(merged)
        anwb = await self._anwb_places()
        await self._top_up(merged, anwb, sem)
        stations = list(merged.values())
        print(f"[AT] {len(stations)} stations from e-control.at ({len(pb_codes)} districts, {by_region} by district, {len(anwb)} ANWB places)")
        self._record_accuracy(stations, anwb)
        return stations

    async def _anwb_places(self) -> List[Dict[str, Any]]:
        try:
            return await _ATAnwb(self.session).fetch_stations()
        except Exception as e:  # noqa: BLE001 - ANWB is only a helper here; the district crawl stands on its own
            print(f"[AT] ANWB places not available ({type(e).__name__}: {e}); district crawl only")
            return []

    async def _top_up(self, merged: Dict[str, Dict], anwb: List[Dict], sem: asyncio.Semaphore) -> None:
        """Ask e-control by-address at ANWB places that no e-control station sits at yet; each answer is the 10 nearest stations."""
        t0, asked = time.monotonic(), 0
        pts = [(s["lat"], s["lon"]) for s in anwb if s.get("lat") is not None and s.get("lon") is not None]
        seen_cells: Dict[tuple, List[tuple]] = {}

        def cell(lat, lon):
            return (round(lat / 0.002), round(lon / 0.002))

        def index(st):
            if st.get("lat") is not None and st.get("lon") is not None:
                seen_cells.setdefault(cell(st["lat"], st["lon"]), []).append((st["lat"], st["lon"]))

        discs: List[tuple] = []   # (lat, lon, radius_m) of every answered question: the 10 nearest stations came back, so a place inside the disc has been seen if e-control lists it at all

        def covered(lat, lon):
            cx, cy = cell(lat, lon)
            if any(dist_m(lat, lon, a, b) <= SEED_MATCH_M for dx in (-1, 0, 1) for dy in (-1, 0, 1) for a, b in seen_cells.get((cx + dx, cy + dy), ())):
                return True
            return any(abs(lat - d[0]) < d[2] / 111200 and abs(lon - d[1]) < d[2] / 70000 and dist_m(lat, lon, d[0], d[1]) <= d[2] for d in discs)

        for st in merged.values():
            index(st)
        todo = [p for p in pts if not covered(*p)]
        print(f"[AT] {len(todo)} ANWB places not yet seen at e-control")
        i = 0
        while i < len(todo) and asked < SEED_MAX and time.monotonic() - t0 < SEED_BUDGET_S:
            batch = []
            while i < len(todo) and len(batch) < 6 and asked + len(batch) < SEED_MAX:
                p = todo[i]
                i += 1
                if not covered(*p):          # an earlier answer may already have shown it
                    batch.append(p)
            if not batch:
                continue
            asked += len(batch)
            res = await asyncio.gather(*(self._near(lat, lon, fuel, sem) for lat, lon in batch for fuel in FUEL_MAP if fuel != "GAS"),
                                       return_exceptions=True)
            for k, (lat, lon) in enumerate(batch):            # results are ordered place by place, one answer per fuel
                ans = [x for r in res[k * 2:k * 2 + 2] if not isinstance(r, Exception) and r for x in r if x.get("lat") is not None]
                if ans:
                    discs.append((lat, lon, 0.9 * max(dist_m(lat, lon, x["lat"], x["lon"]) for x in ans)))
            for r in res:
                if isinstance(r, Exception) or not r:
                    continue
                for st in r:
                    if st["id"] not in merged:
                        merged[st["id"]] = st
                        index(st)
                    else:
                        have = {(p["fuel_type"], p.get("octane")) for p in merged[st["id"]]["prices"]}
                        merged[st["id"]]["prices"].extend(p for p in st["prices"] if (p["fuel_type"], p.get("octane")) not in have)
        print(f"[AT] top-up: {asked} places asked, {len(merged)} stations now")

    def _record_accuracy(self, stations: List[Dict], anwb: List[Dict]) -> None:
        """ANWB against e-control, station by station: how far off is the aggregator where the official price is known? (the Swiss
        ANWB data has no official feed to check against, so this is the nearest thing to an estimate of its accuracy there)"""
        path = Path(os.environ.get("AT_ACCURACY_PATH") or Path(__file__).resolve().parents[2] / "data" / "at_accuracy.json")
        try:
            from .germany import accuracy_update, accuracy_summary
            pairs = []
            idx: Dict[tuple, List[Dict]] = {}
            for s in stations:
                idx.setdefault((round(s["lat"] / 0.002), round(s["lon"] / 0.002)), []).append(s)
            import zlib
            for a in anwb:
                if a.get("lat") is None:
                    continue
                cx, cy = round(a["lat"] / 0.002), round(a["lon"] / 0.002)
                best, bd = None, 1e9
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for s in idx.get((cx + dx, cy + dy), ()):
                            d = dist_m(a["lat"], a["lon"], s["lat"], s["lon"])
                            if d < bd:
                                best, bd = s, d
                if best is None or bd > SEED_MATCH_M:
                    continue
                ap = {("D" if p["fuel_type"] == "DIESEL" else "P"): p["price"] for p in a["prices"] if p["fuel_type"] in ("95", "E5", "E10", "DIESEL")}
                op = {("D" if p["fuel_type"] == "DIESEL" else "P"): p["price"] for p in best["prices"] if p["fuel_type"] in ("95", "E5", "E10", "DIESEL")}
                for k, fuel in (("P", "petrol"), ("D", "diesel")):
                    if k in ap and k in op:
                        pairs.append((fuel, "other", (a.get("brand") or "?").strip().upper()[:40], round((ap[k] - op[k]) * 100, 1),
                                      (zlib.crc32(str(best["id"]).encode()) << 1) | (fuel == "diesel")))
            if not pairs:
                return
            try:
                store = json.loads(path.read_text(encoding="utf-8"))
                if store.get("v") != 2:
                    store = {}
            except (OSError, ValueError):
                store = {}
            day = datetime.now(timezone.utc).date().isoformat()
            store["v"] = 2
            accuracy_update(store, pairs, day)
            sm = accuracy_summary(store)
            if sm.get("n"):   # the German wording of the line does not fit here
                sm["line"] = (f"ANWB matched the official e-control price to within 1 cent for {sm['within_1ct_pct']}% of {sm['n']} checks on Austrian stations "
                              f"(last {sm['days']} days); median difference {sm['bias_median_ct']:+g} ct, 90% of checks within {sm['abs_p90_ct']} ct.")
            store["summary"] = sm
            store["updated"] = datetime.now(timezone.utc).isoformat()
            store["note"] = "ANWB minus e-control (statutory), Austria. ANWB is also the only source for Switzerland, where no official feed exists."
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"[AT] accuracy meter (ANWB vs e-control): {store['summary'].get('line', '')}")
        except Exception as e:  # noqa: BLE001 - the meter must never break the price feed
            print(f"[AT] accuracy meter failed: {type(e).__name__}: {e}")

    async def _fetch_pb_codes(self) -> List[int]:
        try:
            async with self.session.get(
                REGIONS_URL,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[AT] regions HTTP {resp.status} — falling back to BL")
                    return []
                regions = await resp.json(content_type=None)
        except Exception as e:
            print(f"[AT] regions fetch: {type(e).__name__}: {e} — falling back to BL")
            return []

        codes = []
        for bl in regions:
            for pb in bl.get("subRegions", []):
                code = pb.get("code")
                if code is not None:
                    try:
                        codes.append(int(code))
                    except (TypeError, ValueError):
                        pass
        return codes

    async def _fetch(self, region_type: str, code: int, fuel: str, sem: asyncio.Semaphore) -> List[Dict]:
        return await self._get(BY_REGION_URL, {"type": region_type, "code": code, "fuelType": fuel, "includeClosed": "false"}, fuel, sem)

    async def _near(self, lat: float, lon: float, fuel: str, sem: asyncio.Semaphore) -> List[Dict]:
        return await self._get(BY_ADDRESS_URL, {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "fuelType": fuel, "includeClosed": "false"}, fuel, sem)

    async def _get(self, url: str, params: Dict, fuel: str, sem: asyncio.Semaphore) -> List[Dict]:
        region_type, code = params.get("type", "ADDR"), params.get("code", params.get("latitude"))
        async with sem:
            try:
                async with self.session.get(
                    url, params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={"Accept": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"HTTP {resp.status}")
                    raw = await resp.json(content_type=None)
            except Exception as e:
                print(f"[AT] {region_type}={code} fuel={fuel}: {type(e).__name__}: {e}")
                raise

        if not isinstance(raw, list):
            return []

        ft, unit = FUEL_MAP[fuel]
        result = []
        for s in raw:
            price_val = None
            row_ft, row_unit = ft, unit
            for p in s.get("prices", []):
                if p.get("fuelType") == fuel and p.get("amount"):
                    try:
                        price_val = float(p["amount"])
                    except (TypeError, ValueError):
                        pass
                    if fuel == "GAS" and "CNG" in str(p.get("label", "")).upper():
                        row_ft, row_unit = "CNG", "kg"
                    break
            if not price_val or price_val <= 0:
                continue

            addr = s.get("address") or {}
            loc  = s.get("location") or {}
            result.append({
                "id": f"at_{s.get('id', '')}",
                "country": "AT",
                "name": s.get("name", ""),
                "brand": (s.get("name", "") or "").split(",")[0].strip(),
                # e-control puts the postal address in "location" ({address, postalCode, city, latitude, longitude}); the old "address" object is not there (2026-11-16: every Austrian station had no city)
                "address": (loc.get("address") or f"{addr.get('street', '')} {addr.get('streetnumber', '')}").strip(),
                "city": loc.get("city") or addr.get("city", ""),
                "lat": loc.get("latitude"),
                "lon": loc.get("longitude"),
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "prices": [self.price_entry(row_ft, price_val, row_unit, octane=95 if row_ft == "E5" else None)],
            })
        return result
