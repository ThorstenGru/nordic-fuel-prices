"""Price-cycle collector -> data/price_cycles.json.  See docs/PRICE_CYCLES.md.

After every run the national median price (EUR, meta.json countries[].stats_eur) is folded into a compact
grid per country and fuel: ISO weekday (0-6) x LOCAL hour (0-23) = 168 cells. A cell holds the running mean of
"median relative to the slow baseline, in percent" plus a sample count (capped, so old weeks fade out).
No raw snapshots and no station data are stored. State is carried through the previously PUBLISHED file
(data/ is rebuilt on every CI run); an unreadable or missing previous file never causes an empty publish.
"""
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "price_cycles.json"
META = ROOT / "data" / "meta.json"
UA = {"User-Agent": "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"}
FUELS = ("p95", "diesel")
BASE_ALPHA = 1 / 672        # slow baseline: ~one week of 15-minute runs
N_CAP = 20                  # samples per cell before the mean turns into an EMA (~5 weeks); rounding trap < 0.1 %
DEDUP_MIN = 5               # a re-run within 5 minutes of the last fold is ignored
MAX_AGE_MIN = 120           # a stale meta.json (main.py failed earlier) is not folded
LVL_UNIT, LVL_OFF = 0.01, 2048   # cell level: 0.01 % steps, +-20.47 %, 2 base-64 chars
BUDGET = 60_000
A64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
EMPTY = (A64[LVL_OFF >> 6] + A64[LVL_OFF & 63] + "A") * 168

# Standard-time UTC offset (hours). EU rule: summer time last Sunday March 01:00 UTC .. last Sunday October 01:00 UTC.
TZ = {**{c: 1 for c in "SE NO DK DE FR ES AD NL BE LU CH LI AT CZ SK PL HU IT MT SI HR BA ME RS MK AL XK".split()},
      **{c: 2 for c in "FI EE LV LT GR CY RO BG".split()}, "GB": 0, "IE": 0, "PT": 0}
NO_DST = {"IS": 0, "TR": 3}


# -- pure helpers (tested offline) ---------------------------------------------------------------

def _last_sunday(y: int, m: int) -> date:
    d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def local_slot(cc: str, now_utc: datetime) -> Optional[tuple]:
    """(ISO weekday 0-6, local hour 0-23) for a country, or None for an unknown country. No tzdata needed."""
    if cc in NO_DST:
        off = NO_DST[cc]
    elif cc in TZ:
        s = datetime.combine(_last_sunday(now_utc.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
        e = datetime.combine(_last_sunday(now_utc.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
        off = TZ[cc] + (1 if s <= now_utc < e else 0)
    else:
        return None
    t = now_utc + timedelta(hours=off)
    return t.weekday(), t.hour


def dec(cells: str, i: int) -> tuple:
    """(level %, n) of cell i."""
    c = cells[i * 3:i * 3 + 3]
    return ((A64.index(c[0]) << 6 | A64.index(c[1])) - LVL_OFF) * LVL_UNIT, A64.index(c[2])


def enc(lvl: float, n: int) -> str:
    v = max(0, min(4095, round(lvl / LVL_UNIT) + LVL_OFF))
    return A64[v >> 6] + A64[v & 63] + A64[n]


def fold(st: Optional[Dict[str, Any]], median: Any, now_utc: datetime, slot: tuple) -> Optional[Dict[str, Any]]:
    """Fold one median into a series state {"b": baseline, "t": iso time of last fold, "c": 168-cell string}.
    Returns the new state, the unchanged one for a duplicate run, or None if the median is unusable."""
    if not isinstance(median, (int, float)) or not 0.2 < median < 20:
        return None
    if not st or not isinstance(st.get("c"), str) or len(st["c"]) != 504 or not st.get("b"):
        st = {"b": round(median, 4), "t": "", "c": EMPTY}
    if st["t"]:
        try:
            gap = (now_utc - datetime.strptime(st["t"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)).total_seconds() / 60
        except ValueError:
            gap = 1e9
        if gap < DEDUP_MIN:           # same fetch seen again (or a clock going backwards): ignore
            return st
    base = st["b"]
    i = slot[0] * 24 + slot[1]
    lvl, n = dec(st["c"], i)
    x = max(-20.47, min(20.47, (median / base - 1) * 100))
    n = min(n + 1, N_CAP)
    cells = st["c"][:i * 3] + enc(lvl + (x - lvl) / n, n) + st["c"][i * 3 + 3:]
    return {"b": round(base + (median - base) * BASE_ALPHA, 4), "t": now_utc.strftime("%Y-%m-%dT%H:%MZ"), "c": cells}


def cheapest_windows(st: Optional[Dict[str, Any]], min_n: int = 8, width: int = 1, top: int = 3) -> List[Dict[str, Any]]:
    """Cheapest weekday/hour windows of one series: `width` consecutive local hours (wrapping inside the day),
    ranked by mean level (percent vs baseline, lower = cheaper). Windows with any cell below min_n samples are
    skipped, so a fresh file returns [] instead of noise. Each item: wd, hr, width, lvl, n (smallest cell count)."""
    c = st.get("c") if st else None
    if not isinstance(c, str) or len(c) != 504:
        return []
    out = []
    for wd in range(7):
        for hr in range(24):
            cells = [dec(c, wd * 24 + (hr + k) % 24) for k in range(width)]
            n = min(n for _, n in cells)
            if n < min_n:
                continue
            out.append({"wd": wd, "hr": hr, "width": width, "lvl": round(sum(lv for lv, _ in cells) / width, 2), "n": n})
    return sorted(out, key=lambda w: w["lvl"])[:top]


def build(prev: Dict[str, Any], meta: Dict[str, Any], now_utc: datetime) -> Optional[Dict[str, Any]]:
    """New file content, or None if nothing could be folded (caller then keeps the last good file).
    Each country is folded at ITS OWN meta fetched_at (when the data was really fetched), so a source that is only
    re-published between its refreshes adds nothing, and the hour slot is the hour the data came from."""
    series = {cc: {f: dict(s) for f, s in fs.items() if isinstance(s, dict)} for cc, fs in (prev.get("series") or {}).items()}
    folded = 0
    for c in meta.get("countries") or []:
        cc, stats = c.get("country"), c.get("stats_eur") or {}
        try:
            at = datetime.fromisoformat(str(c.get("fetched_at")).replace("Z", "+00:00"))
            at = (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        except ValueError:
            continue
        slot = local_slot(cc, at) if cc else None
        if not slot or c.get("status") != "ok":
            continue
        for f in FUELS:
            old = series.get(cc, {}).get(f)
            new = fold(old, (stats.get(f) or {}).get("median"), at, slot)
            if new:
                series.setdefault(cc, {})[f] = new
                folded += new is not old   # an unchanged state (same fetch seen again) is carried, not counted
    if not folded:
        return None
    return {"schema": 1, "updated": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), "series": series}


# -- I/O ----------------------------------------------------------------------------------------

async def fetch_prev(session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """Local data/price_cycles.json, else the live file. {} = none exists yet, None = could not be read."""
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    from scrapers.geocoder import PAGES_BASES
    # 404 only means "start fresh" when EVERY base says 404 on EVERY pass; a deploy gap or one bad base must not erase the history.
    clean_404 = True
    for attempt in range(3):
        for base in PAGES_BASES:
            try:
                async with session.get(f"{base}/price_cycles.json", headers={**UA, "Cache-Control": "no-cache"},
                                       timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
                    if r.status != 404:
                        clean_404 = False
            except Exception as e:  # noqa: BLE001
                clean_404 = False
                print(f"[price_cycles] no previous file ({base}, try {attempt + 1}): {type(e).__name__}: {e}")
        await asyncio.sleep(1 + attempt * 2)
    return {} if clean_404 else None


async def run() -> int:
    """Returns the number of series written. Never raises, never publishes an empty file, never restarts history blindly."""
    try:
        meta = json.loads(META.read_text(encoding="utf-8"))
        now = datetime.fromisoformat(str(meta["fetched_at"]).replace("Z", "+00:00"))
        now = (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (OSError, ValueError, KeyError):
        print("[price_cycles] no usable meta.json: nothing folded")
        return 0
    if (datetime.now(timezone.utc) - now).total_seconds() > MAX_AGE_MIN * 60:
        print("[price_cycles] meta.json is stale: nothing folded")
        return 0
    async with aiohttp.ClientSession() as session:
        prev = await fetch_prev(session)
    if prev is None:
        print("[price_cycles] previous file unreadable: not publishing (the workflow keeps the last good file)")
        return 0
    out = build(prev, meta, now)
    if not out:
        print("[price_cycles] nothing to fold")
        return 0
    txt = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if len(txt) > BUDGET:
        print(f"[price_cycles] {len(txt)} bytes exceeds the {BUDGET} budget: not publishing")
        return 0
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(txt, encoding="utf-8")
    tmp.replace(OUT)
    n = sum(len(v) for v in out["series"].values())
    print(f"[price_cycles] {n} series, {len(txt)} bytes")
    return n


if __name__ == "__main__":
    asyncio.run(run())
