# Romania: station-price source options
Date: 2026-11-06. Research only. GET requests only, no credentials, no accounts, no POST. Nothing committed.
Labels: (O) = opened/called by me today, (S) = web-search snippet only, (U) = unverified.

## Bottom line
- The official Monitorul Preturilor site has a keyless public GET API that returns real per-station prices with a per-station update timestamp (O). The earlier gap was the wrong controller and parameters, not a block.
- Coverage and prices match peco-online closely in a Cluj test area (60 vs 63 stations; same chains) (O).
- No licence or terms were found for reuse (O: no terms link on the site, /robots.txt is 404; S: the portal is run by the Competition Council). So it is technically easy and legally unconfirmed. This is the owner's decision.
- Recommendation: ask the Consiliul Concurentei for written permission; meanwhile keep peco-online as is. After permission (or a no-objection reply), make Monitorul the primary and peco-online the fallback.

## How the official API works (all O, 2026-11-06)
Found by reading https://monitorulpreturilor.info/index.min.js (public JS) and the page's inline script.
- Base: `https://monitorulpreturilor.info/pmonsvc/Gas/` (the page's `/pmonsvc/Retail` is only for shops; gas actions live under `/Gas/`).
- Catalogs: `GetGasProductsFromCatalog` (ids: 11 petrol std, 12 petrol premium, 21 diesel std, 22 diesel premium, 31 LPG, 41 EV charging), `GetGasNetworks`. XML.
- Prices: `GetGasItemsByLatLon?lon=&lat=&buffer=<metres>&CSVGasCatalogProductIds=<one id>&OrderBy=dist`, send `Accept: application/json`. Also `GetGasItemsByUat?UatId=&CSVGasCatalogProductIds=` and `GetGasItemsByRoute` (the latter not called).
- JSON: `Stations[]` (id, name, `updatedate` "dd/mm/yyyy hh:mm", network, address, lat/lon, `uatid`) and `Products[]` (stationid, price in RON, product, network).
- Limits seen: max 50 stations per call; buffer 5000 m works, 8000 m and above return an empty `{}`; a list like `11,21` fails with a server Postgres error, so one product per call; the HTTP service returned 200 in about 0.3 to 0.6 s.
- The site's `authManager.js` has a login/registration flow; I did not use it and did not need it.

## Quality and freshness vs peco-online
| Check | Monitorul (official) | peco-online (current scraper) |
|---|---|---|
| Per-station timestamp | Yes. In the Cluj test, 57 of 61 stations dated 05/11, 3 on 06/11 and 1 on 06/10 (O) | None; live `ro.json` has `updated_at: null` (O) |
| Cluj test area (lat 46.4 to 47.2, lon 22.8 to 24.2) | 60 stations | 63 stations in our published file; 57 matched within 300 m (O) |
| Chains | Lukoil, Petrom, MOL, Rompetrol, OMV, Socar, Gazprom (O) | Same plus a few small ones; 1078 stations nationally (O) |
| Price agreement on matched stations | Exact on 53 of 124 fuel pairs; Monitorul 0.03 to 0.18 RON lower on 70; higher on 1 (O). Cause not established (our file refreshes one county quarter per run, so staleness is plausible) (U) | |
| Fuels | Petrol std/premium, diesel std/premium, LPG, EV | E5, diesel, LPG only |
| Request cost | One call per tile per fuel | POST per county per fuel, throttled, needs a signed page token since Oct 2026 |
| Fragility | Public JSON, but undocumented | Token and throttle; already one outage this autumn |

National cost (estimate, not run): tiles of 5 km radius at 7 km spacing need roughly 4000 tiles x 3 fuels, about 12000 calls (about 2 hours sequentially, about 15 to 20 minutes with 8 workers). Cheaper design: discover stations once, then query by `UatId` only for the ~1500 UATs that contain stations, and tile big cities (Bucharest hit the 50 cap at 5 km). Not tested nationally.

## Other routes
| Route | Finding |
|---|---|
| data.gov.ro | No fuel-price dataset (O: CKAN search for "carburant" returned 0; "monitorul" returned 3 unrelated health/nature/NGO datasets under CC BY 4.0 or OGL-ROU-1.0). Source: https://data.gov.ro/api/3/action/package_search?q=carburant |
| Brand feeds (Rompetrol, OMV Petrom, MOL, Lukoil) | Not opened. Per-brand scraping would multiply licence questions (U). |
| fuel-prices.eu | Aggregator; says RO data comes from Monitorul, collected every 2 hours; no licence stated (O: https://www.fuel-prices.eu/about/). Not a source for us. |
| Legal basis for station reporting | Lege 162/2026 art. 15 requires monthly reports to authorities (already in docs/REGULATORY_REPORTING.md). Search snippets show a joint margin-reporting order (numbers conflict between two sources) (S). I found no rule that makes the Monitorul data open or reusable. I did not verify an "Ordin ANPC" text. |
| Operator | Search snippets say the portal is run by the Consiliul Concurentei with ANPC as partner, started 2016, national since 2019 (S: financialintelligence.ro, profit.ro). |

## Decision table
| Option | Realtime | Quality | Legal | Effort | Verdict |
|---|---|---|---|---|---|
| A. Keep peco-online only | Medium (about 2 h cycle, no timestamps) | Good coverage, unknown age | Unclear (ANPC-derived, no licence found) | None | Fallback |
| B. Monitorul official API, no permission | High (stations update through the day, timestamps) | High | Unconfirmed; undocumented use of a public endpoint | 1 to 2 days to wire in | Do not switch silently |
| C. B after written OK from the Competition Council | High | High | Clean | B plus one email | Recommended |
| D. Brand feeds | High per brand | Mixed | Several licences | High | No |

## What the owner must decide
1. Send the permission request to the Consiliul Concurentei (non-commercial map, attribution to Monitorul Preturilor, polling about every 30 to 60 min, cache). Draft the email in English plus Romanian if wanted.
2. Whether to wait for the reply or switch earlier on a risk-accepted basis (public unauthenticated endpoint, low load, attribution). My advice: wait a short, fixed period, then decide.
3. Accept that the 12:00 daily price-increase rule makes a refresh just after noon local time worthwhile.

## Prototype
`tools/analysis/ro_monitorul_probe.py` (not wired into the pipeline): tile scan, per-fuel, de-duplicates by station id, prints how many tiles hit the 50 cap and the update-date histogram. Run for Cluj in 6 min 44 s sequential at 0.25 s pacing (about 600 calls). Known shortcut: fixed grid, no auto-subdivision.
