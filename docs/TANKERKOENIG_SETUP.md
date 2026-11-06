# Tankerkoenig (MTS-K) setup for Germany

Code: `src/scrapers/germany.py`. Tests: `src/tests/test_germany_tankerkoenig.py`. Decision background: `GERMANY_SOURCE_DECISION_2026-11-06.md` (addendum with Tankerkoenig's reply).

Germany always publishes the ANWB baseline (about 14.9k stations, grade C, no timestamps). Tankerkoenig is an optional upgrade, off by default.

## Rules from Tankerkoenig (email 2026-11-06)
- Free API: radius 25 km, exactly one request per minute per key (Bundeskartellamt rule), no bulk crawl of all stations.
- Over the limit: HTTP 503 first, then a one-hour IP block (the GitHub runner IP would be blocked). No availability guarantee.
- Commercial API (contract): no rate or radius limit, ZIP and radius search, history. Not yet signed, request format not yet known.

## Owner steps (free key, test mode)
1. Register at https://onboarding.tankerkoenig.de/ and get the API key.
2. GitHub repo, Settings, Secrets and variables, Actions:
   - Secret `TANKERKOENIG_API_KEY` = the key (the workflow already passes it).
   - Variable `TANKERKOENIG_MODE` = `test`.
3. Trigger one run (workflow_dispatch) and check the logs (below). To switch off again set the variable to `off` or delete it.

Without the variable the mode is `off`, even if the secret exists.

## Modes
| Mode | Requests | Result |
|---|---|---|
| `off` (default) | none | ANWB only. Log: `TANKERKOENIG_MODE=off - ANWB baseline only`. |
| `test` | strictly sequential, at least 62 s between the end of one request and the start of the next, at most 5 circles (radius 25 km) per run, first HTTP 503/429 (also 401/403 or `ok:false`) aborts the Tankerkoenig step with no retry, own time budget (420 s, and never closer than 90 s to `SCRAPER_TIMEOUT_S`). | Only ANWB stations within 150 m of a returned station are upgraded to MTS-K prices (E5, E10, diesel; station grade A). No extra stations are added. Country grade stays C and the country source reads `... partial test coverage`, so it is never shown as full MTS-K coverage. |
| `commercial` | circles of `TANKERKOENIG_RADIUS_KM` (default 25) laid as a hex lattice over Germany, limited to areas with ANWB stations, densest first; concurrency `TANKERKOENIG_CONCURRENCY` (default 4); at most `TANKERKOENIG_MAX_REQ` (default 400) requests per run; same abort rule. | Matched stations upgraded, unmatched MTS-K stations added. Country grade becomes A only when at least 10,000 MTS-K stations were read. |

Test mode rotation: the run's time slot (30 min) picks 5 of the 40 metro circles in `GRID`, so all 40 are visited in 8 slots (about 4 h). Between runs the other stations fall back to ANWB, so upgraded prices appear and disappear over time. That is expected in test mode.

Other env (all optional): `TANKERKOENIG_BASE_URL` (default `https://creativecommons.tankerkoenig.de/json`, `/list.php` is appended), `TANKERKOENIG_BUDGET_S`.

## Data handling
- Both readings are kept. The MTS-K price wins; if the replaced ANWB price differs by 2 % or more it is stored as `alt: [{price, source: "anwb", updated_at}]` on that price (`disagree: true` from 8 %), the same shape the merge engine uses. ANWB gives one "95" slot (E5 or E10 unknown), so it is compared with the closer of E5 and E10. ANWB's 98 price is kept (source `anwb`) because the feed has no 98.
- E5 and E10 are published as separate fuel types. With 30 or more stations that have both, `checks.e10_gt_e5` in meta/health becomes active.
- Upgraded stations keep their ANWB id, so the 48 h "unchanged" tracker keeps working. Its signature changes once at upgrade (95 slot becomes E5/E10), which restarts that station's 48 h clock. In test mode the flip back to ANWB on the next rotation resets the clock again, so the 48 h flag will rarely fire for stations in test circles. This is a known limit of test mode.
- Station `source` is `tankerkoenig.de (MTS-K)`, per-price `source` is `tankerkoenig` (the app already labels it "Tankerkönig").
- The API key is never logged (`apikey=` is masked).

## What to check in the logs ("Run scrapers" step)
- `[DE] tankerkoenig mode=test: N stations from R/5 circles, aborted=None, stopped=None, errors=0` is healthy. `aborted=HTTP 503` or `429`: stop, wait at least one hour, and check no other run uses the key. `stopped=time budget`: fewer circles than planned, not an error.
- `[DE] MTS-K merge: X ANWB stations upgraded, Y added, Z alt readings`.
- `health.json`, `countries.DE.merge.tankerkoenig` holds mode, requests, circles planned, abort reason, upgraded, added, alt values. `failed_sources` lists tankerkoenig when it aborted or failed. DE data is still published from ANWB.
- Only one scrape run uses the key at a time (workflow concurrency group). A manual forced run less than 62 s after the previous run ended could still break the one-per-minute rule: avoid that.

## When the commercial contract and API docs exist
1. Set `TANKERKOENIG_MODE=commercial`, `TANKERKOENIG_BASE_URL` to the contract endpoint, and the secret to the new key.
2. Compare the real response with `parse_tk_stations()` (the only place with the free-API field names `e5, e10, diesel, lat, lng, brand, name, street, houseNumber, place, id`) and adapt it.
3. If the contract offers ZIP search or a snapshot of all stations, replace `_cover_circles()` and the circle loop in `_fetch_tankerkoenig()` with that, which needs far fewer requests. Open questions from the decision memo (redistribution terms, "low traffic" definition, requests needed for a 15 minute full cover) must be answered before signing. The 10,000 request per day limit for the low-traffic tariff matters: 400 requests per run at the current cadence is far above it.
4. Revisit `REFRESH_MINUTES` (30) and `TANKERKOENIG_MAX_REQ`.
5. Add the attribution in the app (below).

## Attribution
Required: "Tankerkoenig / MTS-K, Bundeskartellamt" (CC BY 4.0). `web/index.html` only maps the price source id `tankerkoenig` to the label "Tankerkönig"; `web/about.html` has a hard-coded sentence on Germany. There is no data-driven source list with this attribution line, so it has to be added in the web code by hand before test or commercial mode goes public.
