"""Standalone live test: python -m src.test_czechia  (run from repo root) or python test_czechia.py from src."""
import asyncio, collections, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiohttp
from scrapers.czechia import CzechiaScraper


async def main():
    async with aiohttp.ClientSession() as s:
        sc = CzechiaScraper(s)
        st = await sc.fetch_stations()
    c = collections.Counter(p["fuel_type"] for x in st for p in x["prices"])
    srcs = collections.Counter(tuple(x["sources"]) for x in st)
    ts = sorted(p["updated_at"] for x in st for p in x["prices"] if p["updated_at"])
    print("stations", len(st), "priced", sum(1 for x in st if x["prices"]))
    print("per fuel", dict(c)); print("by sources", dict(srcs))
    print("oldest/newest ts", ts[0] if ts else None, ts[-1] if ts else None)
    print("price sources", dict(collections.Counter(p["source"] for x in st for p in x["prices"])))
    print("BenzinMapa requests", CzechiaScraper.requests_made)
    ex = next((x for x in st if len(x["sources"]) > 1), None) or next(x for x in st if x["prices"])
    print(json.dumps(ex, ensure_ascii=False, indent=1))
asyncio.run(main())
