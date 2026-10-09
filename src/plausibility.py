"""Price plausibility marking.

Prices that look wrong are NOT deleted: they are flagged on the price entry so the frontend can show
"not plausible" and keep them out of rankings, colours and statistics.

    price["plausible"] = False
    price["implausible_reason"] = "<code>"        # only present on flagged prices

Reasons
    outside_eur_band      absolute EUR/L (or /kg for CNG) band per fuel, using the ECB rate
    far_from_country      < 0.6x or > 1.6x the country's median for the same fuel group (>= 20 prices)
    inconsistent_fuels    the diesel/petrol ratio of one station is far from the country's usual ratio
                          and this is the price that deviates more from its own country median

    octane_order          98 priced below its own station's 95 (> 0.5 %; the older of the two when both are dated), or the whole 98 slot of one source
                          is priced < 1 % above those stations' 95 on >= 20 paired stations (a real 98 costs
                          3-10 % more: ANWB's mislabelled SE / SK / EE / GB petrol slots)

Regulated maxima (basis == "regulated_max") only face the absolute band: they are one number for a whole
country, so "far from the country median" is meaningless for them.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

# plausible EUR per litre (CNG: per kg) — deliberately wide: this catches broken data, not expensive stations
EUR_BANDS: Dict[str, tuple] = {
    "P95": (0.8, 3.4), "P98": (0.9, 3.6), "DIESEL": (0.8, 3.4), "LPG": (0.3, 1.9),
    "CNG": (0.6, 3.2), "E85": (0.5, 2.2), "HVO100": (1.0, 3.4),
}
LOW, HIGH = 0.6, 1.6            # relative to the country median of the same fuel group
MIN_GROUP = 20                  # prices needed before the median is trusted
RATIO_TOL = 0.30                # station diesel/petrol ratio may deviate this much from the country's ratio
MIN_RATIO_STATIONS = 30
DEVIATION_MIN = 0.10            # ...and the culprit must itself be at least this far from its group median


def fuel_group(p: Dict[str, Any]) -> Optional[str]:
    ft = p.get("fuel_type")
    if ft in ("E10", "E5", "95", "98"):
        try:
            o = int(p.get("octane") or 0)
        except (TypeError, ValueError):
            o = 0
        return "P98" if (o >= 97 or ft == "98") else "P95"
    return ft


def _station_price(p: Dict[str, Any]) -> bool:
    return p.get("basis") != "regulated_max" and p.get("plausible") is not False and bool(p.get("price"))


def _flag(p: Dict[str, Any], reason: str, counts: Dict[str, int]) -> None:
    if p.get("plausible") is False:
        return
    p["plausible"] = False
    p["implausible_reason"] = reason
    counts[reason] += 1


def mark_implausible(stations: List[Dict[str, Any]], currency: str, fx: Optional[Dict[str, float]] = None) -> Dict[str, int]:
    """Flag implausible prices in place. Returns {reason: count}."""
    counts: Dict[str, int] = defaultdict(int)
    rate = 1.0 if currency == "EUR" else (fx or {}).get(currency)

    # 1 — absolute EUR band
    if rate:
        for s in stations:
            for p in s.get("prices") or []:
                g = fuel_group(p)
                band = EUR_BANDS.get(g or "")
                v = p.get("price")
                if band and v and not (band[0] <= v / rate <= band[1]):
                    _flag(p, "outside_eur_band", counts)

    # 1b — octane order: 98 must cost more than 95 (station level, then whole source slot)
    pairs: Dict[Any, List[tuple]] = defaultdict(list)
    for s in stations:
        p95 = [p for p in s.get("prices") or [] if _station_price(p) and fuel_group(p) == "P95"]
        for p in s.get("prices") or []:
            if p95 and _station_price(p) and fuel_group(p) == "P98":
                pairs[p.get("source")].append((min(p95, key=lambda q: q["price"]), p))
    for lst in pairs.values():
        slot_bad = len(lst) >= MIN_GROUP and statistics.median(b["price"] / a["price"] for a, b in lst) < 1.01
        for a, b in lst:
            if slot_bad or b["price"] < a["price"] * 0.995:
                # both timestamped and the 98 is the newer one: the 95 is the stale side
                stale95 = not slot_bad and a.get("updated_at") and b.get("updated_at") and a["updated_at"] < b["updated_at"]
                _flag(a if stale95 else b, "octane_order", counts)

    # 2 — far from the country median of the same fuel group (station prices only)
    groups: Dict[str, List[float]] = defaultdict(list)
    for s in stations:
        for p in s.get("prices") or []:
            if p.get("basis") == "regulated_max" or p.get("plausible") is False or not p.get("price"):
                continue
            g = fuel_group(p)
            if g:
                groups[g].append(p["price"])
    med = {g: statistics.median(v) for g, v in groups.items() if len(v) >= MIN_GROUP}
    for s in stations:
        for p in s.get("prices") or []:
            if p.get("basis") == "regulated_max" or p.get("plausible") is False or not p.get("price"):
                continue
            m = med.get(fuel_group(p) or "")
            if m and not (m * LOW <= p["price"] <= m * HIGH):
                _flag(p, "far_from_country", counts)

    # 2b — a source's whole 98 slot priced below the country's 95 median (too few same-station pairs for 1b)
    if "P95" in med:
        by_src: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
        for s in stations:
            for p in s.get("prices") or []:
                if _station_price(p) and fuel_group(p) == "P98":
                    by_src[p.get("source")].append(p)
        for lst in by_src.values():
            if len(lst) >= MIN_GROUP and statistics.median(p["price"] for p in lst) < med["P95"]:
                for p in lst:
                    _flag(p, "octane_order", counts)

    # 3 — a station's diesel/petrol ratio vs the country's usual ratio
    ratios = []
    for s in stations:
        pp = _pair(s)
        if pp:
            ratios.append(pp[1]["price"] / pp[0]["price"])
    if len(ratios) >= MIN_RATIO_STATIONS and "P95" in med and "DIESEL" in med:
        r0 = statistics.median(ratios)
        for s in stations:
            pp = _pair(s)
            if not pp:
                continue
            pet, dsl = pp
            r = dsl["price"] / pet["price"]
            if abs(r / r0 - 1) <= RATIO_TOL:
                continue
            dp = abs(pet["price"] / med["P95"] - 1)
            dd = abs(dsl["price"] / med["DIESEL"] - 1)
            culprit = pet if dp >= dd else dsl
            if max(dp, dd) >= DEVIATION_MIN:
                _flag(culprit, "inconsistent_fuels", counts)
    return dict(counts)


def _pair(s: Dict[str, Any]):
    """(cheapest plausible petrol-95 price, cheapest plausible diesel price) of one station, or None."""
    pet = dsl = None
    for p in s.get("prices") or []:
        if p.get("basis") == "regulated_max" or p.get("plausible") is False or not p.get("price"):
            continue
        g = fuel_group(p)
        if g == "P95" and (pet is None or p["price"] < pet["price"]):
            pet = p
        elif g == "DIESEL" and (dsl is None or p["price"] < dsl["price"]):
            dsl = p
    return (pet, dsl) if pet and dsl else None
