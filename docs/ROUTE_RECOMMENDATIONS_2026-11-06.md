# Route and trip calculation: recommendations for the owner (2026-11-06)

Status: decision document. Research only, no code touched, nothing committed.

How to read this. Facts come from the six research notes `ROUTE_IDEAS_A_benchmarks.md` to `ROUTE_IDEAS_F_feasibility.md` (in this folder) and from the reviewed idea list. Those notes label each source as opened, snippet, vendor or idea; I did not open new web pages for this synthesis, so every claim below inherits the grade given in the note it comes from. Anything marked "my estimate" or "illustrative" is an invention for the sake of the example, not data. All money examples are for your Santa Fe PHEV (47 l tank, 13.8 kWh battery, roughly 40-54 km electric).

---

## 1. The vision in 5 lines

1. You type a trip and get one honest card: total cost (fuel, electricity, crossing), time, and a range instead of a fake-exact number.
2. The plan tells you in plain words where to fill up and how many litres, and why ("fill 22 l in Lübeck, it is about 9 cents cheaper than at the border").
3. It knows your car: the battery covers the commute, petrol covers the long haul, and it learns from your own logged trips.
4. It admits when it does not know: old or undated prices widen the range, and fares are labelled "check operator".
5. It stays free, keyless and private: no account, no tracking, the plan lives in a link you can share.

---

## 2. Recommendations

Scale: impact 1 (small) to 5 (large); effort S (days), M (a week or two), L (a month or more). Verdicts: do now, next, later, skip.

Two facts shape everything (note F, measured on live data 2026-11-06):
- Routing is fast (Valhalla answers in 0.5-0.7 s, corridor search 28-70 ms on desktop). Price data is the weak link: Germany has zero dated 95 prices (ANWB gives no timestamps), Sweden has 196 dated 95 prices out of 4,018 stations, and Billeberga-Malmo has 7 candidates, none dated.
- Crossings often cost more than the fuel. Oresund bridge for a car: 470 DKK at the booth, 420 online, 182 with ØresundGO (page opened, valid from 14 Sep 2026, note D). Scandlines Puttgarden-Rodby from 101.25 EUR (page opened, note D); other sources show 117-128 EUR; TT-Line Trelleborg-Travemünde about 247 EUR on average (aggregator, weak).

### R1. Share plan as a link
- What: the whole plan (route, fuel type, start fuel, reserve, assumptions) is stored in the URL hash, so you can send or bookmark it.
- Example: you plan Malmö-Hamburg, send the link to your partner, and she sees the same plan on her phone. The Billeberga-Malmö commute becomes a saved bookmark.
- Impact 4. Effort S.
- Dependencies: none. Do not put home tariff or home address in the link. Add a test that every assumption field survives the round trip (ABRP's shared-link bug loses assumptions, note A).
- Risks: long URLs; old links break if the field format changes, so version the hash.
- Recommendation: do now. It is also the cheapest way to test everything else.

### R2. Multi-stop fuel plan with "buy N litres here"
- What: replace the ranked pump list with a real plan of 0-3 stops, each with litres to buy and a one-line reason, using a small exact fuel-level calculation (note B, algorithm from an opened blog).
- Example: Malmö-Hamburg, 373 km. Start with a full battery and 20 l. The plan says: "Stop at Rødby side or Lübeck, buy about 25 l, arrive Hamburg with the reserve intact." Billeberga-Malmö: plan says "no petrol stop needed, battery covers it".
- Impact 5. Effort M.
- Dependencies: existing start fuel, reserve and consumption inputs; unit tests in `tools/test_route_model.js`. Needs the price freshness guard (R3), otherwise it plans around prices that may be wrong.
- Risks: precision it cannot back up. Use "about" and "estimate" wording. Cap at 3 stops and always keep the reserve.
- Recommendation: do now. This is the core upgrade.

### R3. Plan trust: price-age range and freshness line
- What: the plan total is shown as a range with a line like "prices up to 14 h old, 2 of 3 stops undated". Replace the hard 10-hour cliff with a simple age-based penalty. Skip the fancy statistics for now.
- Example: Malmö-Hamburg: "about 61-68 EUR for fuel; Germany prices undated". Billeberga-Malmö: "no dated price near this route, showing nearest priced stations".
- Impact 4. Effort S.
- Dependencies: age and grade fields already exist. Guessed constants are my estimate; mark the range as an estimate until R11 provides real data.
- Risks: a range that looks too wide frightens users; a range that is too narrow lies. Start conservative.
- Recommendation: do now, together with R2.

### R4. Trip cost card with alternatives table
- What: one card showing for each route alternative: fuel, electricity, crossing fare, time. Cheapest, Balanced and Fastest as rows.
- Example: Malmö-Hamburg via the bridge and Rødby ferry versus via Trelleborg-Travemünde: the table shows the crossing cost is larger than the fuel difference, so the ranking flips versus a fuel-only view.
- Impact 5. Effort M.
- Dependencies: Valhalla alternatives are not verified on the FOSSGIS instance (note C says `alternates` is supported by Valhalla; note E says not verified on the public instance). Test first. Needs R5 for fares.
- Risks: tolls and fares are not verified data. Label "check operator". Keep to one screen on a phone.
- Recommendation: next. Ship fuel plus electricity plus time first, add fares when R5 exists.

### R5. Crossing and toll fare table (hand-kept, dated)
- What: a small JSON file with bridge, ferry and vignette fares, each with a "seen on" date and source link. Entries older than 90 days grey out, following the EV_PRICE_SOURCES rule.
- Example: Oresund bridge shown as "420-470 DKK (182 with ØresundGO), seen 2026-11-06". Fehmarn tunnel shows no toll because it opens no earlier than 2031 (note D).
- Impact 4. Effort S-M.
- Dependencies: you or I refresh the file by hand; Valhalla only gives a toll flag (`has_toll`) and a ferry flag, never money amounts (opened docs, note D). Paid toll APIs are out.
- Risks: stale fares. The 90-day grey-out and the "check operator" label handle this.
- Recommendation: next, alongside R4.

### R6. Assumptions panel: speed, value of time, start energy
- What: one small panel with three controls (cruise speed, what an hour is worth to you, start fuel and battery). Results show ranges. This merges the earlier speed slider, time-value slider and what-if ideas.
- Example: dropping from 130 to 110 km/h on Malmö-Hamburg saves roughly a quarter of battery-equivalent energy and costs about 15-20 minutes (my estimate from a road-load calculation, note C; it matched one measured Zoe data point, so it is generic SUV physics, not Santa Fe data). The panel shows "slower saves about 21 EUR per hour of time given up" (my model, labelled estimate).
- Impact 4. Effort M.
- Dependencies: verify that Valhalla's `top_speed` behaves as promised before promising it; default stop minutes assumed.
- Risks: false precision. Drop stop-quality penalties (stop attributes are mostly unavailable and would be invented).
- Recommendation: next.

### R7. Per-segment energy profile (foundation)
- What: compute energy use per road segment (speed, optionally elevation) instead of one temperature and the fixed `RT_REAL = 0.75` factor.
- Example: Billeberga-Malmö is a mostly motorway commute, so the battery drains faster than the flat factor assumes; the profile shows you arrive with the battery at 3 percent, not 12.
- Impact 4 (enabler). Effort M.
- Dependencies: one live Valhalla call to confirm the maneuver and speed fields; `elevation_interval` returns elevation inside the existing /route call (verified live, note C), so no new host. Public rate limits and response size (20-50 kB per route, note F) are the risk.
- Risks: elevation is noisy at bridges and tunnels; Sweden-Germany is nearly flat (100 m climb costs about 0.67 kWh, my calculation), so treat elevation as optional.
- Recommendation: next. It unlocks R8, R12 and later accuracy.

### R8. Energy-along-route strip
- What: one thin line under the map showing battery and fuel level along the trip.
- Example: Malmö-Hamburg: battery empties around Lund, petrol takes over, fill-up marks show where the plan refuels.
- Impact 3. Effort M.
- Dependencies: R7. Do not promise elevation.
- Risks: clutter on a phone. Keep it to one line.
- Recommendation: later (after R7). ABRP's per-segment graph is its best-loved feature (note A), so it earns its place, but not before the foundation.

### R9. Border-aware tankering card (one-way first)
- What: when the destination or route crosses a border, say whether to fill before or after it, using live station prices only, never national averages.
- Example: Sweden-to-Germany: the EU Weekly Oil Bulletin week of 19 Oct 2026 shows petrol at 1.64 EUR/l in Sweden and 2.18 in Germany (opened, republished; grade assumed, note B). So fill up in Sweden. For diesel the gap is much flatter (2.04 vs 2.27), so the card must not assume the same advice. Denmark at 2.61 is dearer than both, so never fill on the Danish leg.
- Impact 4 for you, 3 overall. Effort M.
- Dependencies: R2 plan engine; live per-fuel prices; German price quality (Tankerkönig is still pending, emails sent today, so German prices are undated for now).
- Risks: carrying fuel across a border is only worth it if the tank can hold the gap; the plan must respect the 47 l tank. Use "about" in the wording.
- Recommendation: next.

### R10. Germany and Austria 12:00 price-rise rule
- What: if you arrive at a German station before noon it is typically a bit dearer or cheaper depending on the rule; the plan nudges stop time or notes it.
- Example: arriving near Flensburg at 11:40 versus 12:20 changes the shown price expectation.
- Impact 2-3. Effort S.
- Dependencies: confirm the legal state from a primary source first (Germany from 1 Apr 2026; Austria dates conflict between sources). Make the rule a per-country config flag. Any "5-10 ct/l" claim needs a citation or must go.
- Risks: acting on a rule that is not actually in force.
- Recommendation: next, but only after the primary-source check.

### R11. Price-cycle learning job (collect now, use later)
- What: a scheduled GitHub Action stores small aggregates (hour of day, weekday, per country) of price changes. Never raw snapshots.
- Example: after eight weeks it can say "Danish petrol is usually cheapest Tuesday evenings", and it calibrates the error range in R3.
- Impact 5 long term, 0 short term. Effort M.
- Dependencies: weeks of data; repo-size discipline. Current scrape history is not retained.
- Risks: repo growth; aggregates only.
- Recommendation: do now (start collecting), use later.

### R12. Local trip log and calibration
- What: you enter kWh, litres, km, temperature and speed after a trip (manual only, stored in the browser). The app fits a correction for your Santa Fe.
- Example: after five Malmö-Hamburg trips it says "your real consumption is 8 percent above the model; applying it".
- Impact 4 long term. Effort M.
- Dependencies: localStorage, outlier guards (sanity ranges). Fuelio and Spritmonitor CSV import is deferred because the column layouts are unverified.
- Risks: a sample of one car is small; show the correction as a suggestion, not silent.
- Recommendation: next. It is the only real calibration lever.

### R13. Multi-waypoint export to navigation apps
- What: "Open in Maps" with the plan's fuel stops as waypoints.
- Example: Malmö-Hamburg with two fuel stops opens in Google Maps with both. Google's format uses `%7C` as separator, limit 3 waypoints on mobile browsers and 9 elsewhere (opened, note E). Apple Maps multi-stop is unofficial and must be tested on your iPhone.
- Impact 3. Effort S.
- Dependencies: device testing on iPhone and Android. Cap at 3 stops.
- Risks: app behaviour changes.
- Recommendation: next.

### R14. Destination and hotel charging credit
- What: a checkbox "I can charge at the destination or hotel" which credits the electric kilometres on the way back.
- Example: Hamburg hotel with a charger: the return trip starts with a full battery, so the plan buys less petrol. The 6.5 EUR value is an estimate, labelled.
- Impact 3. Effort S (checkbox); the two-leg return view is M and should wait.
- Dependencies: your own statement only.
- Risks: assuming charging access you do not have.
- Recommendation: next (checkbox only).

### R15. Backup pump line
- What: one line under each stop: "if dearer, next pump in 12 km".
- Example: Plan names a Lübeck station; fallback says "next cheaper option in 14 km".
- Impact 2. Effort S.
- Dependencies: the top list already exists.
- Risks: none notable. Skip the minimax-regret maths (too complex for a phone).
- Recommendation: next.

### R16. AC charging stop verdict
- What: answers "does a public AC charging stop pay?" for a PHEV that charges slowly.
- Example: at the German average of roughly 52 cents/kWh (my estimate, secondary source, note C) a 30-minute stop adds a few kWh worth less than the time. Usual answer: not worth it.
- Impact 3. Effort S.
- Dependencies: your charger's rating (kW); cited, dated AC prices; no Swedish AC price source exists. If inputs are missing, show nothing.
- Risks: rests on one secondary price source.
- Recommendation: later.

### R17. Round-trip planning
- What: plan the way back too, including the fuel that carries over and the return crossing.
- Example: Malmö-Hamburg-Malmö in one view with one total cost.
- Impact 4 for you. Effort L.
- Dependencies: R2, R9, R14.
- Risks: complexity, long phone screens.
- Recommendation: later.

### R18. Departure-time hint
- What: "leaving a few hours later saves about X" from your own price history.
- Example: only shown where data supports it; not for Sweden at first.
- Impact 2. Effort M.
- Dependencies: R11 data.
- Risks: noise passed off as advice.
- Recommendation: later.

---

## 3. Bundles and suggested order

### Bundle A: Smart fill-up (the plan engine)
R1 share link, R2 multi-stop plan, R3 plan trust, R15 backup pump, R9 border-aware tankering, R10 noon rule, R13 nav export.
Order: R1, R3, R2, R15, R13, R9, R10 (after source check).
Why: all use existing inputs, and the order delivers a visibly better plan within a few small steps.

### Bundle B: Hybrid brain (knows your Santa Fe)
R7 energy profile, R6 assumptions panel, R12 trip log, R14 charging credit, R8 strip, R16 AC verdict.
Order: R7, R6, R14, R12, R8, R16.
Why: R7 replaces the generic 0.75 factor, R12 then calibrates it with your real trips.

### Bundle C: Trip companion (whole-trip view)
R4 cost card, R5 fare table, R17 round trip, R11 price-cycle job, R18 departure hint.
Order: R11 (start now, runs in the background), R5, R4, then R17 and R18 when data and the plan engine exist.
Why: the cost card needs fares and alternatives; round trip needs the finished engine.

Suggested overall first five: R1, R3, R2, R11 (collect), R5/R4.

---

## 4. What we should NOT do

- Hourly weather and wind along the route: wind scaling is an assumption dressed as precision, Open-Meteo's free tier is non-commercial, and it needs a CSP change and per-point calls. Revisit only if the trip log shows wind is a real error source.
- Per-segment battery hold/spend advice: the claimed gain is single digits at best and depends on Santa Fe drive-mode behaviour that is unconfirmed.
- Separate "what I paid" log: a sample of one cannot calibrate error bars; the trip log covers it.
- Paid toll APIs such as TollGuru: they need a key and a backend and are metered.
- Crowd-reported prices, accounts or location tracking (GasBuddy style, note A): the opposite of this project.
- Neighbour-shrinkage and z-score price refinements, minimax regret, "gap to theoretical floor", stop-quality penalties: guessed constants would be false precision, or too complex for a phone.
- CarPlay or Android Auto app, home-screen widget, per-user web push: native-only, or need a backend that conflicts with the privacy rule (note E).
- Fehmarn toll: no toll is set and the tunnel is not open before 2031 (note D).
- Quoting national averages as if they were station prices.

---

## 5. Open decisions for you

1. Is "do now" = R1, R2, R3, R11 acceptable, or do you want R4/R5 first because crossing costs dominate your Sweden-Germany trips?
2. Will you keep the fare table by hand, and is a 90-day grey-out acceptable?
3. Are you willing to log trips after driving (R12), and can you share some past figures (kWh, litres, km, speed, temperature) to seed the calibration?
4. What is your home charger rating in kW, and a typical AC price you accept for R16?
5. Does the Santa Fe in your use keep EV mode on motorways, or does it switch automatically? (Needed before reconsidering hold/spend advice.)
6. May I check Valhalla alternatives and `top_speed` on the public FOSSGIS instance before we promise R4 and R6?
7. Germany: wait for Tankerkönig before shipping R9 and R10, or ship with undated ANWB prices labelled as such?
8. Which nav app do you use most on the iPhone (affects R13 testing)?
9. Do you want round trips (R17) to be the next big thing after the engine, or stay on the later list?
