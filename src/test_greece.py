import sys, asyncio, collections, json
sys.path.insert(0, ".")
import aiohttp
import scrapers.greece as G, os
if os.environ.get("GR_TEST_BUDGET"): G.FPEU_MAX_REQUESTS = int(os.environ["GR_TEST_BUDGET"])
from scrapers.greece import GreeceScraper


async def main():
    async with aiohttp.ClientSession() as s:
        sc = GreeceScraper(s)
        st = await sc.fetch_stations()
    priced = [x for x in st if x["prices"]]
    print("stations", len(st), "priced", len(priced), "stats", sc.stats)
    print("fuels", collections.Counter(p["fuel_type"] for x in st for p in x["prices"]))
    print("price by source", collections.Counter(p["source"] for x in st for p in x["prices"]))
    print("station sources", collections.Counter("+".join(x["sources"]) for x in st))
    ts = sorted(p["updated_at"] for x in st for p in x["prices"] if p.get("updated_at"))
    print("ts newest", ts[-1] if ts else None, "oldest", ts[0] if ts else None,
          "with_ts", len(ts), "of", sum(len(x["prices"]) for x in st))
    print("ids unique", len({x["id"] for x in st}) == len(st), "fpeu requests", sc.requests_made)
    multi = [x for x in st if len(x["sources"]) > 1 and any(p["source"] != x["sources"][0] for p in x["prices"])]
    print(json.dumps((multi or st)[0], ensure_ascii=False, indent=1))
    print("lat", min(x["lat"] for x in st), max(x["lat"] for x in st),
          "lon", min(x["lon"] for x in st), max(x["lon"] for x in st))
    json.dump(st, open("gr_test_out.json", "w", encoding="utf8"), ensure_ascii=False)

asyncio.run(main())
