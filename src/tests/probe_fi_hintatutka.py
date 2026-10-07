"""Probe + gain measurement for src/sources/fi_hintatutka.py vs live fi.json.
Run: python src/tests/probe_fi_hintatutka.py"""
import asyncio, json, math, os, sys, urllib.request
import aiohttp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sources import fi_hintatutka as ht

def hav(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(x))

def bk(s):
    t = (s.get("brand") or s.get("name") or "").lower()
    for k in ("neste", "st1", "abc", "teboil", "shell", "seo"):
        if k in t:
            return k
    return t[:4]

async def main():
    async with aiohttp.ClientSession() as se:
        new = await ht.fetch(se)
    live = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://eurofuelprices.com/fi.json", headers={"User-Agent": ht.UA})))["stations"]
    print("hintatutka stations:", len(new), "with both:", sum(len(s["prices"]) == 2 for s in new))
    gain95 = fresher = newst = 0
    for n in new:
        c = [(hav(n["lat"], n["lon"], l["lat"], l["lon"]), l) for l in live if l.get("lat")]
        d, l = min(c, key=lambda x: x[0])
        if d > 100 or bk(l) != bk(n):
            newst += 1; continue
        has95 = any(p["octane"] == 95 if "octane" in p else False for p in l["prices"]) or any(p["fuel_type"] in ("95", "E10", "E5") and p.get("octane", 95) == 95 for p in l["prices"])
        if not has95:
            gain95 += 1
        if all(p.get("updated_at") is None for p in l["prices"]):
            fresher += 1
    print(f"matched<=100m same brand but live lacks 95: {gain95}; matched live had no timestamps: {fresher}; unmatched/new: {newst}")
asyncio.run(main())
