"""Multi-source merge engine for EuroFuelPrices (pure Python, stdlib only, no network).

One tested module that replaces the ad-hoc merges in the country scrapers.  See
EuroFuelPrices_MERGE_DESIGN.md sections 2-6 and decisions D1-D15.

Principles ("wrong data is worse than no data"):
  * never average / interpolate - every displayed price is exactly one source's value;
  * when unsure whether two records are the same station, do NOT merge;
  * disagreements are exposed (``alt`` / ``disagree``), never hidden;
  * regulated maxima never override a station price (D9) and are flagged ``basis: regulated_max``.

Public API:
    SourceResult, MergeConfig, merge_sources(results, cfg) -> (stations, report)
"""
from __future__ import annotations

import copy
import math
import re
import statistics
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --------------------------------------------------------------------------------------------
# Public data classes
# --------------------------------------------------------------------------------------------


@dataclass
class SourceResult:
    source_id: str
    name: str
    stations: List[dict]
    priority: int                 # lower = preferred
    kind: str                     # official|company|crowd|aggregator|regulated_cap|geometry
    currency: str
    ok: bool = True
    error: Optional[str] = None


@dataclass
class MergeConfig:
    country: str
    match_radius_m: float = 100
    unknown_brand_radius_m: float = 40
    conflict_abs_pct: float = 0.08
    alt_min_pct: float = 0.02
    outlier_neighbour_pct: float = 0.25
    outlier_radius_km: float = 5
    outlier_min_neighbours: int = 5
    prefer_newer_timestamp: bool = True
    newer_by_minutes: int = 30
    max_ts_future_min: int = 10


# --------------------------------------------------------------------------------------------
# Fuel buckets (octane_of re-implemented identically to scrapers.base.octane_of so that this
# module does not pull in aiohttp)
# --------------------------------------------------------------------------------------------


def octane_of(price: Dict) -> Optional[int]:
    o = price.get("octane")
    if o:
        try:
            return int(o)
        except (TypeError, ValueError):
            pass
    ft = price.get("fuel_type")
    if ft in ("E10", "95"):
        return 95
    if ft == "98":
        return 98
    if ft == "E5":
        return 95
    return None


_PETROL_TYPES = {"E10", "E5", "95", "98"}
BUCKET_ORDER = ["95", "98+", "DIESEL", "LPG", "CNG", "E85", "HVO100"]


def bucket_of(price: Dict) -> Optional[str]:
    """'95' | '98+' for petrol (by RON), otherwise the upper-cased fuel_type."""
    ft = str(price.get("fuel_type") or "").strip()
    if not ft:
        return None
    if ft.upper() in _PETROL_TYPES or price.get("octane"):
        if ft.upper() in ("DIESEL", "LPG", "CNG", "E85", "HVO100"):
            return ft.upper()
        o = octane_of({**price, "fuel_type": ft.upper()})
        if o is None:
            return ft.upper()
        return "98+" if o >= 97 else "95"
    return ft.upper()


def _bucket_sort_key(b: str) -> Tuple[int, str]:
    return (BUCKET_ORDER.index(b), b) if b in BUCKET_ORDER else (len(BUCKET_ORDER), b)


# --------------------------------------------------------------------------------------------
# Brand normalisation
# --------------------------------------------------------------------------------------------

_UNKNOWN_BRANDS = {"", "unknown", "unbranded", "independent", "other", "n a", "na", "none", "null",
                   "okand", "neznamy", "nepoznato", "ismeretlen", "unbekannt", "inconnu", "generic"}
_GENERIC_WORDS = {"tankstelle", "station", "stations", "service", "servis", "petrol", "gas", "fuel",
                  "tank", "tankstation", "petrolstation", "stazione", "benzina", "benzinka", "pumpa"}

_ALIAS_SRC = {
    "shell": ["shell", "shell express", "shell recharge"],
    "bp": ["bp", "bp express", "british petroleum"],
    "esso": ["esso", "esso express", "esso on the run"],
    "circle k": ["circle k", "circlek", "circle-k", "statoil", "statoil fuel", "ik", "ica circle k"],
    "okq8": ["okq8", "ok q8", "okq 8"],
    "ok": ["ok"],
    "q8": ["q8", "q8 easy", "kuwait petroleum"],
    "preem": ["preem", "preem express"],
    "st1": ["st1", "st 1", "st1 energy"],
    "ingo": ["ingo"],
    "qstar": ["qstar", "q star"],
    "neste": ["neste", "neste express"],
    "teboil": ["teboil"],
    "abc": ["abc", "abc station"],
    "uno-x": ["uno x", "unox", "uno x 7 eleven", "uno x automat"],
    "yx": ["yx", "yx 7 eleven", "yx truck"],
    "best": ["best"],
    "tanka": ["tanka"],
    "orlen": ["orlen", "pkn orlen", "benzina", "benzina orlen", "orlen benzina"],
    "mol": ["mol", "mol plugee", "mol nyrt"],
    "omv": ["omv", "omv viva", "omv tankstelle"],
    "aral": ["aral", "aral tankstelle"],
    "total": ["total", "totalenergies", "total energies", "total access", "total energies access"],
    "texaco": ["texaco"],
    "gulf": ["gulf"],
    "jet": ["jet", "jet tankstelle"],
    "applegreen": ["applegreen", "apple green"],
    "maxol": ["maxol"],
    "topaz": ["topaz"],
    "emo": ["emo"],
    "certa": ["certa"],
    "eni": ["eni", "agip", "agip eni", "eni station"],
    "repsol": ["repsol"],
    "cepsa": ["cepsa", "moeve"],
    "galp": ["galp"],
    "lukoil": ["lukoil", "luk oil"],
    "petrom": ["petrom", "omv petrom"],
    "rompetrol": ["rompetrol"],
    "avia": ["avia"],
    "tamoil": ["tamoil"],
    "q1": ["q1"],
    "star": ["star"],
    "hem": ["hem"],
    "migrol": ["migrol"],
    "agrola": ["agrola"],
    "coop": ["coop", "coop pronto"],
    "ip": ["ip", "ip italiana petroli", "italiana petroli"],
    "tango": ["tango"],
    "elan": ["elan"],
    "hoyer": ["hoyer"],
    "westfalen": ["westfalen"],
    "tesco": ["tesco", "tesco express"],
    "sainsburys": ["sainsburys", "sainsbury s", "sainsbury"],
    "asda": ["asda", "asda express"],
    "morrisons": ["morrisons"],
    "murco": ["murco"],
    "moto": ["moto"],
    "go on": ["go on", "goon"],
    "f24": ["f24"],
    "oil": ["oil", "oil express"],
    "monta": ["monta"],
    "euro oil": ["euro oil", "eurooil"],
}
_ALIASES: Dict[str, str] = {}
for _canon, _names in _ALIAS_SRC.items():
    _ALIASES[_canon] = _canon
    for _n in _names:
        _ALIASES[_n] = _canon
_MAX_ALIAS_TOKENS = max(len(k.split()) for k in _ALIASES)


def normalise_text(value: Any) -> str:
    """lower-case, strip accents and punctuation, collapse spaces."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def _alias_scan(tokens: List[str], first_only: bool) -> Optional[str]:
    positions = [0] if first_only else range(len(tokens))
    for i in positions:
        for n in range(min(_MAX_ALIAS_TOKENS, len(tokens) - i), 0, -1):
            cand = " ".join(tokens[i:i + n])
            if cand in _ALIASES:
                return _ALIASES[cand]
    return None


def canonical_brand(brand: Any, name: Any = None) -> str:
    """Canonical brand key ('' = unknown).  Falls back to the leading token(s) of ``name`` only when
    the brand field is empty/unknown and the name starts with a known brand alias."""
    nb = normalise_text(brand)
    if nb in _UNKNOWN_BRANDS:
        nb = ""
    if nb:
        hit = _alias_scan(nb.split(), first_only=False)
        if hit:
            return hit
        toks = [t for t in nb.split() if t not in _GENERIC_WORDS]
        return " ".join(toks) if toks else ""
    nn = normalise_text(name)
    if nn:
        return _alias_scan(nn.split(), first_only=True) or ""
    return ""


# --------------------------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------------------------


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class _Grid:
    """Uniform lat/lon grid; query() returns indices from the 3x3 neighbourhood (cell >= radius)."""

    def __init__(self, points: List[Tuple[float, float]], cell_m: float):
        self.points = points
        max_lat = max((abs(p[0]) for p in points), default=0.0)
        self.dlat = max(cell_m, 1.0) / 111320.0
        self.dlon = self.dlat / max(math.cos(math.radians(min(max_lat, 85.0))), 0.05)
        self.cells: Dict[Tuple[int, int], List[int]] = {}
        for i, (la, lo) in enumerate(points):
            self.cells.setdefault(self._key(la, lo), []).append(i)

    def _key(self, lat: float, lon: float) -> Tuple[int, int]:
        return (int(math.floor(lat / self.dlat)), int(math.floor(lon / self.dlon)))

    def query(self, lat: float, lon: float) -> List[int]:
        ky, kx = self._key(lat, lon)
        out: List[int] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out.extend(self.cells.get((ky + dy, kx + dx), ()))
        return out


# --------------------------------------------------------------------------------------------
# Timestamps
# --------------------------------------------------------------------------------------------


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --------------------------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------------------------


@dataclass
class _Cand:
    source_id: str
    priority: int
    kind: str
    price: Dict
    ts: Optional[datetime]


def _rel(a: float, b: float) -> float:
    lo = min(a, b)
    return abs(a - b) / lo if lo > 0 else float("inf")


def _valid_coord(st: dict) -> Optional[Tuple[float, float]]:
    try:
        lat, lon = float(st.get("lat")), float(st.get("lon"))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
        return None
    return lat, lon


class _Canon:
    """Working canonical station."""
    __slots__ = ("base", "lat", "lon", "brand", "cands", "sources", "merged", "has_price")

    def __init__(self, base: dict, lat: float, lon: float, brand: str):
        self.base = base
        self.lat, self.lon, self.brand = lat, lon, brand
        self.cands: Dict[str, List[_Cand]] = {}
        self.sources: List[str] = []
        self.merged = 0
        self.has_price = False


def _pair_radius(b1: str, b2: str, cfg: MergeConfig) -> Optional[float]:
    """Max distance at which two stations with these brands may be the same; None = incompatible."""
    if b1 and b2:
        return cfg.match_radius_m if b1 == b2 else None
    return cfg.unknown_brand_radius_m


def _clean_source_station(st: dict, res: SourceResult, cfg: MergeConfig, now: datetime,
                          rep: dict) -> Dict[str, _Cand]:
    """Per-bucket best price of one source record: bad prices dropped, future timestamps nulled,
    duplicates within a bucket reduced to the lower price."""
    out: Dict[str, _Cand] = {}
    horizon = now + timedelta(minutes=cfg.max_ts_future_min)
    for p in st.get("prices") or []:
        try:
            val = float(p.get("price"))
        except (TypeError, ValueError):
            rep["invalid_prices_dropped"] += 1
            continue
        if not math.isfinite(val) or val <= 0:
            rep["invalid_prices_dropped"] += 1
            continue
        b = bucket_of(p)
        if b is None:
            rep["invalid_prices_dropped"] += 1
            continue
        q = dict(p)
        q["price"] = val
        q["source"] = res.source_id
        ts = _parse_ts(q.get("updated_at"))
        if ts is not None and ts > horizon:
            q["updated_at"] = None
            ts = None
            rep["future_ts_nulled"] += 1
        cur = out.get(b)
        if cur is not None:
            rep["duplicate_prices_dropped"] += 1
            if val < cur.price["price"] or (val == cur.price["price"] and ts and not cur.ts):
                out[b] = _Cand(res.source_id, res.priority, res.kind, q, ts)
            continue
        out[b] = _Cand(res.source_id, res.priority, res.kind, q, ts)
    return out


def merge_sources(results: List[SourceResult], cfg: MergeConfig,
                  now: Optional[datetime] = None) -> Tuple[List[dict], dict]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    rep: Dict[str, Any] = {
        "country": cfg.country,
        "sources": {},
        "matched_pairs": 0,
        "ambiguous_skipped": 0,
        "conflicts": 0,
        "alt_values": 0,
        "outliers_dropped": 0,
        "regulated_fills": 0,
        "future_ts_nulled": 0,
        "duplicate_prices_dropped": 0,
        "invalid_prices_dropped": 0,
        "invalid_stations_dropped": 0,
        "geometry_dropped": 0,
        "final_station_count": 0,
        "priced_station_count": 0,
        "failed_sources": [],
    }

    usable: List[SourceResult] = []
    for r in results:
        rep["sources"][r.source_id] = {"name": r.name, "kind": r.kind, "priority": r.priority,
                                       "stations_in": len(r.stations or []), "stations_used": 0,
                                       "prices_contributed": 0, "prices_won": 0}
        if not r.ok:
            rep["failed_sources"].append({"source_id": r.source_id, "error": r.error})
        else:
            usable.append(r)
    order = sorted(usable, key=lambda r: (r.kind == "geometry", r.priority, r.source_id))

    canon: List[_Canon] = []
    used_ids = set()

    for res in order:
        srep = rep["sources"][res.source_id]
        # -- prepare batch ------------------------------------------------------------------
        batch: List[Tuple[dict, float, float, str, Dict[str, _Cand]]] = []
        for st in res.stations or []:
            xy = _valid_coord(st)
            if xy is None:
                rep["invalid_stations_dropped"] += 1
                continue
            cands = _clean_source_station(st, res, cfg, now, rep)
            srep["prices_contributed"] += len(cands)
            batch.append((st, xy[0], xy[1], canonical_brand(st.get("brand"), st.get("name")), cands))

        # -- candidate pairs against pre-batch canonical stations ----------------------------
        grid = _Grid([(c.lat, c.lon) for c in canon], max(cfg.match_radius_m, cfg.unknown_brand_radius_m))
        by_i: Dict[int, List[Tuple[float, int]]] = {}
        by_k: Dict[int, List[Tuple[float, int]]] = {}
        for i, (_st, lat, lon, brand, _c) in enumerate(batch):
            for k in grid.query(lat, lon):
                ck = canon[k]
                if res.source_id in ck.sources:
                    continue                      # a station never merges with two of one source
                rad = _pair_radius(brand, ck.brand, cfg)
                if rad is None:
                    continue
                d = haversine_m(lat, lon, ck.lat, ck.lon)
                if d <= rad:
                    by_i.setdefault(i, []).append((d, k))
                    by_k.setdefault(k, []).append((d, i))
        for lst in list(by_i.values()) + list(by_k.values()):
            lst.sort()

        def _ambiguous(lst: List[Tuple[float, int]]) -> bool:
            if len(lst) < 2:
                return False
            d1, d2 = lst[0][0], lst[1][0]
            return d2 < max(2 * d1, d1 + 15.0)

        match: Dict[int, int] = {}
        for i, lst in by_i.items():
            k = lst[0][1]
            if (_ambiguous(lst) or by_k[k][0][1] != i or _ambiguous(by_k[k])):
                rep["ambiguous_skipped"] += 1
                continue
            match[i] = k

        priced_idx = [j for j, c in enumerate(canon) if c.has_price]
        pgrid = None
        if res.kind == "geometry" and priced_idx:
            pgrid = (_Grid([(canon[j].lat, canon[j].lon) for j in priced_idx], cfg.match_radius_m), priced_idx)

        new_canon: List[_Canon] = []
        for i, (st, lat, lon, brand, cands) in enumerate(batch):
            if i in match:
                ck = canon[match[i]]
                ck.merged += 1
                rep["matched_pairs"] += 1
                for f in ("name", "brand", "address", "city"):
                    if not ck.base.get(f) and st.get(f):
                        ck.base[f] = st[f]
                if not ck.brand:
                    ck.brand = brand
            else:
                if pgrid is not None and i not in by_i:
                    g, idxs = pgrid
                    if any(haversine_m(lat, lon, canon[idxs[n]].lat, canon[idxs[n]].lon) <= cfg.match_radius_m
                           for n in g.query(lat, lon)):
                        rep["geometry_dropped"] += 1
                        continue
                elif pgrid is not None:
                    rep["geometry_dropped"] += 1       # geometry duplicate that could not be matched
                    continue
                base = copy.deepcopy({k: v for k, v in st.items() if k not in ("prices", "sources", "match")})
                sid = str(base.get("id", ""))
                if sid in used_ids:
                    base["id"] = f"{sid}~{res.source_id}"
                used_ids.add(str(base.get("id", "")))
                ck = _Canon(base, lat, lon, brand)
                new_canon.append(ck)
            ck.sources.append(res.source_id)
            for b, cand in cands.items():
                ck.cands.setdefault(b, []).append(cand)
                if cand.kind != "regulated_cap":
                    ck.has_price = True
            if cands and res.kind != "regulated_cap":
                ck.has_price = True
        canon.extend(new_canon)

    # -- select displayed price per bucket ----------------------------------------------------
    out: List[dict] = []
    final_pts: List[Tuple[_Canon, dict]] = []
    for ck in canon:
        st = ck.base
        st["sources"] = list(ck.sources)
        if ck.merged:
            st["match"] = {"merged": ck.merged}
        prices: List[dict] = []
        for b in sorted(ck.cands, key=_bucket_sort_key):
            pool = sorted(ck.cands[b], key=lambda c: (c.priority, c.source_id))
            normal = [c for c in pool if c.kind != "regulated_cap"]
            if not normal:
                win = pool[0]
                w = dict(win.price)
                w["basis"] = "regulated_max"
                rep["regulated_fills"] += 1
                prices.append(w)
                continue
            win = normal[0]
            if cfg.prefer_newer_timestamp:
                thr = timedelta(minutes=cfg.newer_by_minutes)
                for c in normal[1:]:
                    if c.ts and win.ts and c.ts - win.ts >= thr:
                        win = c
            w = dict(win.price)
            alts = []
            disagree = False
            for c in normal:
                if c is win or c.source_id == win.source_id:
                    continue
                if c.price.get("currency") != w.get("currency"):
                    continue
                r = _rel(w["price"], c.price["price"])
                if r >= cfg.alt_min_pct:
                    alts.append({"price": c.price["price"], "source": c.source_id,
                                 "updated_at": c.price.get("updated_at")})
                    if r >= cfg.conflict_abs_pct:
                        disagree = True
            if alts:
                w["alt"] = alts
                rep["alt_values"] += len(alts)
            if disagree:
                w["disagree"] = True
                rep["conflicts"] += 1
            prices.append(w)
        st["prices"] = prices
        out.append(st)
        final_pts.append((ck, st))

    # -- neighbour outlier filter -------------------------------------------------------------
    pts = [(ck.lat, ck.lon) for ck, _ in final_pts]
    if pts and cfg.outlier_min_neighbours > 0:
        grid = _Grid(pts, cfg.outlier_radius_km * 1000.0)
        radius_m = cfg.outlier_radius_km * 1000.0
        drops: List[Tuple[int, int]] = []
        for i, (ck, st) in enumerate(final_pts):
            near = [n for n in grid.query(ck.lat, ck.lon) if n != i
                    and haversine_m(ck.lat, ck.lon, pts[n][0], pts[n][1]) <= radius_m]
            if len(near) < cfg.outlier_min_neighbours:
                continue
            for pi, p in enumerate(st["prices"]):
                if p.get("basis") == "regulated_max":
                    continue
                b = bucket_of(p)
                vals = []
                for n in near:
                    for q in final_pts[n][1]["prices"]:
                        if (q.get("basis") != "regulated_max" and bucket_of(q) == b
                                and q.get("currency") == p.get("currency")):
                            vals.append(q["price"])
                if len(vals) < cfg.outlier_min_neighbours:
                    continue
                med = statistics.median(vals)
                if med > 0 and abs(p["price"] - med) / med > cfg.outlier_neighbour_pct:
                    drops.append((i, pi))
        for i, pi in sorted(drops, reverse=True):
            del final_pts[i][1]["prices"][pi]
            rep["outliers_dropped"] += 1

    # -- report -------------------------------------------------------------------------------
    for ck, st in final_pts:
        for sid in st["sources"]:
            rep["sources"][sid]["stations_used"] += 1
        for p in st["prices"]:
            sid = p.get("source")
            if sid in rep["sources"]:
                rep["sources"][sid]["prices_won"] += 1
    rep["final_station_count"] = len(out)
    rep["priced_station_count"] = sum(1 for s in out if s["prices"])
    return out, rep
