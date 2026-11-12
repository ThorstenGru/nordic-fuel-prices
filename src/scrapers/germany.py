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
import json
import zlib
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from merge_engine import MergeConfig, bucket_of
from .base import BaseScraper, dist_m
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

# Country-side circles (D): the metro circles above hold most stations, but a measurement of how good ANWB is must also
# see villages and the east. Each run takes METRO_PER_RUN circles from GRID and RURAL_PER_RUN from here, both rotating.
RURAL = [
    (53.60, 12.50), (52.60, 11.50), (52.80, 13.90), (51.50, 14.20), (50.60, 13.00), (50.50, 12.20), (50.70, 10.80),
    (51.70, 10.60), (51.30, 9.50), (51.20, 8.20), (50.20, 6.60), (49.90, 7.40), (49.40, 7.00), (49.30, 8.00),
    (49.60, 9.00), (50.40, 9.90), (49.50, 10.80), (49.00, 13.00), (47.70, 10.30), (47.80, 12.00), (48.40, 9.40),
    (48.20, 8.20), (52.70, 7.30), (53.40, 7.50), (54.60, 8.90), (54.00, 9.60), (53.00, 10.20), (51.90, 9.30),
]
METRO_PER_RUN, RURAL_PER_RUN = 2, 3        # = TEST_MAX_CIRCLES
RURAL_SET = set(RURAL)

# Accuracy meter (A): every ANWB-versus-MTS-K difference is counted in 1-cent bins, per day, so we can say how far ANWB is off.
RISKY_MIN_N, RISKY_PCT = 20, 30.0          # a brand is "often a few cents off" with >= 20 checks and >= 30 % of them 2 ct or more away
ACC_DAYS = 14
ACC_CLIP = 25                              # bins beyond +-25 ct are pooled

_APIKEY_RE = re.compile(r"apikey=[^&\s'\"]+")
FUEL_MAP = {"e5": ("E5", "L"), "e10": ("E10", "L"), "diesel": ("DIESEL", "L")}


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
                    if dist_m(lat, lon, a, b) <= r_km * 1000)
            if n:
                out.append((n, round(lat, 4), round(lon, 4)))
            lon += lon_step
        lat += lat_step
        row += 1
    out.sort(reverse=True)
    return [(a, b) for _, a, b in out]


def parse_tk_stations(data: Dict, price_entry, read_at: Optional[str] = None) -> List[Dict[str, Any]]:
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
                if read_at:   # NOT updated_at (that is the time the source says the price was set, which the free API does not give);
                    e["checked_at"] = read_at   # the official feed is near real time, so this is when the price was read from it
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


def accuracy_update(store: Dict, pairs: List[Tuple[str, str, str, float, int]], day: str) -> Dict:
    """Add one run's (fuel, stratum, BRAND, diff_ct, key) pairs to the per-day histograms and drop days older than ACC_DAYS.
    diff_ct = ANWB price minus official MTS-K price, in cents. Each station and fuel counts ONCE per day (the first reading wins):
    stations are re-read on every visit of their circle, and repeats are not new evidence. `key` is a hash of station id + fuel."""
    days = store.setdefault("days", {})
    d = days.setdefault(day, {"bins": {}, "brands": {}})
    seen = set(d.get("seen", []))
    for fuel, stratum, brand, diff, key in pairs:
        if key in seen:
            continue
        seen.add(key)
        k = f"{fuel}|{stratum}"
        b = d["bins"].setdefault(k, {})
        bin_ = str(max(-ACC_CLIP, min(ACC_CLIP, round(diff))))
        b[bin_] = b.get(bin_, 0) + 1
        t = d["brands"].setdefault(brand, [0, 0])
        t[0] += 1
        if abs(diff) >= 2:
            t[1] += 1
    d["seen"] = sorted(seen)
    for old_day, v in days.items():   # the seen-list is only needed for today: keeps the published file small
        if old_day != day:
            v.pop("seen", None)
    for old in sorted(days)[:-ACC_DAYS]:
        del days[old]
    return store


def _pct(hist: Dict[int, int], q: float) -> float:
    n = sum(hist.values())
    if not n:
        return 0.0
    acc, target = 0, q * n
    for k in sorted(hist):
        acc += hist[k]
        if acc >= target:
            return float(k)
    return float(max(hist))


def accuracy_summary(store: Dict) -> Dict:
    """Read the histograms back: share within 1 ct, median bias (signed), median/90th-percentile absolute error, worst brands."""
    def stats(hist: Dict[int, int]) -> Dict:
        n = sum(hist.values())
        if not n:
            return {"n": 0}
        ab: Dict[int, int] = defaultdict(int)
        for k, c in hist.items():
            ab[abs(k)] += c
        return {"n": n, "within_1ct_pct": round(100 * sum(c for k, c in hist.items() if abs(k) <= 1) / n, 1),
                "bias_median_ct": _pct(hist, 0.5), "abs_median_ct": _pct(ab, 0.5), "abs_p90_ct": _pct(ab, 0.9)}
    days = store.get("days") or {}
    allh: Dict[int, int] = defaultdict(int)
    per: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    brands: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for d in days.values():
        for k, bins in d.get("bins", {}).items():
            for b, c in bins.items():
                allh[int(b)] += c
                per[k][int(b)] += c
        for br, (n, o) in d.get("brands", {}).items():
            brands[br][0] += n
            brands[br][1] += o
    out = {"days": len(days), **stats(allh), "by": {k: stats(h) for k, h in sorted(per.items())}}
    worst = sorted(((100 * o / n, br, n) for br, (n, o) in brands.items() if n >= RISKY_MIN_N), reverse=True)[:15]
    out["worst_brands"] = [{"brand": br, "n": n, "over_2ct_pct": round(r, 1)} for r, br, n in worst]
    if out["n"]:
        out["line"] = (f"ANWB matched the official MTS-K price to within 1 cent for {out['within_1ct_pct']}% of {out['n']} checks "
                       f"on German stations (last {out['days']} days); median difference {out['bias_median_ct']:+g} ct, "
                       f"90% of checks within {out['abs_p90_ct']:g} ct.")
    return out


def _num(name, default, cast):
    """Number from the environment; a typo in a repo variable (400x) must not take the whole pipeline down."""
    raw = os.environ.get(name)
    try:
        return cast(raw) if raw not in (None, "") else default
    except ValueError:
        print(f"[DE] {name}={raw!r} is not a number - using {default}")
        return default


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
        self.radius_km = _num("TANKERKOENIG_RADIUS_KM", 25, float)
        self.max_req = _num("TANKERKOENIG_MAX_REQ", 400, int)
        self.concurrency = _num("TANKERKOENIG_CONCURRENCY", 4, int)
        self.budget_s = _num("TANKERKOENIG_BUDGET_S", 420, float)
        self.scraper_timeout_s = _num("SCRAPER_TIMEOUT_S", 900, float)   # same default as main.py
        # injectable for tests
        self._sleep = asyncio.sleep
        self._clock = time.monotonic
        self._wall = time.time
        self.tk_info: Dict[str, Any] = {"mode": mode}
        # accuracy meter file (published as /de_accuracy.json; the workflow downloads the last copy before the run). None = off.
        self.acc_path: Optional[Path] = Path(env("DE_ACCURACY_PATH") or Path(__file__).resolve().parents[2] / "data" / "de_accuracy.json")

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
                pairs: List[Tuple[str, str, str, float, int]] = []
                self._merge(stations, tk, add_extras=self.mode == "commercial", info=self.tk_info, acc=pairs)
                self._label(len(tk))
                self._record_accuracy(pairs)
        except Exception as e:  # noqa: BLE001 - the ANWB baseline must survive any Tankerkoenig failure
            print(f"[DE] Tankerkoenig step failed, keeping ANWB baseline: {type(e).__name__}: {self._scrub(e)}")
            self.tk_info["error"] = type(e).__name__
        self._flag_risky(stations)
        self._report(stations)
        return stations

    def _flag_risky(self, stations: List[Dict]) -> None:
        """Mark ANWB-only stations of brands that the accuracy meter found to be often wrong (station["uncertain"] = True).
        The price is not changed; the app adds a note. Stations upgraded to the official feed are never flagged."""
        for s in stations:
            s.pop("uncertain", None)
        if self.acc_path is None:
            return
        try:
            worst = json.loads(self.acc_path.read_text(encoding="utf-8")).get("summary", {}).get("worst_brands") or []
        except (OSError, ValueError):
            return
        risky = {w["brand"] for w in worst if w.get("n", 0) >= RISKY_MIN_N and w.get("over_2ct_pct", 0) >= RISKY_PCT}
        if not risky:
            return
        n = 0
        for s in stations:
            if s.get("source") != TK_SOURCE and (s.get("brand") or "").strip().upper()[:40] in risky:
                s["uncertain"] = True
                n += 1
        self.tk_info["risky_brands"] = sorted(risky)
        print(f"[DE] {n} ANWB-only stations of {len(risky)} often-wrong brands flagged uncertain: {', '.join(sorted(risky))}")

    def _record_accuracy(self, pairs: List[Tuple[str, str, str, float, int]]) -> None:
        """Fold this run's differences into the rolling 14-day file and put the summary into the health report."""
        if not pairs or self.acc_path is None:
            return
        try:
            try:
                store = json.loads(self.acc_path.read_text(encoding="utf-8"))
                if store.get("v") != 2:   # v1 counted every re-reading of the same station as a new check
                    store = {}
            except (OSError, ValueError):
                store = {}
            day = datetime.fromtimestamp(self._wall(), tz=timezone.utc).date().isoformat()
            store["v"] = 2
            accuracy_update(store, pairs, day)
            summ = accuracy_summary(store)
            store["updated"] = datetime.fromtimestamp(self._wall(), tz=timezone.utc).isoformat()
            store["summary"] = summ
            self.acc_path.parent.mkdir(parents=True, exist_ok=True)
            self.acc_path.write_text(json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            self.tk_info["accuracy"] = {k: summ[k] for k in ("days", "n", "within_1ct_pct", "bias_median_ct", "abs_p90_ct", "line") if k in summ}
            print(f"[DE] accuracy meter: {summ.get('line', 'no pairs')}")
        except Exception as e:  # noqa: BLE001 - the meter must never break the price feed
            print(f"[DE] accuracy meter failed: {type(e).__name__}: {e}")

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
            m, r = (slot * METRO_PER_RUN) % len(GRID), (slot * RURAL_PER_RUN) % len(RURAL)
            return ([GRID[(m + i) % len(GRID)] for i in range(METRO_PER_RUN)]
                    + [RURAL[(r + i) % len(RURAL)] for i in range(RURAL_PER_RUN)])
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
                        st["_stratum"] = "rural" if circle in RURAL_SET else ("metro" if test else "cover")
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
            parsed = parse_tk_stations(data, self.price_entry,
                                       datetime.fromtimestamp(self._wall(), tz=timezone.utc).isoformat()) if ok else []
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
               info: Optional[Dict] = None, acc: Optional[List] = None) -> List[Dict]:
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
                        d = dist_m(t["lat"], t["lon"], s["lat"], s["lon"])
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
            if old.get("95"):      # ANWB does not say E5 or E10: compare with the closer of the two (so petrol differences are, if anything, understated)
                a = old["95"]
                c = min((p for p in new if p["fuel_type"] in ("E5", "E10")),
                        key=lambda p: abs(p["price"] - a["price"]), default=None)
                pairs.append((a, c, "petrol"))
            if old.get("DIESEL"):
                pairs.append((old["DIESEL"], next((p for p in new if p["fuel_type"] == "DIESEL"), None), "diesel"))
            for a, p, fuel in pairs:
                if p is None:
                    continue
                if acc is not None:
                    acc.append((fuel, t.get("_stratum", "other"), (t.get("brand") or "?").strip().upper()[:40],
                                round((a["price"] - p["price"]) * 100, 1), zlib.crc32(f"{t.get('id')}|{fuel}".encode())))
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
