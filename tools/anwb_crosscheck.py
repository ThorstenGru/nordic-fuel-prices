"""One-off cross-check (run by hand, ~5 min, live network): ANWB against the other sources of DK, FI and SE, station by station (<=120 m), in percent of the other price.

    python tools/anwb_crosscheck.py

Result of 2026-11-16: docs/ANWB_RATING_2026-11-16.md. Nothing is written or published.
"""
import asyncio, sys, statistics, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import aiohttp
from scrapers.base import dist_m
from scrapers import denmark, finland, sweden
captured = {}


def wrap(mod, cc):
    orig = mod.merge_sources

    def f(results, cfg, *a, **k):
        captured[cc] = results
        return orig(results, cfg, *a, **k)
    mod.merge_sources = f


wrap(denmark, "DK"); wrap(finland, "FI"); wrap(sweden, "SE")


def prices(st):
    d = {}
    for p in st.get("prices") or []:
        ft = p.get("fuel_type")
        if ft in ("95", "E5", "E10"):
            d.setdefault("P", p["price"])
        elif ft == "DIESEL":
            d["D"] = p["price"]
    return d


def compare(anwb, other):
    cell = 0.003
    idx = {}
    for s in other:
        if s.get("lat") is None:
            continue
        idx.setdefault((round(s["lat"] / cell), round(s["lon"] / cell)), []).append(s)
    diffs = {"P": [], "D": []}
    st_n = 0
    for a in anwb:
        if a.get("lat") is None:
            continue
        cx, cy = round(a["lat"] / cell), round(a["lon"] / cell)
        best, bd = None, 1e9
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for o in idx.get((cx + dx, cy + dy), ()):
                    d = dist_m(a["lat"], a["lon"], o["lat"], o["lon"])
                    if d < bd:
                        best, bd = o, d
        if best is None or bd > 120:
            continue
        st_n += 1
        pa, po = prices(a), prices(best)
        for k in diffs:
            if k in pa and k in po and pa[k] > 0 and po[k] > 0:
                # relative, so SEK/DKK/EUR compare: diff in percent of the other price
                diffs[k].append(round((pa[k] - po[k]) / po[k] * 100, 2))
    return st_n, diffs


def summ(v):
    if not v:
        return "no pairs"
    ab = sorted(abs(x) for x in v)
    return f"n={len(v)} median={statistics.median(v):+.2f}% within1%={100*sum(1 for x in ab if x<=1)/len(ab):.0f}% within2%={100*sum(1 for x in ab if x<=2)/len(ab):.0f}% p90={ab[int(.9*len(ab))]:.1f}%"


async def main():
    async with aiohttp.ClientSession() as s:
        for cls in (denmark.DenmarkScraper, finland.FinlandScraper, sweden.SwedenScraper):
            try:
                await cls(s).fetch_stations()
            except Exception as e:
                print(cls.__name__, "failed", type(e).__name__, e)
    for cc, res in captured.items():
        anwb = next((r for r in res if r.source_id == "anwb"), None)
        print("==", cc, [(r.source_id, len(r.stations), r.priority, r.ok) for r in res])
        if not anwb:
            continue
        for r in res:
            if r.source_id in ("anwb", "osm") or not r.stations:
                continue
            n, d = compare(anwb.stations, r.stations)
            print(f"  ANWB vs {r.source_id}: {n} stations matched; petrol {summ(d['P'])}; diesel {summ(d['D'])}")

asyncio.run(main())
