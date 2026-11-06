# Route planner ideas F: feasibility audit against our code and data (2026-11-06)

Research only. No code edited, nothing committed.

## How claims are labelled

- **[code]** read in `web/index.html` (route section, lines ~4043-4368) on 2026-11-06.
- **[measured]** computed by me today from data. Live files were downloaded from https://eurofuelprices.com/{meta,se,dk,de,no}.json (fetched 2026-11-06 ~14:25 UTC). The local `data/*.json` is a stale 2026-10-07 snapshot and `data/meta.json` there is a 4-country test run, so I did NOT use it for the numbers below. Routes came from the live Valhalla FOSSGIS server (5 calls, 2 s apart). The corridor timings re-implement `rtCorridor` and `minOf` in Node (scripts in the scratchpad, not in the repo).
- **[opened]** I fetched the page today. **[search]** only a search snippet. **[invented]** my own idea or estimate.

## 1. Summary

1. The route engine itself is fine. The corridor search is cheap (40-70 ms in Node for a 1,000 km route over 21k stations [measured]), Valhalla answers in about 0.5-0.7 s [measured], and one route costs 1 geocode x2 + 1 Valhalla + country files.
2. **The limiting factor is price data, not routing.** On the owner's Germany leg, 0 of 117 candidate pumps carry a timestamp [measured], because ANWB (Germany, Norway, NL, PL, ...) gives no `updated_at`. In Sweden only 196 of 4,018 stations have a dated 95 price [measured]. The planner (correctly) refuses to call an undated pump "best" (`R.best` needs tier 0 [code]), so on Malmo-Hamburg the headline recommendation can only come from the 43 dated pumps in Denmark/Sweden even though about 60 % of the pumps on the corridor are German.
3. Tankerkoenig (planned) is the single biggest quality lever for the owner's trips. It is a data-pipeline task (scheduled job), not a client task.
4. Several free external calls would add value but each leaks route-related data to a third party. Per-route Open-Meteo/elevation calls are within limits but are the privacy-sensitive ones. Only the position-rounding trick already used in the app keeps them acceptable.
5. What must be precomputed by scheduled jobs: per-country price-quality tiers, a "trusted fresh 95" flag per station, corridor reference prices, toll/ferry cost tables. Anything per-route stays in the browser.

## 2. Measured price coverage per country (live data, 2026-11-06 14:00-14:25 UTC)

95 = lowest plausible non-regulated octane-95 row per station (same filter as `minOf`). "Dated" = row has `updated_at`. Fresh = at most 10 h old at fetch time (the app's `MAX_AGE_H`).

| Country | Stations | With a 95 price | 95 price dated | Fresh at most 10 h (share of priced) | Notes |
|---|---|---|---|---|---|
| SE | 4,018 | 533 (13 %) | 196 | 37 % | bensinpriser.nu crowd + ANWB undated; grade D |
| DK | 2,238 | 1,648 (74 %) | 1,084 | 54 % (66 % at 36 h) | ok.dk, Shell, Q8, Go'on; best of the three |
| DE | 14,949 | 13,900 (93 %) | 0 | 0 % | ANWB only; every price tier 1 (unknown age) |
| NO | 2,420 | 440 (18 %) | 0 | 0 % | ANWB only |

Same files, meta.json: `with_timestamp_pct` SE 17.9, DK 59.6, DE 0.0, NO 0.0, NL 0.0, PL 0.0, AT 0.0 (AT grade A, e-control.at, so prices are official even without per-row stamps), CZ 3.1 [measured].

From the stale local snapshot (2026-10-07, indicative only): FR 45 % within 36 h, IT 11 %, ES 100 %, GB 100 %. These countries (and any live change since) must be re-measured before use.

Implication of "undated": the user sees these pumps in a weaker tier and an "age unknown" label. That is honest, but a Malmo-Hamburg-Berlin driver gets a ranked list where the whole German part is "unverified".

## 3. Typical corridors (Valhalla route, corridor 3 km, live data)

| Corridor | Route km (Valhalla) | Candidates with a 95 price | Per 100 km | Dated candidates | Longest stretch with no candidate | Longest stretch with no fresh dated candidate |
|---|---|---|---|---|---|---|
| Billeberga-Malmo | 47 | 7 (all SE) | 15 | 0 | 29 km | whole route |
| Malmo-Hamburg (via Rodby-Puttgarden ferry) | 373 | 210 (SE 10, DK 83, DE 117) | 56 | 55 (SE 3, DK 52) | 27 km | 178 km |
| Malmo-Berlin | 471 | 180 (SE 10, DK 84, DE 86) | 38 | 55 | 46 km | 284 km |
| Malmo-Munich (extra test) | 1,017 | 341 (SE 10, DK 84, DE 247) | 34 | 55 | 46 km | 830 km |
| Stockholm-Oslo | 526 | 48 (SE 36, NO 12) | 9 | 10 | 102 km (at about km 339) | 217 km |

Reading:
- Density is excellent on the DK/DE legs and thin in Sweden/Norway, simply because few Swedish/Norwegian stations carry a price at all (13 % and 18 % of stations).
- On Billeberga-Malmo (the owner's commute) every one of the 7 candidates is undated, so the planner can never name a "best" stop. For a commute the owner likely knows the pumps already. A better product for commuting is a saved recurring route with a "cheapest on my way home today" card (idea 3).
- Stockholm-Oslo has a real hole: 102 km between priced pumps, which matters for a 47 l tank (about 600+ km range, so not a range problem, but there is nothing to recommend).
- With 2 km or 5 km corridors the picture is the same; 5 km roughly doubles candidates but only in rural stretches.
- The 10 h cutoff (owner decision 2026-10-07) hides 12 Danish candidates on the Malmo corridors [measured]. That is the right choice for trust, but it silently shrinks the list. The UI already shows "n hidden" (`rtOld` [code]).
- Caveat: one snapshot, one fetch time (14:00-14:25 UTC, Friday afternoon). Night-time freshness will be different (bensinpriser crowd reports thin out at night).

## 4. How stale data affects recommendations [code + measured]

- `rtTier`: 0 = dated and trusted, 1 = age unknown, 2 = flagged (`ps` unchanged 48 h+, `suspectLow`, or country feed stale). Only tier 0 with saving at least 1 EUR may be called best [code].
- Reference price per 20 km bucket is the median of rows within 100 km along the route, preferring dated rows if 3 or more exist [code]. On a Germany-heavy route the reference is therefore a median of undated ANWB prices; the "saves X EUR" number rests on undated data. This is the main correctness risk.
- A single global rule in `rtRank` converts every price with `fxRank` (ECB rate); for SEK/DKK/NOK that is fine, but SEK crowd prices and EUR ANWB prices are compared directly, so a systematic source offset (the owner's own notes: ANWB SE 95 runs about 2.5 SEK under dated prices) can masquerade as savings. The country-level `suspectLow` guard handles only strong outliers.
- Stale feed per country: `metaOf[cc].status === 'stale'` demotes the entire country to tier 2 [code]. Good, but binary.

## 5. Performance limits of the client-side corridor search [measured]

- Corridor search, Node 24-ish on a desktop, all stations of SE+DK+DE (21k): 28-70 ms for 373-1,017 km, 3-5 km width; 5.6 ms for 47 km. Phones are typically 4-8x slower [invented estimate], so a 1,000 km route is likely 0.3-0.5 s. Not a bottleneck.
- Polyline size: 3,809 points (Malmo-Hamburg), 9,960 (Malmo-Munich), 8,395 (Stockholm-Oslo) [measured]. Drawing a Leaflet polyline of 10k points is fine; the cost is in `rtCorridor`'s densification (a point per 1.5 km, 9 grid cells each).
- **The real cost is download and parse of country files.** Live `de.json` transferred about 1.0 MB compressed (curl, `--compressed`); raw local file 6.7 MB; JSON.parse 80 ms in Node, 15k stations in memory. SE 150 kB, DK 86 kB, NO 87 kB. A Malmo-Munich trip pulls SE+DK+DE = about 1.2 MB over the wire and about 9 MB parsed. A trip to Italy/France (IT raw 9.8 MB, FR 5.4 MB, parse 57-101 ms in Node) is heavier but still feasible on 4G; the service worker caches versioned files cache-first [code, sw.js].
- Ceiling: Europe-wide (45 countries) is about 123k stations; if a user planned Lisbon-Helsinki the app would load roughly 10+ country files (tens of MB parsed). Feasible but a mobile memory risk [invented]. The mitigation is a precomputed **corridor-slice** (section 8).
- Valhalla with `directions_type: none` returns about 20-50 kB for 400-1,000 km [measured: 19.6, 23.2, 39.9, 49.4 kB]. Fine.

## 6. External calls: limits, terms, privacy

| Call | Verified limits and terms | What it learns about the user | Verdict |
|---|---|---|---|
| Valhalla FOSSGIS `valhalla1.openstreetmap.de` | [search: fossgis.de terms] extra condition of 1 request/s per client on the routing servers; high-traffic sites not permitted; mass downloads prohibited; do not hard-code URLs; run by volunteers, no SLA. Secondary source: 1 call/user/s and 100 calls/s total (not confirmed from FOSSGIS). I did not open the fossgis.de page itself. | Route start and end coordinates (full precision), IP address, user agent | Fine at current traffic. The docs already recommend a Worker proxy if traffic grows. One route = 1 call, so the 1 req/s rule is easy to respect. Re-check terms before promoting widely. |
| Valhalla options we do not use yet | [opened valhalla.github.io route API reference] `use_ferry`, `use_tolls` (0-1), `alternates` (not for multipoint), summary has `has_toll`, `has_ferry`, `has_highway`. Max locations/distance are server config, not published. | same | `has_toll` is true for Malmo-Munich (Oresund bridge) [measured] and we show neither the toll nor its cost. |
| Nominatim | [opened operations.osmfoundation.org/policies/nominatim] max 1 req/s per application, **autocomplete forbidden**, valid Referer/User-Agent required, cache repeated queries | The typed place names, IP | Current design (submit only) is policy-clean. Autocomplete is out. Saved places must be cached locally. |
| Open-Meteo forecast | [opened open-meteo.com/en/terms] free tier non-commercial: 600/min, 5,000/h, 10,000/day, 300,000/month, per IP and application. CC BY 4.0. | Rounded position, IP | Multi-location requests work: I sent 3 coordinates in one call and got a 3-element list in 0.28 s [measured]. A route with 6-10 sample points = 1 call. Daily limit of 10,000 is per IP/application, so a shared limit is not a concern at hobby scale. |
| Open-Meteo elevation | [opened open-meteo.com/en/docs/elevation-api] max 100 coordinates per request, 90 m resolution (Copernicus GLO-90), free for non-commercial, attribution to Copernicus and Open-Meteo. Verified one call returns 200 [measured]. | Rounded position, IP | 100 points = 1 request, enough for 1 point per 10 km on 1,000 km. |
| ORS / GraphHopper | [docs/ROUTING_BACKEND_2026-11-06.md] need keys, so only behind a Worker | route | Not needed now. |

Privacy implications [invented analysis built on the facts above]:
- Today a route reveals start and end to Nominatim (names) and Valhalla (coordinates), plus IP to both. Corridor search, ranking, car profile and battery state stay on device. That is the strongest property of the current design.
- Adding weather/elevation per route sends a series of coordinates along the route to Open-Meteo. Rounding to 0.1 degree (about 11 km, as the app already does) hides little for a route polyline because points are connected and the endpoints are inferable. The app's own privacy text correctly says rounding does not hide the IP. Any such feature needs consent per route (the app already has an explicit tap-to-fetch consent for temperature) and updated privacy text in 5 languages.
- A Cloudflare Worker for routing moves visibility from FOSSGIS to the owner's own infrastructure (Cloudflare sees IPs). It must not log URLs. That is a trade-off the owner decides, not a free improvement.
- Precomputed approaches (section 8) send nothing about the user, which is the privacy-best option wherever it works.

## 7. What the current model does not know (feasibility of closing each gap)

| Gap | Can we close it with static files + keyless data? |
|---|---|
| Tolls and ferry fares | Valhalla flags exist. Costs do not come from Valhalla. A hand-maintained table of the owner's real corridors (Oresund, Rodby-Puttgarden, Great Belt) is feasible; I did not verify any fares today. |
| Wind, rain, temperature along the route | Open-Meteo forecast, one multi-point call. Feasible; effect on PHEV is already modelled for one temperature, and the model could use a route average. |
| Elevation / hills | Open-Meteo elevation, one call. Effect on energy is real for PHEV but the owner's Sweden-Germany corridors are flat; low value for those corridors [invented]. |
| Live traffic | No keyless source. Not feasible. |
| Charging stops | Documented in EV_PRICE_SOURCES; separate topic. Out of scope here. |
| Ferry timetable and price | No keyless API checked. Owner table only. |
| Fuel price at arrival time | Static daily/hourly price history per station would need an archive job; GitHub Actions can store it. See idea 6. |

## 8. What must be precomputed by scheduled jobs (GitHub Actions, no backend)

- A per-station trust flag (fresh dated, undated-but-plausible, flagged), so the client stops recomputing `suspectLow` and tier per route. Cheap, deterministic, and testable in Python next to `plausibility.py`.
- Per-country reference statistics (median and 5th percentile of fresh dated 95/diesel) so the route "reference price" is not a median of undated rows. `_cs[cc]` already does this client-side for loaded countries; moving it to meta.json removes a dependency on the country file being loaded.
- **Corridor slices** for the owner's recurring corridors: a small JSON per named corridor (for example `corridors/malmo-hamburg.json`, a few kB to a few tens of kB) containing only the stations within 5 km of the Valhalla route plus fresh trust flags. Measured sizes: 330 stations for Malmo-Hamburg at 5 km. At about 0.5-1 kB per station that is under 330 kB raw, versus loading 6.7 MB DE raw. Feasible and the biggest performance and bandwidth win for repeat routes. Requires the route geometry to be computed once in the job (Valhalla called from Actions, 1 call per corridor per month, well inside terms).
- A toll/ferry cost table (hand-curated YAML to JSON).
- Price history per station or per corridor for "usually cheaper on Tuesdays" style hints: needs an archive job. Storage in the git repo grows, so use a rolling window.

## 9. Ideas, ranked (impact for the user, effort S/M/L for one developer, dependencies, risks)

1. **Tankerkoenig for Germany, then use it in the route tier logic.**
   - What: finish the planned Tankerkoenig integration (docs/TANKERKOENIG_SETUP.md exists) so Germany has dated 95/diesel prices; then German pumps reach tier 0 and can be called best.
   - Why: DE has 0 % dated prices today and holds 117 of 210 candidates on Malmo-Hamburg [measured]. This is the largest single quality gain for the owner.
   - Impact: very high. Effort: M (scraper + merge + licence/terms check, plus owner's key). Needs: Tankerkoenig API key (free, registration), licence confirmation (replies from MTS-K/Tankerkoenig/TankPuls pending per memory). Risk: licence terms for a public site; rate limits; ANWB fallback must remain.

2. **Honest confidence indicator on the route result ("price evidence: 55 of 210 pumps dated, 0 in Germany").**
   - What: one line plus a per-leg strip under the summary showing, per country on the route, how many candidates are dated/fresh/undated, computed from `R.cands`.
   - Why: the planner is already conservative but silent about why "best" is missing; the strip explains it without hiding data. All numbers are already in memory.
   - Impact: high (trust). Effort: S. Needs: new i18n strings in 5 languages. Risk: more text on a phone; keep it one line.

3. **Saved routes and a "my commute today" card.**
   - What: store up to 3 routes (start, end, car state) in localStorage and show the cheapest dated pump on the route on open, without typing or any network call except country files already cached.
   - Why: Billeberga-Malmo is a daily trip; routing and geocoding happen once, then replays need only the stored polyline (a 629-point polyline is about 3.6 kB raw JSON [measured]).
   - Impact: high for repeat users (the owner). Effort: M. Needs: nothing external. Risk: localStorage can be empty or blocked (wrap in try/catch); stored polyline gets stale if roads change, so re-route monthly.

4. **Show tolls and ferry cost, not just a ferry flag.**
   - What: use Valhalla `has_toll` / `has_ferry` (already in the response) to add the owner-maintained cost to the total trip cost and to the comparison "ferry route vs bridge route" (Valhalla `use_ferry` option allows a second request).
   - Why: Malmo-Hamburg is 373 km with the ferry vs 503 km without [from docs/ROUTING_BACKEND]; trip cost depends on fare, not just fuel. Today the ferry flag is stored but not shown prominently.
   - Impact: high for Sweden-Germany. Effort: M. Needs: curated fare table (I did not verify any fare), an extra Valhalla call for the alternative. Risk: fares change; mark the table with a date and say "estimate".

5. **Precomputed corridor slices for popular corridors.**
   - What: a scheduled job builds small JSON files per popular corridor (Malmo-Hamburg, Malmo-Berlin, Stockholm-Oslo, Oresund-Hamburg, Copenhagen-Hamburg) with trusted fresh stations, and the app uses them when the route matches.
   - Why: avoids downloading 1 MB compressed (6.7 MB parsed) DE data on a phone for a corridor that needs 330 stations [measured].
   - Impact: medium-high on slow mobile data. Effort: L (route matching logic, job, cache invalidation). Needs: Actions job calling Valhalla monthly. Risk: complexity, mismatch between precomputed and user route; fall back to the live path.

6. **Per-station price history and a "likely cheaper later today" hint.**
   - What: scheduled job stores a rolling 14-day hourly median per country and per corridor; the route card says "prices in Denmark are usually lowest in the evening".
   - Why: unique value over competitors, and static-file friendly.
   - Impact: medium. Effort: L. Needs: archive job and storage; need to prove a pattern exists first (do a one-off analysis before building). Risk: spurious patterns; wrong advice destroys trust.

7. **Weather-aware PHEV energy along the route, one consented multi-point Open-Meteo call.**
   - What: sample the route every 100-150 km, call Open-Meteo once (multi-location, 0.28 s for 3 points [measured]), average temperature feeds the existing `phevF`, show "cold in Hamburg, expect +x l".
   - Why: the temperature model exists; currently one temperature for the whole route.
   - Impact: medium (accuracy of the PHEV verdict). Effort: M. Needs: consent UI, privacy text in 5 languages, CSP is already open for api.open-meteo.com [code]. Risk: privacy (route-shaped coordinates); explicit tap per route; do not call without consent.

8. **Range-aware stop planner: "stop here or the next pump is 102 km away".**
   - What: use the measured gap logic (distance between priced, trusted pumps) to warn when no trusted pump exists within the remaining range, and suggest the last pump before a gap.
   - Why: Stockholm-Oslo has a 102 km hole [measured] and Billeberga-Malmo 29 km; combined with reserve litres it is a safety feature.
   - Impact: medium-high on long, rural legs. Effort: S-M (a pass over `R.cands` sorted by `along`). Needs: nothing new. Risk: absence of price data does not mean absence of pumps (SE: 13 % of stations carry a 95 price); wording must say "no priced pump", not "no pump".

9. **Sanity-check mix of reference prices and sources.**
   - What: compute the route reference price from dated rows only when 3 or more exist per 100 km window (already partly done), and when not, hide "saves X EUR" and show only the price rank. Add source-offset detection for ANWB vs dated sources per country in the pipeline.
   - Why: on Germany-heavy routes the "saves" amount is a median of undated rows [code]; wrong savings numbers are worse than none.
   - Impact: medium (trust). Effort: S. Needs: no external data. Risk: fewer headline numbers; acceptable.

10. **Keep Valhalla but add a one-line proxy and fallback plan.**
    - What: no change now; prepare the Cloudflare Worker (`route.<domain>`) described in docs/ROUTING_BACKEND_2026-11-06.md with ORS fallback, trigger it when FOSSGIS errors or traffic grows.
    - Why: FOSSGIS is volunteer-run without SLA and bars high-traffic sites [search].
    - Impact: reliability. Effort: M. Needs: ORS key, Cloudflare Worker. Risk: Worker shifts privacy responsibility to the owner.

## 10. Not checked

- I did not open the fossgis.de terms page itself (only a search snippet) or Tankerkoenig's terms. Re-read before launching widely.
- Toll and ferry prices were not verified.
- One snapshot at 14:00-14:25 UTC on a Friday; night/weekend freshness not measured. Countries other than SE, DK, DE, NO were measured only from a stale local copy.
- Timings are Node on a desktop; no real phone measurement. Route polylines come from live Valhalla, which may differ from what the app returns tomorrow.
- Not checked: Open-Meteo rate limits for browser-originating traffic from many different users (they are per IP, so each user has their own), Overpass or other sources, EV charging.
