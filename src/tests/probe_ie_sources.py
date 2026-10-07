"""Probe for Irish per-station fuel price sources (2026-10-07). Run: python src/tests/probe_ie_sources.py
Findings: no usable legal source; ANWB emits only DIESEL + EURO95 in IE (no hidden 95 fuelType)."""
import collections, json, urllib.request
UA = "EuroFuelPrices/1.0 (+https://eurofuelprices.com)"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode("utf8", "replace")
d = json.loads(get("https://api.anwb.nl/routing/points-of-interest/v3/all?type-filter=FUEL_STATION&bounding-box-filter=53.2%2C-6.5%2C53.5%2C-6.0"))["value"]
c = collections.Counter((p["fuelType"], p["fuelName"], (p.get("priceTier") or {}).get("value")) for s in d for p in s["prices"])
print(len(d), "stations;", sum(1 for s in d if s["prices"]), "with prices"); print(c)
for name, url in [("fuelwatch.ie", "https://fuelwatch.ie/robots.txt"), ("fuelfinder.ie", "https://www.fuelfinder.ie/robots.txt")]:
    print(name, [l for l in get(url).splitlines() if "/api" in l])   # /api/ disallowed for all agents
# ToS (manual): fuelwatch.ie/terms s.4, pickapump.com (main.js ToS), conjora.ie/terms all prohibit scraping/automated access.
