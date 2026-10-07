"""Standalone live check of the UK scraper on the shared merge engine (network required)."""
import asyncio, sys, os, collections
sys.path.insert(0, os.path.dirname(__file__))
import aiohttp
from scrapers.united_kingdom import UnitedKingdomScraper
from merge_engine import bucket_of


async def main():
    async with aiohttp.ClientSession() as s:
        sc = UnitedKingdomScraper(s)
        st = await sc.fetch_stations()
    rep = sc.merge_report
    pr = [p for x in st for p in x["prices"]]
    print("report", {k: v for k, v in rep.items() if k != "sources"})
    for sid, v in rep["sources"].items():
        print("  source", sid, v)
    print("stations", len(st), "priced", sum(1 for x in st if x["prices"]), "prices", len(pr))
    print("buckets", dict(collections.Counter(bucket_of(p) for p in pr)))
    print("currencies", dict(collections.Counter(p["currency"] for p in pr)))
    print("timestamped", sum(1 for p in pr if p["updated_at"]), "/", len(pr))
    print("alt", sum(1 for p in pr if p.get("alt")), "disagree", sum(1 for p in pr if p.get("disagree")))
    print("station sources", dict(collections.Counter(tuple(x["sources"]) for x in st).most_common(8)))
    assert {p["currency"] for p in pr} == {"GBP"}
    assert not any(p["fuel_type"] == "95" for p in pr), "ANWB 95 must be relabelled E5@97"
    print("merged example", next((x for x in st if len(x["sources"]) > 1), None))

asyncio.run(main())
