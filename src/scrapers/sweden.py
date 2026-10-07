"""
Sweden fuel price scraper.

Station locations: OpenStreetMap (Overpass API) — all brands, GPS included (the location backbone).
Prices:           bensinpriser.nu via the henrikhjelm.se proxy — crowd + station-owner reported.
                  GRADE D (community). Realistic ceiling ~20 % of all Swedish stations.

Why prices are scarce in Sweden: no statutory duty to report prices exists, and the major
chains (Circle K, OKQ8, Preem, St1) do not publish per-station prices online. See
docs/REGULATORY_REPORTING.md. Stations without a crowd price stay on the map as location-only pins.

Feed key format (verified 2026-10-01):
    {lan_slug}_{Brand}_{City}__{Street}[__{Sublocality}]__{fuel}      e.g.
    stockholmslan_St1_Taby__Enhagsvagen_2__Roslags_Nasby__95
The previous parser expected camelCase and silently matched NOTHING, so every priced station was
dropped (0 priced stations for months). The feed also carries ``created_at`` per county, which we
now use as the real price timestamp.
"""

import aiohttp
import asyncio
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import importlib

from merge_engine import MergeConfig, SourceResult, merge_sources
from .base import BaseScraper, iso_utc
from ._anwb import ANWBScraper
from . import geocoder as _geo


# ── OpenStreetMap (Overpass API) ───────────────────────────────────────────────

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",   # last resort (works when others time out)
]
BACKBONE_FILE = "se_osm_backbone.json"   # last good OSM snapshot, re-published with every run
OVERPASS_QUERY = """[out:json][timeout:60];
area["ISO3166-1"="SE"]->.se;
(
  node["amenity"="fuel"](area.se);
  way["amenity"="fuel"](area.se);
);
out center tags;"""
OVERPASS_HEADERS = {
    "User-Agent": "EuroFuelPrices/1.0 (https://github.com/ThorstenGru/nordic-fuel-prices)",
}


# ── bensinpriser.nu / henrikhjelm.se ──────────────────────────────────────────

HENRIKHJELM_URL = "https://henrikhjelm.se/api/getdata.php"

COUNTIES = [
    "blekinge-lan", "dalarnas-lan", "gavleborgs-lan", "gotlands-lan",
    "hallands-lan", "jamtlands-lan", "jonkoping-lan", "kalmar-lan",
    "kronobergs-lan", "norrbottens-lan", "orebro-lan", "ostergotlands-lan",
    "skane-lan", "sodermanlands-lan", "stockholms-lan", "uppsala-lan",
    "varmlands-lan", "vasterbottens-lan", "vasternorrlands-lan",
    "vastmanlands-lan", "vastra-gotalands-lan",
]

FUEL_MAP = {
    "95":         ("E10",    "L"),
    "98":         ("E5",     "L"),
    "diesel":     ("DIESEL", "L"),
    "biodiesel":  ("HVO100", "L"),
    "etanol":     ("E85",    "L"),
    "fordonsgas": ("CNG",    "kg"),
}

MAX_FEED_AGE = timedelta(hours=48)   # a county feed older than this is dead (Gotland: 3 months stale)
MATCH_RADIUS_M = 150                 # geocoded priced station -> existing OSM station


# ── Normalisation ─────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase, strip diacritics, keep alphanumerics only."""
    nfkd = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in nfkd if not unicodedata.combining(c)))


def _brand_key(raw: str) -> str:
    n = _norm(raw)
    if not n:
        return ""
    if n.startswith("circlek") or "statoil" in n:
        return "circlek"
    if n.startswith("okq8") or n in ("ok", "q8") or (n.startswith("ok") and "q8" in n):
        return "okq8"
    if n.startswith("preem"):
        return "preem"
    if n.startswith("st1") or n.startswith("shell"):   # St1 rebranded Shell Sweden
        return "st1"
    for b in ("ingo", "qstar", "tanka", "gulf", "pump", "dinx"):
        if n.startswith(b):
            return b
    return n[:14]


def _street_token(street: str) -> str:
    """First alphabetic word of a street, normalised ('Enhagsvägen 2' -> 'enhagsvagen')."""
    m = re.search(r"[^\W\d_]+", street or "", flags=re.UNICODE)
    return _norm(m.group(0)) if m else ""


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(a))


def _parse_station_id(station_id: str) -> Dict[str, str]:
    """'{lan}_{Brand}_{City}__{Street}[__{Sub}]' -> brand / city / street / street_q / name."""
    parts = station_id.split("_", 2)
    if len(parts) < 3:
        brand, rest = (parts[1] if len(parts) > 1 else station_id), ""
    else:
        _, brand, rest = parts
    if brand == "Circle" and rest.startswith("K_"):
        brand, rest = "Circle K", rest[2:]
    segs = [x for x in rest.split("__")]
    city = segs[0].replace("_", " ").strip() if segs else ""
    streets = [x.replace("_", " ").strip() for x in segs[1:] if x.strip()]
    street = " ".join(streets)
    street_q = streets[0] if streets else ""          # Nominatim wants just the street + number
    display = brand.replace("_", " ")
    if street and city:
        name = f"{display} · {street}, {city}"
    elif city:
        name = f"{display} · {city}"
    else:
        name = display
    return {"name": name, "brand": display, "city": city, "street": street, "street_q": street_q}


# ── Scraper ────────────────────────────────────────────────────────────────────

class _SEAnwb(ANWBScraper):
    """ANWB's Swedish feed (~1.5k stations with diesel/95 in EUR, converted to SEK, no timestamps)."""
    COUNTRY    = "SE"
    ISO3       = "SWE"
    CURRENCY   = "SEK"
    BBOX       = (55.0, 10.9, 69.1, 24.2)
    SOURCE     = "anwb.nl (ANWB POI API)"
    CONFIDENCE = 0.80


# Optional extra SE price sources (src/sources/se_*.py exposing `async def fetch(session)`),
# loaded lazily: (module, source_id, display name, priority, kind).  Adding one = one line.
OPTIONAL_SOURCES: List[Tuple[str, str, str, int, str]] = []


class SwedenScraper(BaseScraper):
    COUNTRY    = "SE"
    CURRENCY   = "SEK"
    SOURCE     = "openstreetmap.org + bensinpriser.nu + anwb.nl"
    CONFIDENCE = 0.70
    GRADE      = "D"
    REFRESH_MINUTES = 55   # upstream (bensinpriser.nu) itself only refreshes about every 3 h

    _CONCURRENCY = 4  # max concurrent county requests to henrikhjelm.se

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        osm_els, priced, anwb, *extra_res = await asyncio.gather(
            self._fetch_osm(), self._fetch_all_counties(), _SEAnwb(self.session).fetch_stations(),
            *[self._fetch_optional(m) for m, *_ in OPTIONAL_SOURCES], return_exceptions=True)
        osm_err = None
        if isinstance(osm_els, Exception) or not osm_els:
            osm_err = str(osm_els) if isinstance(osm_els, Exception) else "empty"
            osm_els = []
        priced_err = None
        if isinstance(priced, Exception):
            priced_err = str(priced)
            print(f"[SE/bensinpriser] failed: {priced}")
            priced = []
        anwb_err = None
        if isinstance(anwb, Exception):
            anwb_err = str(anwb)
            print(f"[SE/ANWB] failed: {anwb}")
            anwb = []

        osm_stations = self._parse_osm(osm_els)
        by_brand_city: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        by_brand_street: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        by_city_street: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        for s in osm_stations:
            bk, ck, st = s.pop("_bk", ""), s.pop("_ck", ""), s.pop("_st", "")
            if bk and ck:
                by_brand_city[(bk, ck)].append(s)
            if bk and st:
                by_brand_street[(bk, st)].append(s)
            if ck and st:
                by_city_street[(ck, st)].append(s)

        def free(cands: List[Dict]) -> List[Dict]:
            return [c for c in cands if not c["prices"]]

        def attach(osm_st: Dict, p: Dict) -> None:
            osm_st["prices"] = p["prices"]
            osm_st["source"] = "bensinpriser.nu"
            osm_st["confidence"] = 0.70

        unmatched: List[Dict] = []
        matched_n = 0
        for p in priced:
            bk, ck, st = _brand_key(p["brand"]), _norm(p["city"]), _street_token(p["street_q"])
            cand: Optional[Dict] = None
            options = free(by_brand_city.get((bk, ck), []))
            if options and st:
                same_street = [c for c in options if _street_token(c.get("address", "")) == st]
                options = same_street or options
            if options:
                cand = options[0]
            elif st and bk:
                opts = free(by_brand_street.get((bk, st), []))
                cand = opts[0] if opts else None
            if cand is None and st and ck and bk in ("ovriga", ""):
                opts = free(by_city_street.get((ck, st), []))
                cand = opts[0] if opts else None
            if cand is not None:
                attach(cand, p)
                matched_n += 1
            else:
                unmatched.append(p)

        # Geocode the rest (cached across runs), then snap to a nearby OSM pin or keep as own pin
        await _geo.apply_geocoding(
            unmatched, "SE", self.session,
            key_fn=lambda s: s.get("geo_key", ""),
            query_fn=lambda s: (s["city"], s["street_q"], ""),
        )
        osm_cells: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)
        for s in osm_stations:
            osm_cells[(round(s["lat"] / 0.002), round(s["lon"] / 0.002))].append(s)

        extra: List[Dict] = []
        snapped = 0
        for p in unmatched:
            p.pop("geo_key", None)
            if p.get("lat") is None:
                continue
            bk = _brand_key(p["brand"])
            cx, cy = round(p["lat"] / 0.002), round(p["lon"] / 0.002)
            best, best_d = None, 1e9
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for s in osm_cells.get((cx + dx, cy + dy), []):
                        if s["prices"]:
                            continue
                        sbk = _brand_key(s.get("brand", ""))
                        if bk not in ("ovriga", "") and sbk and sbk != bk:
                            continue
                        d = _dist_m(p["lat"], p["lon"], s["lat"], s["lon"])
                        if d < best_d:
                            best, best_d = s, d
            if best is not None and best_d <= MATCH_RADIUS_M:
                attach(best, p)
                snapped += 1
            else:
                extra.append(p)

        crowd = [o for o in osm_stations if o["prices"]] + extra
        geometry = [o for o in osm_stations if not o["prices"]]
        results = [
            SourceResult("bensinpriser", "bensinpriser.nu (crowd, matched onto OSM)", crowd, 2, "crowd", "SEK",
                         ok=priced_err is None, error=priced_err),
            SourceResult("anwb", "ANWB", anwb, 9, "aggregator", "SEK", ok=anwb_err is None, error=anwb_err),
            SourceResult("osm", "OpenStreetMap", geometry, 99, "geometry", "SEK",
                         ok=osm_err is None, error=osm_err),
        ]
        for (mod, sid, name, prio, kind), r in zip(OPTIONAL_SOURCES, extra_res):
            bad = isinstance(r, Exception)
            results.append(SourceResult(sid, name, [] if bad else r, prio, kind, "SEK",
                                        ok=not bad, error=str(r) if bad else None))
        usable = sum(len(r.stations) for r in results if r.ok and r.kind != "geometry")
        if osm_err is not None and usable <= 1000:
            # Without the OSM backbone (and no other source with >1000 stations) we would publish a
            # regression. Raise so the pipeline keeps the last good file.
            raise RuntimeError(f"OSM backbone unavailable: {osm_err}")
        all_stations, self.merge_report = merge_sources(results, MergeConfig(country="SE"))
        rp = self.merge_report
        print(f"[SE] {len(all_stations)} stations total, {rp['priced_station_count']} with prices "
              f"(OSM match {matched_n}, geocode-snap {snapped}, own pin {len(extra)}, "
              f"{len(priced) - matched_n - snapped - len(extra)} priced but un-locatable; "
              f"conflicts {rp['conflicts']}, outliers {rp['outliers_dropped']}, failed {rp['failed_sources']})")
        return all_stations

    async def _fetch_optional(self, module: str) -> List[Dict]:
        mod = importlib.import_module(f"sources.{module}")
        return await mod.fetch(self.session)

    # ── OSM fetch ──────────────────────────────────────────────────────────────

    async def _fetch_osm(self) -> list:
        els = await self._fetch_osm_live()
        path = _geo._DATA_DIR / BACKBONE_FILE
        if els:
            try:
                _geo._DATA_DIR.mkdir(exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(els, f, ensure_ascii=False, separators=(",", ":"))
            except OSError as e:
                print(f"[SE/OSM] snapshot save failed: {e}")
            return els
        # Overpass is down: fall back to the last good snapshot published on GitHub Pages
        try:
            base = await _geo.resolve_pages_base(self.session)
            async with self.session.get(f"{base}/{BACKBONE_FILE}",
                                        timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    els = await resp.json(content_type=None)
                    if els:
                        print(f"[SE/OSM] Overpass down — using cached backbone ({len(els)} elements)")
                        _geo._DATA_DIR.mkdir(exist_ok=True)
                        with open(path, "w", encoding="utf-8") as f:   # keep it published
                            json.dump(els, f, ensure_ascii=False, separators=(",", ":"))
                        return els
        except Exception as e:
            print(f"[SE/OSM] cached backbone unavailable: {e}")
        # Last resort: a snapshot committed to the repo itself. This is the one tier that can
        # never be wiped — gh-pages is force-orphaned every run, so if Overpass AND the published
        # cache both fail on the same run (as happened 2026-10-02: a Overpass outage hit before any
        # cache snapshot had ever been published), there would otherwise be nothing left to fall
        # back to and Sweden goes to zero stations. Goes stale over time but keeps the map alive.
        try:
            seed_path = Path(__file__).parent.parent / "seed" / BACKBONE_FILE
            with open(seed_path, "r", encoding="utf-8") as f:
                els = json.load(f)
            if els:
                print(f"[SE/OSM] Overpass + published cache both down — using repo seed ({len(els)} elements, may be stale)")
                try:
                    _geo._DATA_DIR.mkdir(exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:   # keep it published so the next run's cache tier has something
                        json.dump(els, f, ensure_ascii=False, separators=(",", ":"))
                except OSError as e:
                    print(f"[SE/OSM] snapshot save failed: {e}")
                return els
        except Exception as e:
            print(f"[SE/OSM] repo seed unavailable: {e}")
        raise RuntimeError("OSM backbone unavailable (all Overpass mirrors, cache and repo seed failed)")

    async def _fetch_osm_live(self) -> list:
        last_err = "no mirror tried"
        for attempt in range(len(OVERPASS_URLS) + 2):
            url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
            try:
                async with self.session.post(
                    url, data={"data": OVERPASS_QUERY}, headers=OVERPASS_HEADERS,
                    timeout=aiohttp.ClientTimeout(total=70),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        els = data.get("elements", [])
                        if len(els) > 500:          # Sweden has ~3,000+; fewer = broken/partial mirror
                            return els
                        last_err = f"{url}: only {len(els)} elements"
                    else:
                        last_err = f"{url}: HTTP {resp.status}"
            except Exception as e:
                last_err = f"{url}: {type(e).__name__} {e}"
            print(f"[SE/OSM] {last_err} (attempt {attempt + 1})")
            await asyncio.sleep(3)
        return []

    def _parse_osm(self, elements: list) -> List[Dict]:
        stations: List[Dict] = []
        seen: set = set()
        cells: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)   # de-dup node+way of one pump
        for el in elements:
            eid = el.get("id")
            if (el.get("type"), eid) in seen:
                continue
            seen.add((el.get("type"), eid))

            if el["type"] == "node":
                lat, lon = el.get("lat"), el.get("lon")
            else:
                c = el.get("center", {})
                lat, lon = c.get("lat"), c.get("lon")
            if lat is None or lon is None:
                continue

            tags = el.get("tags", {})
            brand = tags.get("brand") or tags.get("operator") or tags.get("name") or ""
            bk = _brand_key(brand)
            cell = (round(lat / 0.0005), round(lon / 0.0005))
            dup = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for o in cells.get((cell[0] + dx, cell[1] + dy), []):
                        if _dist_m(lat, lon, o["lat"], o["lon"]) <= 30 and (not bk or not o["_bk"] or bk == o["_bk"]):
                            dup = True
            if dup:
                continue

            name = tags.get("name") or tags.get("brand") or tags.get("operator") or "Bränslestation"
            city = (tags.get("addr:city") or tags.get("addr:town")
                    or tags.get("addr:village") or tags.get("addr:municipality") or "")
            street = tags.get("addr:street", "")
            address = f"{street} {tags.get('addr:housenumber', '')}".strip()
            st = {
                "id": f"se_osm_{el.get('type', 'n')[0]}{eid}",
                "country": "SE", "name": name, "brand": brand, "address": address, "city": city,
                "lat": lat, "lon": lon, "source": "openstreetmap.org", "confidence": 0.75,
                "prices": [], "_bk": bk, "_ck": _norm(city), "_st": _street_token(street),
            }
            cells[cell].append(st)
            stations.append(st)

        print(f"[SE/OSM] {len(stations)} stations")
        return stations

    # ── bensinpriser.nu (via henrikhjelm.se) ──────────────────────────────────

    async def _fetch_all_counties(self) -> List[Dict]:
        sem = asyncio.Semaphore(self._CONCURRENCY)
        results = await asyncio.gather(*[self._fetch_county_throttled(c, sem) for c in COUNTIES],
                                       return_exceptions=True)

        station_prices: Dict[str, Dict[str, float]] = defaultdict(dict)
        station_ts: Dict[str, Optional[str]] = {}
        station_county: Dict[str, str] = {}
        dead, ok_counties = [], 0

        for county, result in zip(COUNTIES, results):
            if isinstance(result, Exception) or not result:
                dead.append(county)
                continue
            created_at, entries = result
            ts = iso_utc(created_at)
            if ts is None or datetime.fromisoformat(ts) < datetime.now(timezone.utc) - MAX_FEED_AGE:
                print(f"[SE/bensinpriser] {county}: feed stale (created_at={created_at}) — ignored")
                dead.append(county)
                continue
            ok_counties += 1
            for station_id, fuel_raw, price in entries:
                station_prices[station_id][fuel_raw] = price
                station_ts[station_id] = ts
                station_county[station_id] = county

        stations = []
        for station_id, prices_by_fuel in station_prices.items():
            entries = []
            for ft_raw, (ft, unit) in FUEL_MAP.items():
                p = prices_by_fuel.get(ft_raw)
                if p and p > 0:
                    entries.append(self.price_entry(ft, p, unit, updated_at=station_ts.get(station_id),
                                                    octane={"95": 95, "98": 98}.get(ft_raw)))
            if not entries:
                continue
            info = _parse_station_id(station_id)
            stations.append({
                "id": f"se_{station_id}",
                "country": "SE",
                "name": info["name"], "brand": info["brand"],
                "address": info["street"], "city": info["city"],
                "street_q": info["street_q"],
                "geo_key": f"{_norm(info['city'])}|{_norm(info['street_q'])}" if info["city"] else "",
                "county": station_county.get(station_id, ""),
                "lat": None, "lon": None,
                "source": "bensinpriser.nu", "confidence": 0.70,
                "prices": entries,
            })

        print(f"[SE/bensinpriser] {len(stations)} priced stations from {ok_counties}/{len(COUNTIES)} fresh counties"
              + (f" (dead/stale: {', '.join(dead)})" if dead else ""))
        return stations

    async def _fetch_county_throttled(self, county: str, sem: asyncio.Semaphore):
        async with sem:
            result = await self._fetch_county(county)
            await asyncio.sleep(0.3)
            return result

    async def _fetch_county(self, county: str):
        """Return (created_at, [(station_id, fuel_raw, price), ...]) or None on failure."""
        data = None
        for attempt in range(3):
            try:
                async with self.session.get(
                    HENRIKHJELM_URL, params={"lan": county},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        break
                    print(f"[SE/bensinpriser] {county}: HTTP {resp.status} (attempt {attempt + 1})")
            except Exception as e:
                print(f"[SE/bensinpriser] {county}: {type(e).__name__} {e} (attempt {attempt + 1})")
            await asyncio.sleep(2 * (attempt + 1))
        if not isinstance(data, dict) or "error" in data:
            return None

        entries = []
        for key, raw_val in data.items():
            if "__" not in key:
                continue
            station_id, fuel_raw = key.rsplit("__", 1)
            if fuel_raw not in FUEL_MAP:
                continue
            try:
                price = float(str(raw_val).replace(",", "."))
            except (ValueError, TypeError):
                continue
            if price > 0:
                entries.append((station_id, fuel_raw, price))
        return data.get("created_at"), entries
