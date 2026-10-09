import sys, asyncio, collections, json
sys.path.insert(0, ".")
import aiohttp
from scrapers.moldova import MoldovaScraper

async def main():
    async with aiohttp.ClientSession() as s:
        st = await MoldovaScraper(s).fetch_stations()
    print(len(st), collections.Counter(p["fuel_type"] for x in st for p in x["prices"]))
    print(json.dumps(st[0], ensure_ascii=False, indent=1))
    print("lat", min(x["lat"] for x in st), max(x["lat"] for x in st),
          "lon", min(x["lon"] for x in st), max(x["lon"] for x in st))
    print(collections.Counter(x["brand"] for x in st).most_common(6))
asyncio.run(main())
