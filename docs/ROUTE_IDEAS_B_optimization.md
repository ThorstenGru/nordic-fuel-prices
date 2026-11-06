# Route ideas B: optimal fuel-stop planning, price cycles, uncertainty (2026-11-06)

Status: research only. No code edited, nothing committed. Owner decides what to build.
Tone: plain English.

## How claims are labelled

- **[opened]** = I fetched the page today and read the relevant part.
- **[snippet]** = only seen in a web-search result summary; not opened. Treat as a lead, not a fact.
- **[code]** = read in `web/index.html` today (`rtPlan`, `rtCand`, `rtRef`, `rtRank`, `rtTier`, `rtCorridor`).
- **[doc]** = read in `docs/ROADMAP_2026-11-06.md` today.
- **[invented]** = my own idea, formula or number. Needs testing before users see it.
- Numbers for the Santa Fe (7.0 L/100 km petrol-only, 47 L tank, 40 km electric) come from the roadmap doc and are assumptions there too.

---

## 1. Where the planner stands (from the code)

[code] Today `rtCand` prices one pump at a time: it assumes you buy "what is burned from here to the destination, capped by tank space", compares to a local reference price (median of pumps within 100 km along the route, `rtRef`), and subtracts the detour cost. `rtRank` then sorts by trust tier, then by net saving, and shows the top 10 with at least one per country. `rtPlan` only answers "do I need a stop at all" (`needStop`, `reachKm`).

What is missing for a real plan:
1. No sequence of stops (a second stop changes how much the first one should buy).
2. Pumps are valued independently, so "buy just enough here because the next country is cheaper" is not expressed.
3. Price age is a hard cutoff (10 h) plus three trust tiers; no graded uncertainty.
4. Time of day is ignored although the route gives an ETA for every pump.
5. Only money is optimised.

All five can be added client-side with data the app already loads.

---

## 2. The classic problem and the algorithms

### 2.1 Statement (fixed route, "gas station problem")

Pumps i = 1..n at distance x_i from the start, price p_i per litre, detour d_i (km). Tank capacity C (L), start fuel F0, consumption c (L per km, = cons/100), reserve R. Choose litres g_i >= 0 bought at each used pump to minimise sum(p_i * g_i + detour cost), subject to never going below R and never above C.

Literature: [snippet] a general-purpose DP for the "gas station problem" exists and has since been sped up; a key result is that only a finite set of purchase quantities needs to be considered, which gives a finite DP state space (found via arXiv "Heuristic Search for Path Finding with Refuelling", https://arxiv.org/html/2309.10796v2 and related papers; I did not read the papers themselves). The fixed-route case is also described as a special case of capacitated lot-sizing [snippet, econpapers.repec.org result].

### 2.2 Greedy "cheapest in range" (what the roadmap calls X1)

[opened] https://vanja.io/cheapest-way-across-america/ (a blog, secondary source, but the maths is checkable):
- Rule: at a pump, if a cheaper pump (or the destination) lies within range, buy just enough to reach the first such pump; otherwise fill the tank. O(n log n) on a fixed path.
- Under "stops are free and pumps are on the road" it is optimal, and the optimal cost has a closed form: every km is paid at the minimum price among pumps within one tank range behind it: cost = c * integral of w(m) dm, with w(m) = min{ p_i : m - R_range <= x_i <= m }.
- It breaks when (a) stops are not free (the cheapest plan may want many tiny stops) and (b) pumps are off the road: a detour burns fuel regardless of how much you buy, so the effective price falls as the purchase grows and posted prices stop ranking pumps correctly.

### 2.3 Dynamic programming with fuel level as state (exact, with detours)

[opened] same page. State = fuel level on a grid; process pumps in route order; array cost[f] = least cost of being at level f.
- Drive: shift the array by the distance in grid steps.
- Stop at pump i with detour fuel b_i and fixed stop penalty s_i: arrive at level a (after the detour burn), leave at level t > a.
  leave[t] = min over a < t of ( cost[a + b_i] + (t - a) * p_i ) + s_i
  Split the linear purchase term: g[a] = cost[a + b_i] - a * p_i, then leave[t] = t * p_i + s_i + prefixmin(g)[t-1]. The prefix minimum makes each pump O(K) instead of O(K^2).
- Merge: cost[f] = min(cost[f], leave[f + b_i]) (second detour leg).
- Backtrack from destination; then recompute purchase amounts greedily for the chosen pumps and drop any pump that buys nothing.
- The page reports 362 pumps x 2,001 levels (~0.7 M cells) in ~10 ms in NumPy and verifies against an LP and a MILP solver.

For EuroFuelPrices: tank 47 L at 1 L resolution is K = 48 levels (or 0.5 L, K = 95). 200 corridor pumps x 95 levels = 19,000 cells. That is nothing for a phone. Even a 3-objective version is cheap.

### 2.4 Formulas to implement [invented adaptation of 2.3 to this codebase]

Let for pump i: `off_i` km off route, `detourKm_i = 2 * off_i * ROAD_FACTOR` (existing), `b_i = detourKm_i * cons/100` litres burned in the detour (zero if still on battery at that point, as `rtCand` already does), `eur_i` price in EUR/L.

Effective price when buying g litres at pump i:

    p_eff(g) = eur_i + detourEnergyCost_i / g       (g > 0)

So a pump 6 km round trip off route costs about 6 * 0.07 * 2.0 = 0.84 EUR; buying 10 L makes a 0.084 EUR/L surcharge, buying 40 L only 0.021 EUR/L. This is why "minimum fill" at an off-route pump is almost never right and why the ranking must depend on litres bought, not just on price. (Numbers illustrative.)

PHEV handling: the battery is used first, so fuel does not decrease until `along > elecKm` (already in `rtCand`). In the DP: start the walk with fuel = fuelL, and let the first `elecKm` km drain zero fuel. No extra state is needed because battery charge is a function of `along` only (assuming no en-route charging; charging stops are a later feature [doc L1]).

Generalised cost for multi-objective (see section 6):

    J = sum_i ( p_i * g_i + detourEnergyCost_i ) + lambda_t * ( sum_i (stopMin + detourMin_i) ) + sum_i q_i

lambda_t = EUR per minute the user assigns to time (slider, default 0 or small), q_i = a stop-quality penalty (section 6).

### 2.5 Minimum-fill rule (the "buy just enough before an expensive country" tactic)

Given the next pump j with price p_j < p_i that is reachable, the optimal purchase at i is

    g_i = max( 0, min( C - f_i,  (x_j - x_i) * cons/100 + R - f_i ) )

where f_i is the fuel on arrival at i. If no cheaper pump is within the full-tank range, fill to C (capped by what is needed to the destination, as `rtCand` does). This is the greedy rule; the DP gives the same answer when stops are free and handles the cases where they are not.

Bound on how much a good plan can save: the minimum-price-in-range formula from 2.2 gives the floor on cost for a given set of pumps, so "plan cost vs floor" is a free quality number to show ("your plan is within 0.8 EUR of the theoretical best for the prices we have").

---

## 3. Tankering across borders

### 3.1 The price gradient is real and large [opened]

Weekly national averages, EU Weekly Oil Bulletin as republished by fuel-prices.eu, week of 19 Oct 2026, EUR/L, taxes included: https://www.fuel-prices.eu/news/weekly/europe-fuel-prices-week-2026-10-19/ (the page labels the column "petrol" and does not name the grade; I assume Euro-super 95).

| Country | Petrol | Diesel |
|---|---|---|
| Poland | 1.560 | 1.791 |
| Sweden | 1.640 | 2.040 |
| Luxembourg | 1.788 | 2.081 |
| Austria | 1.817 | 2.132 |
| Czechia | 1.862 | 1.953 |
| Germany | 2.179 | 2.266 |
| Netherlands | 2.391 | 2.456 |
| Denmark | 2.605 | 2.502 |

Cross-check [snippet from a search result, not opened]: the 26 Oct bulletin put Sweden at 1.560 and Denmark at 2.525 EUR/L, about 0.96 EUR/L dearer in Denmark.

These are national averages, one week, one secondary aggregator. Station prices differ (motorway pumps, brands, cities). Use them only to show the order of magnitude, never to quote a saving. For the owner's trip the in-app live prices replace them.

Observation (from the table, so [opened] data plus my reading): in this week Sweden is 0.54 EUR/L cheaper than Germany for petrol, Germany is 0.43 cheaper than Denmark, Poland is 0.62 cheaper than Germany. Diesel is different: Sweden diesel (2.04) is only 0.23 below German diesel (2.27), and Danish diesel (2.50) is below Danish petrol (2.61). Gradients are fuel-specific, so tankering logic must run per fuel type, not assume "Sweden is cheap".

### 3.2 Tankering break-even [invented]

Fuel carried across a border is limited by the tank, not by weight (47 L is ~35 kg, under 2% of a typical SUV's mass; effect on consumption is small, but I have no source for the exact number, so I would not model it).

For a segment in an expensive zone Z (length L_Z km) following a cheap pump i at price p_c with an expensive pump j at p_e on the other side:

    litres_to_carry = min( C - f_i,  L_Z * cons/100 + R' )     where R' = reserve you want at the first cheap pump after the zone
    net_saving      = litres_to_carry * (p_e - p_c) - detourEnergyCost_i - lambda_t * detourMin_i

The planner should print this as one plain sentence: "Fill up at X (last pump before Denmark): 22 L more than you need here saves about 4.80 EUR over buying in Denmark." It falls out of the DP, but the sentence is the user value.

### 3.3 Round trip and commuter pattern [invented]

The owner (and most cross-border drivers) goes both ways with different prices at each end. The correct unit is the round trip, not one direction. Run the DP over outbound + return concatenated with the fuel level carried across the turnaround (the destination is a "free stop" with no purchase assumed, or an optional stop). A simple version: after planning outbound, pre-fill the return plan's start fuel from the outbound arrival fuel (the existing `fuelPct` input already allows that by hand). The big win is a statement like "On the way home buy only 22 L in Germany, the rest in Sweden".

Illustrative arithmetic (assumed car 47 L, 7.0 L/100 km, 463 km petrol part, 4.7 L reserve; prices are the national averages above, not live): return leg needs 32.4 L + 4.7 reserve = 37.1 L at departure. Arrive in Hamburg with 14.6 L, so buy 22.5 L in Germany instead of filling the tank (32.4 L). Saving about 9.9 L x (2.179 - 1.640) = about 5.3 EUR for one trip, from the minimum-fill rule alone. This is small per trip but concrete, and a commuter makes the trip repeatedly.

### 3.4 What I did not find

- No sourced tankering cost analysis for car drivers (search returned nothing on point).
- No current Germany-Denmark station-level comparison. Poland, Luxembourg and Austria comparisons are from the weekly table only; no cross-border station study opened.
- Austria's October 2026 petrol tax cut (415 EUR per 1,000 L, 1-31 Oct) appeared in a search snippet from fuel-prices.eu; not opened. Tax changes at month boundaries can move a whole country's level overnight; a flag "country level changed >5% in a week" from the pipeline would help.

---

## 4. Price cycles

### 4.1 Austria: the 12:00 rule [opened]

https://www.wko.at/branchen/transport-verkehr/garagen-tankstellen-serviceunternehmungen/spritpreisverordnung.html (page dated 13 Apr 2026):
- A price increase is permitted once a day at 12:00; price reductions at any time.
- A March 2026 amendment (BGBl 13 Mar 2026) limited increases to Monday, Wednesday and Friday at 12:00; that variant expired at the end of 12 April 2026. The page does not say when the daily rule resumed. Another WKO regional page and a derstandard headline ("Spritpreise dürfen weiter nur mittags steigen", https://www.derstandard.at/story/3000000302278/spritpreise-duerfen-weiter-nur-mittags-steigen) [snippet] suggest the regulation is extended to end of 2028. Verify the current state in the Austrian Bundesgesetzblatt before hard-coding.
- Technical detail: changeover at 12:00, manual pumps within 5 to 10 minutes of that.

### 4.2 Germany: copied the idea from 1 April 2026 [opened, two sources]

- https://www.zdfheute.de/wirtschaft/spritpreise-benzin-diesel-12-uhr-regel-wirkung-daten-100.html : before the rule stations changed prices more than 20 times a day; since 1 April, "up once at midday, otherwise down". Super E5 is roughly 5 to 10 cents per litre dearer at midday than in morning or evening (rounded estimates from the article; the analysis covers the two weeks before 9 April 2026; no compliance figure in the text). The article says the rule has not lowered the price level.
- https://www.auto-motor-und-sport.de/verkehr/spritpreis-bremse-ab-1-4-2026-tanken-sie-zu-diesen-uhrzeiten/ : cheapest 09:00 to 11:45, dearest 12:00 to 12:30. No cent figures.
- [snippet only] A zdfheute headline "12-Uhr-Regel tausendfach gebrochen" and a consumer-service number (2,995 of 15,240 stations raising outside the window) were in search results; I did not open them. Compliance is therefore uncertain; the pattern should be learned from data, not assumed.
- Older pre-2026 German pattern [snippet]: cheapest roughly 18 to 20 h, dearest in the morning (around 5 to 8 h), weekday of little importance; differences of about 8 to 20 cents per litre depending on source. From search summaries of Bundeskartellamt/MTS-K material, not opened. Probably outdated since April 2026.

### 4.3 Sweden and others

I found no sourced daily or weekly price-change pattern for Swedish pumps. One aggregator (nakordoni.eu) says prices "often drop on certain weekdays" without naming which; not usable. Do not hard-code a Swedish pattern. Let the data speak (idea 5).

### 4.4 What the 12:00 rule means for a route planner [invented, logical consequence of 4.1 and 4.2]

1. **One-sided uncertainty.** If increases are only allowed at 12:00, a price observed after the last noon can only have stayed or gone down since (no increase is allowed in between). So in the morning, any price observed since the last 12:00 is an upper bound on the current price. After 12:00 the bound flips: the price may have jumped up. Practical rule for DE and AT: 
   - observed after the last 12:00 and now before the next 12:00: label "at most" (the true price is this or lower);
   - observed before the last 12:00 and now after it: label "may have risen" and apply a positive margin.
   The ANWB-based German data has no timestamps [doc], but our own pipeline knows when it scraped; use scrape time as the observation time.
2. **Arrival-time aware prices.** The route gives ETA for every pump (`along / km * minutes`). A pump reached at 13:30 will probably show the daily peak; one reached at 10:00 the morning low. For DE and AT, an arrival-time adjustment of the price (up for 12:00 to ~13:00 arrivals) is a cheap, explainable correction. Size of the adjustment should come from measured data, not from the 5 to 10 cent rough number.
3. **Plan the stop before noon.** A tie-break that prefers an ETA between 09:00 and 11:45 in DE/AT [invented]; the effect is visible as "arrive 11:20 vs 12:40".
4. **Staleness resets at noon.** The 10 h cutoff means a price scraped at 08:00 is dropped at 18:00. After a 12:00 change it is wrong sooner for those two countries. A per-country "valid until" (next 12:00) is more accurate than a flat 10 h.

---

## 5. Uncertainty of prices

### 5.1 What exists today [code]

`rtTier`: 0 trusted and dated, 1 age unknown, 2 not verified (stuck 48 h `ps`, suspect-low, country feed stale). Hard cutoff `MAX_AGE_H = 10`. Net saving is deterministic: (ref - price) * litres - detour. The reference is a median over pumps up to 100 km away, of which at least three dated ones must exist, else all.

### 5.2 Model [invented]

Treat the true price at the pump as p_true = p_obs + e, with e unknown. Model the error spread as a function of age a (hours) and country/source grade:

    sigma(a) = sigma_floor(source) + k_source * sqrt(a)         (random-walk style growth)

Calibrate sigma_floor and k from our own scrape history: for each pump with two consecutive observations dt hours apart, record |p2 - p1|; the 80th percentile by dt bucket is the error bar. Until history exists, start with conservative guesses (e.g. 0.01 EUR floor, 0.004 EUR per sqrt-hour) and label them as guesses in the doc and UI.

For DE/AT after 4.4, use an asymmetric spread: no upward error before noon.

**Risk-adjusted price** used for ranking and planning:

    p_rank = p_obs + z * sigma(a)       z = 0 (optimist), 0.5 (default), 1 (cautious)

Replaces the hard cutoff with a soft one: an old price is not removed, it competes with a margin. A pump with a 1.55 price 14 h old and sigma 0.04 competes at 1.57, a fresh 1.57 is equal. The existing tier gates can stay for "not verified".

**Shrink towards neighbours** (empirical-Bayes flavour): `p_hat = w * p_obs + (1 - w) * p_local_median`, w = exp(-a / tau), tau about 12 h. A price that is days old is replaced mostly by the local median of fresh prices, so one stale cheap outlier cannot win. `rtRef` already computes a local median; this reuses it. [invented; tau needs calibration]

**Show the error bar.** Rows say "1.69 (about +/-0.03)". The planner's total says "plan cost 58 EUR, likely 56 to 61 EUR" by adding variances across stops (independent assumption; crude, say so).

### 5.3 Robust choice under stale data [invented]

1. **Backup pump rule.** A plan stop A is only recommended if there is a second reasonable pump B within range of the fuel left after skipping A (i.e. when A's price turns out wrong the trip is still feasible without detour). Check: `fuelAt_A - burn(x_B - x_A) >= reserve` for some B with `x_B > x_A`. This is a range-feasibility test, no prices needed. A driver arriving at a pump that is 10 cents dearer than shown should be able to say "fine, next one in 40 km".
2. **Minimax regret choice.** For the top few plans, evaluate cost at p_obs and at p_obs + 1 sigma for each stop; choose the plan with the smallest worst-case regret relative to the best plan in that scenario. Cheap: a handful of plans times two scenarios.
3. **Don't let a single tier-2 price define the plan.** Already done for "best" [code]; extend to the DP: tier-2 pumps are allowed only as backup, or with their price replaced by `p_hat`.
4. **Show the freshness of the decision**, e.g. "built from prices up to 3 h old (DE: 40% older than 6 h)". Honest and small.

---

## 6. Multi-objective: cost, time, comfort, stop quality

### 6.1 One generalised cost, a slider, three named plans [invented]

    J = fuelCost + detourCost + lambda_t * (extraMinutes) + stopQualityPenalty

- extraMinutes = stops * stopMin + detourKm / v_detour * 60. Assumptions: stopMin 5 to 8 min, v_detour 50 km/h (both mine, to be tuned).
- lambda_t slider "How much is an hour worth to you?" Default 0 EUR/h shows the cheapest plan; a value like 15 to 30 EUR/h (illustrative) typically removes 3 to 5 km detours that save 1 EUR. The slider doubles as an explanation: "this pump saves 1.40 EUR but costs 9 minutes".
- Output three plans from three lambdas: "Cheapest", "Balanced", "Fewest stops". Pareto-style, small table (cost, extra minutes, stops).

### 6.2 Stop quality / comfort (data we have or could cheaply get) [invented]

- Open 24 h, staffed, brand / card acceptance, toilet or shop if the source has it (what the datasets carry varies by country; check per source before promising).
- Distance from the main road (already `off`): on-route pumps (off < 0.5 km) are quieter to enter.
- Penalty q_i small (e.g. 0.30 EUR equivalent) for unknown/unverified, 0 for brand pumps with known hours. Keep q_i a plain list in the code, easy to tune.
- Comfort rule: avoid stops in the first 30 minutes and last 15 minutes of the trip unless needed (drivers dislike stopping just after departure); and prefer a stop near the 2 to 3 hour mark for a rest. [invented; the 2 to 3 hour rest guidance is common practice, I did not source it]

### 6.3 PHEV-specific [invented]

- Electricity at 0.25 EUR/kWh x 20 kWh/100 km = 5 EUR per 100 km vs petrol 7 L x 1.8 EUR = 12.6 EUR per 100 km (assumed numbers from the roadmap doc, not verified). So the first ~40 km are far cheaper; never plan a petrol purchase to "save" the battery. The planner therefore keeps electric-first, which `rtPlan` already does.
- If the destination is a home with a charger, an empty battery at arrival has no cost. If the user marks "no charger at destination", the return start battery is 0: an input the planner should carry into a round-trip plan.

---

## 7. What is cheap to implement client-side

| Piece | Where it fits | Why cheap |
|---|---|---|
| Fuel-level DP, 1 L grid, ~200 pumps | new pure function next to `rtPlan`, inside RT-PURE-BEGIN/END, so `tools/test_route_model.js` can test it | 19k cells; uses `rtCand` pieces (detour burn, on-battery detour); no network |
| Min-fill litres and "buy N L here" sentence | output of DP or greedy | one formula (2.5) |
| Risk-adjusted price and shrinkage | before DP in `rtRank`, uses `age`, `rtRef` | two lines per pump |
| DE/AT 12:00 label and arrival-time adjust | `rtRank` knows `along`, `R.min`, local clock | needs a country list and one hour-of-day table |
| Lambda slider and 3 plans | re-run DP three times | DP is fast; UI is a slider |
| Backup pump check | post-process plan | pure range arithmetic |
| Counterfactual "vs naive fill at first pump" | simulate the old rule on the same pumps | proves value, builds trust |

Needs data work (scheduled job, still static): hourly and weekday price profile per country, and per-pump price-change history to calibrate sigma(a). Needs owner decision: whether history is stored (public prices, no personal data, so privacy is not affected).

Detour refinement (roadmap X2): run the DP on the straight-line estimates, then route only the 3 to 5 pumps in the chosen plan (plus the next best of each) with the real router, and re-run the DP. Cuts routing calls to a handful per plan.

---

## 8. Top ideas for EuroFuelPrices

(Same list is returned in the structured summary. Effort: S = 1 to 3 days, M = 1 to 2 weeks, L = a month+, one developer.)

1. **Multi-stop plan with exact DP and a "buy N litres here" sentence.** Impact high: turns a list of pumps into a plan and handles the country-border minimum-fill logic automatically. Effort M. Needs: roadmap N5 (start fuel, reserve; exist [code]); tests in `tools/test_route_model.js`. Risk: wrong consumption inputs make wrong litres; keep "estimate" wording and reserve.
2. **Border-aware "fill here, skip there" card (tankering) and round-trip planning.** Impact high for the owner and cross-border commuters (Sweden-Denmark-Germany). Effort M. Needs: idea 1; per-fuel prices; a turnaround/destination model. Risk: national averages mislead (3.1), only live station prices may be used for savings; diesel and petrol gradients differ.
3. **Soft price-age uncertainty: sigma(age), risk-adjusted price, neighbour shrinkage, error bars.** Impact high: fixes "stale cheap outlier wins" and replaces the 10 h cliff. Effort S (with guessed constants), M (with calibration). Needs: age (exists [code]), later scrape history. Risk: made-up constants; label as such until calibrated.
4. **Arrival-time rules for Germany and Austria (12:00 rule).** Impact medium-high: explains "arrive before noon", flags "at most" vs "may have risen", sets valid-until to the next noon. Effort S. Needs: ETA per pump (route duration, exists), scrape timestamp; confirm the current legal state (4.1, 4.2). Risk: German compliance uncertain [snippet]; Austria rule dates conflicting; verify before hard-coding.
5. **Price-cycle learning job (24x7 profile per country, error-bar calibration).** Impact high long-term and makes ideas 3 and 4 data-driven; yields a Swedish pattern where none is sourced. Effort M. Needs: scheduled GitHub Actions job storing hourly aggregates (public data, no personal data). Risk: repo growth; keep aggregates, not raw snapshots.
6. **Time-value slider with three plans (Cheapest / Balanced / Fewest stops) and stop-quality penalties.** Impact medium-high: explains detour trade-offs honestly and makes the result feel personal. Effort S-M. Needs: lambda_t, stopMin and speed assumptions; stop attributes vary by source. Risk: invented defaults; show them and let users change them.
7. **Backup-pump (plan B) and minimax-regret choice.** Impact medium: trust when a price is wrong at the pump; no new data. Effort S. Needs: idea 1 or just the current top list. Risk: more text on a small screen; show as one line "If this one is dearer, next in 38 km".
8. **Plan receipt: savings vs a naive baseline, plan-vs-floor gap, price-freshness line.** Impact medium: evidence the planner works; marketing without tracking. Effort S. Needs: idea 1. Risk: baseline choice can look cherry-picked; define it in the UI ("filling the tank at the first cheap-looking pump").
9. **Lightweight local "what I paid" log to calibrate error bars for this user.** Impact low-medium. Effort S-M. Needs: local storage only, no upload. Risk: scope creep; optional, later.

## 9. What was not checked

- The arXiv papers on the gas-station problem were seen in search results only; the algorithm details are from the vanja.io blog [opened], whose claims I verified only by reading, not by running code.
- Weekly Oil Bulletin numbers are via a secondary aggregator; the column grade (Euro-super 95) is my assumption.
- Sweden: no sourced price-change pattern found. Poland, Luxembourg and Czechia: only the weekly table.
- German pre-2026 time-of-day pattern: snippets only; and likely changed by the April 2026 rule.
- Current legal state of the Austrian rule (daily vs Mon/Wed/Fri, extension to 2028) is unclear between sources.
- All constants (sigma, tau, stopMin, lambda, comfort penalties) are mine and uncalibrated. Nothing was run or measured.
