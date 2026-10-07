import asyncio, sys, os, collections
sys.path.insert(0, os.path.dirname(__file__))
import aiohttp
from scrapers.united_kingdom import UnitedKingdomScraper


async def main():
    async with aiohttp.ClientSession() as s:
        sc = UnitedKingdomScraper(s)
        st = await sc.fetch_stations()
    print(sc.merge_stats)
    print("entries by source", dict(collections.Counter(p["source"] for x in st for p in x["prices"])),
          "currencies", dict(collections.Counter(p["currency"] for x in st for p in x["prices"])))
    ts = sum(1 for x in st for p in x["prices"] if p["updated_at"])
    print("timestamped", ts, "/", sum(len(x["prices"]) for x in st))
    print("station sources", dict(collections.Counter(tuple(x["sources"]) for x in st)))
    for want in (["retailer", "anwb"], ["anwb"]):
        print(want, [x for x in st if x["sources"] == want][:1])

asyncio.run(main())
