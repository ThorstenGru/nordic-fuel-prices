"""Prototype (NOT wired into the pipeline): Romanian station prices from the official
Monitorul Preturilor public GET API, found by reading https://monitorulpreturilor.info/index.min.js.

Endpoint (GET, keyless, JSON when Accept: application/json):
  https://monitorulpreturilor.info/pmonsvc/Gas/GetGasItemsByLatLon?lon=&lat=&buffer=<metres>
      &CSVGasCatalogProductIds=<ONE id>&OrderBy=dist
Observed 2026-11-06: buffer must be <= ~5000 m (8000+ returns "{}"); max 50 stations per call;
a list such as "11,21" fails (Postgres int error) so one product id per call.
Product ids: 11 petrol std, 12 petrol premium, 21 diesel std, 22 diesel premium, 31 LPG, 41 EV.

Usage: python -X utf8 ro_monitorul_probe.py LAT_MIN LAT_MAX LON_MIN LON_MAX [step_km] [out.json]
shortcut: fixed grid + one-level split is not a full-country scheduler, upgrade before wiring in.
"""
import json, math, sys, time, urllib.request, collections

BASE = "https://monitorulpreturilor.info/pmonsvc/Gas/GetGasItemsByLatLon"
PRODUCTS = {"11": "E5", "21": "DIESEL", "31": "LPG"}
R = 5000
PACE = 0.25


def get(lat, lon, prod, buf=R):
    url = f"{BASE}?lon={lon:.5f}&lat={lat:.5f}&buffer={buf}&CSVGasCatalogProductIds={prod}&OrderBy=dist"
    req = urllib.request.Request(url, headers={"User-Agent": "EuroFuelPrices-research/1.0 (+https://eurofuelprices.com)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        d = json.loads(r.read().decode("utf-8"))
    time.sleep(PACE)
    return d.get("Stations", []), d.get("Products", [])


def scan(lat0, lat1, lon0, lon1, step_km=8.0):
    st, capped = {}, 0
    dlat = step_km / 111.0
    lat = lat0
    while lat <= lat1:
        dlon = step_km / (111.0 * math.cos(math.radians(lat)))
        lon = lon0
        while lon <= lon1:
            for prod, ft in PRODUCTS.items():
                try:
                    stations, products = get(lat, lon, prod)
                except Exception as e:
                    print("ERR", lat, lon, prod, repr(e), file=sys.stderr)
                    continue
                if len(stations) >= 50:
                    capped += 1  # density cap hit: tile needs subdividing
                byid = {p["stationid"]: p["price"] for p in products if p.get("price", 0) > 0}
                for s in stations:
                    e = st.setdefault(s["id"], {"id": s["id"], "name": s["name"], "brand": s["network"]["id"],
                                                "address": s["addr"].get("addrstring", ""), "lat": s["addr"]["location"]["Lat"],
                                                "lon": s["addr"]["location"]["Lon"], "updatedate": s["updatedate"].strip(),
                                                "prices": {}})
                    if s["id"] in byid:
                        e["prices"][ft] = byid[s["id"]]
            lon += dlon
        lat += dlat
    return list(st.values()), capped


if __name__ == "__main__":
    a = sys.argv
    lat0, lat1, lon0, lon1 = map(float, a[1:5])
    step = float(a[5]) if len(a) > 5 else 8.0
    out, capped = scan(lat0, lat1, lon0, lon1, step)
    print(f"stations={len(out)} capped_tiles={capped}")
    days = collections.Counter(s["updatedate"][:10] for s in out)
    print("updatedate days (newest 8):", sorted(days.items(), key=lambda kv: kv[0][6:] + kv[0][3:5] + kv[0][:2])[-8:])
    if len(a) > 6:
        json.dump(out, open(a[6], "w", encoding="utf-8"), ensure_ascii=False)
