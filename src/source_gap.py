"""Neutral source-gap report: how much do two sources differ on the SAME station? Never changes a price.

Only stations where the sources differ by >= alt_min_pct (2%) carry an 'alt' entry, so this is the gap AMONG
DIFFERING stations; stations where sources agree are not counted (no denominator here). 'n' = differing pairs.
Alt readings are not plausibility-flagged by the pipeline, so a ratio guard drops gross outliers (mislabelled slots).
"""
import statistics
from collections import defaultdict
from typing import Any, Dict, List

MIN_PAIRS = 30
MAX_RATIO = 2.0  # alt/primary outside 1/2..2 is treated as a mislabelled reading, not a source gap


def _bucket(p: Dict[str, Any]):
    ft = p.get("fuel_type")
    if ft in ("E10", "E5", "95", "98"):
        return "p95" if int(p.get("octane") or (98 if ft == "98" else 95)) == 95 else None
    return "diesel" if ft == "DIESEL" else None


def source_gap(stations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Median of other/primary-1 (percent) among differing stations per (fuel, primary, other), n >= 30."""
    pairs = defaultdict(list)
    for s in stations:
        for p in s.get("prices") or []:
            b = _bucket(p)
            if not b or p.get("basis") == "regulated_max" or p.get("plausible") is False:
                continue
            if not p.get("price") or not p.get("source"):
                continue
            for a in p.get("alt") or []:
                if not a.get("price") or not a.get("source") or not 1 / MAX_RATIO <= a["price"] / p["price"] <= MAX_RATIO:
                    continue
                pairs[(b, p["source"], a["source"])].append(a["price"] / p["price"] - 1)
    out = [{"fuel": f, "primary": pr, "other": ot, "n": len(v), "median_pct": round(statistics.median(v) * 100, 1)}
           for (f, pr, ot), v in sorted(pairs.items()) if len(v) >= MIN_PAIRS]
    return out
