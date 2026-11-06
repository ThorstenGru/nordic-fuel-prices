"""Per-country data checks for sources without timestamps (first enabled for DE / ANWB). Never changes a price.

* track_changes: per-station ``pc`` (last price change, epoch MINUTES, int) carried from the previous published
  file; ``ps: 1`` when unchanged for more than STALE_H hours. Previous state = previous published <cc>.json.
* quality_report: band / E10-vs-E5 / duplicate counts for meta.json (``meta["checks"]``).
* median_jump: national median vs the previous run (prev meta.stats_eur), alert only.
"""
from collections import Counter
from typing import Any, Dict, List, Optional

from plausibility import fuel_group

STALE_H = 48
BAND = (1.0, 3.5)             # EUR; report-only (plausibility.py flags the wider 0.8-3.4 bands)
BAND_GROUPS = ("P95", "P98", "DIESEL")   # LPG / CNG / E85 legitimately sit below 1.0
E10_TOL = 1.005               # E10 above E5 x1.005 at one station is suspicious
MIN_PAIRS = 30
JUMP_PCT = 3.0                # median moving > 3 % between two runs (<= 30 min apart) is not market movement


def _sig(s: Dict[str, Any]) -> tuple:
    return tuple(sorted((p.get("fuel_type") or "", p.get("octane") or 0, p.get("price") or 0) for p in s.get("prices") or []))


def track_changes(stations: List[Dict[str, Any]], prev: Optional[List[Dict[str, Any]]], now_min: int,
                  stale_h: int = STALE_H) -> Dict[str, int]:
    """Set s['pc'] / s['ps'] in place. New stations start at now (true age unknown), so nothing can be
    flagged before STALE_H hours of observation."""
    old = {s.get("id"): s for s in prev or []}
    n = Counter()
    for s in stations:
        o = old.get(s.get("id"))
        pc = now_min
        if o is not None and isinstance(o.get("pc"), int):
            pc = o["pc"] if _sig(o) == _sig(s) else now_min
        else:
            n["new"] += 1
        s["pc"] = pc
        s.pop("ps", None)
        if now_min - pc > stale_h * 60 and s.get("prices"):
            s["ps"] = 1
            n["stale"] += 1
    return dict(n)


def quality_report(stations: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    band: Counter = Counter()
    pairs = bad = 0
    keys: Counter = Counter()
    stale = priced = 0
    for s in stations:
        e5 = e10 = None
        for p in s.get("prices") or []:
            v = p.get("price")
            if not v or p.get("basis") == "regulated_max":
                continue
            g = fuel_group(p)
            if g in BAND_GROUPS and not BAND[0] <= v <= BAND[1]:
                band[g] += 1
            if p.get("fuel_type") == "E5" and int(p.get("octane") or 95) == 95:
                e5 = v if e5 is None else min(e5, v)
            elif p.get("fuel_type") == "E10":
                e10 = v if e10 is None else min(e10, v)
        if e5 and e10:
            pairs += 1
            bad += e10 > e5 * E10_TOL
        if s.get("prices"):
            priced += 1
            stale += bool(s.get("ps"))
        try:
            keys[(round(float(s["lat"]), 4), round(float(s["lon"]), 4), (s.get("brand") or s.get("name") or "").strip().lower())] += 1
        except (KeyError, TypeError, ValueError):
            pass
    if any("pc" in s for s in stations[:50]) and priced:
        out["stale48_n"] = stale
        out["stale48_pct"] = round(100 * stale / priced, 1)
    if band:
        out["band_out"] = dict(band)
    if pairs >= MIN_PAIRS:
        out["e10_gt_e5"] = {"n": pairs, "pct": round(100 * bad / pairs, 1)}
    dup = sum(c - 1 for c in keys.values() if c > 1)
    if dup:
        out["dup_n"] = dup
    return out


def median_jump(stats: Optional[Dict[str, Any]], prev_stats: Optional[Dict[str, Any]],
                thr: float = JUMP_PCT) -> List[Dict[str, Any]]:
    res = []
    for k, v in (stats or {}).items():
        a, b = (prev_stats or {}).get(k, {}).get("median"), v.get("median")
        if a and b and abs(b / a - 1) * 100 > thr:
            res.append({"fuel": k, "prev": a, "now": b, "pct": round((b / a - 1) * 100, 1)})
    return res
