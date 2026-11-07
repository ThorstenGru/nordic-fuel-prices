# Romania source switch

Code: `src/scrapers/romania.py` (peco-online.ro, default) and `src/scrapers/romania_official.py` (Monitorul Preturilor API). Tests: `src/tests/test_romania_carry.py`, `src/tests/test_romania_official.py` (no network). Research: `ROMANIA_OPTIONS_2026-11-06.md`.

## Switch
Environment variable `ROMANIA_SOURCE`, passed by `scrape.yml` from the repository variable of the same name (Settings, Secrets and variables, Actions, Variables).

| Value | Behaviour |
|---|---|
| `peco` (default, also when unset or invalid) | peco-online.ro only, as before. One rotating quarter of the counties per run. No timestamps: price time = when we last saw the station. |
| `official` | Monitorul Preturilor only. Real per-station `updatedate` (Europe/Bucharest) becomes `updated_at`. |
| `both` | Both run; an official station replaces a peco-online station within 150 m. |

Optional: `ROMANIA_OFFICIAL_BUDGET` = GET calls per run (default 150, about 50 tiles x 3 fuels).

## Permission status: NOT obtained
The official API is keyless and public, but no reuse terms were found and no written permission exists (2026-11-07). The default therefore stays `peco`. Switch to `official` or `both` only after the owner has permission (or consciously accepts the risk) from the Consiliul Concurentei. peco-online.ro permission is also not asked.

## How the official source behaves
- Endpoint `GetGasItemsByLatLon`, one product per call (11 petrol, 21 diesel, 31 LPG), 5 km radius, at most 50 stations per call. A call that returns 50 is re-queried as four 2.5 km circles.
- Tiles: a 7 km grid restricted to the places of stations we already know (the previously published `ro.json`); county seats bootstrap an empty start. Each run scans a rotating slice of the tiles, so a full pass takes several runs. Coverage grows by one ring of cells per pass as new stations are found.
- Politeness: at least 1.1 s between calls, User-Agent `EuroFuelPrices/1.0 (+https://eurofuelprices.com)`, request budget and a 200 s wall-clock cap per run.
- Not done: `GetGasItemsByUat` (cheaper; needs UAT ids stored per station), auto-refinement beyond one split level, refresh just after the 12:00 price-change time.
- Brand comes from the API's network name (for example "MOL Romania Petroleum Products"), not normalised to the peco-online brand names.
- Verified live on 2026-11-07 with 3 GET calls for one Cluj tile (15 stations, timestamps parsed). The full national cycle and the `both` merge on real data were NOT run.
