"""EuroFuelPrices scrape pipeline.

For every country scraper:  fetch -> validate/clean -> decide (fresh | keep last good) -> publish.

Reliability rules (the product lives on its data):
  * A failing / empty / suddenly-shrunken scraper NEVER overwrites good data. The last
    published file is kept, marked ``status: "stale"`` with ``stale_since`` and the error.
  * ``fetched_at`` of a country is when its data was REALLY fetched (stays old while stale).
  * Price entries keep ``updated_at`` = source time (null when the source gives none).
  * ``health.json`` records per-source status, counts, age and errors for the admin page.
"""

import asyncio
import json
import os
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from scrapers import ALL_SCRAPERS
from scrapers.geocoder import resolve_pages_base

OUTPUT_DIR = Path(__file__).parent.parent / "data"
SCRAPER_TIMEOUT_S = int(os.environ.get("SCRAPER_TIMEOUT_S", "900"))
MIN_KEEP_RATIO = 0.6          # new result smaller than 60 % of the last good one => suspicious
SCHEMA_VERSION = 2          # JSON layout; app release version lives in /VERSION (see below)
try:
    APP_VERSION = (Path(__file__).parent.parent / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    APP_VERSION = "unknown"
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "0") == "1"

# Sanity band per currency (min, max) for ONE unit (litre / kg). Anything outside is a
# currency/unit error or a parsing glitch and is dropped (and counted in health.json).
PRICE_BANDS: Dict[str, Tuple[float, float]] = {
    "EUR": (0.4, 4.5), "SEK": (8, 40), "NOK": (8, 40), "DKK": (5, 35), "CZK": (15, 90),
    "PLN": (3, 16), "HUF": (250, 1200), "CHF": (0.9, 3.8), "ISK": (150, 500), "RON": (3, 16),
    "BAM": (1, 5), "RSD": (100, 400), "ALL": (100, 300), "MKD": (40, 150), "MDL": (10, 50),
    "GBP": (0.9, 3.0), "BGN": (0.8, 4.0),
}
BAND_EXEMPT_FUELS = {"H2"}    # hydrogen is priced far above the litre bands

# Rough lat/lon envelope of Europe (+ Iceland, Cyprus, Canaries); anything outside is bad data.
EUROPE_BOUNDS = (26.0, 72.0, -32.0, 46.0)  # min_lat, max_lat, min_lon, max_lon


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ── cleaning / validation ────────────────────────────────────────────────────

def clean_stations(stations: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    dropped = Counter()
    future_limit = datetime.now(timezone.utc).timestamp() + 600   # >10 min ahead = bad source clock/zone
    out: Dict[str, Dict[str, Any]] = {}
    for s in stations or []:
        if not isinstance(s, dict):
            dropped["not_a_dict"] += 1
            continue
        lat, lon = s.get("lat"), s.get("lon")
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            dropped["no_coords"] += 1
            continue
        if not (EUROPE_BOUNDS[0] <= lat <= EUROPE_BOUNDS[1] and EUROPE_BOUNDS[2] <= lon <= EUROPE_BOUNDS[3]):
            dropped["coords_outside_europe"] += 1
            continue
        s["lat"], s["lon"] = round(lat, 6), round(lon, 6)

        good_prices = []
        for p in s.get("prices") or []:
            try:
                val = float(p.get("price"))
            except (TypeError, ValueError):
                dropped["price_unparsable"] += 1
                continue
            band = PRICE_BANDS.get(p.get("currency", ""))
            if val <= 0 or (band and p.get("fuel_type") not in BAND_EXEMPT_FUELS
                            and not (band[0] <= val <= band[1])):
                dropped["price_outlier"] += 1
                continue
            p["price"] = round(val, 3)
            ts = parse_iso(p.get("updated_at"))
            if ts and ts.timestamp() > future_limit:
                p["updated_at"] = None            # never publish a timestamp from the future
                dropped["future_timestamp"] += 1
            good_prices.append(p)
        s["prices"] = good_prices

        sid = s.get("id") or f"{s.get('country', '')}_{lat}_{lon}"
        s["id"] = sid
        prev = out.get(sid)
        if prev is None:
            out[sid] = s
        else:
            dropped["duplicate_id"] += 1
            if len(s["prices"]) > len(prev["prices"]):
                out[sid] = s
    return list(out.values()), dict(dropped)


def summarize(stations: List[Dict[str, Any]], fallback_currency: str) -> Dict[str, Any]:
    priced = [s for s in stations if s["prices"]]
    entries = [p for s in priced for p in s["prices"]]
    ts = [parse_iso(p.get("updated_at")) for p in entries]
    ts = [t for t in ts if t]
    currencies = Counter(p.get("currency") for p in entries if p.get("currency"))
    return {
        "station_count": len(stations),
        "priced_count": len(priced),
        "price_entries": len(entries),
        "currency": currencies.most_common(1)[0][0] if currencies else fallback_currency,
        "with_timestamp_pct": round(100 * len(ts) / len(entries), 1) if entries else 0.0,
        "newest_price_at": max(ts).isoformat() if ts else None,
        "oldest_price_at": min(ts).isoformat() if ts else None,
    }


# ── I/O helpers ──────────────────────────────────────────────────────────────

async def fetch_json(session: aiohttp.ClientSession, url: str, timeout: int = 60) -> Optional[Any]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                               headers={"Cache-Control": "no-cache"}) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except Exception as e:
        print(f"[prev] {url}: {e}")
    return None


def write_json(path: Path, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


# ── per-country run ──────────────────────────────────────────────────────────

async def run_one(scraper_cls, session: aiohttp.ClientSession, prev_meta: Dict[str, Dict]) -> Dict[str, Any]:
    cc = scraper_cls.COUNTRY
    started = time.monotonic()

    # Per-source cadence: a source refreshed recently is re-published unchanged (no upstream call).
    last = prev_meta.get(cc) or {}
    fetched = parse_iso(last.get("fetched_at"))
    if (not FORCE_REFRESH and fetched and last.get("status") == "ok"
            and (datetime.now(timezone.utc) - fetched).total_seconds() / 60 < scraper_cls.REFRESH_MINUTES * 0.9):
        base = await resolve_pages_base(session)
        old = await fetch_json(session, f"{base}/{cc.lower()}.json")
        if old and old.get("stations"):
            write_json(OUTPUT_DIR / f"{cc.lower()}.json", old)
            print(f"[{cc}] re-published (refreshed {int((datetime.now(timezone.utc) - fetched).total_seconds() / 60)} min ago, "
                  f"cadence {scraper_cls.REFRESH_MINUTES} min)")
            return {"cc": cc, "meta": old["meta"], "health": {"seconds": 0, "skipped": True, **{k: v for k, v in old["meta"].items() if k != "country"}}}
    error: Optional[str] = None
    stations: List[Dict[str, Any]] = []
    scraper = scraper_cls(session)
    try:
        stations = await asyncio.wait_for(scraper.fetch_stations(), timeout=SCRAPER_TIMEOUT_S)
    except asyncio.TimeoutError:
        error = f"timeout after {SCRAPER_TIMEOUT_S}s"
    except Exception as e:  # noqa: BLE001 — a scraper must never take the pipeline down
        error = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    stations = stations or []

    clean, dropped = clean_stations(stations)
    summ = summarize(clean, scraper_cls.CURRENCY)
    prev = prev_meta.get(cc) or {}
    prev_count = int(prev.get("station_count") or 0)
    prev_priced = int(prev.get("priced_count") or 0)

    reason: Optional[str] = None
    if error:
        reason = error
    elif not clean:
        reason = "scraper returned 0 usable stations"
    elif prev_count >= 20 and summ["station_count"] < prev_count * MIN_KEEP_RATIO:
        reason = f"station count regressed {prev_count} -> {summ['station_count']}"
    elif prev_priced >= 50 and summ["priced_count"] < prev_priced * 0.5:
        reason = f"priced stations regressed {prev_priced} -> {summ['priced_count']}"

    meta: Dict[str, Any] = {
        "country": cc,
        "currency": summ["currency"],
        "source": scraper.SOURCE,
        # DEPRECATED (D5): grade/confidence stay for one more release, then are replaced by the
        # descriptive provenance in meta.sources / health.merge and per-price source/alt/basis.
        "grade": getattr(scraper, "GRADE", "C"),
        "confidence": scraper.CONFIDENCE,
        "fetched_at": scraper.fetched_at,
        "status": "ok",
        **{k: summ[k] for k in ("station_count", "priced_count", "price_entries",
                                "with_timestamp_pct", "newest_price_at", "oldest_price_at")},
    }
    health: Dict[str, Any] = {"seconds": round(time.monotonic() - started, 1), "dropped": dropped, "error": error}
    # Provenance from the merge engine (optional; scrapers not yet migrated simply have none).
    report = getattr(scraper, "merge_report", None)
    if isinstance(report, dict) and report:
        srcs = report.get("sources")
        compact = []
        if isinstance(srcs, dict):
            for sid, v in srcs.items():
                v = v if isinstance(v, dict) else {}
                e: Dict[str, Any] = {"id": sid, "stations_used": v.get("stations_used", 0),
                                     "prices_won": v.get("prices_won", 0)}
                if v.get("name"):
                    e["name"] = v["name"]
                compact.append(e)
        elif isinstance(srcs, list):
            compact = [{k: v.get(k) for k in ("id", "name", "stations_used", "prices_won") if k in v}
                       for v in srcs if isinstance(v, dict)]
        if compact:
            meta["sources"] = compact
        health["merge"] = report

    if reason:
        base = await resolve_pages_base(session)
        old = await fetch_json(session, f"{base}/{cc.lower()}.json")
        old_stations = (old or {}).get("stations") or []
        if old_stations:
            old_meta = old.get("meta", {})
            meta.update({k: v for k, v in old_meta.items() if k in (
                "currency", "source", "grade", "confidence", "fetched_at", "station_count", "priced_count",
                "price_entries", "with_timestamp_pct", "newest_price_at", "oldest_price_at")})
            meta["status"] = "stale"
            meta["stale_since"] = old_meta.get("stale_since") or old_meta.get("fetched_at") or now_iso()
            meta["last_error"] = reason
            meta["last_attempt_at"] = now_iso()
            meta.setdefault("station_count", len(old_stations))
            clean = old_stations
            print(f"[{cc}] KEEPING LAST GOOD ({len(old_stations)} stations) — {reason}")
        else:
            meta["status"] = "failed"
            meta["last_error"] = reason
            print(f"[{cc}] FAILED and no previous data — {reason}")
    else:
        print(f"[{cc}] {summ['station_count']} stations, {summ['priced_count']} priced "
              f"({summ['with_timestamp_pct']}% with source timestamps)"
              + (f"  dropped={dropped}" if dropped else ""))

    write_json(OUTPUT_DIR / f"{cc.lower()}.json", {"meta": meta, "stations": clean})
    health.update({k: v for k, v in meta.items() if k != "country"})
    return {"cc": cc, "meta": meta, "health": health}


# ── main ─────────────────────────────────────────────────────────────────────

async def run_all() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    t0 = time.monotonic()
    connector = aiohttp.TCPConnector(limit=60, limit_per_host=12)
    async with aiohttp.ClientSession(connector=connector) as session:
        base = await resolve_pages_base(session)
        prev = await fetch_json(session, f"{base}/meta.json", timeout=30) or {}
        prev_meta = {c["country"]: c for c in prev.get("countries", []) if isinstance(c, dict) and "country" in c}
        results = await asyncio.gather(*(run_one(sc, session, prev_meta) for sc in ALL_SCRAPERS))

    generated = now_iso()
    metas = [r["meta"] for r in results]
    total = sum(m["station_count"] for m in metas)
    priced = sum(m.get("priced_count", 0) for m in metas)
    status_counts = Counter(m["status"] for m in metas)
    failed_src_countries = sum(1 for r in results if (r["health"].get("merge") or {}).get("failed_sources"))

    write_json(OUTPUT_DIR / "meta.json", {
        "schema": SCHEMA_VERSION,
        "version": APP_VERSION,
        "fetched_at": generated,
        "total_stations": total,
        "total_priced": priced,
        "countries": metas,
    })
    write_json(OUTPUT_DIR / "health.json", {
        "schema": SCHEMA_VERSION,
        "version": APP_VERSION,
        "generated_at": generated,
        "run_seconds": round(time.monotonic() - t0, 1),
        "totals": {"stations": total, "priced": priced, "countries": len(metas),
                   "countries_with_failed_sources": failed_src_countries, **dict(status_counts)},
        "countries": {r["cc"]: r["health"] for r in results},
    })

    print(f"\nDone in {time.monotonic() - t0:.0f}s — {total} stations ({priced} priced) | "
          + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())))
    bad = [r["cc"] for r in results if r["meta"]["status"] != "ok"]
    if bad:
        print(f"::warning::Sources not fresh this run: {', '.join(bad)}")


if __name__ == "__main__":
    asyncio.run(run_all())
