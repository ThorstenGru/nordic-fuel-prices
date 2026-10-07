"""
Greece - merge of two open datasets, ANWB only as gap filler / full fallback.

  fuelgr  : athanasso/fuelGR-scraper GitHub release dataset (stations_latest.min.json, ~4.7k stations, GPS,
            prices per station, one date per station). Built from the Ministry of Development price
            observatory (fuelprices.gr). Naive dates are Europe/Athens.
  fpeu    : fuel-prices.eu open API (CC BY 4.0, no key). Per-station GPS/brand/address/per-fuel price with
            per-price timestamp. HARD LIMITS of that service: it blocks an IP for an hour after bulk use
            (>120 station requests or >300 API calls per IP), radius is capped at 50 km and limit at 100
            stations per call (no paging). We therefore plan a small covering set of circles (at most
            FPEU_MAX_REQUESTS calls, >= 1.2 s apart) from the other sources' coordinates, stop at once on
            HTTP 429/403/410 and refresh at most every REFRESH_MINUTES. Dense city centres are only
            partially covered by fpeu (the fuelgr dataset covers them). IMPORTANT: for Greece fpeu's
            "station prices" are the ministry's prefecture averages (identical on hundreds of stations);
            those are detected and dropped, so fpeu mainly contributes extra station locations.
  anwb    : unofficial ANWB aggregator, no timestamps - only adds priced stations absent from both
            sources above, or is the full fallback when both fail.

Merge: delegated to merge_engine.merge_sources (one tested engine for all countries). SourceResults:
fuelgr priority 1 'community' (real prices), fpeu priority 5 'geometry' (locations only, its prices are
prefecture averages and are stripped), anwb priority 9 'aggregator' (priced stations only). The engine
does matching, 'newer timestamp wins by >= 30 min else priority', conflict flags and outlier filtering.
A failing source is marked ok=False; the scraper raises only when every source failed.
"""

import asyncio
import collections
import heapq
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .base import BaseScraper, iso_utc, octane_of
from ._anwb import ANWBScraper
from merge_engine import MergeConfig, SourceResult, merge_sources

GR_TZ = "Europe/Athens"
UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"

# DISABLED 2026-10-07: the fuelGR-scraper dataset has no licence and re-scrapes the fuelGR app backend,
# whose owner states it is closed to third parties. Re-enable only with written permission from fuelGR.
USE_FUELGR = False
FUELGR_RELEASES_API = "https://api.github.com/repos/athanasso/fuelGR-scraper/releases?per_page=5"
FUELGR_URL = "https://github.com/athanasso/fuelGR-scraper/releases/download/{tag}/stations_latest.min.json"
FUELGR_PREF_URL = "https://github.com/athanasso/fuelGR-scraper/releases/download/{tag}/prefectures_latest.min.json"
# fuel-prices.eu serves the ministry's PREFECTURE AVERAGES as "station prices" for Greece (verified
# 2026-10-07: 219 Attica stations share 2.182/2.14/1.038 = Attica average). Such prices are dropped.
AVG_REPEAT_MIN = 8   # fallback rule when prefecture averages are unavailable: same (fuel, price, ts) on >= 8 stations
FPEU_URL = "https://www.fuel-prices.eu/live/api.php"

FPEU_MAX_REQUESTS = 55          # hard limit of the service is 120 station requests per hour per IP
FPEU_SLEEP_S = 1.2
FPEU_MAX_RADIUS_KM = 50.0       # server-side cap
FPEU_PAGE_LIMIT = 100           # server-side cap per call

SOURCE_LABEL = {"fuelgr": "fuelGR-scraper", "fpeu": "fuel-prices.eu", "anwb": "anwb.nl"}

# plausible EUR bands per fuel type (litre; CNG per kg)
BANDS = {"E5": (0.9, 3.2), "DIESEL": (0.9, 3.2), "LPG": (0.4, 1.6), "CNG": (0.5, 3.0)}
LAT_RANGE, LON_RANGE = (34.5, 42.0), (19.0, 30.0)

# fuelGR keys: u95 unleaded 95 (E5 in Greece), u98/u100 premium grades (no site fuel type), d diesel,
# dp premium diesel, dh heating oil (not a motor fuel), lpg, cng.
FUELGR_MAP = {"u95": ("E5", "L"), "d": ("DIESEL", "L"), "lpg": ("LPG", "L"), "cng": ("CNG", "kg")}
FPEU_MAP = {"sp95": ("E5", "L"), "diesel": ("DIESEL", "L"), "gpl": ("LPG", "L"), "lpg": ("LPG", "L"),
            "cng": ("CNG", "kg")}

SOURCE_STRING = ("anwb.nl (ANWB POI API) prices + fuel-prices.eu station locations "
                 "(CC BY 4.0, https://www.fuel-prices.eu/)")

# last-resort planning centres if no source delivered coordinates (Athens, Thessaloniki, Patras, ...)
FALLBACK_CENTRES = [(37.98, 23.73), (40.64, 22.94), (38.25, 21.73), (35.34, 25.14), (39.66, 20.85),
                    (39.64, 22.42), (35.51, 24.02), (36.43, 28.22), (39.62, 19.92), (37.08, 22.42)]

def _dist_m(a_lat, a_lon, b_lat, b_lon) -> float:
    dlat = (b_lat - a_lat) * 111_320.0
    dlon = (b_lon - a_lon) * 111_320.0 * math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot(dlat, dlon)


def _hav_km(a_lat, a_lon, b_lat, b_lon) -> float:
    return _dist_m(a_lat, a_lon, b_lat, b_lon) / 1000.0


def _in_greece(lat, lon) -> bool:
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1])


def _slot(p: Dict) -> str:
    """Merge slot: petrol bucketed by octane (95 / 98+), other fuels by fuel_type."""
    o = octane_of(p)
    if o is None:
        return p["fuel_type"]
    return "P98" if o >= 97 else "P95"


class _GRAnwb(ANWBScraper):
    COUNTRY    = "GR"
    ISO3       = "GRC"
    BBOX       = (34.70, 19.30, 41.80, 29.70)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.90


class GreeceScraper(BaseScraper):
    COUNTRY    = "GR"
    CURRENCY   = "EUR"
    SOURCE     = SOURCE_STRING
    CONFIDENCE = 0.95
    GRADE      = "B"
    REFRESH_MINUTES = 180   # fuel-prices.eu rate limit; ministry data changes ~twice a day anyway

    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.requests_made = 0          # fuel-prices.eu station requests of the last run
        self.stats: Dict[str, Any] = {}
        self.merge_report: Dict[str, Any] = {}
        self._pref_avgs: set = set()    # {(fuel_type, price)} of ministry prefecture averages

    # ── orchestration ────────────────────────────────────────────────────────

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        by_source: Dict[str, List[Dict]] = {}
        errors: Dict[str, str] = {}

        # fuelgr and anwb are independent; anwb is also the planning pool when fuelgr is down
        async def _no_fuelgr():
            raise RuntimeError("fuelGR source disabled (no licence)")
        res = await asyncio.gather(self._fetch_fuelgr() if USE_FUELGR else _no_fuelgr(), self._fetch_anwb(),
                                   return_exceptions=True)
        for name, r in zip(("fuelgr", "anwb"), res):
            if isinstance(r, BaseException):
                errors[name] = f"{type(r).__name__}: {r}"
                print(f"[GR/{name}] FAILED: {errors[name]}")
            elif not r:
                errors[name] = "0 stations"
                print(f"[GR/{name}] returned 0 stations")
            else:
                by_source[name] = r

        pool = by_source.get("fuelgr") or by_source.get("anwb") or []
        try:
            fp = await self._fetch_fpeu([(s["lat"], s["lon"]) for s in pool])
            if fp:
                by_source["fpeu"] = fp
            else:
                errors["fpeu"] = "0 stations"
                print("[GR/fpeu] returned 0 stations")
        except Exception as e:  # noqa: BLE001
            errors["fpeu"] = f"{type(e).__name__}: {e}"
            print(f"[GR/fpeu] FAILED: {errors['fpeu']}")

        # fpeu contributes LOCATIONS only: its Greek "station prices" are prefecture averages.
        fp_stations = by_source.get("fpeu", [])
        for st in fp_stations:
            st["prices"] = []
        priced_anwb = [s for s in by_source.get("anwb", []) if s["prices"]]   # location-only ANWB rows are mostly stale/closed
        results = [
            SourceResult("fuelgr", SOURCE_LABEL["fuelgr"], by_source.get("fuelgr", []), 1, "community", "EUR",
                         "fuelgr" in by_source, errors.get("fuelgr")),
            SourceResult("fpeu", SOURCE_LABEL["fpeu"], fp_stations, 5, "geometry", "EUR",
                         "fpeu" in by_source, errors.get("fpeu")),
            SourceResult("anwb", SOURCE_LABEL["anwb"], priced_anwb, 9, "aggregator", "EUR",
                         "anwb" in by_source, errors.get("anwb")),
        ]
        if not any(r.ok for r in results):
            raise RuntimeError(f"GR: all sources failed ({errors})")
        merged, self.merge_report = merge_sources(results, MergeConfig(country="GR"))
        for st in merged:
            st["source"] = "+".join(SOURCE_LABEL.get(s, s) for s in st.get("sources", []))
            st.setdefault("confidence", self.CONFIDENCE)
        self.stats = {"raw": {k: len(v) for k, v in by_source.items()}, "merged": len(merged),
                      "fpeu_requests": self.requests_made, "errors": errors}
        rp = self.merge_report
        print("[GR] sources: " + ", ".join(f"{k}={len(v)}" for k, v in by_source.items())
              + f" | after merge={len(merged)} priced={rp['priced_station_count']} conflicts={rp['conflicts']}"
              + f" outliers={rp['outliers_dropped']} | fpeu requests={self.requests_made}"
              + (f" | errors={errors}" if errors else ""))
        return merged

    # ── fuelGR dataset ───────────────────────────────────────────────────────

    async def _get_json(self, url: str, timeout: int = 60) -> Any:
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                    headers={"User-Agent": UA, "Accept": "application/json"}) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} {url}")
            return await resp.json(content_type=None)

    async def _fetch_fuelgr(self) -> List[Dict]:
        rels = await self._get_json(FUELGR_RELEASES_API, 30)
        tags = [r.get("tag_name") for r in rels if isinstance(r, dict) and r.get("tag_name") and not r.get("draft")]
        tags.sort(reverse=True)     # tags are ISO dates
        data, last_err = None, None
        for tag in tags[:3]:
            try:
                data = await self._get_json(FUELGR_URL.format(tag=tag), 90)
                if isinstance(data, list) and data:
                    break
            except Exception as e:  # noqa: BLE001
                last_err = e
                data = None
        if not data:
            raise RuntimeError(f"no usable fuelGR release ({last_err})")
        try:
            prefs = await self._get_json(FUELGR_PREF_URL.format(tag=tag), 30)
            for r in prefs:
                for key, ft in (("unleaded_95", "E5"), ("diesel", "DIESEL"), ("lpg", "LPG")):
                    if isinstance(r.get(key), (int, float)):
                        self._pref_avgs.add((ft, round(float(r[key]), 3)))
        except Exception as e:  # noqa: BLE001
            print(f"[GR/fuelgr] prefecture averages unavailable ({e}); using repeat heuristic only")

        out: List[Dict] = []
        for it in data:
            try:
                lat, lon = float(it.get("lat")), float(it.get("lng"))
            except (TypeError, ValueError):
                continue
            if not _in_greece(lat, lon):
                continue
            ts = it.get("dt")   # 'YYYY-MM-DD' = Athens local date
            prices = []
            for key, val in (it.get("p") or {}).items():
                m = FUELGR_MAP.get(key)
                if not m:
                    continue
                pr = self._ok_price(m[0], val)
                if pr is not None:
                    prices.append(self.price_entry(m[0], pr, m[1], updated_at=ts, tz=GR_TZ,
                                                   octane=95 if m[0] == "E5" else None))
            addr = (it.get("a") or "").strip()
            street, _, city = addr.rpartition(",")
            if not street:
                street, city = addr, ""
            brand = (it.get("b") or "").strip()
            out.append({
                "id": f"gr_fg_{it.get('id')}",
                "country": "GR",
                "name": brand or (it.get("n") or "").strip(),
                "brand": brand,
                "address": street.strip(),
                "city": city.strip() or (it.get("pref") or "").strip(),
                "lat": lat, "lon": lon,
                "source": SOURCE_LABEL["fuelgr"],
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        print(f"[GR/fuelgr] {len(out)} stations ({sum(1 for s in out if s['prices'])} priced) from release {tags[0]}")
        return out

    # ── fuel-prices.eu (rate limited!) ───────────────────────────────────────

    def _plan_circles(self, pool: List[Tuple[float, float]]) -> List[Tuple[float, float, float]]:
        """Greedy max-coverage plan of (lat, lon, radius_km) circles over the pool coordinates.

        Each circle's radius is limited to 50 km and shrunk so that it holds roughly <= 70 pool stations
        (fpeu has ~1.3x as many stations and returns max 100 per call, nearest first). Stops after
        FPEU_MAX_REQUESTS circles, so very dense areas stay partially covered.
        """
        pool = [p for p in pool if _in_greece(*p)]
        if not pool:
            return [(la, lo, FPEU_MAX_RADIUS_KM) for la, lo in FALLBACK_CENTRES[:FPEU_MAX_REQUESTS]]
        # spatial index: 0.5 deg buckets
        buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for i, (la, lo) in enumerate(pool):
            buckets[(int(la * 2), int(lo * 2))].append(i)

        def near(i: int) -> List[Tuple[float, int]]:
            la, lo = pool[i]
            bi, bj = int(la * 2), int(lo * 2)
            res = []
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for j in buckets.get((bi + di, bj + dj), ()):
                        d = _hav_km(la, lo, *pool[j])
                        if d <= FPEU_MAX_RADIUS_KM:
                            res.append((d, j))
            res.sort()
            return res

        MAXN = 70
        cover: Dict[int, Tuple[float, List[int]]] = {}
        for i in range(len(pool)):
            nb = near(i)
            if len(nb) > MAXN:
                r = max(nb[MAXN][0] - 0.05, 1.0)
                nb = [x for x in nb if x[0] <= r]
            else:
                r = FPEU_MAX_RADIUS_KM
            cover[i] = (r, [j for _, j in nb])

        uncovered = set(range(len(pool)))
        heap = [(-len(c[1]), i) for i, c in cover.items()]
        heapq.heapify(heap)
        plan: List[Tuple[float, float, float]] = []
        while heap and uncovered and len(plan) < FPEU_MAX_REQUESTS:
            neg, i = heapq.heappop(heap)
            gain = sum(1 for j in cover[i][1] if j in uncovered)
            if gain == 0:
                continue
            if heap and gain < -heap[0][0]:
                heapq.heappush(heap, (-gain, i))   # stale bound: re-queue (lazy greedy)
                continue
            r, members = cover[i]
            plan.append((pool[i][0], pool[i][1], round(r, 1)))
            uncovered.difference_update(members)
        print(f"[GR/fpeu] plan: {len(plan)} circles, pool {len(pool)} stations, "
              f"{len(uncovered)} pool stations left outside plan (budget {FPEU_MAX_REQUESTS})")
        return plan

    async def _fpeu_request(self, params: Dict[str, str]) -> Tuple[int, Any]:
        """One fuel-prices.eu station request -> (http status, json payload). Overridable (tests replay a cache)."""
        async with self.session.get(FPEU_URL, params=params, timeout=aiohttp.ClientTimeout(total=30),
                                    headers={"User-Agent": UA, "Accept": "application/json"}) as resp:
            if resp.status != 200:
                return resp.status, None
            return 200, await resp.json(content_type=None)

    async def _fetch_fpeu(self, pool: List[Tuple[float, float]]) -> List[Dict]:
        plan = self._plan_circles(pool)
        seen: Dict[Any, Dict] = {}
        self.requests_made = 0
        for k, (lat, lon, r) in enumerate(plan):
            if k:
                await asyncio.sleep(FPEU_SLEEP_S)
            params = {"action": "stations", "country": "GR", "lat": f"{lat:.4f}", "lng": f"{lon:.4f}",
                      "radius": f"{max(r, 1.0):g}", "limit": str(FPEU_PAGE_LIMIT)}
            self.requests_made += 1
            try:
                status, payload = await self._fpeu_request(params)
                if status in (429, 403, 410):
                    print(f"[GR/fpeu] HTTP {status} - stopping to respect the rate limit "
                          f"after {self.requests_made} requests")
                    break
                if status != 200:
                    print(f"[GR/fpeu] HTTP {status} on circle {k} - skipped")
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"[GR/fpeu] circle {k} error: {e}")
                continue
            if not isinstance(payload, dict) or not payload.get("ok"):
                print(f"[GR/fpeu] circle {k} not ok: {str(payload)[:120]}")
                continue
            for it in (payload.get("data") or {}).get("stations", []) or []:
                sid = it.get("id")
                if sid is not None and sid not in seen:
                    seen[sid] = it

        # Drop prefecture-average prices masquerading as station prices.
        sig = collections.Counter()
        for it in seen.values():
            for key, v in (it.get("prices") or {}).items():
                if isinstance(v, dict):
                    sig[(key, v.get("price"), v.get("updated") or v.get("ts"))] += 1
        dropped_avg = 0

        out: List[Dict] = []
        for sid, it in seen.items():
            try:
                lat, lon = float(it.get("lat")), float(it.get("lng"))
            except (TypeError, ValueError):
                continue
            if not _in_greece(lat, lon):
                continue
            prices = []
            for key, v in (it.get("prices") or {}).items():
                m = FPEU_MAP.get(key)
                if not m or not isinstance(v, dict):
                    continue
                pr = self._ok_price(m[0], v.get("price"))
                if pr is None:
                    continue
                ts = v.get("updated") or v.get("ts")
                n_same = sig[(key, v.get("price"), ts)]
                if ((m[0], round(pr, 3)) in self._pref_avgs and n_same >= 3) or n_same >= AVG_REPEAT_MIN:
                    dropped_avg += 1
                    continue
                prices.append(self.price_entry(m[0], pr, m[1], updated_at=ts, tz=GR_TZ,
                                                   octane=95 if m[0] == "E5" else None))
            brand = (it.get("brand") or it.get("name") or "").strip()
            out.append({
                "id": f"gr_fp_{sid}",
                "country": "GR",
                "name": (it.get("name") or brand).strip(),
                "brand": brand,
                "address": (it.get("address") or "").strip(),
                "city": (it.get("city") or "").strip(),
                "postal_code": str(it.get("postal_code") or ""),
                "lat": lat, "lon": lon,
                "source": SOURCE_LABEL["fpeu"],
                "confidence": self.CONFIDENCE,
                "prices": prices,
            })
        print(f"[GR/fpeu] {len(out)} stations ({sum(1 for s in out if s['prices'])} with own prices; "
              f"{dropped_avg} prefecture-average prices dropped) in {self.requests_made} requests")
        return out

    # ── ANWB ─────────────────────────────────────────────────────────────────

    async def _fetch_anwb(self) -> List[Dict]:
        sts = await _GRAnwb(self.session).fetch_stations()
        out = [s for s in sts if _in_greece(s.get("lat"), s.get("lon"))]
        for s in out:   # Greek 95 is one product (E5, octane 95); ANWB's "95" (old: E10/E5) -> unify
            for p in s["prices"]:
                if p["fuel_type"] in ("E10", "E5", "95") and (octane_of(p) or 95) < 97:
                    p["fuel_type"] = "E5"
                    p["octane"] = 95
            seen_ft: Dict[str, Dict] = {}
            for p in s["prices"]:      # one price per octane bucket (95 / 98+): keep the lower
                k = _slot(p)
                if k not in seen_ft or p["price"] < seen_ft[k]["price"]:
                    seen_ft[k] = p
            s["prices"] = list(seen_ft.values())
        return out

    # ── helpers / merge ──────────────────────────────────────────────────────

    @staticmethod
    def _ok_price(fuel_type: str, val: Any) -> Optional[float]:
        try:
            v = float(val)
        except (TypeError, ValueError):
            return None
        lo, hi = BANDS.get(fuel_type, (0.4, 4.5))
        return v if lo <= v <= hi else None
