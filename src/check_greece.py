import sys as _s; _s.stdout.reconfigure(encoding="utf-8")
import sys, asyncio, collections, json, os
sys.path.insert(0, ".")
import aiohttp
import scrapers.greece as G, os
if os.environ.get("GR_TEST_BUDGET"): G.FPEU_MAX_REQUESTS = int(os.environ["GR_TEST_BUDGET"])
from scrapers.greece import GreeceScraper

# fuel-prices.eu politeness: GR_FPEU_CACHE=<file> records every fpeu response on the first (live) run and
# replays them on later runs (no fpeu requests at all). Delete the file to refresh.
CACHE = os.environ.get("GR_FPEU_CACHE")
_store = json.load(open(CACHE, encoding="utf8")) if CACHE and os.path.exists(CACHE) else {}
_live = bool(CACHE) and not _store


class CachedGreece(GreeceScraper):
    async def _fpeu_request(self, params):
        if not CACHE:
            return await super()._fpeu_request(params)
        key = json.dumps(params, sort_keys=True)
        if key in _store:
            return 200, _store[key]
        if not _live:
            return 404, None          # replay mode: never hit the network for an unseen circle
        status, payload = await super()._fpeu_request(params)
        if status == 200:
            _store[key] = payload
        return status, payload


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
        sc = CachedGreece(s)
        st = await sc.fetch_stations()
    if _live: json.dump(_store, open(CACHE, "w", encoding="utf8"))
    report(sc, st)
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
