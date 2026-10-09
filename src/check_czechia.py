import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
"""Standalone live test: python -m src.check_czechia  (run from repo root) or python check_czechia.py from src."""
import asyncio, collections, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiohttp
from scrapers.czechia import CzechiaScraper


def coverage(st):
    n = len(st)
    def has(pred): return sum(1 for x in st if any(pred(p) for p in x["prices"]))
    from merge_engine import bucket_of
    return {"stations": n, "priced": sum(1 for x in st if x["prices"]),
            "with95": has(lambda p: bucket_of(p) == "95"), "withDiesel": has(lambda p: bucket_of(p) == "DIESEL"),
            "prices": sum(len(x["prices"]) for x in st),
            "with_ts": sum(1 for x in st for p in x["prices"] if p.get("updated_at"))}


def report(sc, st):
    print("coverage", coverage(st))
    rp = sc.merge_report
    print("merge report", {k: v for k, v in rp.items() if k != "sources"})
    for sid, s in rp["sources"].items(): print("  src", sid, s)


async def main():
    async with aiohttp.ClientSession() as s:
        sc = CzechiaScraper(s)
        st = await sc.fetch_stations()
    c = collections.Counter(p["fuel_type"] for x in st for p in x["prices"])
    srcs = collections.Counter(tuple(x["sources"]) for x in st)
    ts = sorted(p["updated_at"] for x in st for p in x["prices"] if p["updated_at"])
    report(sc, st)
    print("stations", len(st), "priced", sum(1 for x in st if x["prices"]))
    print("per fuel", dict(c)); print("by sources", dict(srcs))
    print("oldest/newest ts", ts[0] if ts else None, ts[-1] if ts else None)
    print("price sources", dict(collections.Counter(p["source"] for x in st for p in x["prices"])))
    print("BenzinMapa requests", CzechiaScraper.requests_made)
    ex = next((x for x in st if len(x["sources"]) > 1), None) or next(x for x in st if x["prices"])
    print(json.dumps(ex, ensure_ascii=False, indent=1))
asyncio.run(main())
