# Price-cycle collector (R11)

Backend only. `src/price_cycles.py` writes `data/price_cycles.json`, a compact record of when fuel is cheap in each
country by weekday and local hour. It feeds the R10 noon price-rise rule and R18 departure hint later; no frontend uses it yet.

## What is stored
After every scrape the national median (EUR) for 95-octane (`p95`) and `diesel` is read from `meta.json`
`countries[].stats_eur` (already computed by `price_stats`). Per country and fuel the file holds:

- `b`: slow baseline, an EMA of the median (alpha 1/672, about one week of 15-minute runs)
- `t`: UTC time of the last fold (`YYYY-MM-DDTHH:MMZ`)
- `c`: 168 cells x 3 characters, index = ISO weekday (0 = Monday) * 24 + LOCAL hour

Cell = level (2 base-64 chars, 0.01 % steps, offset 2048, so -20.47 % .. +20.47 %) + n (1 char, 0-20).
Level = running mean of `(median / baseline - 1) * 100`. After n reaches 20 the mean becomes an EMA (alpha 1/20,
about 5 weeks per cell), so old behaviour fades and a changed price regime is learned. Negative level = cheaper than usual.
Alphabet: `A-Za-z0-9-_`. `EMPTY` (all cells n = 0) is `A`-padded around the offset.

```json
{"schema":1,"updated":"2026-11-06T12:00:00Z","series":{"SE":{"p95":{"b":1.742,"t":"2026-11-06T12:00Z","c":"...504 chars..."},"diesel":{...}}}}
```

No raw snapshots, no station data. Local time per country uses a built-in standard offset plus EU summer-time rule
(no tzdata dependency); Iceland and Turkey have no summer time. Countries not in the table are skipped.

## Pipeline
`scrape.yml`, after the elpris steps: `python src/price_cycles.py` (continue-on-error), then a curl fallback that copies
the live file if none was produced. The script reads `data/meta.json`, loads the previous file (local, else live site,
3 tries), folds, and writes. Rules:

- previous file unreadable (network error): publish nothing, the fallback step keeps the live file; 404 = start fresh only if every Pages base says 404 on every one of 3 passes
- nothing foldable (all countries failed or meta stale > 2 h): nothing written, history untouched
- a country missing in a run keeps its history; a re-run within 5 minutes of the last fold is ignored
- result above 60 000 bytes: not published

## Reading it
`cheapest_windows(series, min_n=8, width=1, top=3)` returns the cheapest weekday/hour windows (`wd`, `hr`, `width`, `lvl`
percent vs baseline, `n` smallest cell count). Windows with any cell below `min_n` samples are skipped, so a new file
returns an empty list. With about 4 samples per cell per week, `min_n=8` means roughly two weeks of data; use a higher
value (12+) before showing a claim to users. The baseline lags real trends slightly; the signal is the shape within a
week, not the absolute level.

## Size
Measured in test with every known country (40) x 2 fuels over two weeks of 15-minute runs: about 44.8 KB (budget 60 KB).
Fixed size once all cells exist: 504 chars per series, so 45 countries x 2 fuels is about 50 KB.

## Not included
Previous-run delta (would cost one more field per cell), station-level cycles, per-region cycles.
