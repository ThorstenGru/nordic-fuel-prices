# Fare table (web/fares.json)

Hand-kept list of crossings, tolls and vignettes for a passenger car. Not verified data: every entry carries `check_operator: true` and the UI must say "check operator". Valhalla only gives toll/ferry flags, never amounts.

## Rules
- Enter a price only if you read it on an opened operator page. Otherwise `price: null` and say why in `conditions`.
- `confidence`: "operator page opened" or "aggregator" (use "not read" when no price). Prefer operator pages.
- `seen_on` is the date you read the page. Entries older than 90 days grey out in the UI (owner decision).
- `price` is `{min, max, currency}`; either bound may be null (e.g. "from" fare only). It spans different products (1-day to 1-year vignette, contract vs booth) and must never be shown as a trip cost. `trip_price` `{amount, currency, basis}` is the one figure for a single one-way trip with no contract (or null); the UI shows that, with `conditions` next to it.
- A priced entry needs a confirmed vehicle class (car). Gedser-Rostock has no price until the car fare is confirmed.
- `match.endpoints` are approximate lat/lon of the crossing ends; `match.names` are lowercase-insensitive name hints for route steps.

## Refresh routine (about every 60 days, always before the 90-day grey-out)
1. `node tools/check_fares.js` lists stale entries and schema errors (`--today YYYY-MM-DD` to test ahead).
2. Open each stale entry's `source`, update `price`, `conditions` (validity date, height/length limits) and `seen_on`.
3. Fill the `null` entries when you can open the page: Great Belt, TT-Line Trelleborg-Travemunde, Stena Trelleborg-Rostock, Helsingborg-Helsingor, Switzerland.
4. Re-run the check, then `node tools/test_*.js`. Do not commit tooling output elsewhere.

## Known gaps on 2026-11-06
- Great Belt, both Trelleborg ferries, Helsingborg-Helsingor standalone fare and the Swiss vignette: no price read.
- Fehmarn: no toll, not open before 2031 per ROUTE_IDEAS_D (internal note, not a primary page).
- France/Italy: "varies", no per-100 km band because no primary source was read.
- Czech tier for the owner's PHEV (CO2 up to 50 g/km) is cheaper than the standard price; confirm eligibility on the operator page.


## App use (route planner wave 2)
- The app loads `web/fares.json?v=<FARES_V>` lazily (constant in `web/index.html`; bump it whenever this file changes, the service worker serves `?v=` URLs cache-first).
- Only `trip_price` is ever counted in a trip cost, and only when `seen_on` is within 90 days; `price` min..max is never shown as a cost. Older entries are greyed in the list and treated as unknown.
- Optional field `"open": false` (not built yet, for example the Fehmarnbelt tunnel): the entry is never matched to a route.
- Matching: ferry entries need a ferry on the route and both endpoints within 15 km of it; bridges and tunnels both endpoints within 15 km; vignettes and toll notes match when every listed country is driven.
