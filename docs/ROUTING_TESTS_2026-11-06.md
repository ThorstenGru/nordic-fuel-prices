# Routing capability tests, 2026-11-06

Server: `https://valhalla1.openstreetmap.de/route` (public FOSSGIS Valhalla, the one used by `rtValhalla` in `web/index.html`).
Request shape used (identical to the app): `GET /route?json=<urlencoded JSON>` with `{"locations":[{lat,lon},{lat,lon}],"costing":"auto","directions_type":"none"}` plus the option under test. All 27 `/route` calls and 1 `/trace_attributes` call were made from `tools/archive/valhalla_probe.js` (plus one ad-hoc POST), at least 1.1 s apart, all HTTP 200. Latencies are measured from a Swedish office network via Node, so a phone on mobile data will be slower.

Points: Malmo 55.605/13.000, Hamburg 53.551/9.994, Berlin 52.520/13.405, Stockholm 59.329/18.069, Oslo 59.913/10.752, Billeberga 55.917/13.083, Copenhagen 55.676/12.568.

## Summary for the frontend

- Alternatives work (`"alternates": N`), but quality varies: real for Malmo-Hamburg and Stockholm-Oslo, weak for Malmo-Berlin, none for short routes.
- `use_ferry`, `use_tolls`, `use_highways` are soft preferences, not hard constraints. `top_speed` works in the low range (it changes time and path), is silently ignored above the default.
- Per-segment energy is possible with `directions_type:"maneuvers"` (length, time, highway/toll/ferry flags per maneuver, no speed or road class), or better with `/trace_attributes` (per edge speed, speed_limit, road_class, use), or with `elevation_interval` for climb.
- Policy: **max 1 request per second**. Multi-stop planning and alternatives must be serialised with 1 s spacing.
- `has_toll` is true for the Oresund bridge route. It is also true when a ferry maneuver carries a fare, so it is a "something costs money" flag, not a bridge flag.

## 1. Alternatives (`"alternates": 2`)

Response top level: `{ trip, alternates: [ { trip }, ... ] }`. Each alternate has the same `trip` shape as the main route, one leg each. Up to 2 alternates requested; fewer may come back.

| Route | Option | km | min | ferry | toll | vs fastest | latency | payload |
|---|---|---|---|---|---|---|---|---|
| Malmo-Hamburg | main | 373.9 | 283 | yes (Rodby-Puttgarden) | yes | | 624 ms | 44 kB total |
| | alt 1 | 505.2 | 327 | no | yes | +131 km, +44 min | | |
| Malmo-Berlin | main | 471.7 | 407 | yes | yes | | 619 ms | 63 kB total |
| | alt 1 | 426.8 | 554 | yes | no | -45 km, +147 min | | |
| | alt 2 | 545.7 | 580 | yes | yes | +74 km, +173 min | | |
| Stockholm-Oslo | main | 526.4 | 376 | no | yes | | 656 ms | 138 kB total |
| | alt 1 | 602.2 | 460 | no | yes | +76 km, +84 min | | |
| | alt 2 | 664.3 | 453 | no | yes | +138 km, +77 min | | |
| Billeberga-Malmo | main | 49.7 | 47 | no | no | | 99 ms | 3.7 kB |
| | alt | none returned (key `alternates` absent) | | | | | | |

Reading: Malmo-Hamburg alt 1 is the useful "no ferry" alternative (same as `use_ferry=0`). Malmo-Berlin alternatives are 2.5 to 3 h slower and not worth offering; filter by a time-penalty threshold (for example hide alternatives more than 60 min slower, and show at most 2). Stockholm-Oslo alternatives are genuinely different roads at +77 to +84 min. Short routes return no alternatives, so the UI must handle `alternates` being undefined. Alternate calls are about 2.5x slower than a single route and 2 to 7x bigger.

## 2. Costing options (Malmo-Hamburg, `costing_options.auto.*`)

| Option | km | min | ferry | toll | path differs from base |
|---|---|---|---|---|---|
| base (none) | 373.9 | 283 | yes | yes | |
| `use_ferry: 0` | 505.2 | 327 | no | yes | yes (same as alt 1 above) |
| `use_tolls: 0` | 502.4 | 328 | no | **yes** | yes (avoids ferry, still crosses a toll) |
| `use_highways: 0` | 366.9 | **711** | yes | no | yes (avoids motorways, including Oresund) |
| `top_speed: 90` | 371.1 | 313 | yes | yes | yes (+30 min) |
| `top_speed: 130` | 373.9 | 283 | yes | yes | no (identical to base) |
| `top_speed: 200` | 373.9 | 283 | yes | yes | no, silently ignored (no error) |
| `top_speed: 20` | 366.9 | 1111 | yes | no | yes (absurd, avoids all fast roads) |

- Values 0 to 1 are accepted for the `use_*` options; none produced an error. They are preferences: `use_tolls: 0` still returned `has_toll: true`, so it cannot be used to guarantee a toll-free route.
- `top_speed` changes both time and path at 90 km/h. At 130 and 200 the result equals the default, so there is no way to model "I drive faster than the default" with it. No out-of-range error was returned for 20 or 200 (both HTTP 200). Valhalla documents a range of about 10 to 252 km/h, but I only observed the behaviour above. For the Santa Fe in auto mode, top_speed is only useful as a "cap at 110 or 90" what-if; do not use values below about 60.
- Time changes in the 90 km/h case do not include ferry time (the ferry has fixed time).

## 3. Fields for per-segment energy

### 3a. `directions_type: "maneuvers"` (Malmo-Hamburg: 34 maneuvers, 29.1 kB vs 19.6 kB for `none`, 306 ms; Billeberga-Malmo 9.1 kB vs 3.7 kB, 185 ms)

`trip.legs[0].maneuvers[]` keys seen: `type, instruction (empty string unless language/instructions requested), length (km), time (s), cost, begin_shape_index, end_shape_index, travel_mode, travel_type, street_names, bearing_before, bearing_after, sign, roundabout_exit_count, begin_street_names` and optional booleans `highway`, `toll`, `ferry`.

- Sum of maneuver `length` = 373.871 km vs summary 373.876 km: consistent.
- `begin_shape_index/end_shape_index` index into the decoded polyline, so each maneuver can be tied to a slice of the geometry (gradient, cumulative km).
- No speed limit and no road class. Average speed per maneuver is `length / time * 3600`, which blends the real speed with delays. Only `highway:true` marks motorway-class roads (8 of 34 maneuvers).
- The ferry is explicit: maneuver `type 28` with `ferry:true, toll:true, length 18.968, time 3046 s`, street name "Rodby (DK) - Puttgarden (D)", followed by `type 29` (exit ferry). Energy for ferry maneuvers should be zero (and fuel stops should not be placed on them).
- Toll flag: 2 maneuvers carry `toll:true` on Malmo-Hamburg: `E 20` (40.0 km, starting at the Malmo end, i.e. the whole motorway stretch containing the Oresund bridge, not only the bridge) and the ferry. Use the flag for a "toll or fare on this route" note, not for costing.

### 3b. `/trace_attributes` (POST, shape matching of the route polyline, tested on Billeberga-Malmo, 619 ms, 29.3 kB, 206 edges for 49.7 km)

Request: `{shape_match:"map_snap", encoded_polyline:<leg.shape>, shape_format:"polyline6", costing:"auto", filters:{action:"include", attributes:["edge.length","edge.speed","edge.speed_limit","edge.road_class","edge.use","edge.toll","edge.begin_shape_index","edge.end_shape_index"]}}`.
Response: `{ units, edges:[{ length, speed, speed_limit?, road_class, use, toll, begin_shape_index, end_shape_index }], alternate_paths }`. `speed` is the routing speed in km/h, `speed_limit` was present on 205 of 206 edges (tagged limit, km/h). Road classes seen: motorway 81 edges, secondary 76, tertiary 36, residential 10, primary 2, service_other 1. This is the best source for a speed-based consumption model, at the cost of a second request per route (which also counts against the 1 req/s limit). Not verified: CORS for the POST from a browser (the app only uses GET so far) and latency/size on a 370 km route (expect several times larger).

### 3c. `elevation_interval` (request key, in metres)

`{..., "elevation_interval": 100}` adds `trip.legs[0].elevation_interval` (100) and `trip.legs[0].elevation[]` (heights in metres, 0.1 m resolution, one sample per 100 m, no nulls seen).

| Route | samples | range | latency | payload |
|---|---|---|---|---|
| Billeberga-Malmo (49.7 km) | 499 | -1.5 to 71.3 m | 83 ms | 6.0 kB (vs 3.7 kB) |
| Malmo-Hamburg (373.9 km) | 3740 | -4.4 to 116.7 m | 245 ms (vs 225 ms) | 36.9 kB (vs 19.6 kB) |

Cheap: about +17 kB per 370 km and negligible latency. Cumulative ascent can be computed on the client; a 500 m or 1000 m interval would shrink it 5 to 10x with little loss for energy estimates on Nordic and North German terrain. Not checked: elevation values over the ferry stretch and over bridges (bridges often show terrain height, so expect small errors).

## 4. Request size, latency, rate limit, policy

- GET URL length: 230 to 236 characters for a 2-point request, well below any limit. A multi-stop route (R2) with 3 to 5 locations adds about 55 characters per point. No limit was approached.
- Latency (single route, `none`): 216 to 497 ms for 370 km, 99 ms for 50 km. Alternatives: 620 to 660 ms.
- 10 sequential identical calls (Billeberga-Malmo, 1.1 s apart): all HTTP 200, 67 to 226 ms (median about 89 ms). These repeats were probably served from a cache, so they understate cold latency (cold 50 km call was 99 ms). No `429`, no `Retry-After`, no rate-limit headers; the only response header of interest was `server: nginx`. Behaviour above 1 req/s was deliberately not tested, so 429/ban behaviour is unknown.
- Fair-use text (FOSSGIS Nutzungsbedingungen, https://fossgis.de/arbeitsgruppen/osm-server/nutzungsbedingungen/, German, retrieved today): "Maximal eine Anfrage pro Sekunde" for `routing.openstreetmap.de` and `valhalla1.openstreetmap.de` (max one request per second). General rules: clear OSM attribution plus a link to `openstreetmap.org/fixthemap`; a valid HTTP User-Agent and Referer where technically possible (a browser sends its own); at most 2 download connections; commercial use only if the service is not a substantial part of the offering; websites with high traffic must not use the services; mass downloading is forbidden; the URLs should preferably not be hard coded; access can be revoked at any time and a single server stands behind the service with no availability promise.
- Consequences for the app: serialise all calls with at least 1 s between request starts (queue in `rtRoute`), never fire alternatives plus per-stop legs in parallel, keep the OSRM fallback, cache per from/to/options in memory, and plan for the server being unavailable (the current 15 s timeout plus fallback is right). Since the URL is hard coded in the app, keeping `ROUTER` as the single switch point is the recommended mitigation. For growth, a self-hosted Valhalla or a commercial endpoint is the clean answer.

## 5. Toll flags (Oresund)

- Malmo-Copenhagen (46.3 km): `summary.has_toll: true`, also on `legs[0].summary`. Malmo-Hamburg: true. Billeberga-Malmo: false. Stockholm-Oslo: true (a toll somewhere, not identified).
- Summary flags live in both `trip.summary` and `trip.legs[i].summary`: `has_toll, has_highway, has_ferry, has_time_restrictions, min_lat/min_lon/max_lat/max_lon, time (s), length (km), cost`. The app reads `legs[].summary.has_ferry` today; `has_toll` is available the same way. Leg summaries may also have `level_changes`.
- Caveats: the flag does not tell which toll or how much (no price in the response); the ferry maneuver can itself carry `toll:true`; Malmo-Berlin alt 1 had `has_ferry:true` and `has_toll:false`, so fares are not consistently reported. Show tolls as "may include tolls, check operator", never as a computed cost.

## JSON shape the frontend can rely on (observed, all 200 OK)

```
{
  trip: {
    status: 0, status_message: "Found route between points", units: "kilometers",
    locations: [ { type, lat, lon, original_index, side_of_street? } ],
    summary: { time /*s*/, length /*km*/, cost, has_toll, has_highway, has_ferry,
               has_time_restrictions, min_lat, min_lon, max_lat, max_lon },
    legs: [ {
      summary: { ...same keys, level_changes? },
      shape: "<polyline6 string>",
      maneuvers?: [ { type, length /*km*/, time /*s*/, begin_shape_index, end_shape_index,
                      travel_mode, travel_type, street_names?, highway?: true, toll?: true,
                      ferry?: true, sign?, instruction: "" } ],       // directions_type:"maneuvers"
      elevation_interval?: 100, elevation?: [ metres, ... ]          // elevation_interval:100
    } ]
  },
  alternates?: [ { trip: { ...same as trip... } } ]                   // alternates:N, may be absent
}
```
Errors were not provoked (no invalid requests were sent beyond out-of-range `top_speed`, which was accepted). One leg per pair of locations; a route with `via`-type waypoints returns one leg per segment (not tested, expect `legs.length = locations.length - 1`).

## Not tested / open

- Multi-location requests (3+ points) for R2, and `type:"through"` vs `"break"` locations.
- `trace_attributes` latency and CORS on long routes from a browser.
- Waze: no Valhalla relation; per the owner's decision R13 navigates to the first stop only for Waze.
- Behaviour above 1 req/s (intentionally avoided).
- Raw response dump was kept outside the repo; re-run `node tools/archive/valhalla_probe.js out.json` to regenerate (27 requests, about 45 s).
