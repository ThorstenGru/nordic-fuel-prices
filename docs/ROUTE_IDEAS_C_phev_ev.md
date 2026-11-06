# Route ideas C: PHEV and EV trip intelligence (2026-11-06)

Research only. No code changed, nothing committed. Lens: what makes the route planner exceptional for a plug-in hybrid (Santa Fe PHEV, Type 2 AC only) on Sweden-Germany and commuting trips, using only static files, Actions jobs and keyless or hobby-friendly APIs.

Labels: **[V]** = I ran or opened it this session. **[S]** = taken from a source I opened or saw as a search snippet (stated per row). **[A]** = my assumption or my own arithmetic. **[INV]** = my invention (feature idea, not a fact). Existing docs are cited by file name.

## 0. What the code does today (read from web/index.html, rt* functions, lines 4047-4368)

- `rtPlan` walks a single energy budget: electric km first (`elecKm = car.range * 0.75 * f(T) * battPct`), then petrol for the rest, one temperature `tmpNow()` for the whole trip, `gEl` extra litres while on battery. Battery is always spent from the start of the route, at a speed-blind consumption.
- `rtCand` prices a detour as electric if the pump is reached while battery remains, else petrol. Litres bought = what is burned from there to the destination.
- Valhalla is called with `directions_type: 'none'`, no elevation, no per-segment speeds. `top_speed` and `use_highways` are not used.
- Not modelled anywhere: speed, wind, elevation, charging stops, destination charging, roof box or trailer, temperature that changes along the route or over the trip hours.
- The weakest assumption for the owner's real trips is the single constant `RT_REAL = 0.75` and one scalar temperature. Almost every idea below replaces that scalar with a per-segment profile.

## 1. Facts I verified live this session [V]

| Check | Result |
|---|---|
| Open-Meteo forecast with two comma-separated locations, hourly `temperature_2m, wind_speed_10m, wind_direction_10m` | HTTP 200, header `access-control-allow-origin: *`, `X-RateLimit-Limit: 600` per minute window, request cost 2.0 for 2 locations (so cost is per location). This **settles the CORS question** left open in PHEV_TEMPERATURE_MODEL_2026-11-06.md. |
| Open-Meteo elevation `api.open-meteo.com/v1/elevation?latitude=55.6,57.7&longitude=13.0,11.9` | `{"elevation":[8.0, 17.0]}`. Docs page (opened): up to 100 coordinates per call, 90 m resolution, Copernicus GLO-90, attribution to Copernicus and Open-Meteo, non-commercial free use. |
| Valhalla FOSSGIS `/route` with `"elevation_interval":100` added to the existing request | Returns `legs[0].elevation` as an array of metres, one per 100 m of route, in the **same call** the app already makes. No extra request, no new host. Route API docs (opened) say 30 m matches the data resolution and no elevation is returned unless you ask. |
| Valhalla FOSSGIS `/height` POST with `range:true, resample_distance` | Returns a resampled shape with heights. Works as an alternative, not needed if `elevation_interval` is used. |
| Valhalla route options (docs opened) | `alternates` (not for multi-point routes), auto costing `top_speed` 10-252 km/h (default 140), `use_highways` 0-1, `use_tolls`, `use_ferry`. |

Consequence: elevation and wind need **no new keys, no new CSP host beyond `api.open-meteo.com`**, and elevation needs no host at all. Open-Meteo's free tier is non-commercial; the earlier licence caveat (ads, subscriptions) still applies.

## 2. Mixed-energy optimisation: when to burn the battery

### 2.1 What the literature says

- Route-aware blending beats the default "deplete first, then sustain" strategy. Reported gains are 1 to 20 percent of fuel depending on route, length and start state of charge: SAE 2024-01-2775 route-optimized mode blending, up to 20 percent [S, search snippet; https://saemobilus.sae.org/papers/route-optimized-energy-usage-a-plug-hybrid-electric-vehicle-using-mode-blending-2024-01-2775], Chalmers study up to 20 percent vs charge-depleting-then-sustaining, strongly trip-dependent [S, snippet; https://publications.lib.chalmers.se/records/fulltext/160800/local_160800.pdf], UC Irvine dissertation 1-10 percent on long traffic-heavy routes [S, snippet; https://escholarship.org/uc/item/83p636qq]. None opened in full.
- An old Argonne-archived Prius conversion test found fuel saved during depletion was larger on an urban cycle (55 percent) than on the highway cycle (44 percent), and depletion took about 54 km urban vs 80 km highway [S, snippet; http://www.transportation.anl.gov/pdfs/HV/462.pdf]. One old vehicle; treat as direction only.
- Hyundai's own manual describes charge-depleting (electric motor alone until the battery is low) and charge-sustaining (motor-only at start and low speed, engine plus motor on acceleration and at high speed, regen on deceleration) [V, https://ownersmanual.hyundai.com/full_webhelp/NX4PHEV/2026/en_US/id863e08c99ae.html, a Tucson PHEV page, not Santa Fe]. That page does not cover the EV/HEV/AUTO selector, cold behaviour or reserve thresholds. I found **no source** that the Santa Fe PHEV has a dedicated "charge while driving" mode; sources for the Tucson say EV, HEV and Auto, and EV mode becomes unavailable at low charge (one test: about 15 percent) [S, snippet; automobile-propre.com Tucson Supertest]. Drive-mode lists for the Santa Fe conflict between sources (Normal/Eco/Sport/Smart/Snow vs Eco/Sport/MyDrive) [S, search summary]. **Owner must read the Santa Fe manual** before the app says anything about "HEV hold".
- The Cars.com Tucson PHEV test at 37 F: EV range at start 31 of 33 mile EPA, battery fully used after 31 miles of a 200-mile route, engine often started with charge left [V, https://www.cars.com/articles/toyota-rav4-prime-and-hyundai-tucson-plug-in-hybrid-testing-ev-range-efficiency-in-colder-temperatures-462054]. So in Auto mode the Hyundai family may not use the battery the way a planner assumes. A planner that says "use battery on city segments" is only true if the driver selects EV or HEV deliberately.

### 2.2 My model of where a kWh is worth most [A]

Value of one battery kWh = litres of petrol it displaces times pump price, minus a charge cost. Rough PHEV numbers [A]: city electric 14-16 kWh/100 km vs charge-sustaining 5-6 l/100 km gives about 0.35-0.40 l per kWh; motorway electric 24-28 kWh/100 km vs CS 8-9 l/100 km gives about 0.33-0.36 l per kWh. These are close, so **the electric-vs-petrol equal-value argument is weak** and the stronger levers are:

1. Do not waste battery in segments where the engine runs anyway (hard acceleration, steep climb, extreme cold), and do not leave charge unused at the destination if a charger is there.
2. Use electric where the engine is least efficient: stop-and-go, cold-start city, low load (engine at 20-25 percent efficiency vs about 30-35 percent at steady motorway load) [A, typical engine physics, no source opened].
3. Zero-emission or low-emission zones and noise-sensitive destinations (hotel, city centre) where the battery is the only option [INV]. I did not verify any zone rules for PHEV in SE/DK/DE.
4. Keep the last X km of the trip, and the first km at the destination, electric if the destination has no charger but a city leg follows.

Hence the useful planner output is not "optimal control" but a **per-segment advice with an honest euro value**: "Hold charge (HEV) for the last 40 km in the Malmo urban area; save about X EUR vs spending it on E20". Because the gain depends on a driver action the car may not honour in Auto mode, ship it as advice with a stated, small confidence, never as a promise.

Simple algorithm [INV]: split the route into 5-10 km segments by road class and speed (from Valhalla maneuvers), compute for each the marginal litres saved per kWh using the model in section 3, sort descending, assign battery energy greedily until the usable kWh is spent, output contiguous runs. This is the same ranking idea the SAE paper uses (segments sorted by battery-vs-fuel effectiveness) [S, snippet], so the design is not novel physics.

## 3. Speed effect on consumption (motorway 90/110/130)

### 3.1 Sources
- ÖAMTC test via e-mobileo, one Renault Zoe over 91 km: 21.4 kWh/100 km at 100 km/h vs more than 27.8 at 130, about 30 percent more [V, https://www.e-mobileo.de/wie-schnell-auf-der-autobahn-das-optimale-tempo-fuer-e-autos]. One car, one test.
- ADAC winter test: at 0 C and mostly motorway speeds consumption averaged 57 percent above WLTP [S, snippet; https://heise.de/-11149567]. ADAC 2025 EV range 15.5 to 29.7 kWh/100 km, a 90 percent spread [S, snippet; autokostencheck.de].
- Test-Aankoop: 100 vs 120 km/h costs 3 minutes on 30 km; its only measured figures are a Lynk & Co 01 PHEV at 120 km/h: about 12.7 l/100 km while charging the battery on the move vs about 6.8 l/100 km when not [V, https://www.test-aankoop.be/mobiliteit/auto-s/nieuws/hoeveel-bespaar-je-als-100-per-uur-rijdt-op-de-snelweg]. Evidence that the engine-charging-the-battery mode is very expensive; relevant if the Santa Fe has a charge mode at all (unverified).
- Real-world PHEV charge-sustaining average in Europe: 7.4 l/100 km; overall real-world average 5.9 l/100 km [S, snippet; ICCT-type analysis cited in search results, topontiki.gr PB-PHEV PDF, not opened].

### 3.2 My road-load calculation [A, my arithmetic, not a measurement]

Assumptions: mass 2,100 kg, CdA 0.85 m2, Crr 0.009, air density 1.2, drivetrain 85 percent electric, engine thermal efficiency 30 percent (10 kWh per litre, so about 3 kWh at the wheels per litre).

| Cruise | Wheel energy kWh/km | Battery Wh/km | vs 110 km/h | Time for 300 km |
|---|---|---|---|---|
| 90 km/h | 0.140 | about 165 | -23 % | 3 h 20 |
| 110 km/h | 0.183 | about 215 | 0 | 2 h 44 |
| 130 km/h | 0.236 | about 278 | +29 % | 2 h 19 |

Sanity check: 130 vs 100 km/h gives about +30 to +35 percent in my model, matching the Zoe measurement (+30 percent) [S, V]. My absolute Wh/km are higher than the app's 192 Wh/km WLTP value, which is expected: 192 is a WLTP number, and the app already applies `RT_REAL = 0.75`. The speed model is a way to replace that constant with a function of speed.

Value of time implied by slowing from 130 to 110 [A]: 0.053 kWh/km less wheel energy is about 1.8 l per 100 km, about 2.9 EUR per 100 km at 1.60 EUR/l, or 8.7 EUR over 300 km for 25 minutes: about 21 EUR per hour of time bought. If the driver's time is worth more, drive faster; the app can show this number and let the user set a value of time. Legal speed caps matter more than choice in Sweden (110/120 km/h) and Denmark (130); Germany has many unlimited stretches where the choice is real [A, general knowledge, not sourced here].

### 3.3 Feature use
Get per-segment speed from Valhalla by switching `directions_type` from `none` to `maneuvers` (maneuver `length` and `time` give average speed per maneuver; field names from Valhalla docs memory, not verified this session: test one call). Apply a speed multiplier per segment, scale electric and petrol use, and show "your trip at 130 vs 110: +X EUR, -Y min" as a slider (Cruise speed cap 90/110/120/130/no cap). Also offer `top_speed` in the Valhalla request so the route and time reflect the cap.

## 4. Wind, elevation, temperature along the route

### 4.1 Wind [A computation, Open-Meteo data verified]
Aerodynamic energy scales with airspeed squared. At 110 km/h a 20 km/h headwind makes airspeed 130 and aero energy x1.40 (aero is about 72 percent of wheel energy at 110 in my model), so wheel energy +29 percent; a 20 km/h tailwind gives aero x0.67, so about -24 percent. Because of the convexity, a round trip in constant wind costs more than a calm one. Open-Meteo gives 10 m wind speed and direction hourly [V]; road-level wind is usually lower, so apply a factor of about 0.6 [A, not sourced]; flag it as uncertain. Cost: one forecast call with 8-12 comma-separated points along the route (rate cost per location, 600/min limit [V]).

### 4.2 Elevation [A computation, data verified]
Climbing 100 m costs m g h = 2,100 x 9.81 x 100 = 2.06 MJ = 0.57 kWh at the wheels, about 0.67 kWh from the battery at 85 percent. A 300 m net climb is about 2 kWh, roughly a fifth of the usable battery. Regen on descent returns part of it; 60-70 percent is my assumption, unsourced. Sweden-Germany via Oresund and Jutland is nearly flat (Open-Meteo samples at 55.6 N 13.0 E gave 8 m, Gothenburg 17 m [V]), so the feature matters for Norway, the Alps, Czech Republic detours. Net gain or loss is the large term; wiggles are second-order. Data: Valhalla `elevation_interval` [V], zero extra requests.

### 4.3 Temperature and weather along and over time [INV built on existing PHEV model]
The existing curve in PHEV_TEMPERATURE_MODEL_2026-11-06.md uses one daily temperature. A Malmo to Munich drive at 06:00 to 18:00 in November can span 0 to 10 C. Query hourly `temperature_2m` at each sample point for the estimated arrival hour at that point (time from Valhalla cumulative time) and apply f(T), m_el(T), g(T), m_p(T) per segment. Rain and snow (`precipitation`) add rolling resistance [A, unsourced multiplier]; leave them as an information chip, do not model.

## 5. Charging stop for a Type 2 AC-only PHEV: is it worth it?

### 5.1 Facts and prices
- Battery 13.8 kWh, onboard charger 7.2 kW per Enel X Way and Pod Point, but 3.3 or 3.6 kW per Yahoo, Auto Express and a Czech test [S, search summaries; https://enelxway.com/us/en/resources/ev-comparisons/hyundai-charging-stations/santa-fe-phev and https://pod-point.com/guides/vehicles/hyundai/2021/santa-fe-phev]. It likely depends on model year. **Owner must state which**; the planner must use it.
- Germany public charging, Verbraucherzentrale March 2026: about 52 ct/kWh AC, 60 ct DC; ACE July 2026 ad-hoc AC 52.30 ct; contract AC 39 to 62 ct; ADAC motorway ad-hoc up to about 62 percent above contract; blocking fees of the type 10 ct per minute after 180 to 241 minutes on AC [V via https://www.emobility.energy/e-auto-magazin/strompreis-ladesaeule, itself citing those sources; one secondary page].
- Sweden: only DC list prices known (Ionity 5.79-6.09 kr/kWh, Mer 3.40-5.10 kr/kWh, Circle K 5.79-5.89; EV_PRICE_SOURCES_2026-11-06.md, from Hurbra roundup). **I found no Swedish AC per-kWh price**; the search returned none.

### 5.2 Break-even arithmetic [A]
Energy price per electric km at the wall = 0.192 kWh/km / 0.88 charging efficiency x price. Petrol per km in charge-sustaining = 0.075 l x pump price.

| Charging at | EUR/kWh | EUR per 100 electric km | Petrol 7.5 l/100 at 1.60 EUR/l |
|---|---|---|---|
| Home (example 0.20) | 0.20 | 4.4 | 12.0 |
| German public AC average | 0.52 | 11.3 | 12.0 |
| German ad-hoc AC motorway (about 0.85) | 0.85 | 18.5 | 12.0 |
| Free hotel or workplace charger | 0 | 0 | 12.0 |

Findings [A]:
- Paying public AC at the German average price is roughly break-even against petrol; at ad-hoc motorway prices it is **more expensive than petrol**. A paid public AC stop only wins with a cheap contract tariff (about 39 ct) or when petrol is dear.
- Time: a full 13.8 kWh at 7.2 kW takes about 2 h (at 3.3 kW about 4.2 h). A 30-minute stop adds about 3.6 kWh gross, about 3.2 kWh into the battery, about 17 electric km, saving about 1.3 l, about 2 EUR gross of any charge cost. At 52 ct the electricity costs about 1.9 EUR. **Net about zero for 30 minutes of time.** This is the answer the planner should compute and show: "A 30 min AC stop here does not pay."
- Free or destination charging is where PHEV value lives: a full hotel charge replaces about 54 km of petrol, about 4 l or 6.5 EUR; at 0.20 EUR/kWh home it is about 6.5 vs 2.7 EUR. Trip planning should therefore ask "does the destination or hotel have a charger" and credit the free kWh to the **return** leg (which means the battery should be preserved for city segments or start-of-return, not depleted at the destination). The return trip from Germany starts full only if the hotel charges.
- Parking fees: charging while parked may be cheaper than a stop at a fuel pump if the charger sits at a place you visit anyway (supermarket, restaurant) [INV]. Data for that is the same unknown as charger prices (section 8.3).

## 6. Other trip factors

| Factor | Evidence | Use |
|---|---|---|
| Preconditioning | Existing doc: pre-heating from the grid is the biggest user lever (PHEV_TEMPERATURE_MODEL, no new source). Heating with mains kWh at home avoids pulling the battery in the first km. | A "plugged in before departure" checkbox that restores the cold penalty reduction; saves some of the 25-45 percent cold-month premium shown in the model's worked table. |
| Roof box | ADAC-attributed 18 percent more fuel at 130 km/h; roof bars alone about +0.4 l/100; University of Zilina measured over 1.5 l/100 km extra at 130 [S, snippets; https://drepo.uniza.sk/handle/hdluniza/328, subito.it, driving.co.uk]. Secondary sources for ADAC. | Toggle "roof box / cargo carrier": multiply aero term by about 1.18-1.30 [A], applied only above 80 km/h. |
| Trailer | Not researched, no source. | Out of scope; mention a future toggle. |
| Winter tyres | Only a tyre-shop blog says +5 to 15 percent; Continental says rolling resistance is not higher [S, snippet; tires-easy.com, tyrepress.com]. Contradictory. | Do not model. At most a "tyre pressure" tip. |
| Regen | Hyundai manual: regeneration on deceleration [V]. No Santa Fe regen figures found. | Model only via the descent efficiency assumption in 4.2. |
| Battery SOC floor | Tucson: EV mode locks out at about 15 percent [S, snippet]. | Replace `0.75` by usable fraction (0.85 minus floor) in config rather than a constant. |

## 7. Honest limits
- My road-load numbers (3.2, 4.1, 4.2) are physics calculations with assumed vehicle constants. They are good for ranking options and for showing direction and size; they are not a measurement of the Santa Fe. The owner's trip log (kWh and litres per trip with temperature and speed) would calibrate them.
- No Santa Fe PHEV speed-specific consumption or mode logic was found in any source. Do not claim it.
- German prices come from one secondary page that cites Verbraucherzentrale, ACE, ADAC; individual price points were not opened at origin.

## 8. Ideas for EuroFuelPrices (ranked by user value per effort)

Impact = user value. Effort S/M/L = one developer.

### 8.1 Trip energy profile: replace the scalar with per-segment physics (foundation)
- What: request `elevation_interval` (about 100 m) and `directions_type: 'maneuvers'` in the existing Valhalla call, cut the route into 5-10 km segments with speed and elevation delta, and run `rtPlan` on the list instead of the whole route. All other ideas hang on this.
- Impact: high (it makes every later feature possible and fixes the wrong constant `RT_REAL = 0.75`).
- Effort: M. Pure function in the RT-PURE region, testable with the existing node test.
- Data: Valhalla FOSSGIS [V]. Needs one live test of maneuver `length`/`time` fields.
- Risks: public Valhalla instance rate limits, response size on long routes (Sweden-Germany ok); 300 m resolution is enough.

### 8.2 Cruise-speed slider with euro and minutes
- What: control "max cruise 90 / 110 / 120 / 130 / free", shows trip cost, minutes and implied EUR per hour saved (about 21 EUR/h from 130 to 110 in my model). Sends `top_speed` to Valhalla.
- Impact: high and highly visible; the Sweden-Germany Autobahn stretch is exactly where it matters.
- Effort: S after 8.1; M standalone.
- Data: none new. Calibrate with ÖAMTC Zoe (+30 percent 100 to 130) [V] and owner log.
- Risks: model is generic SUV physics; show a range, "model estimate".

### 8.3 AC charging stop verdict: "does a stop pay?"
- What: at any point show "A 30 min AC stop gives 17 km, saves about 2 EUR gross, costs about X EUR electricity: net Y". Inputs: onboard charger kW (owner setting, default unset), public AC price per kWh (country default with source and date, editable), blocking fee note. No stations, no feed needed.
- Impact: high, because the likely default answer ("do not stop") saves time and is not obvious; also credits hotel and free charging.
- Effort: S.
- Data: Germany AC average 52 ct [V via emobility.energy, secondary]; Sweden AC price unknown, user enters it; keep EV_PRICE_SOURCES rules (dated, cited, greyed after 90 days).
- Risks: prices drift; mixed-currency display already exists.

### 8.4 Destination and hotel charging credit, battery-preserving advice
- What: a checkbox "charger at destination / hotel" (and "free"). If yes, the plan treats the destination as full-recharge, so the battery can be used fully on the way; if no, it advises holding some charge for the urban end or return start. Shows the value of a free full charge (about 6.5 EUR at 1.60 EUR/l).
- Impact: high for the owner's Sweden-Germany trips and commutes, aligned with the existing home tariff input.
- Effort: S to M (a two-leg view for return trips is the M part).
- Data: none. Optional later: OSM or Bundesnetzagentur charger locations (locations only, not price).
- Risks: user must tell the truth about chargers; no verification.

### 8.5 Hourly weather along the route: temperature and wind
- What: Open-Meteo forecast for 8-12 points at the estimated passage hour. Apply the existing PHEV temperature curve per segment, plus a headwind/tailwind aero factor (x1.4 / x0.67 at plus or minus 20 km/h in my model) with a 0.6 road-level scaling.
- Impact: medium to high in winter and on windy coasts; makes the plan visibly "intelligent" (a Skane-Jutland headwind day is plausible).
- Effort: M. Caching by rounded point and hour.
- Data: Open-Meteo, CORS ok and rate cost per location [V]; CSP add `api.open-meteo.com`; non-commercial terms.
- Risks: free tier prohibits ads/subscriptions; forecast beyond 16 days unavailable; wind scaling is an assumption.

### 8.6 Battery-use advice per segment ("hold" and "spend" runs)
- What: greedy ranking of segments by litres saved per kWh (section 2.2) and output such as "Spend battery on km 0-35 (city), hold on motorway, spend again on last 18 km". Shows EUR gain, small and honest.
- Impact: medium (literature says 1-20 percent fuel; real gain on the owner's trip likely single digits [A]); feels special but needs correct mode names for the car.
- Effort: M after 8.1.
- Data: Santa Fe EV/HEV/Auto behaviour **unverified**; owner must read the manual and confirm which buttons exist.
- Risks: Auto mode may not obey; engine-charging mode could cost 12.7 l/100 in Lynk & Co [V], so never advise it. Ship last, labelled "advice".

### 8.7 Elevation-aware range
- What: net climb and descent into the energy budget, chip "net +420 m climb adds about 3 kWh". Matters for Norway, Alps, Harz.
- Impact: low on flat Sweden-Germany, medium for other users and trips.
- Effort: S after 8.1.
- Data: Valhalla `elevation_interval` [V] or Open-Meteo elevation [V].
- Risks: regen efficiency 60-70 percent assumed; route data noise (bridges, tunnels).

### 8.8 Cargo and car-state toggles: roof box, plugged-in preconditioning
- What: two checkboxes affecting the aero factor (about +18-30 percent aero above 80 km/h [S]) and the cold-start penalty.
- Impact: low to medium; cheap and credible for holiday trips.
- Effort: S.
- Data: ADAC-attributed 18 percent via secondary sources [S]; keep as editable multipliers.
- Risks: sources are secondary; label as typical.

### 8.9 "Calibrate from my last trip" (owner's own data wins)
- What: allow entering kWh and litres and km for one trip (or paste from the trip computer) and store `{speed, T, kWh, l}` locally to re-fit f(T) and a speed multiplier. Privacy: localStorage only.
- Impact: high long-term accuracy; matches the existing PHEV doc's instruction that owner data override defaults.
- Effort: M.
- Data: user entries only.
- Risks: small sample; needs a sanity range check.

### 8.10 Charger locations (optional, low priority)
- What: charger points along the route (locations only) with no price, so the 8.3 verdict can say "an AC charger exists at km 140". Source: Bundesnetzagentur register (keyless CSV, about 200k points, no price) and NOBIL for Sweden (key needed, tariff fill rate unknown) per EV_PRICE_SOURCES_2026-11-06.md.
- Impact: low to medium; only valuable if prices also exist.
- Effort: L (size, licence, update job).
- Risks: ODbL or CC BY duties; stale data; do not show prices that are not parsed.

### Suggested order [INV]
8.1 (foundation) then 8.3 and 8.4 (cheap, high value), 8.2 (speed slider), 8.5 (weather), 8.9 (calibration), then 8.6, 8.7, 8.8, 8.10.

## 9. Open items and not verified
- Santa Fe EV/HEV/Auto selector behaviour, SOC floor, charger rating (3.3/3.6/7.2 kW). Needs the owner's manual and the owner's car.
- Valhalla maneuver field names and whether a long route in `maneuvers` form stays within the public server's limits.
- Open-Meteo CORS and rate limit were tested only for a short forecast call; elevation endpoint CORS not tested; commercial-use restriction unchanged.
- Valhalla public server elevation is verified for one Skane to Gothenburg route only.
- No Swedish AC per-kWh price found; German figures are from one secondary page.
- Several sources are search snippets only (marked [S, snippet]); none of the ICCT, ADAC and SAE papers was opened in full.

## Sources
- [Open-Meteo elevation API docs](https://open-meteo.com/en/docs/elevation-api) (opened)
- [Open-Meteo forecast docs](https://open-meteo.com/en/docs) (opened)
- [Valhalla route API reference](https://valhalla.github.io/valhalla/api/route/api-reference/) (opened)
- [Valhalla FOSSGIS public server](https://valhalla1.openstreetmap.de/route) (live call)
- [Hyundai Tucson PHEV owner's manual, PHEV system](https://ownersmanual.hyundai.com/full_webhelp/NX4PHEV/2026/en_US/id863e08c99ae.html) (opened)
- [Cars.com Tucson PHEV at 37 F](https://www.cars.com/articles/toyota-rav4-prime-and-hyundai-tucson-plug-in-hybrid-testing-ev-range-efficiency-in-colder-temperatures-462054) (opened)
- [e-mobileo: motorway speed and EV consumption (OAMTC Zoe)](https://www.e-mobileo.de/wie-schnell-auf-der-autobahn-das-optimale-tempo-fuer-e-autos) (opened)
- [Test-Aankoop: 100 vs 120 km/h](https://www.test-aankoop.be/mobiliteit/auto-s/nieuws/hoeveel-bespaar-je-als-100-per-uur-rijdt-op-de-snelweg) (opened)
- [emobility.energy: German charging prices](https://www.emobility.energy/e-auto-magazin/strompreis-ladesaeule) (opened)
- [Enel X Way Santa Fe PHEV](https://enelxway.com/us/en/resources/ev-comparisons/hyundai-charging-stations/santa-fe-phev), [Pod Point Santa Fe PHEV](https://pod-point.com/guides/vehicles/hyundai/2021/santa-fe-phev) (snippets)
- [SAE route-optimized blending](https://saemobilus.sae.org/papers/route-optimized-energy-usage-a-plug-hybrid-electric-vehicle-using-mode-blending-2024-01-2775), [Chalmers blending study](https://publications.lib.chalmers.se/records/fulltext/160800/local_160800.pdf), [UC Irvine route-aware PHEV](https://escholarship.org/uc/item/83p636qq), [Argonne Prius conversion](http://www.transportation.anl.gov/pdfs/HV/462.pdf) (snippets)
- [ADAC winter EV test via heise](https://heise.de/-11149567), [University of Zilina roof box study](https://drepo.uniza.sk/handle/hdluniza/328), [tyre rolling resistance, Continental via tyrepress](https://www.tyrepress.com/2008/10/rolling-resistance-for-summer-winter-tyres-equal-says-conti/) (snippets)
- Repo docs: PHEV_TEMPERATURE_MODEL_2026-11-06.md, EV_PRICE_SOURCES_2026-11-06.md, ROUTING_BACKEND_2026-11-06.md
