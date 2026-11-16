"""Flag ANWB prices that are a chain's list price, not a station price.

In several countries ANWB gives ONE price per chain: dozens of stations of a brand show exactly the same number (Sweden: every St1 21.593 SEK,
while the crowd source has 20.39-21.29 at the same stations). Such a price is fine for "which chain is cheaper" but not for "which station near me".
A station gets ``chain_price = True`` when one of its ANWB prices (no timestamp, source anwb) is the brand's most common price for that fuel and at least
MIN_SHARE of the brand's >= MIN_STATIONS stations carry it. Stations whose price differs from the common one are left alone. Prices with a timestamp
or from another source are never touched.

    python src/chain_price.py DATA_DIR      # prints the share per country (data/*.json)
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

MIN_STATIONS = 15
MIN_SHARE = 0.5


def _bucket(p: Dict) -> Optional[str]:
    ft = p.get("fuel_type")
    if ft == "DIESEL":
        return "D"
    if ft in ("95", "E5", "E10") and int(p.get("octane") or 95) == 95:
        return "P"
    return None


def _is_anwb(p: Dict, st: Dict) -> bool:
    if p.get("updated_at") or p.get("checked_at"):
        return False
    src = p.get("source") or st.get("source") or ""
    return "anwb" in str(src).lower()


def flag_chain_prices(stations: List[Dict[str, Any]]) -> int:
    """Set/clear station["chain_price"]; returns the number of flagged stations."""
    groups: Dict[tuple, List[tuple]] = defaultdict(list)
    for s in stations:
        s.pop("chain_price", None)
        brand = (s.get("brand") or "").strip().upper()
        if not brand:
            continue
        for p in s.get("prices") or []:
            b = _bucket(p)
            if b and _is_anwb(p, s) and p.get("price"):
                groups[(brand, b)].append((s, round(p["price"], 3)))
    n = 0
    for members in groups.values():
        if len(members) < MIN_STATIONS:
            continue
        price, cnt = Counter(v for _, v in members).most_common(1)[0]
        if cnt / len(members) < MIN_SHARE:
            continue
        for s, v in members:
            if v == price and not s.get("chain_price"):
                s["chain_price"] = True
                n += 1
    return n


if __name__ == "__main__":
    d = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    print("country  anwb-priced stations  flagged  share")
    for f in sorted(d.glob("??.json")):
        try:
            st = json.loads(f.read_text(encoding="utf-8")).get("stations") or []
        except (OSError, ValueError, AttributeError):
            continue
        base = sum(1 for s in st if any(_is_anwb(p, s) and _bucket(p) for p in s.get("prices") or []))
        if base:
            n = flag_chain_prices(st)
            print(f"{f.stem.upper():7s}  {base:6d}  {n:6d}  {100 * n / base:4.0f}%")
