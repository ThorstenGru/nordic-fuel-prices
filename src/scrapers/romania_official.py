"""Romania: official Monitorul Preturilor public GET API (Competition Council portal).

PERMISSION NOT YET OBTAINED (2026-11-07): the API is keyless and public but no reuse terms were found
(docs/ROMANIA_OPTIONS_2026-11-06.md). It is only used when ROMANIA_SOURCE=official|both
(see docs/ROMANIA_SETUP.md). The default stays peco-online.

Endpoint  GET https://monitorulpreturilor.info/pmonsvc/Gas/GetGasItemsByLatLon
              ?lon=&lat=&buffer=<m>&CSVGasCatalogProductIds=<ONE id>&OrderBy=dist     (Accept: application/json)
Limits    one product id per call, max 50 stations per call, buffer 5000 m works (8000+ returns {}).
Products  11 petrol standard (E5 / 95), 21 diesel standard, 31 LPG.
Response  Stations[] {id, name, updatedate "dd/mm/yyyy hh:mm" (Europe/Bucharest), network, addr{addrstring,
          location{Lat,Lon}}, uatid} and Products[] {stationid, price, ...}.

Tiling    A 7 km grid of 5 km-radius circles, restricted to the footprint of stations we already know (the
          previously published ro.json; county seats bootstrap an empty start). New stations extend the
          footprint to their own grid cell, so coverage grows by one ring per cycle. A call that returns the
          50-station cap is re-queried as four 2.5 km sub-circles (one level).
          shortcut: GetGasItemsByUat (cheaper, one call per UAT) is not used because UAT ids are not
          persisted; upgrade by storing `uatid` per station.
Politeness  >= 1.1 s between calls, honest User-Agent, per-run request budget and wall-clock cap, rotating
          slice of the tile list per run.
"""
import asyncio
import math
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import aiohttp

from .base import iso_utc

BASE = "https://monitorulpreturilor.info/pmonsvc/Gas/GetGasItemsByLatLon"
UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
TZ = "Europe/Bucharest"
PRODUCTS = {"11": ("E5", "L"), "21": ("DIESEL", "L"), "31": ("LPG", "L")}
BUFFER_M = 5000
CAP = 50
GRID_KM = 7.0                      # circle spacing; half-diagonal 4.95 km < BUFFER_M so cells are fully covered
PACE_S = 1.1
LAT_RANGE, LON_RANGE = (43.5, 48.4), (20.0, 30.2)
SEEDS = [(46.77, 23.59), (44.43, 26.10), (45.75, 21.23), (47.16, 27.59), (44.18, 28.64), (45.65, 25.60),
         (47.05, 21.93), (44.32, 23.80), (45.44, 28.05), (47.66, 23.57), (45.79, 24.15), (44.94, 26.03)]


def parse_gas(payload: Any, fuel: str, unit: str) -> List[Dict[str, Any]]:
    """One API reply -> [{sid, name, brand, address, lat, lon, ft, unit, price, updated_at}] (bad rows skipped)."""
    if not isinstance(payload, dict):
        return []
    prices = {}
    for p in payload.get("Products") or []:
        try:
            if float(p["price"]) > 0:
                prices[p["stationid"]] = float(p["price"])
        except (KeyError, TypeError, ValueError):
            continue
    out = []
    for s in payload.get("Stations") or []:
        try:
            sid = s["id"]
            loc = s["addr"]["location"]
            lat, lon = float(loc["Lat"]), float(loc["Lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if sid not in prices or not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            continue
        net = s.get("network") if isinstance(s.get("network"), dict) else {}
        brand = str(net.get("name") or net.get("id") or s.get("name") or "").strip()
        out.append({"sid": sid, "name": str(s.get("name") or brand).strip(), "brand": brand,
                    "address": str((s.get("addr") or {}).get("addrstring") or "").strip(),
                    "lat": lat, "lon": lon, "ft": fuel, "unit": unit, "price": prices[sid],
                    "updated_at": iso_utc(str(s.get("updatedate") or "").strip(), TZ)})
    return out


def plan_tiles(known: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Sorted grid-cell centres covering the known stations (or the county-seat seeds when none)."""
    dlat = GRID_KM / 111.32
    cells: Set[Tuple[int, int]] = set()
    for lat, lon in list(known) or SEEDS:
        dlon = GRID_KM / (111.32 * math.cos(math.radians(lat)))
        cells.add((math.floor(lat / dlat), math.floor(lon / dlon)))
    out = []
    for i, j in sorted(cells):
        lat = (i + 0.5) * dlat
        out.append((round(lat, 5), round((j + 0.5) * GRID_KM / (111.32 * math.cos(math.radians(lat))), 5)))
    return out


class MonitorulSource:
    def __init__(self, session: aiohttp.ClientSession, budget: int = 150, wall_clock_s: float = 200.0,
                 pace_s: float = PACE_S):
        self.session, self.budget, self.wall_clock_s, self.pace_s = session, budget, wall_clock_s, pace_s
        self.requests = 0
        self.tiles_done = 0
        self.tiles_total = 0
        self.errors = 0
        self._t0 = 0.0

    def _exhausted(self) -> bool:
        return self.requests >= self.budget or time.monotonic() - self._t0 > self.wall_clock_s

    async def _get(self, lat: float, lon: float, buffer: int, product: str) -> Optional[dict]:
        """One polite GET (>= pace_s after the previous). None on any failure."""
        if self.requests:
            await asyncio.sleep(self.pace_s)
        self.requests += 1
        params = {"lon": f"{lon:.5f}", "lat": f"{lat:.5f}", "buffer": str(buffer),
                  "CSVGasCatalogProductIds": product, "OrderBy": "dist"}
        try:
            async with self.session.get(BASE, params=params, timeout=aiohttp.ClientTimeout(total=30),
                                        headers={"User-Agent": UA, "Accept": "application/json"}) as r:
                if r.status != 200:
                    self.errors += 1
                    return None
                return await r.json(content_type=None)
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            print(f"[RO/official] {type(e).__name__}: {e}")
            return None

    async def _query(self, lat: float, lon: float, product: str, buffer: int = BUFFER_M,
                     split: bool = True) -> List[dict]:
        payload = await self._get(lat, lon, buffer, product)
        fuel, unit = PRODUCTS[product]
        rows = parse_gas(payload, fuel, unit)
        n_st = len(payload.get("Stations") or []) if isinstance(payload, dict) else 0
        if split and n_st >= CAP:                       # density cap: four half-radius sub-circles
            d = buffer / 2 / 111_320.0 * 0.7
            dlon = d / math.cos(math.radians(lat))
            for sy in (-1, 1):
                for sx in (-1, 1):
                    if self._exhausted():
                        break
                    rows += await self._query(lat + sy * d, lon + sx * dlon, product, buffer // 2, split=False)
        return rows

    async def fetch(self, known: Iterable[Tuple[float, float]], slot: int) -> Dict[str, Dict[str, Any]]:
        """Scan this run's slice of tiles. Returns {station_id: info + prices {ft: (price, unit, updated_at)}}."""
        tiles = plan_tiles(known)
        self.tiles_total = len(tiles)
        per_run = max(1, self.budget // len(PRODUCTS))
        start = (slot * per_run) % len(tiles)
        order = (tiles[start:] + tiles[:start])[:per_run]
        self._t0 = time.monotonic()
        out: Dict[str, Dict[str, Any]] = {}
        for lat, lon in order:
            if self._exhausted():
                break
            for product in PRODUCTS:
                for r in await self._query(lat, lon, product):
                    st = out.setdefault(r["sid"], {"prices": {}, **{k: r[k] for k in ("name", "brand", "address", "lat", "lon")}})
                    st["prices"][r["ft"]] = (r["price"], r["unit"], r["updated_at"])
            self.tiles_done += 1
        print(f"[RO/official] {len(out)} stations, {self.tiles_done}/{len(order)} tiles of {self.tiles_total} "
              f"(slot {slot}), {self.requests} requests, {self.errors} failed")
        return out
