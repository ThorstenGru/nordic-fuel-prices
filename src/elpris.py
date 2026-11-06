"""Electricity prices (spot, SEK/kWh ex VAT) for SE1-SE4 -> data/elpris.json.  See docs/ELPRIS_PIPELINE.md.

Source: elprisetjustnu.se (ENTSO-E based, keyless, one JSON file per day and area).
Published file: today/tomorrow per area (hourly), monthly means per year, seasonal mean + band.
State is carried between runs through the previously PUBLISHED elpris.json (data/ is rebuilt on every
CI run), plus a committed seed of complete past months: src/seed/elpris_monthly.json
(create/refresh with: python src/elpris.py --backfill [YYYY-MM-DD]).

Monthly mean = equal weight per price row (hourly before 2025-10-01, 15 min after); this matches the
retailer "Medelspotpris" within 0.001 SEK/kWh.
"""
import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

ROOT = Path(__file__).parent.parent
OUT = ROOT / "data" / "elpris.json"
SEED = Path(__file__).parent / "seed" / "elpris_monthly.json"
API = "https://www.elprisetjustnu.se/api/v1/prices/{y}/{m:02d}-{d:02d}_{a}.json"
UA = {"User-Agent": "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"}
AREAS = ("SE1", "SE2", "SE3", "SE4")
SOURCE = "elprisetjustnu.se (ENTSO-E)"
MIN_ROWS, PRICE_MIN, PRICE_MAX = 20, -5.0, 50.0   # sanity band for a day file (SEK/kWh)
SEASON_YEARS = 4


# ── pure helpers (tested offline) ────────────────────────────────────────────

def _last_sunday(y: int, m: int) -> date:
    d = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def stockholm_today(now_utc: Optional[datetime] = None) -> date:
    """Local date in Sweden without tzdata (EU DST: last Sunday March 01:00 UTC .. last Sunday October 01:00 UTC)."""
    n = now_utc or datetime.now(timezone.utc)
    start = datetime.combine(_last_sunday(n.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(n.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return (n + timedelta(hours=2 if start <= n < end else 1)).date()


def parse_day(rows: Any) -> Optional[Dict[str, Any]]:
    """Validate one day file. Returns {"mean","n","hourly"} (hourly = mean per local clock hour) or None."""
    if not isinstance(rows, list) or len(rows) < MIN_ROWS:
        return None
    vals: List[float] = []
    hours: Dict[tuple, List[float]] = {}
    for r in rows:
        try:
            v, ts = float(r["SEK_per_kWh"]), r["time_start"]
        except (KeyError, TypeError, ValueError):
            return None
        if not PRICE_MIN <= v <= PRICE_MAX or not isinstance(ts, str) or len(ts) < 19:
            return None
        vals.append(v)
        hours.setdefault((ts[:13], ts[19:]), []).append(v)   # offset in the key keeps the DST fall-back hour apart
    return {"mean": sum(vals) / len(vals), "n": len(vals),
            "hourly": [round(sum(h) / len(h), 4) for h in hours.values()]}


def month_mean(days: Dict[str, List[float]], ym: str) -> Optional[Dict[str, Any]]:
    """days = {"YYYY-MM-DD": [mean, n]}. Returns {"mean","ndays","complete"} for month ym or None."""
    sel = [v for k, v in days.items() if k.startswith(ym)]
    if not sel:
        return None
    y, m = int(ym[:4]), int(ym[5:])
    dim = ((date(y + (m == 12), m % 12 + 1, 1)) - date(y, m, 1)).days
    n = sum(v[1] for v in sel)
    return {"mean": sum(v[0] * v[1] for v in sel) / n, "ndays": len(sel), "complete": len(sel) == dim}


def _pct(xs: List[float], p: float) -> float:
    xs = sorted(xs)
    i = (len(xs) - 1) * p
    lo = int(i)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (i - lo)


def seasonal(monthly: Dict[str, List[Optional[float]]], partial_ym: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Per calendar month: mean and low/high band over ONE fixed window of the latest SEASON_YEARS years present
    (the same years for every month, so a month the current year has not reached yet does not pull in the 2022 crisis year).
    Band = min/max with <4 values, 25th/75th percentile with 4+ (2022 was a crisis year, so min/max would be extreme)."""
    out: Dict[str, Dict[str, Any]] = {}
    window = sorted(monthly, reverse=True)[:SEASON_YEARS]
    for m in range(1, 13):
        vals = []
        for y in window:
            v = monthly[y][m - 1]
            if v is not None and f"{y}-{m:02d}" != partial_ym:
                vals.append(v)
        if not vals:
            continue
        lo, hi = (min(vals), max(vals)) if len(vals) < 4 else (_pct(vals, .25), _pct(vals, .75))
        out[str(m)] = {"mean": round(sum(vals) / len(vals), 4), "lo": round(lo, 4), "hi": round(hi, 4), "n": len(vals)}
    return out


def build_area(prev: Dict[str, Any], seed: Dict[str, List[Optional[float]]], today: date,
               today_day: Dict[str, Any], tomorrow_day: Optional[Dict[str, Any]],
               days: Dict[str, List[float]]) -> Dict[str, Any]:
    """Assemble one area block. `days` = per-day [mean, n] for the previous and current month (already merged)."""
    monthly: Dict[str, List[Optional[float]]] = {}
    for src in (prev.get("monthly") or {}, seed):         # seed last: complete past months in the seed always win, slot by slot
        for y, arr in src.items():
            cur = monthly.setdefault(y, [None] * 12)
            for i, v in enumerate(arr[:12]):
                if v is not None:
                    cur[i] = v
    keep = {f"{today.year}-{today.month:02d}", (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")}
    days = {k: v for k, v in days.items() if k[:7] in keep}
    partial = None
    for ym in sorted(keep):
        mm = month_mean(days, ym)
        if not mm:
            continue
        is_cur = ym == f"{today.year}-{today.month:02d}"
        if not (mm["complete"] or is_cur):
            continue                                       # an incomplete previous month never overwrites or enters the history
        monthly.setdefault(ym[:4], [None] * 12)[int(ym[5:]) - 1] = round(mm["mean"], 5)
        if is_cur and not mm["complete"]:
            partial = {"month": ym, "days": mm["ndays"]}
    tom = {"date": (today + timedelta(days=1)).isoformat(), "sek": tomorrow_day["hourly"]} if tomorrow_day else None
    return {"slot_min": 60, "today": {"date": today.isoformat(), "sek": today_day["hourly"]}, "tomorrow": tom,
            "monthly": dict(sorted(monthly.items())), "partial": partial,
            "seasonal": seasonal(monthly, partial["month"] if partial else None), "days": days}


# ── I/O ──────────────────────────────────────────────────────────────────────

async def fetch_day(session: aiohttp.ClientSession, sem: asyncio.Semaphore, area: str, d: date) -> Optional[Dict[str, Any]]:
    url = API.format(y=d.year, m=d.month, d=d.day, a=area)
    async with sem:
        for attempt in range(3):
            try:
                async with session.get(url, headers=UA, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    if r.status == 404:
                        return None                     # not published yet (or before history); never cached
                    if r.status == 200:
                        return parse_day(await r.json(content_type=None))
            except Exception as e:  # noqa: BLE001
                print(f"[elpris] {area} {d}: {type(e).__name__}: {e}")
            await asyncio.sleep(1 + attempt * 2)
    return None


async def fetch_prev(session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
    """Last published file: local data/elpris.json if present, else the live site (3 tries). {} = none exists yet, None = could not be read."""
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    from scrapers.geocoder import resolve_pages_base
    for attempt in range(3):
        try:
            base = await resolve_pages_base(session)
            async with session.get(f"{base}/elpris.json", headers={**UA, "Cache-Control": "no-cache"},
                                   timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status == 404:
                    return {}
                if r.status == 200:
                    return await r.json(content_type=None)
        except Exception as e:  # noqa: BLE001
            print(f"[elpris] no previous file (try {attempt + 1}): {type(e).__name__}: {e}")
        await asyncio.sleep(1 + attempt * 2)
    return None


def load_seed() -> Dict[str, Dict[str, List[Optional[float]]]]:
    try:
        return json.loads(SEED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


async def run() -> int:
    """Returns the number of areas refreshed. Never raises, never publishes an empty file."""
    today = stockholm_today()
    seed = load_seed()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=4)) as session:
        prev = await fetch_prev(session)
        if prev is None:
            print("[elpris] previous file unreadable: history is rebuilt from the seed and day files")
            prev = {}
        prev_areas = prev.get("areas") or {}
        sem = asyncio.Semaphore(4)
        month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        async def one(area: str) -> Optional[Dict[str, Any]]:
            pa = prev_areas.get(area) or {}
            days = {k: v for k, v in (pa.get("days") or {}).items()}
            want = [month_start + timedelta(days=i) for i in range((today - month_start).days + 1)]
            missing = [d for d in want if d.isoformat() not in days and d != today]
            res = await asyncio.gather(fetch_day(session, sem, area, today), fetch_day(session, sem, area, today + timedelta(days=1)),
                                       *(fetch_day(session, sem, area, d) for d in missing))
            if not res[0]:
                return None                             # keep last good block
            for d, r in zip(missing, res[2:]):
                if r:
                    days[d.isoformat()] = [round(r["mean"], 5), r["n"]]
            days[today.isoformat()] = [round(res[0]["mean"], 5), res[0]["n"]]   # today is re-derived every run, never frozen
            return build_area(pa, seed.get(area, {}), today, res[0], res[1], days)

        fresh = await asyncio.gather(*(one(a) for a in AREAS))
    areas = {a: (f or prev_areas.get(a)) for a, f in zip(AREAS, fresh)}
    areas = {a: v for a, v in areas.items() if v}
    n_ok = sum(1 for f in fresh if f)
    if not areas:
        print("[elpris] no data and no previous file: nothing published")
        return 0
    if n_ok:
        write_json(OUT, {"schema": 1, "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "source": SOURCE, "areas": areas})
    else:                                               # all fetches failed: republish the last good file unchanged
        write_json(OUT, prev)
    print(f"[elpris] refreshed {n_ok}/{len(AREAS)} areas, {OUT.stat().st_size} bytes")
    return n_ok


async def backfill(start: date) -> None:
    """One-off: monthly means for every complete month since `start` -> src/seed/elpris_monthly.json."""
    today = stockholm_today()
    end = today.replace(day=1) - timedelta(days=1)       # last complete month
    seed: Dict[str, Dict[str, List[Optional[float]]]] = {a: {} for a in AREAS}
    sem = asyncio.Semaphore(4)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=4)) as session:
        for a in AREAS:
            days: Dict[str, List[float]] = {}
            span = [start + timedelta(days=i) for i in range((end - start).days + 1)]
            for i in range(0, len(span), 40):
                chunk = span[i:i + 40]
                for d, r in zip(chunk, await asyncio.gather(*(fetch_day(session, sem, a, d) for d in chunk))):
                    if r:
                        days[d.isoformat()] = [r["mean"], r["n"]]
            for ym in sorted({k[:7] for k in days}):
                mm = month_mean(days, ym)
                if mm and mm["complete"]:
                    seed[a].setdefault(ym[:4], [None] * 12)[int(ym[5:]) - 1] = round(mm["mean"], 5)
            print(f"[backfill] {a}: {len(days)} days")
    write_json(SEED, seed)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        asyncio.run(backfill(date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2022, 1, 1)))
    else:
        asyncio.run(run())
