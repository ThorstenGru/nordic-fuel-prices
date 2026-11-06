# Route ideas D: real total trip cost beyond fuel

Research only, 2026-11-06. No code touched. Labels: **[opened]** = I fetched the page and read it; **[search]** = only seen as a search-result snippet or a search-engine summary, treat as a lead; **[mine]** = my own idea or arithmetic, not a fact. Prices move, so every number below is a "seen on date" value, not a constant.

## 1. Short answer

A trip card that says "fuel 41 EUR" is wrong for the owner's own main trip (Sweden to Germany): the bridge or ferry is often the biggest line. Rough order of size for one car, one way, from what I found:

| Item | Seen value | Source status |
|---|---|---|
| Oresund bridge, car up to 6 m | 470 DKK booth, 420 DKK online, 182 DKK with ØresundGO (annual fee 370 DKK) | [opened] https://www.oresundsbron.com/en/prices (page says valid from 14 Sep 2026) |
| Great Belt (Storebaelt), standard car | about 235 DKK card/cash, about 205 DKK Express (BroBizz/plate) | [search] https://www.fuel-prices.eu/tolls/denmark/ ; official page https://storebaelt.dk/en/prices/ [opened] confirms "from 1 Jan 2026", size measured automatically, but its price table did not come through |
| Scandlines Puttgarden-Rodby | "from 101.25 EUR" one way on the Standard ticket, per car up to 9 persons (the page's combined Puttgarden-Rodby + Oresund bridge product) | [opened] https://scandlines.com/prices/puttgarden-rodby-oresund-bridge/standard. Other sources: about 117-128 EUR sample July sailings (https://www.aferry.com/de-de/rodby-puttgarden/ [search]) and "port purchase costs 15 EUR more than online" (blog, [search]) |
| TT-Line Trelleborg-Travemuende | average about 247 EUR, range 107-420 EUR (aggregator) | [search] https://www.directferries.ie/trelleborg_travemunde_ferry.htm |
| Trelleborg-Rostock | average about 117 EUR (aggregator, undated) | [search] https://www.directferries.ie/trelleborg_rostock_ferry.htm |
| Helsingborg-Helsingor | low season from 299 SEK (cheapest), 680 SEK standard; June-Aug standard 710 SEK, car under 6 m | [search], a mirror of the operator page, https://www.silvernimbus.lt/oresundslinjen/en/prices.html (third-party domain) |
| Austria vignette | 10-day 12.80, 2-month 32.00, annual 106.80 EUR (one source says 32.10 and another 95.80, so verify) | [search] https://www.tolls.eu/austria |
| Switzerland vignette | CHF 40 annual, one source only | [search] https://pixidia.com/?p=89865 |
| Slovenia | week about 16 EUR, annual 117.50 EUR | [search] aggregators, consistent |
| Czech, Slovakia, Hungary | sources conflict (Slovakia 10-day 8-12 EUR; Czech annual 2,300-2,570 CZK) | [search] do not hardcode without the operator page |
| France tolls | about 9-12 cent/km class 1 (no official reference found) | [search] https://tolltickets.com/fr/blog/france-toll-roads-telepeage-guide/ |
| Germany | no car toll or vignette | known fact, not re-verified today |
| Sweden | no motorway toll or vignette; Stockholm and Gothenburg congestion tax charged to foreign plates by invoice | [search] https://www.evz.de/en/topics/transport/car/fines-abroad/congestion-charge-sweden/ |

Fehmarnbelt tunnel: the official line is "no earlier than 2031", road first, rail at least a year later; toll not set. [search] https://www.yahoo.com/news/articles/major-tunnel-between-german-danish-151344342.html (quotes Sund & Baelt CEO, January 2026). Wikipedia's text mentions a 2032 revision, which I could not confirm. Do not show a Fehmarn toll at all; just keep the Scandlines ferry.

Key insight: **Malmo to Hamburg is a three-way choice with very different money**: Oresund bridge (470 DKK booth) + Great Belt (about 235 DKK) + fuel for about 600+ km, versus Oresund + Rodby-Puttgarden ferry (about 100-130 EUR), versus Trelleborg-Travemuende (about 107-420 EUR, but no driving through Denmark). Valhalla chose the Rodby ferry (373.9 km, ferry flag) in the repo's own probe (docs/ROUTING_BACKEND_2026-11-06.md). A fuel-only ranking hides all of this.

## 2. What can be an estimate, what needs input, what to avoid

### 2a. Show as a clearly labelled estimate with a free source

1. **Fixed crossings table (bridges and key ferries).** A small hand-curated `data/crossings.json`: id, name, polyline or two-end bounding boxes, price per class, currency, payment variants (booth, online, subscription), source URL, "seen on" date, "valid from". Detect by testing whether the route polyline passes near both ends (works for Oresund, Great Belt, Rodby-Puttgarden, Helsingborg-Helsingor, Trelleborg ferries). Only about 8 to 12 entries matter for the owner's routes. Price source is the operator page; refresh by hand once or twice a year (Oresund and Great Belt both change on 1 Jan / autumn). [mine]
2. **Vignette countries.** The router/country list already knows which countries the route crosses. For each vignette country show the cheapest sensible product for the trip length (10-day or week, not annual) with the official operator link. Only hardcode countries whose official page was opened by the maintainer; I only have aggregator numbers (see table). [mine]
3. **CO2 per trip, PHEV well-to-wheel** (details in section 4).
4. **Wear cost per km** as one adjustable number with a default, shown inside the total (section 5).
5. **Ferry cost shown as a range** ("about 100-130 EUR, check booking") not a point. Prices are dynamic by date, car length and booking time; I found no free API.

### 2b. Needs manual input from the user

- Which tolls the user already pays by subscription (Oresund ØresundGO / BroBizz) and so the discounted price applies. Store as a toggle in localStorage, no server.
- Ferry ticket actually booked (type the price; skip the guess).
- Parking: city, hours, nights. No free pan-European parking price source exists. A single "parking at destination" field, default 0, is honest.
- Car dimensions (over 6 m or trailer changes Oresund and Great Belt class; Great Belt even measures bike racks and towbars, [opened] storebaelt.dk/en/prices).
- Time value (EUR per hour), default off or a clearly named "your hourly value" input.
- Depreciation/wear per km if the user knows their car (default from a table below).

### 2c. Avoid

- **A single pan-European "tolls" number from a paid API.** TollGuru: official beta pricing page lists a trial of up to 150 transactions/day for business accounts and 15/day for individuals, Starter 80 USD/month for 5,000 transactions, and one origin-destination route counts as about 5 transactions. [search] https://tollguru.mapup.ai/toll-api-pricing-plans . I did not find or open the API terms of service. Needs a key, a backend to hide it, per-user quota, and likely forbids storing/redistributing. Conflicts with "keyless, static files".
- **Parking prices, congestion zones, low-emission zone rules beyond a link.** No reliable free data; stale numbers erode trust.
- **Live ferry fares** by scraping operator sites (terms, fragility, no API).
- **Fehmarn tunnel toll**, any 2031 figure (not set).
- **Per-km French toll as a precise number.** Real tolls are per-section by concessionaire; the 9-12 ct/km range is only good for "roughly".
- **Presenting depreciation as a fact.** It is a modelled number; label as a default the user can edit.
- **Open Charge Map for tolls.** It is an EV-charging database, not a toll source (see 3.4). Its use here is the electric leg, not tolls.

## 3. Free and open data sources, what they really give

1. **OSM toll tags.** [opened] https://wiki.openstreetmap.org/wiki/Key:toll documents `toll=yes/no`, `barrier=toll_booth`, `highway=toll_gantry`, per-class overrides like `toll:hgv`. `charge=*` appears only under "similar tags" for the amount; `toll:motorcar` is not documented there, and the wiki says there is no community consensus for ferry tagging. A German forum thread says amount/class tagging is inconsistent [search]. Conclusion: OSM tells you "this road segment is tolled", not "what it costs". Good for detection and for a "tolls on route: yes" flag, bad for amounts.
2. **Valhalla toll support.** [opened] https://valhalla.github.io/valhalla/api/route/api-reference/ : costing options `use_tolls` (0-1, default 0.5), `toll_booth_cost` (time, default 15 s), `toll_booth_penalty`, `exclude_cash_only_tolls`; route summary `has_toll`; maneuver attribute `toll`; ferry options `use_ferry`, `ferry_cost`, `has_ferry`, maneuver `ferry`. The docs describe **no monetary amount**. The repo already reads `has_ferry`; `has_toll` is a one-line addition. [mine] Both flags only tell the UI to show "tolls on this route, estimate below", which then comes from the curated table. Caveat: the public FOSSGIS server is for development and testing, with a fair-use limit of about 1 request/s/user in a mirrored config. [search] https://raw.githubusercontent.com/api-evangelist/valhalla/refs/heads/main/rate-limits/openstreetmap-de.yml ; official policy https://wiki.openstreetmap.org/wiki/FOSSGIS/Server/Policy was not opened. This is already the owner's known N1 risk.
3. **A "toll-free alternative" check.** Valhalla `use_tolls` below 0.5 can ask for a cheaper-in-money route. Two routing calls cost more load on the public server, so make it a button, not automatic. [mine]
4. **Open Charge Map.** [search] licence CC BY 4.0 with attribution, data from third-party providers keeps the provider's copyright and attribution must be visible to the end user, keys are free for registered use; hard limits unpublished. https://community.openchargemap.org/t/announcing-our-new-simpler-data-license-for-ocm-data-cc-by-4-0-international/565 and https://beta.openchargemap.org/about/terms . Useful for "charge on the way for the electric leg", not tolls. The repo already has an OCM key (memory).
5. **Operator pages** (Oresund, Great Belt, Scandlines, TT-Line, Stena, Oresundslinjen, DARS, eznamka.sk, NUSZ, Czech eDalnice, Austrian ASFINAG, Swiss BAZG). Only reliable source of amounts. No API found. Hand-maintain with "seen on" dates. A scheduled GitHub Action can only do a "page still contains this number?" check, and that scraping must respect each site's terms (not verified).
6. **Aggregators with tables** (fuel-prices.eu/tolls, tollguru wiki, tolls.eu, vignette comparison sites): used here as leads only. Several disagreed with each other, and one search note flagged tollguru pages mixing Oresund and Swedish congestion tax. Never copy into the product without checking the official page. [search]

## 4. CO2 per trip for a PHEV

- **Car data.** WLTP CO2 for Santa Fe PHEV 1.6 T-GDi about 37-38 g/km, electric range about 54 km, petrol 1.38 l/100 km. [search] https://autotijd.be/en/consumption/hyundai/santa-fe ; Hyundai tech spec July 2024 quoted 54.2 km [search]. WLTP is an optimistic cycle; owner logs on Spritmonitor range from 5.7 to 16.1 kWh/100 km electric, [search] https://www.spritmonitor.de/en/detail/1311671.html?cdetail=2. I found no official WLTP kWh/100 km value.
- **Petrol, well-to-wheel.** About 2.075 kg CO2e/L tank-to-wheel plus about 0.58 kg/L well-to-tank = about 2.66 kg/L, from a DEFRA mirror. [search] https://greencalculus.com/factors/well-to-tank-fuel-factors/ . Official DESNZ workbook not opened; use the real file as the source when implementing.
- **Electricity.** Use grid intensity of the country where the car is charged (mostly Sweden at home). EEA publishes country-level gCO2e/kWh, but the page is an interactive chart. [search] https://www.eea.europa.eu/en/analysis/indicators/greenhouse-gas-emission-intensity-of-1/greenhouse-gas-emission-intensity-of-electricity-generation-country-level . A 2021 AIB table gave Sweden about 8 g, Denmark about 180 g, Germany about 378 g per kWh (old, [search]). Use a small hardcoded table refreshed yearly with source and year.
- **Formula [mine].** trip CO2 = (litres petrol used by the existing PHEV model x 2.66) + (kWh used x grid factor of the charging country) + optionally ferry CO2 (skip; no good free per-car figure found). The existing rt* PHEV model already splits electric km and petrol litres, so this is a pure display layer.
- **Honesty line.** Say "estimate, well-to-wheel, your real use will differ; temperature and speed matter" and show the factor values behind a tap.
- **Not shown:** vehicle production CO2 (no source, contested).

## 5. Wear, depreciation, time value

- **Fact-ish.** I found no usable official per-km depreciation or workshop figure. A secondary article said ADAC totals (fixed + running, 5 years, 75,000 km) land at roughly 39-45 ct/km for cheap compacts and 60-75 ct/km for big SUVs, unverified against ADAC. [search] https://automobilisto.de/magazine/market/tco-segment-comparison . Those totals include insurance, tax and depreciation, so they are NOT a marginal per-km number and must not be added to fuel.
- **Marginal vs total cost, the important distinction [mine].** For "is the detour worth it" only marginal cost counts: fuel plus tyres plus brakes/service plus a small depreciation-by-km. A reasonable placeholder is a single editable "wear and tear" value (for example 0.06-0.12 EUR/km) with the label "assumption, edit to your car". I could not source the number, so ship it as an input with a prefilled default and say so.
- **Tax-style references.** Swedish and German mileage allowances exist (for example the Swedish skattefri milersattning), but I did not open them today. Mention only as a possible "official reference" if verified at implementation time.
- **Time value.** Pure user input, default 0, shown as an extra line "your time at X EUR/h". Reuses existing duration. This lets a user compare a 30-minute-faster toll road to its price; it is my own idea and needs no data.

## 6. Ideas for EuroFuelPrices (ranked)

All effort is for one developer. Impact is user value for the Sweden-Germany driver and similar Nordic-Europe drivers.

### 1. "Total trip cost" card with fuel, crossings, vignettes
- What: below the existing route result add one expandable card: Fuel (existing), Crossings (bridge/ferry from the curated table), Vignettes (by countries crossed), Wear (editable per-km), Total, plus a "per person / per car" toggle. Each line has a label: "estimate" or "you entered".
- Why: closes the biggest hole between "cheapest pump" and real cost for the owner's main trip.
- Impact: very high. Effort: M. Needs: `data/crossings.json`, `data/vignettes.json` curated by hand, existing route polyline and country list. Risk: stale prices; mitigate with "seen on" dates, honest range, source link per line, a visible "last checked" stamp. Do not publish an amount whose official page was not opened.

### 2. Route options compared by money: bridge vs ferry vs Trelleborg
- What: for Sweden to Germany run up to three route variants (bridges only via Valhalla `use_ferry` low, ferry route, and a fixed Trelleborg-Travemuende/Rostock option as a pseudo-route) and show a three-row table of total money and time. Tie to the existing detour-cost ranking.
- Why: this is the genuinely surprising answer for the owner (e.g. Rodby ferry route can win on distance, bridges win on certainty). Competitors rarely do it.
- Impact: high. Effort: M-L (extra routing calls, rate-limit care; fixed Trelleborg option needs hand-written pseudo-route). Needs: Valhalla `use_ferry`, 1 request per second limit respected, curated ferry fares. Risk: public Valhalla fair-use; ferry fares vary by date so show ranges and a booking link.

### 3. Subscription toggles ("I have ØresundGO / BroBizz")
- What: localStorage toggles that switch crossing price to the discounted variant. For Oresund the difference is 470 vs 182 DKK per trip ([opened] oresundsbron.com/en/prices), plus a "break-even trips" hint (annual fee 370 DKK).
- Why: for a commuter this is a bigger saving than any fuel station choice, and it is calculable with no server.
- Impact: high for commuters. Effort: S. Needs: item 1 table. Risk: low; privacy-safe, nothing leaves the device.

### 4. CO2 line for PHEV (well-to-wheel, charging-country aware)
- What: show kg CO2e per trip and per 100 km using petrol 2.66 kg/L and the grid factor of the charging country, with a "what if all-electric" comparison.
- Why: the PHEV model already knows electric vs petrol split; this is the "wow, it understands my car" line and is low cost.
- Impact: medium-high. Effort: S. Needs: a small `data/co2_factors.json` with sources and years; verify against the official DESNZ and EEA files at build time. Risk: spurious precision; mitigate with ranges and an info tap.

### 5. Honesty strip v2: per-line "how sure are we"
- What: extend the existing honesty strip so each cost line shows a state: "fixed price (operator, seen 2026-11-06)", "range (varies by date)", "your input", "not included". Add `has_toll` and ferry flags from Valhalla as a "tolls on route: yes/no" fallback when the crossing is not in our table.
- Why: trust is the product for a free tool; this is cheap and prevents the "wrong toll" complaint.
- Impact: high (trust). Effort: S. Needs: `has_toll` read in `rtRoute` (one line). Risk: none; do it with idea 1.

### 6. "Is it worth the detour" now includes crossings and wear
- What: update break-even logic so a detour that crosses a toll or ferry shows the real cost; marginal wear per km is used instead of total ownership cost.
- Why: current detour-cost ranking only uses fuel; this stops it recommending a cheap pump behind a bridge.
- Impact: medium-high. Effort: M. Needs: item 1; polyline-near-crossing test on detour legs. Risk: more routing calls; limit to the top 3 candidates.

### 7. Vignette helper with official-operator deep links
- What: when the route enters Austria, Switzerland, Czechia, Slovakia, Slovenia, Hungary show "vignette needed", the product that fits the trip length, an estimated price, and a link to the official operator. Never sell or take payment.
- Why: fines for a missing vignette are a real cost; the owner's German-to-Alpine trips make this relevant.
- Impact: medium. Effort: S-M. Needs: hand-verified prices from official operator pages (I have only aggregator numbers). Risk: stale prices, conflicting sources; ship only countries verified from the official page.

### 8. Scheduled "price still correct?" check for the curated tables
- What: a GitHub Action monthly that fetches the few operator pages and fails with an issue if the known number is no longer present on the page, plus a visible "table last reviewed" date in the UI.
- Why: tiny team cannot watch 15 pages by hand; this is the cheapest way to avoid silently wrong prices.
- Impact: medium (maintenance). Effort: S-M. Needs: simple fetch + regex per source; confirm each site's terms and robots first. Risk: scraping fragility and terms; fallback is a calendar reminder.

### 9. Optional: EV charging leg using Open Charge Map
- What: for the PHEV electric leg or a future BEV profile, list chargers near route stops with price if provided. The repo already holds an OCM key.
- Why: ties the existing EV price work to the route; useful for visitors with BEVs.
- Impact: medium. Effort: L. Needs: OCM attribution visible to users; prices are often missing; server-side key use only. Risk: sparse price data; licence attribution per provider.

### 10. Do not build now: parking, live ferry fares, toll API, Fehmarn toll
- What: record the decision. Parking, live fares and congestion zones have no free dataset; TollGuru needs a key and a backend and is metered; Fehmarn opening is 2031 or later with no toll set.
- Why: protects the "no backend, no tracking" promise; avoids trust-damaging stale numbers.
- Impact: n/a. Effort: none. Risk: none.

Suggested first slice if the owner wants one decision: ideas 1, 3 and 5 together (M, one table file, localStorage toggles, one honesty-strip change). They give the biggest visible jump for the owner's Sweden-Germany commute.

## 7. Not verified / gaps

- Great Belt 2026 amounts come from a search summary of fuel-prices.eu; the official page opened but the price table was missing. Check `https://storebaelt.dk/en/prices/` in a browser before using.
- Scandlines: the "from 101.25 EUR" figure is for the Puttgarden-Rodby + Oresund bridge standard ticket page as returned by the tool; the pure ferry fare, flex and early tariffs were not read.
- Oresund page said "valid from Sept 14 2026" and listed DKK only; the 10% newsletter note applies to the online price.
- Czech, Slovak, Hungarian, Swiss vignette prices: not verified from official pages.
- No official WLTP electricity figure, no grid-intensity numbers opened, no depreciation figure verified.
- Norway AutoPASS and Gothenburg/Stockholm congestion amounts not verified (Transportstyrelsen amounts page appeared in search but was not opened).
- TollGuru API terms not read, only pricing summaries.
- FOSSGIS official usage policy not opened; the 1 req/s limit is from a mirrored third-party file.
