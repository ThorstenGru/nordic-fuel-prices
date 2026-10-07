"""Probe + gain measurement for src/sources/se_bensinpriskollen.py against live se.json.

Run:  python src/tests/probe_se_bensinpriskollen.py [--station-pages] [--max-cities N]
Network use: <=1 req/s, honest UA. Writes nothing into the repo (prints a report).
Also prints the ANWB (fuelType, fuelName, priceTier) census for a Stockholm bbox.
"""
import asyncio
import collections
import math
import os
import sys

import aiohttp

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.sources import se_bensinpriskollen as m  # noqa: E402


def _hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(x))


async def anwb_census(session):
    url = ("https://api.anwb.nl/routing/points-of-interest/v3/all?type-filter=FUEL_STATION"
           "&bounding-box-filter=59.2%2C17.8%2C59.5%2C18.3")
    async with session.get(url, headers={"User-Agent": m.UA}) as r:
        d = await r.json(content_type=None)
    c = collections.Counter()
    for p in d.get("value", []):
        for f in p.get("prices", []):
            c[(f["fuelType"], f["fuelName"], f["priceTier"]["value"])] += 1
    print("ANWB stations:", len(d.get("value", [])), "distinct (fuelType, fuelName, tier):")
    for k, v in c.most_common():
        print("  ", k, v)


async def main():
    sp = "--station-pages" in sys.argv
    mc = int(sys.argv[sys.argv.index("--max-cities") + 1]) if "--max-cities" in sys.argv else None
    async with aiohttp.ClientSession() as s:
        await anwb_census(s)
        ref = await m._load_reference(s)
        res = await m.fetch(s, reference=ref, station_pages=sp, max_cities=mc)
    st = m.last_stats
    byid = {r["id"]: r for r in ref}
    gain95 = gaindiesel = fresher = 0
    for o in res:
        r = byid.get(o["ref_id"])
        has95 = any(p["fuel_type"] in ("95", "E10", "E5") for p in r["prices"])
        hasd = any(p["fuel_type"] == "DIESEL" for p in r["prices"])
        gain95 += (not has95) and any(p["fuel_type"] == "95" for p in o["prices"])
        gaindiesel += (not hasd) and any(p["fuel_type"] == "DIESEL" for p in o["prices"])
        old = [p["updated_at"] for p in r["prices"] if p["fuel_type"] in ("E10", "E5", "95") and p["updated_at"]]
        new = [p["updated_at"] for p in o["prices"] if p["fuel_type"] == "95" and p["updated_at"]]
        if new and (not old or max(new) > max(old)):
            fresher += (bool(old))
    print("stats:", st)
    print(f"matched-to-ref stations returned: {len(res)}")
    print(f"gain a 95 price: {gain95}; gain a diesel price: {gaindiesel}; fresher 95 than ref: {fresher}")
    print(f"unmatched (would be 'new stations' if geocoded): {st.get('unmatched')}")


if __name__ == "__main__":
    asyncio.run(main())
