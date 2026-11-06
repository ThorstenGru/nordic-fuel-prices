# Electricity price pipeline (`src/elpris.py` -> `data/elpris.json`)

Source choice and licensing: see `ELPRIS_SOURCES_2026-11-06.md`. Source: elprisetjustnu.se (ENTSO-E based), SE1-SE4 only.
DK (Energi Data Service), NO, FI and DE-LU are not implemented (rate limits / licence or token unresolved).

## Run
- CI: step "Electricity prices" in `.github/workflows/scrape.yml`, after the scrapers, `continue-on-error: true`. Runs on every
  scrape run (about every 15 min): 8 small requests (today + tomorrow x 4 areas) plus any missing days of the current/previous month.
- Local: `PYTHONIOENCODING=utf-8 python src/elpris.py`
- One-off seed (complete months since 2022-01): `python src/elpris.py --backfill [YYYY-MM-DD]` writes
  `src/seed/elpris_monthly.json` (committed, about 7,000 requests, 4 parallel). Re-run only to extend history; past months are frozen.
- Tests: `cd src && python -m unittest tests.test_elpris` (offline; includes the Sep 2026 SE4 invoice check, tolerance 0.002).

## State and failure handling
`data/*.json` is gitignored and `data/` is rebuilt on every CI run, so the previous run's state is read from the
published `elpris.json` (same mechanism as `meta.json`: `resolve_pages_base`, local `data/elpris.json` wins if present).
- No tomorrow file yet (404, before about 13:00 CET): `tomorrow` is `null`. 404s are never cached.
- Today's file missing or invalid for an area: that area keeps its last good block. All areas failing: previous file is republished unchanged.
  Nothing previous and nothing fetched: no file is written (never publish empty).
- Day files are validated: at least 20 rows, SEK/kWh within -5..50.
- Today in Sweden is computed without tzdata (EU DST rule), because Windows has no tz database.
- The `updated` timestamp is of the last successful refresh; the UI should compare `today.date` with the local date to detect staleness.

## Format (`schema: 1`, prices SEK/kWh ex VAT)
```
{"schema":1,"updated":"2026-11-06T13:35:00Z","source":"elprisetjustnu.se (ENTSO-E)",
 "areas":{"SE4":{
   "slot_min":60,
   "today":{"date":"2026-11-06","sek":[24 hourly means; 23/25 on DST days]},
   "tomorrow":{"date":"2026-11-07","sek":[...]} | null,
   "monthly":{"2022":[12 means or null],...,"2026":[... current month partial]},
   "partial":{"month":"2026-11","days":6} | null,
   "seasonal":{"1":{"mean":..,"lo":..,"hi":..,"n":4},...,"12":{...}},
   "days":{"YYYY-MM-DD":[mean,rows],...}   // state only: previous + current month, UI can ignore
 }}}
```
- Hourly values are the mean of the 15-minute rows of each local clock hour (source is 15-min since 2025-10-01).
- `monthly` = equal weight per price row (matches the retailer Medelspotpris within 0.001). The current month is partial (see `partial`).
- `seasonal` per calendar month: mean and band over the latest 4 complete years (the partial month is excluded). Band = min/max with fewer than 4 values,
  25th/75th percentile with 4 or more (2022 was a crisis year). An estimate, not a forecast; the UI must say so.
- Months-ahead estimate for the home tariff = `(seasonal.mean + variable) * 1.25 + 0.773` (band with `lo`/`hi`).

## Attribution
"Elpriser: Elpriset just nu.se (ENTSO-E)". The browser reads only the same-origin `elpris.json`, so no CSP change for this file.
