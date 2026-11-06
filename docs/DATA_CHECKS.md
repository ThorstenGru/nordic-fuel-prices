# Data checks (DE first)

Code: `src/data_checks.py`, wired in `src/main.py` (`run_one`). Enabled per country via env `DATA_CHECKS` (default `DE`; comma list). Nothing changes a price; fields are additive and ignored by `web/index.html` (read-only grep: it only reads `plausible`, `updated_at`, `basis`, `alt`, `source`).

## 1. Last-changed tracking
State = the previous published `<cc>.json` (already fetched from Pages as the last-good source), so no new storage.
- `pc` (station, int): epoch MINUTES of the last observed price change. Compared by signature (fuel, octane, price per slot).
- `ps: 1` (station): unchanged for more than 48 h. Only present when set.
- New stations get `pc = now`, so nothing can be flagged until 48 h after enabling (true age is unknowable from ANWB). If the previous file cannot be fetched in one run, the clock restarts for all stations.
- Stale-keep runs (scraper failed) republish the old file untouched, so `pc` carries on.

## 2. Sanity checks (`meta.countries[].checks`, mirrored to health.json)
- `band_out`: count of P95/P98/DIESEL prices outside 1.0-3.5 EUR (report-only; `plausibility.py` still flags the wider 0.8-3.4 band; LPG/CNG/E85 exempt).
- `e10_gt_e5`: `{n, pct}` share of stations with E10 > E5 x 1.005, only with >= 30 paired stations. ANWB-DE publishes `95`/`98` slots, not E5/E10, so this stays absent until Tankerkoenig (MTS-K) is on (see TANKERKOENIG_SETUP.md; test mode covers too few stations to reach 30 pairs reliably).
- `dup_n`: extra stations sharing lat/lon (4 decimals, about 11 m) and brand.
- `stale48_n` / `stale48_pct`: stations with `ps` among priced stations.

## 3. National jump
`checks.median_jump`: `[{fuel, prev, now, pct}]` when the country median (`stats_eur` p95/diesel) moved > 3 % against the previous run's meta (only if that run was `ok`). Alert only; does not block publishing.

## Size
Measured on the Oct-7 de.json (14,997 stations): +210 KB raw (6.78 -> 6.99 MB, +3.1 %), almost all from `pc` (about 14 bytes/station); `ps` and `checks` are negligible. Gzip on Pages is much smaller.

## Tests
`cd src; python -m unittest discover -s tests -q` (`tests/test_data_checks.py`; 82 tests pass).
## Open
Not run end-to-end against live Pages (no push). On real Oct-7 data: 0 band outliers, 2 duplicates, no E5/E10 pairs.
