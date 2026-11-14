# Architecture

How EuroFuelPrices works end to end. Status: 2026-11-11, app version `2.0.0`. Operations and runbook: [OPERATIONS.md](OPERATIONS.md).

## 1. The big picture

```
 official + 3rd-party feeds ──► GitHub Actions "Scrape" (every ~15 min) ──► static JSON + HTML
   (FR, ES, PT, IT, ANWB, …)        src/main.py + generators               │
                                                                           ▼
                         gh-pages branch (GitHub Pages)  ◄── "Deploy Web" (frontend-only pushes)
                                      │
                        Cloudflare (DNS, CDN cache, Web Analytics, Workers)
                                      │
            browser PWA (map, routes, calculators) · crawlers (town pages, /europe/) · Facebook routine
```

Everything is static files plus a few small serverless pieces. There is no database and no application server. All state lives in the
repository (source, logs) or on the `gh-pages` branch (published data, regenerated every run).

## 2. Repository map

| Path | Purpose |
|---|---|
| `src/main.py` | The scrape pipeline: per country fetch → validate → merge → decide (fresh / keep last good) → publish `data/{cc}.json`, `meta.json`, `health.json` |
| `src/scrapers/` | One module per country (`france.py`, `spain.py`, …), shared ANWB base (`_anwb.py`), `base.py`, `geocoder.py`; list in `__init__.py` (`ALL_SCRAPERS`) |
| `src/sources/` | Extra source modules (e.g. `fi_hintatutka.py`) |
| `src/merge_engine.py` | Multi-source merge (match ≤100 m, brand-compatible, newer timestamp wins, regulated caps fill gaps only) |
| `src/data_checks.py`, `plausibility.py`, `source_gap.py` | Quality checks, implausible-price flags, cross-source comparison |
| `src/chargers.py`, `src/elpris.py`, `src/price_cycles.py` | EV charging posts, electricity prices, weekly price cycles |
| `src/seo_pages.py`, `src/seo_text.py` | Static town pages per country + sitemaps (all countries in `seo_text.COUNTRIES`), Swedish cheapest-towns page; settings and texts are in `seo_text.py` |
| `src/europe_index.py` | `/europe/` ranking (en + sv/de/da), 37 border pages, share pictures (`/og/*.png`), `/open-data/*`, `index_history.json` |
| `src/indexnow.py` | Daily IndexNow ping (Bing/others) for the Europe pages and country hubs |
| `src/seed/` | Seed data: place lists for SE/AT, caps, tariffs |
| `src/tests/` | Python unit tests (no network, 190+) |
| `web/` | The frontend: `index.html` (app, ~700 KB, one file), `sw.js`, `theme.css`, `about.html`, `admin.html`, `embed.html`, `widget.html`, `manifest.json`, icons, fonts, Leaflet in `vendor/`, `vehicles.json`, `fares.json`, `ac_tariffs.json`, IndexNow key file |
| `worker/route/` | Cloudflare Worker: routing proxy at `eurofuelprices.com/api/route` (validates, rounds coordinates to ~100 m, caches, provider fallback) |
| `worker/watchdog/` | Cloudflare Worker (cron every 30 min): reads `meta.json`, pushes an ntfy notification when prices stop updating |
| `tools/` | JS tests and checks (`test_*.js`, `check_*.js`), `growth_kpis.py`, Facebook routine (`fb_*.py`), one-off research in `tools/archive/` |
| `docs/` | Research, decisions, runbooks (see [INDEX.md](INDEX.md)) |
| `.github/workflows/` | `scrape.yml`, `deploy-web.yml`, `tests.yml`, `facebook.yml` |
| `data/` | **Generated** output (git-ignored: `*.json`, generated page folders, `sitemap-*.xml`) |

## 3. Data pipeline

1. **Fetch** — every country scraper runs asynchronously (`aiohttp`). Each has its own refresh interval (`REFRESH_MINUTES`) so upstream APIs are not hammered; a recently refreshed source is re-published from the previous run.
2. **Clean/validate** — `clean_stations` drops bad coordinates and duplicates, applies per-currency price bands, flags implausible prices.
3. **Merge** — `merge_engine` combines sources for countries with several feeds (DK, GB, GR, CZ, SE, NO, FI …). Per price: `source`, `alt`, `disagree`.
4. **Decide** — fresh result, or keep the last good file with `status: "stale"` if the new one is empty, failed or shrank suspiciously (guards can be lifted for one run with the `allow_shrink` input).
5. **Publish** — `data/{cc}.json`, `meta.json` (index + per-country `stats_eur` medians + `fx` rates), `health.json`.
6. **Side jobs (never fail the run):** electricity prices (`elpris.json`), price cycles, EV charging posts (`ev_*.json`, only when the published file is >6 days old).
7. **Generators:** copy `web/*` into `data/`, then `seo_pages.py`, `europe_index.py`, `indexnow.py`.
8. **Deploy:** `peaceiris/actions-gh-pages` publishes `data/` to the `gh-pages` branch (single orphan commit, so history does not bloat).
9. **Chain:** the `chain` job waits ~12 min and dispatches the next run (the cron trigger is only a safety net).

`deploy-web.yml` publishes frontend-only changes immediately (rsync into `gh-pages`). **It deletes anything in `gh-pages` that is not in `web/`**, except
the protected items: root `*.json`, `.git`, `.nojekyll`, and the generated folders listed in its `--exclude` flags (`se/ at/ de/ ch/ fr/ es/ pt/ dk/ nl/ europe/ open-data/ og/`,
`sitemap-*.xml`). **A new generated folder must be added to that list**, otherwise the next frontend push wipes it until the next scrape.

## 4. Data formats

- `{cc}.json` and `meta.json` — see the README. `meta.json` also holds `countries[].stats_eur.{p95,diesel}` = `{n, median, p10, p90, min, max}` in EUR/L, `grade`, `status`, `sources[]`, `source_gap[]` and `fx.rates` (ECB).
- `health.json` — per source: status, counts, newest/oldest price age, error text.
- `index_history.json` — one snapshot per day (`{date, p95:{CC:median}, diesel:{CC:median}}`), read back from the live site and appended by `europe_index.py` (max 400 days); feeds the "7-day change" column.
- `/open-data/national-averages.{json,csv}` — country medians (EUR/L), station count, source grade. Medians only, no station rows.
- Station price entries: `fuel_type` (`E10`, `E5`, `95`, `98`, `DIESEL`, `LPG`, `CNG`, `E85`, `HVO100` …), `octane` for petrol (95/97/98/100), `unit`, `currency`, `updated_at` (source time or `null`).
- Petrol is bucketed by octane (95 vs 98+), so a 98 price never appears under a 95 label.

## 5. Frontend (`web/index.html`)

A single-file PWA (Leaflet map, i18n for en/sv/de/fr/es, light/dark). Main parts: price map with quintile-coloured markers and clusters, per-country lists and
a Prices tab (country medians), bottom sheets (station, favourites, tank/fill cost), search, **Route tab** (route via the Cloudflare proxy, cheapest pumps in a corridor, fuel plan,
trip cost, charging posts near the destination, plan sharing as a URL fragment), **border-run** and **road-trip** calculators, **My car** (profile in local storage), share
(canvas share picture where files can be shared, else text + link), navigation chooser, install nudge from the 2nd visit, privacy: no accounts, location only on request.
`sw.js`: network-first for HTML/data (so deploys reach users at once), cache-first for versioned data and libraries; readable "No connection" page for navigations.
Tests: `tools/test_*.js` (pure functions are extracted from `index.html` between marker comments).

Static companion pages: `about.html` (methodology, grading, regulatory research), `admin.html` (data health), `embed.html` + `widget.html` (free iframe widget; reads `meta.json`),
`theme.css` (shared by generated pages).

## 6. Generated pages and search visibility

- **Town pages** (`seo_pages.py`): per country a hub and one page per town (≥3 stations and at least one fresh price). Two town models: `places` (stations assigned to the nearest OSM place; SE, AT) and `city` (feed's own city names; the rest). Text is localised (sv, de, fr, es, pt, da, nl); timestamps are shown honestly (`snapshot` / `fetched` / `price`). Footers state the source and a note when it is unofficial. JSON-LD: BreadcrumbList + ItemList of GasStation.
- **Europe index** (`europe_index.py`): trust filter — status ok, data <36 h old, ≥30 priced stations per fuel; grade shown on every row. Pages: `/europe/`, `/europe/{sv,de,da}/` (hreflang), `/europe/fuel-prices-<a>-vs-<b>/` (37 pairs), each with an `og:image` card from Pillow (skipped silently if Pillow is missing). Dataset JSON-LD points to the open data.
- **Sitemaps:** `sitemap.xml` (static), `sitemap-seo.xml` (index) → `sitemap-<cc>.xml`, `sitemap-europe.xml`. Submitted to Google Search Console and Bing Webmaster Tools (2026-11-11); IndexNow pings once a day.
- **Analytics:** Cloudflare Web Analytics beacon on every page (no cookies).

## 7. Cloudflare

Domain `eurofuelprices.com` is on Cloudflare (proxied DNS → GitHub Pages). Used for: CDN cache, Web Analytics, the routing Worker (route `eurofuelprices.com/api/route*`),
and the watchdog Worker (cron + KV namespace `STATE`, secret `NTFY_TOPIC`). `/cdn-cgi/trace` gives the home country on first visit. The routing Worker's upstream is the public
Valhalla server with OpenRouteService (api.heigit.org, secret `ORS_KEY`) as backup.

## 8. Facebook routine

`.github/workflows/facebook.yml` runs `tools/fb_bot.py`:

- **post** (07:00 UTC daily, retry 11:00 UTC): `fb_daily.build` picks the weekday's format — Mon ranking, Tue border pair, Wed quiz, Thu feature tip (how to use the app), Fri local spotlight (cheapest within 10 km of a town), Sat "comment your town", Sun feature tip — using `/open-data/national-averages.json` (≥300 priced stations; grade D allowed but marked as estimates). It posts the text with the matching share card via the Graph API and logs it in `docs/facebook/post_log.csv` (one post a day; pairs/features not repeated within 14 days).
- **replies** (hourly at :30): comments on the latest "comment your town" post that name a town in a covered country (DE, CH, FR, ES, PT, DK, NL, SE) get a reply with the cheapest petrol/diesel within 10 km (`fb_local.py`). One reply per comment (`docs/facebook/replied.csv`), max 15 per run, never to the Page itself, nothing about commenters stored.
- **selftest** (manual): verifies the token, reads the feed, creates and deletes an *unpublished* photo — no public effect.
- Everything uses a **Page access token** (secrets `FB_PAGE_ID`, `FB_PAGE_TOKEN`); `verify_page` aborts unless the token belongs to "Euro Fuel Prices". Without the secrets the job exits quietly.
- Aggregate follower-city insight (`page_follows_city`) steers the Friday town when Facebook provides it; individuals are never looked up or tagged.
- Setup and rules: [facebook/GRAPH_API_SETUP.md](facebook/GRAPH_API_SETUP.md), [facebook/PLAYBOOK.md](facebook/PLAYBOOK.md) (the older browser-based route, now disabled), [FACEBOOK.md](FACEBOOK.md).

## 9. Testing and CI

- `tests.yml` (every push/PR): Python unit tests, JS tests, page syntax, data-version check.
- `scrape.yml` runs the same tests before each scrape: **a failing test blocks the scrape and deploy**.
- `deploy-web.yml` runs the frontend tests before rsync.
- Python tests cover scrapers' parsing, merge engine, caps, checks, Europe index, Facebook routine (with a fake Graph API). No test touches the network.
