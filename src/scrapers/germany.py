"""
Germany.

Baseline (no key needed): ANWB POI API, adaptively tiled - ~14.9k stations with prices (GRADE C,
no timestamps). Whole-country boxes are rejected by ANWB with ``limit_exceeded`` which is why
Germany used to publish 0 stations.

Optional upgrade from Tankerkoenig (MTS-K, Bundeskartellamt), controlled by TANKERKOENIG_MODE.
See docs/TANKERKOENIG_SETUP.md. Facts from Tankerkoenig's reply of 2026-11-06:
  * free API: 25 km radius, exactly ONE request per minute per key (Bundeskartellamt rule), no bulk
    crawl of all stations. Over the limit: HTTP 503, then a one-hour IP block.
  * commercial API (contract): no rate/radius limit. Its request format is not yet known.

  off        (default, even with a key present) ANWB only.
  test       free key, strictly compliant: sequential, >= 62 s between requests, at most 5 circles
             per run (rotating through GRID by time slot), abort on the first 503/429, hard time budget.
             Partial coverage by design: only matched ANWB stations are upgraded, country grade stays C.
  commercial full-Germany cover by radius circles, bounded concurrency and a per-run request budget.

Data licence: CC BY 4.0 (attribution "Tankerkoenig / MTS-K, Bundeskartellamt").
"""

import asyncio
import math
import os
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from merge_engine import MergeConfig, bucket_of
from .base import BaseScraper
from ._anwb import ANWBScraper


class _DEAnwb(ANWBScraper):
    COUNTRY    = "DE"
    ISO3       = "DEU"
    BBOX       = (47.27, 5.87, 55.06, 15.04)
    TILE_STEP  = 2.0
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85


TK_SOURCE = "tankerkoenig.de (MTS-K)"
DEFAULT_BASE_URL = "https://creativecommons.tankerkoenig.de/json"
MODES = ("off", "test", "commercial")
MIN_GAP_TEST_S = 62.0         # the free API allows 1 request/minute; 2 s safety margin
TEST_MAX_CIRCLES = 5
REQ_TIMEOUT_S = 25
ABORT_STATUS = (429, 503)     # never retry within the run
FATAL_STATUS = (401, 403)     # bad/blocked key: no point continuing either

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

_APIKEY_RE = re.compile(r"apikey=[^&\s'\"]+")
FUEL_MAP = {"e5": ("E5", "L"), "e10": ("E10", "L"), "diesel": ("DIESEL", "L")}


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cover_circles(stations: List[Dict], r_km: float) -> List[Tuple[float, float]]:
    """Hex lattice of radius-``r_km`` circles that covers Germany. The footprint is taken from the
    ANWB stations (circles with no station within r are dropped); densest circles first so a request
    budget cuts the sparsest areas. Empty when there are no stations (caller falls back to GRID)."""
    cell = 0.25
    buckets: Dict[Tuple[int, int], List[Tuple[float, float]]] = defaultdict(list)
    for s in stations:
        try:
            buckets[(math.floor(s["lat"] / cell), math.floor(s["lon"] / cell))].append((s["lat"], s["lon"]))
        except (KeyError, TypeError):
            continue
    if not buckets:
        return []
    reach = int(r_km / (111.2 * cell * 0.55)) + 1
    lat_step = 1.5 * r_km / 111.2
    out: List[Tuple[int, float, float]] = []
    lat, row = 47.27, 0
    while lat <= 55.06 + lat_step:
        lon_step = r_km * math.sqrt(3) / (111.2 * math.cos(math.radians(lat)))
        lon = 5.87 + (lon_step / 2 if row % 2 else 0.0)
        while lon <= 15.04 + lon_step:
            cx, cy = math.floor(lat / cell), math.floor(lon / cell)
            n = sum(1 for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)
                    for (a, b) in buckets.get((cx + dx, cy + dy), ())
                    if _dist_m(lat, lon, a, b) <= r_km * 1000)
            if n:
                out.append((n, round(lat, 4), round(lon, 4)))
            lon += lon_step
        lat += lat_step
        row += 1
    out.sort(reverse=True)
    return [(a, b) for _, a, b in out]


def parse_tk_stations(data: Dict, price_entry) -> List[Dict[str, Any]]:
    """Parse a Tankerkoenig list.php response (free-API field names).

    The commercial API's response format is not yet known (contract and docs pending). If it differs,
    this is the ONLY function to change: it must return the same station dicts (id, lat, lon, brand,
    name, address, city, prices with E5/E10/DIESEL).
    """
    out = []
    for s in data.get("stations") or []:
        prices = []
        for field, (ft, unit) in FUEL_MAP.items():
            val = s.get(field)
            if isinstance(val, (int, float)) and not isinstance(val, bool) and val > 0:
                e = price_entry(ft, float(val), unit, octane=95 if ft in ("E5", "E10") else None)
                e["source"] = "tankerkoenig"
                prices.append(e)
        brand, name = s.get("brand") or "", s.get("name") or ""
        out.append({
            "id": f"de_tk_{s.get('id', '')}",
            "country": "DE",
            "name": f"{brand} {name}".strip() if brand else name,
            "brand": brand,
            "address": f"{s.get('street') or ''} {s.get('houseNumber') or ''}".strip(),
            "city": s.get("place") or "",
            "lat": s.get("lat"),
            "lon": s.get("lng"),
            "source": TK_SOURCE,
            "confidence": 0.99,
            "grade": "A",
            "prices": prices,
        })
    return out


class GermanyScraper(BaseScraper):
    COUNTRY    = "DE"
    CURRENCY   = "EUR"
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.85
    GRADE      = "C"
    REFRESH_MINUTES = 30

    def __init__(self, session):
        super().__init__(session)
        env = os.environ.get
        mode = (env("TANKERKOENIG_MODE") or "off").strip().lower()
        if mode not in MODES:
            print(f"[DE] unknown TANKERKOENIG_MODE {mode!r} - treated as off")
            mode = "off"
        self.mode = mode
        self.api_key = env("TANKERKOENIG_API_KEY", "")
        self.base_url = (env("TANKERKOENIG_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.radius_km = float(env("TANKERKOENIG_RADIUS_KM") or 25)
        self.max_req = int(env("TANKERKOENIG_MAX_REQ") or 400)
        self.concurrency = int(env("TANKERKOENIG_CONCURRENCY") or 4)
        self.budget_s = float(env("TANKERKOENIG_BUDGET_S") or 420)
        self.scraper_timeout_s = float(env("SCRAPER_TIMEOUT_S") or 900)   # same default as main.py
        # injectable for tests
        self._sleep = asyncio.sleep
        self._clock = time.monotonic
        self._wall = time.time
        self.tk_info: Dict[str, Any] = {"mode": mode}

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        t0 = self._clock()
        stations = await _DEAnwb(self.session).fetch_stations()    # baseline: errors propagate as before

        if self.mode == "off":
            print("[DE] TANKERKOENIG_MODE=off - ANWB baseline only (no statutory MTS-K upgrade)")
            return stations
        if not self.api_key:
            print(f"[DE] TANKERKOENIG_MODE={self.mode} but TANKERKOENIG_API_KEY is not set - ANWB baseline only")
            self.tk_info["error"] = "no api key"
            return stations

        # The whole scraper is cut by main.py's SCRAPER_TIMEOUT_S, which would also throw away the ANWB
        # result. So the Tankerkoenig step gets its own deadline well inside it.
        budget = min(self.budget_s, self.scraper_timeout_s - (self._clock() - t0) - 90)
        if budget < 30:
            print("[DE] no time left for the Tankerkoenig step - ANWB baseline only")
            self.tk_info["error"] = "no time budget"
            return stations
        try:
            tk = await self._fetch_tankerkoenig(stations, budget)
            if tk:
                self._merge(stations, tk, add_extras=self.mode == "commercial", info=self.tk_info)
                self._label(len(tk))
        except Exception as e:  # noqa: BLE001 - the ANWB baseline must survive any Tankerkoenig failure
            print(f"[DE] Tankerkoenig step failed, keeping ANWB baseline: {type(e).__name__}: {self._scrub(e)}")
            self.tk_info["error"] = type(e).__name__
        self._report(stations)
        return stations

    def _label(self, n_tk: int) -> None:
        if self.mode == "commercial":
            self.SOURCE = "tankerkoenig.de (MTS-K) + anwb.nl"
            self.CONFIDENCE = 0.95
            if n_tk >= 10000 and not self.tk_info.get("aborted"):          # ~70 % of the ~14.5k German stations seen by the statutory feed
                self.GRADE = "A"
        else:
            # test mode never claims coverage: country grade stays C, per-station grade A only where matched
            self.SOURCE = "anwb.nl (ANWB POI API) + tankerkoenig.de (MTS-K), partial test coverage"

    def _report(self, stations: List[Dict]) -> None:
        """Provenance for main.py (meta.sources / health.merge)."""
        tk_n = sum(1 for s in stations if s.get("source") == TK_SOURCE)
        won_tk = sum(1 for s in stations for p in s["prices"] if p.get("source") == "tankerkoenig")
        won_anwb = sum(len(s["prices"]) for s in stations) - won_tk
        info = self.tk_info
        problem = info.get("aborted") or info.get("error")
        self.merge_report = {
            "sources": {"anwb": {"name": "ANWB", "stations_used": len(stations) - tk_n, "prices_won": won_anwb},
                        "tankerkoenig": {"name": "Tankerkoenig (MTS-K)", "stations_used": tk_n, "prices_won": won_tk}},
            "failed_sources": [{"source_id": "tankerkoenig", "error": problem}] if problem else [],
            "tankerkoenig": info,
        }

    @staticmethod
    def _scrub(e: Any) -> str:
        return _APIKEY_RE.sub("apikey=***", str(e))

    # -- Tankerkoenig (MTS-K) ---------------------------------------------------

    def _circles(self, baseline: List[Dict]) -> List[Tuple[float, float]]:
        if self.mode == "test":
            slot = int(self._wall() // (self.REFRESH_MINUTES * 60))
            start = (slot * TEST_MAX_CIRCLES) % len(GRID)
            return [GRID[(start + i) % len(GRID)] for i in range(TEST_MAX_CIRCLES)]
        return _cover_circles(baseline, self.radius_km) or list(GRID)   # no footprint: metro circles only

    async def _fetch_tankerkoenig(self, baseline: List[Dict], budget_s: float) -> List[Dict[str, Any]]:
        circles = self._circles(baseline)
        test = self.mode == "test"
        max_req = TEST_MAX_CIRCLES if test else self.max_req
        radius = 25 if test else self.radius_km
        deadline = self._clock() + budget_s
        info = self.tk_info
        info.update(circles_planned=len(circles), requests=0, aborted=None, stopped=None, errors=0)
        seen: Dict[str, Dict] = {}
        it = iter(circles)
        last_end: List[Optional[float]] = [None]

        async def worker() -> None:
            while info["aborted"] is None:
                if info["errors"] >= 10:   # repeated failures: stop hammering a broken endpoint
                    info["aborted"] = "too many errors"
                    return
                circle = next(it, None)
                if circle is None:
                    return
                if info["requests"] >= max_req:
                    info["stopped"] = "request budget"
                    return
                wait = 0.0
                if test and last_end[0] is not None:
                    wait = MIN_GAP_TEST_S - (self._clock() - last_end[0])
                if self._clock() + max(wait, 0) + REQ_TIMEOUT_S > deadline:
                    info["stopped"] = "time budget"
                    return
                if wait > 0:
                    await self._sleep(wait)
                info["requests"] += 1
                try:
                    for st in await self._request(circle, radius):
                        seen.setdefault(st["id"], st)
                finally:
                    last_end[0] = self._clock()

        try:
            await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(1 if test else self.concurrency))),
                                   timeout=budget_s + 30)
        except asyncio.TimeoutError:
            info["stopped"] = "time budget"
        print(f"[DE] tankerkoenig mode={self.mode}: {len(seen)} stations from {info['requests']}/{len(circles)} "
              f"circles, aborted={info['aborted']}, stopped={info['stopped']}, errors={info['errors']}")
        return list(seen.values())

    async def _request(self, circle: Tuple[float, float], radius: float) -> List[Dict]:
        lat, lon = circle
        params = {"lat": lat, "lng": lon, "rad": radius, "sort": "dist", "type": "all", "apikey": self.api_key}
        info = self.tk_info
        try:
            async with self.session.get(f"{self.base_url}/list.php", params=params,
                                        timeout=aiohttp.ClientTimeout(total=REQ_TIMEOUT_S)) as resp:
                if resp.status in ABORT_STATUS or resp.status in FATAL_STATUS:
                    info["aborted"] = f"HTTP {resp.status}"
                    print(f"[DE] tankerkoenig HTTP {resp.status} - aborting the Tankerkoenig step (no retry)")
                    return []
                if resp.status != 200:
                    info["errors"] += 1
                    return []
                data = await resp.json(content_type=None)
            if not isinstance(data, dict):
                raise ValueError("unexpected response shape")
            ok = bool(data.get("ok"))
            parsed = parse_tk_stations(data, self.price_entry) if ok else []
        except Exception as e:  # noqa: BLE001
            info["errors"] += 1
            print(f"[DE] tankerkoenig ({lat:.2f},{lon:.2f}): {type(e).__name__}: {self._scrub(e)}")
            return []
        if not ok:
            info["aborted"] = "api not ok"
            print(f"[DE] tankerkoenig not ok: {self._scrub(data.get('message'))} - aborting the Tankerkoenig step")
            return []
        return parsed

    @staticmethod
    def _merge(base: List[Dict], tk: List[Dict], add_extras: bool = True,
               info: Optional[Dict] = None) -> List[Dict]:
        """MTS-K stations override the matching ANWB station (<=150 m).

        Both readings are kept: where the replaced ANWB petrol/diesel price differs from the MTS-K one by
        >= 2 % it is recorded as price["alt"] (same shape as merge_engine; "disagree" from 8 %). ANWB's
        98-octane price is kept because the Tankerkoenig feed has none. The station keeps its ANWB id, so
        the 48 h unchanged tracker (data_checks.track_changes, keyed on id) carries on; its signature
        changes once at the upgrade (95 slot becomes E5/E10) and its clock restarts then.
        ``add_extras``: add MTS-K stations without an ANWB match (commercial only; test mode stays partial).
        """
        cfg = MergeConfig(country="DE")
        cell = 0.002
        index: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
        for s in base:
            index[(round(s["lat"] / cell), round(s["lon"] / cell))].append(s)
        replaced = added = alts = 0
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
            if best is None or best_d > 150:
                if add_extras:
                    base.append(t)
                    added += 1
                continue
            old = {bucket_of(p): p for p in best.get("prices") or []}
            new = [dict(p) for p in t["prices"]]
            pairs = []
            if old.get("95"):      # ANWB does not say E5 or E10: compare with the closer of the two
                a = old["95"]
                c = min((p for p in new if p["fuel_type"] in ("E5", "E10")),
                        key=lambda p: abs(p["price"] - a["price"]), default=None)
                pairs.append((a, c))
            if old.get("DIESEL"):
                pairs.append((old["DIESEL"], next((p for p in new if p["fuel_type"] == "DIESEL"), None)))
            for a, p in pairs:
                if p is None:
                    continue
                lo = min(a["price"], p["price"])
                r = abs(a["price"] - p["price"]) / lo if lo > 0 else 0
                if r >= cfg.alt_min_pct:
                    p["alt"] = [{"price": a["price"], "source": "anwb", "updated_at": a.get("updated_at")}]
                    alts += 1
                    if r >= cfg.conflict_abs_pct:
                        p["disagree"] = True
            if old.get("98+"):
                new.append({**old["98+"], "source": "anwb"})
            best.update(prices=new, source=t["source"], confidence=t["confidence"], grade="A",
                        name=t["name"] or best["name"], brand=t["brand"] or best["brand"],
                        address=t["address"] or best["address"], city=t["city"] or best["city"])
            replaced += 1
        print(f"[DE] MTS-K merge: {replaced} ANWB stations upgraded, {added} added, {alts} alt readings")
        if info is not None:
            info.update(upgraded=replaced, added=added, alt_values=alts, tk_stations=len(tk))
        return base
