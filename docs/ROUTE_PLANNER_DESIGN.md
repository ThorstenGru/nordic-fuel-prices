# Route planner: cheapest pumps along a route (design, 2026-10-07)

Legend: **[T]** = tested today with a real request; **[D]** = read in docs/search results today; **[U]** = my estimate, unverified. Pricing pages change often; re-check before committing.

## 1. Recommendation

1. Build Phase B directly with **OSRM demo for a prototype only**, then switch to a **Cloudflare Worker proxy in front of a keyed provider** before public launch. Do not ship on the demo server (policy: non-commercial, 1 req/s, no uptime promise) [D].
2. Do not build Phase A (straight line A->B) as a user feature. It is wrong across the Öresund/Baltic/Alps and would mislead; use it only as a dev stub.
3. Build first: two-point route, corridor filter, "cheapest in corridor for my fuel", detour cost, hand-off of ONE chosen stop. That is the 80% value.
4. Defer: multi-stop fuel-planning DP, via-points, automatic multi-waypoint hand-off, price-refresh re-ranking, offline.
5. Geocoding: type-ahead on the public Nominatim is **forbidden by policy** [D]; use submit-on-enter search or tap-on-map.
6. Biggest risk: a routing/geocoding dependency that is free only while nobody uses it. Second: country JSON load time on 4G when a route crosses 3+ countries.

## 2. Routing providers

Test route: Malmö (55.605,13.0038) -> Hamburg (53.5511,9.9937), run from a Windows machine in Sweden/EU.

**Measured [T]**
- OSRM demo `router.project-osrm.org/route/v1/driving`: HTTP 200, `Access-Control-Allow-Origin: *`, 0.32 s first call (17.9 KB polyline5, full overview), ~0.12 s for `overview=false`. Length **503.0 km**, 328 min. 3-waypoint request with geojson simplified overview: 604 km, 35 points, 0.1-0.2 s.
- Valhalla at `valhalla1.openstreetmap.de` (FOSSGIS): 200, CORS `*`, 0.26-0.48 s, 36.7 KB JSON, length **373 km**, `has_ferry: true`. OSRM's car profile does not use ferries by default, which very likely explains 503 vs 373 km (cause not proven). **Consequence: a fuel app must say which route it used; ferry-vs-bridge changes the corridor completely.**
- `routing.openstreetmap.de/routed-car`: 200, CORS `*`, 0.17 s.
- Nominatim: CORS `*`, 0.35 s. Photon (komoot): CORS `*`, 2.4 s (slow cold call).
- ORS `api.openrouteservice.org`: unauthenticated GET -> 401 in 0.38 s; preflight OPTIONS answered 204 with `Access-Control-Allow-Origin: *` and `Authorization` allowed, so browser calls work, but the key would be visible.

| Provider | Free quota | Licence / ToS for ad-free consumer site | CORS | Key / safe handling | Geometry | Notes |
|---|---|---|---|---|---|---|
| OSRM demo | None guaranteed; 1 req/s [D] | "Reasonable, non-commercial" use, no uptime/latency guarantee [D]. Production: **no** | `*` [T] | No key | polyline5/6, geojson | 0.1-0.3 s [T]. Fine for prototype. No ferries in car profile (see above). |
| Self-hosted OSRM / Valhalla | Your hardware | Fully licence-clean (ODbL attribution) | You set it | None | polyline/geojson | EU extract (Geofabrik Europe PBF ~30 GB [U]) needs ~64+ GB RAM for OSRM-MLD prep, ~100+ GB disk [U]; a VM of that size is roughly EUR 60-120/month [U]. Country subsets (SE, DK, DE, NL, PL...) fit in 8-16 GB [U]. Owner must operate it: **not recommended for a solo owner now**. |
| OpenRouteService | Standard plan: 2,000 directions/day, 40/min [D] | Free for everyone, but HeiGIT is a non-profit; heavy/commercial-ish use is negotiated by e-mail [D]. Attribution required (ORS + OSM) | `*` incl. preflight [T] | Key required; **exposed if used from the browser** | geojson/encoded polyline | 2,000/day = 2,000 routes/day max. Good for launch if kept behind a Worker with caching. |
| GraphHopper | 500 credits/day, max 5 locations, **non-commercial only** [D] | Paid from EUR 69/month [D] | not tested | Key | encoded polyline | Free tier forbids commercial use; the site is ad-free but I would treat it as unsuitable without asking them. |
| Mapbox Directions | 100k requests/month free, then $2.00/1k up to 500k, $1.60 up to 1M [D, secondary sources] | Token-based; check ToS on map-display coupling (not verified: docs fetch had no ToS text) | yes (public tokens, URL-restricted) | Public `pk.` token can be URL-restricted to eurofuelprices.com: the best key-in-browser story | polyline5/6, geojson | Up to 25 coordinates [D]. Probably cleanest "free at 10k/month". Needs account with card. |
| Google Routes API | Essentials: 10,000 free calls/month, then ~$5/1k [D, secondary] | Results meant for display on Google Maps; storing/using polyline for own analysis is a ToS grey zone (not verified) | Routes API is server-oriented | Key + referrer restriction possible, quota abuse risk | encoded polyline | Avoid: ToS risk plus per-call cost. |
| HERE Routing v8 | Freemium ~30k transactions/month (sources conflict up to 250k) [D, unreliable] | Freemium allows production; attribution required | yes | Key (referrer-restrictable) | flexible polyline | Plausible alternative to Mapbox. Re-check numbers. |
| Stadia Maps (Valhalla) | Free: 200k credits/month, **non-commercial** [D] | Paid from $20/month | yes | API key / domain auth | polyline6 | Only if owner is willing to count the site as non-commercial. Ask them. |
| Geoapify | 3,000 credits/day; commercial and production allowed on free plan [D] | Needs a visible "Powered by Geoapify" follow-link [D] | yes | Key (can be origin-restricted) | geojson | Routing credit cost per call not verified; likely >1 credit. Easiest licence for ad-free commercial; paid from $59/month [D]. |
| ORS/other key directly in browser | n/a | n/a | n/a | **Leaks the key; anyone can burn your quota** | n/a | Only acceptable with referrer-locked public tokens (Mapbox/HERE/Geoapify), and even then referrers can be spoofed outside browsers. |

**Key-safety pattern.** Cloudflare Worker (free plan: 100k requests/day, 10 ms CPU, 1,000 req/min burst [D]) at `route.eurofuelprices.com`: validates Origin, rounds start/end to ~100 m and caches responses with the Cache API (identical popular routes become free), adds the secret, forwards. CPU limit is fine since the Worker only proxies. Add `connect-src https://route.eurofuelprices.com` to the CSP.

## 3. Algorithm (all client-side except the routing call)

**Inputs.** Route polyline P (simplified, ~1,500-4,000 points for 1,000 km), station list S, corridor half-width w (default 3 km, user 2-5), tank T (L), consumption c (L/100 km), start fuel f0 (L or %), reserve r (e.g. 10%).

**Which countries to load.** Cheap approach: derive crossed countries from the route's bounding boxes of each country (a coarse country bbox table, ~30 entries) plus a 2 km test of P against the stations. Load order: (1) country of the start, (2) country of the destination, (3) transit countries in route order. Render a first answer as soon as the first country arrives ("Sweden done, Denmark/Germany loading"), because only the first fuel stop typically matters. Load in parallel at most 2 at a time on mobile. Germany ~1 MB gz [given]; I estimate 6-12 MB JSON, 150-400 ms parse on a mid phone [U]; avoid re-parsing by using a Worker thread or by keeping only `id,lat,lon,price(fuel),updated_at,source` per station.

**Step 1: spatial pre-filter.** Bucket P's segments into a grid of 5 km cells (Mercator-scaled), each cell storing the segment ids that intersect it dilated by w. For each station: compute its cell, test only those segments (typically 1-3).

```
corridor(P, S, w):
  grid = {}                                  # cell -> [segIdx]
  for i in 0..len(P)-2:
    for cell in cellsCovering(P[i],P[i+1],pad=w): grid[cell].add(i)
  out = []
  for s in S:                                # S already filtered to fuelType & price!=null
    best = inf
    for i in grid[cell(s)]:
      d,t = distToSegment(s, P[i], P[i+1])   # equirectangular local projection
      if d < best: best=d; bi=i; bt=t
    if best <= w:
      s.along = cumLen[bi] + bt*segLen[bi]   # km from start
      s.off = best
      out.append(s)
  return out
```
Complexity O(|P|·cellsPerSeg + |S|·k) with k~2; for 40k stations that is ~100k point-segment tests, **~5-20 ms** on a phone [U]. The real cost is network + JSON parse (above), not geometry. A 1,000 km, 6 km-wide corridor holds roughly 500-2,500 stations, not 40k; the 40k is just the loaded bbox.

**Step 2: cost model.** Per candidate: price in EUR via the `meta.json` currency rates/EUR median (use the already-loaded rates; keep native currency for display and convert only for ranking). Quick detour estimate: `detourKm ≈ 2·off·1.3` (road factor) [U]. Detour cost = `detourKm × c/100 × price`. For the **top N (e.g. 15) candidates** after the quick ranking, refine with one OSRM/Matrix or two `route` calls (`P[i] -> station -> P[i+1]`); with a keyed provider budget N calls, not N per route: use the free OSRM `table` only if self-hosted; otherwise keep the straight-line estimate and label it so. Effective cost of a stop: `fillL × price + detourCost`, where fillL = min(T - fuelAtArrival, planned).

**Step 3: stop selection (range constraints).** Range between refuels R = (T - r)/c·100 km.
- If destination reachable from start: show "no stop needed" plus the cheapest optional pumps with `savings = (routeMedianPrice - price) × fillL - detourCost`.
- Otherwise run the classic gas-station DP/greedy: stations sorted by `along`; state = (station, fuel on arrival). Discretise fuel in 5 L steps (T≤80 L -> 16 states). Transition: from station i with fuel x, buy y so that you reach station j with `x+y-d_ij·c ≥ r`. Cost = price_i×y + detourCost_i. Complexity O(n·K·m) where n = candidate stations kept (prune to the cheapest 5 per 50 km window -> ~100), K = 16 fuel states, m = reachable successors (~10) = ~16k operations, **sub-millisecond to ~5 ms** [U]. Greedy lookahead (buy just enough to reach the next cheaper station within range; fill up if none) is a fine v1 and easier to explain.
- Output: one "recommended plan" (1-3 stops) plus a plain list of the 10 cheapest pumps in the corridor sorted by price and a toggle for "sorted by net cost".

**Tie-breaking.** Rank key: net cost, then price age (fresher first), then source grade (official > ANWB aggregate), then smaller detour. Hide or demote prices older than e.g. 48 h (owner decision).

**Time budget, 1,000 km, 4G.** Routing call 0.3-1 s [T/U] + loading 2-4 country files in parallel 2-6 s [U] + geometry/DP <100 ms [U]. First result target: under 4 s.

## 4. Phone UX

- **Input.** Two fields "From / To" (default From = current location, To = typed). Geocode on explicit submit (Enter/button), one request, with `User-Agent`/Referer set by the browser. **Nominatim bans client-side autocomplete and caps at 1 req/s per whole site** [D]; Photon's public instance allows type-ahead but is throttled and has no guarantee [D] and was slow today (2.4 s) [T]. Recommended: submit-based Nominatim at launch, long-press-on-map as the primary alternative, and add a Geoapify/keyed autocomplete via the Worker later. Add "OpenStreetMap contributors" attribution.
- **Result sheet.** Reuse the draggable bottom sheet: collapsed = "Plan: 1 stop, Q8 Padborg, 1.62 EUR/L, saves ~6.40 EUR vs route average"; half = ordered list with price, age chip, source, detour km; full = filters (fuel, corridor width, reserve). Tapping a row highlights the station on the map and the corridor.
- **"Saves X EUR".** Define it explicitly: `(median price of all corridor stations - chosen price) × litres bought - detour cost`; display "about", never exact. Mention that it is vs. the median of listed stations, not vs. what the driver would really pay.
- **Hand-off URLs (verified in docs today).**
  - Google Maps: `https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=lat,lng|lat,lng&travelmode=driving` [D]. **Waypoints: up to 3 on mobile browsers, 9 elsewhere; URL under 2,048 chars** [D].
  - Waze: deep link `https://waze.com/ul?ll=lat,lng&navigate=yes` supports **a single destination only**; multi-stop is not possible via URL [D]. Offer Waze for "next stop" only.
  - Apple Maps: repeated `daddr=` parameters work for multi-stop on iOS 16+ per developer posts (`maps.apple.com/?saddr=..&daddr=..&daddr=..&dirflg=d`) [D, community sources, not tested on a device]; Apple notes it has regressed before for `lat,lng` form.
  - HERE WeGo: not verified; keep single-destination hand-off.
  Practical rule: always hand off the **next one stop**; for plans with 2-3 stops offer Google Maps with waypoints.
- **Re-ranking.** Static JSON refreshes about every 15 min; on `visibilitychange` or a 15 min timer re-fetch only the country files whose `updated_at` in `meta.json` changed, recompute (geometry is cached in memory), and show a small "prices updated 14:05" toast instead of silently re-ordering while the user is reading.
- **Offline.** Cache the last route polyline and plan in `localStorage`/IndexedDB; the Service Worker already (if present) holds country JSON. Without network: show last plan, labelled with its age; no new routes.

## 5. Honesty constraints

- Each stop shows: price, currency, **"updated 2 h ago"** from `updated_at`, and source name. If the source provides no timestamp, show "time unknown" and do not rank it as fresh.
- Do not use the words "real-time" or "live". Use "updated about every 15 min where the source publishes it". Whole-route statement: "Prices change; verify at the pump."
- Savings and detour numbers labelled "estimate". Detour is straight-line-based unless refined, say so in an info popover.
- State route provider and ferry/toll behaviour used ("route via bridge, tolls not included"); state that fuel-station list may be incomplete in countries with fewer sources (ANWB-derived data).
- No route/position data leaves the browser except to the routing proxy and geocoder; say so in the privacy note. The Worker should not log coordinates.

## 6. Effort, phases, cost

| Slice | Size |
|---|---|
| Corridor filter + along/off distance + list UI | S |
| Routing call via Worker proxy + caching + CSP | S-M |
| Geocoding (submit-based) + map picking | S |
| Multi-country progressive loading | M |
| Detour refinement for top N | S |
| Fuel-stop greedy/DP with tank/reserve | M |
| Hand-off (Google waypoints, Waze single) | S |
| Re-rank on refresh, offline cache | M |
| Via-points, multiple alternatives | M-L |
| Tests (golden routes, e.g. Malmö->Hamburg, Stockholm->Oslo) | M |

**Phase A evaluation:** a straight line is not good enough, because the Malmö->Hamburg road is 373-503 km depending on ferry versus bridge [T], and a straight corridor across water or mountains would list unreachable pumps. Use only as a test stub, or as an "airline distance" preview. **Phase B** (real routing) is the MVP.

**Monthly cost, routing only** (assuming 1 routing call per plan, ~30% cache hits via Worker [U]):
| Requests/month | OSRM demo | ORS (via Worker) | Mapbox | Geoapify | Self-host |
|---|---|---|---|---|---|
| 1k | 0 (but not allowed) | 0 | 0 | 0 | 60-120 EUR |
| 10k | 0 (not allowed) | 0 (~330/day, inside 2,000/day) | 0 | 0 (check credits/route) | same |
| 100k | no | exceeds ORS (3,300/day) without agreement | ~0-5 EUR (within 100k free; Worker free) | ~59 USD plan likely [D] | same |
Cloudflare Worker free tier covers all three levels (100k/day) [D]. Geocoding adds the same order of requests; budget it separately.

**Open decisions for the owner**
1. Provider and commercial stance: will the site count as non-commercial (opens Stadia/GraphHopper/ORS) or do you want a provider whose free tier explicitly permits commercial/production (Mapbox, Geoapify, HERE)? Needs an account with card for most.
2. Geocoding: accept submit-based search and map tap (policy-clean), or pay/accept a keyed autocomplete service?
3. Staleness policy and claims: maximum age before a price is hidden or demoted, and whether "saves X EUR" is shown at all, or only "cheaper than route median by X".
