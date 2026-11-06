# Route ideas A: benchmarks of fuel and trip planners (2026-11-06)

Status: research only, for owner decision. No code changed.
Tone: plain English.

## How claims are labelled

- **[opened]** = I fetched the page and read it today.
- **[snippet]** = only seen in a web-search summary, not opened. Treat as indicative.
- **[vendor]** = vendor marketing; claims are not independent.
- **[idea]** = my invention, not from any source.
- Limits of this research: I did not open abetterrouteplanner.com itself (fetch returned only the title), did not find independent reviews of GasBuddy's trip calculator, and found nothing usable on Chargemap, PlugShare, Fuelmap, Tankbillig or Apple/Google Maps fuel-stop UX beyond the notes below. Gaps are listed at the end rather than filled with guesses.

## 1. What the benchmark tools do

### ABRP (A Better Routeplanner)
- Reference consumption is a base value at constant 110 km/h in near-perfect conditions. The plan then adds elevation, temperature and speed on top. Reference speed is set relative to the speed limit. [snippet] https://abrp.featurebase.app/help/articles/3305478-reference-consumption (search result)
- Users run what-if games with max speed and reference consumption; one reviewer found that clicking a route segment shows elevation and remaining charge. [opened] https://wind-works.org/is-a-better-routeplanner-better-a-review-for-the-bolt/
- Settings: preferred charging networks, minimum arrival charge, departure charge. [snippet, forum-based]
- Shareable plan link exists. A ticket reports a shared link losing reference consumption (defaulting to a wrong value) so the recipient sees a different result. [snippet] https://abrp.featurebase.app/help/articles/6991246-share-a-plan
- Weaknesses (opened): estimates sometimes 10% or more off with no pattern; result shown as percent charge, not kWh; rerouting needs typed waypoints; glitchy, graph unexplained. https://wind-works.org/is-a-better-routeplanner-better-a-review-for-the-bolt/
- Weaknesses (opened, one user): saved routes do not sync between browser and phone; alternatives are hard to select and compare by time, distance and stops. https://abrp.featurebase.app/p/a-few-suggestions-after-using-abrp-extensively
- Weaknesses (snippet, vendor of a competitor, so biased): crashes, Android Auto/CarPlay bugs, charging-time inaccuracy, premium paywall for in-motion features. https://www.upperinc.com/reviews/a-better-route-planner-review/
- Praise: depth of data, accuracy on a hard desert trip, responsive designers. [opened wind-works]

Lesson: the delight is the trust-building transparency (graph of remaining energy per segment, tunable assumptions). The pain is opaque estimates and awkward comparison of alternatives.

### GasBuddy
- Trip Cost Calculator finds cheapest stations along a route, round trip or one way, using crowd-reported prices. [snippet, test-domain copy] https://test.gasbuddy.com/tripcostcalculator
- Advice repeated across articles: use it just before leaving because prices move. [snippet] the-gadgeteer.com 2015
- Crowd-sourcing is the core model: it needs accounts and location, the opposite of this project.

### TollGuru / ViaMichelin (trip cost)
- TollGuru: one request returns cheapest, fastest and other alternatives with toll, fuel, distance, ETA per route. [vendor] https://www.mapup.ai/products/tollguru
- ViaMichelin: fastest, shortest, economic and recommended routes; saves consumption and fuel type; tolls adapted to vehicle type; sources disagree on exactly how "economic" is defined. [snippet] https://www.viamichelin.com/magazine/article/viamichelin-routes-an-ever-tighter-grip-on-your-travel-budget
- A caravan-club forum notes the no-toll route is sometimes much slower, so users want cost versus time side by side. [snippet]

Lesson: the cost-vs-time table of alternatives (fuel + toll + ferry + time per route) is the standard delight. Europe tolls and ferries matter for Sweden-Germany (Oresund bridge, Fehmarn/Rodby-Puttgarden or Trelleborg-Rostock ferries, German no-toll, Danish bridges).

### Google / Waze / Apple Maps
- Google eco-routing: picks a lower-fuel route when arrival time is about equal, shows relative saving and time difference; uses engine type; does not apply to EVs and adds no charging stops. [snippet] https://support.google.com/maps/answer/11470237
- Waze: fuel prices along route (US, older article) and EV charger filtering by plug type. [snippet] https://en.globes.co.il/en/article-1000759047
- Apple Maps EV routing considers elevation, weather and current charge; does not clearly show fuel prices. [snippet, low quality]
- Gap: none of these shows a PHEV plan that mixes electric range, petrol price and electricity price. That is the owner's car and is unserved. [idea, based on absence in results]

### Spritmonitor / Fuelio
- Fuelio: fuel log, cost module (maintenance, tolls, parking), cost per km charts, CSV import/export. [snippet] https://apps.apple.com/us/app/fuelio-gas-log-mpg/id1487753318
- Spritmonitor: free log, offline mode with later sync, selectable units. [snippet] https://apps.apple.com/us/app/spritmonitor/id616137163
- Lesson: real measured consumption is the thing every planner lacks as an input. A privacy-first site can read it from a CSV the user keeps locally.

### German station apps (Clever-Tanken, ADAC, Einfach-Tanken, mehr-tanken)
- Einfach-Tanken v3 added favourites and route search (stations on the way and their current price); data from Bundeskartellamt. How the corridor works is not explained. [opened] https://www.iphone-ticker.de/spritpreis-app-einfach-tanken-erhaelt-neue-funktionen-274514/
- mehr-tanken: forecast of when to fill, price alarm. [snippet] https://www.netzwelt.de/downloads/spritpreis-apps-diesen-smarten-helfern-tankt-guenstiger.html
- Clever-Tanken: large community, ads, cluttered map when dense. [snippet]
- Privacy: test.de flagged mehr-tanken and T-Online Tanken-App as critical (network operator sent to third parties). [opened, but dated January 2014] https://www.test.de/Spritpreis-Apps-im-Datenschutz-Test-Vier-sind-kritisch-4663692-4663694/ Use only as "privacy is a known worry in this category", not as a current claim.
- Lesson: price alarms and "best time to fill" are the sticky features; both need either push (backend) or local logic.

## 2. Delight patterns extracted

1. Cost breakdown per trip: fuel + electricity + ferry + toll + total, per alternative.
2. Alternatives side by side with time, distance, cost, stops (ABRP users ask for this explicitly).
3. Tunable assumptions with live recompute: speed, start charge, reserve, consumption.
4. Per-segment graph of remaining energy/fuel so the plan can be trusted.
5. Plan stops, not only stations: "where, how much to buy, why there".
6. Shareable plan that reproduces exactly (and a known failure when assumptions are not in the link).
7. Honest freshness: "use it just before leaving".

## 3. What a free, static, privacy-first site can do better

- No account and no tracking, and still shareable: put all assumptions in the URL hash (never sent to a server).
- Show data age and grade on every number (already a strength).
- PHEV-aware mixed energy plan nobody else shows.
- Learn from the user's own log locally (localStorage / imported CSV) without upload.
- Cost "what-if" with no server round trip, since prices are already loaded.

## 4. Ideas for EuroFuelPrices (ranked)

All effort for one developer: S = days, M = 1-2 weeks, L = more.

1. **Trip cost card with alternatives table.** For each Valhalla alternative (fastest, no-ferry, no-toll if available) show fuel, electricity, ferry, toll, total, time, difference vs cheapest. Impact: high (the standard delight, absent for Sweden-Germany). Effort: M. Needs: Valhalla alternatives and toll/ferry flags (keyless); ferry fare table maintained by hand as a small JSON; toll data limited (Oresund, Great Belt, Fehmarn) by hand. Risk: hand-kept fares go stale, so label with date and "check operator".
2. **Share plan as URL hash.** Encode from, to, car profile summary, start fuel/battery, reserve, currency in the hash; restore on open. Impact: high (sharing, saved routes without sync, fixes ABRP's complaint). Effort: S. Needs: none. Risk: ABRP-style bug if any assumption is omitted from the link; test round trip. Never put home tariff or exact home address in it.
3. **"Cost of the plan" what-if sliders.** Sliders for speed, start fuel/battery, reserve, price tolerance, with live recompute from cached data. Impact: high. Effort: M. Needs: consumption-vs-speed curve (assumed generic factor, flag as estimate; the PHEV temperature doc already has a model). Risk: false precision; show a range, not a point.
4. **Energy-along-route strip.** A small chart per segment: battery, tank, and the stops, as ABRP's reviewed graph does. Impact: medium-high (trust). Effort: M. Needs: elevation is optional (skip it first). Risk: clutter on phones; keep one line.
5. **Stop plan wording: "buy X litres here, because Y".** Replace "fill the tank" with litres needed to reach the next cheaper stop or the destination plus reserve, with the reason and the saving vs the route median. Impact: high. Effort: M. Needs: existing rank logic. Risk: needs trusted prices; apply the existing freshness/grade guard.
6. **Price-age confidence on the plan total.** Show "cost based on prices 2-9 h old, one station grade C" and a pessimistic/optimistic total. Impact: medium (differentiator vs crowd apps). Effort: S. Needs: existing age and grade fields. Risk: low.
7. **Local trip log and calibration.** Optional: user enters actual litres and km (or imports a Fuelio/Spritmonitor CSV) and the planner uses their real consumption and PHEV electric share. Stays on device. Impact: medium-high for the owner and committed users. Effort: M. Needs: CSV formats (Fuelio export documented as CSV [snippet]; verify columns before building). Risk: parsing variants; start with manual entry.
8. **Fill-before-border advice.** For cross-border routes show "fill in country X, not Y" with the saving net of detour, extending the existing per-country best pick. Impact: medium-high (core Sweden-Germany case). Effort: S-M. Needs: existing data. Risk: currency/fee display consistency with the card-fee setting.
9. **Departure-time hint (later).** Use own scraped price history to say "usually cheaper in the evening for this country" once enough history exists. Impact: medium. Effort: M. Needs: history retention in the scheduled jobs. Risk: weak signal in Sweden; show only where data supports it. Competitors (mehr-tanken) have a forecast [snippet], so it is expected in Germany.
10. **Export plan to nav app with all stops.** Multi-waypoint link to Google/Apple/OsmAnd rather than one "via here". Impact: medium. Effort: S. Needs: none. Risk: waypoint limits per app.

Suggested order if the owner wants quick wins: 2, 6, 10, then 1, 5, 3.

## 5. Not found / not verified

- ABRP premium tiers and exact weather handling (forum-level only).
- GasBuddy independent user reviews; the GasBuddy "Europe, 150,000 stations" claim is unverified.
- Chargemap, PlugShare, Fuelmap, Tankbillig, Apple/Google fuel-stop UX: no usable sources found.
- Fuelio/Spritmonitor CSV column layouts: not opened.
