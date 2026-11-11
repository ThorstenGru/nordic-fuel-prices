# EuroFuelPrices

Live fuel prices at every station across **Europe and the EEA** — 40+ countries and territories, 120,000+ stations, a mobile-first PWA
(map, route planner, cost calculators), crawlable town pages in nine countries, and a fully automated growth routine.
Free to use, no account, no ads. Owner: Thorsten Grund.

- **Live:** https://eurofuelprices.com/ · **Europe ranking:** https://eurofuelprices.com/europe/ · **Data health:** https://eurofuelprices.com/admin.html
- **Facebook Page:** https://www.facebook.com/eurofuelprices · **Repository:** `ThorstenGru/nordic-fuel-prices` (GitHub is the source of truth)
- **Project status (2026-11-11):** production, version `2.0.0` (see `VERSION`). Everything is free-tier: GitHub Actions + Pages, Cloudflare (DNS/CDN, Workers, Web Analytics), Meta developer app, ntfy.

> **Data is king.** Every price carries its **source grade** and its **real age**. Where a source gives no timestamp we say
> "price time unknown" instead of faking freshness. Estimates (grade D) are always labelled as estimates, in the app and in posts.

## What it does

| Area | What | Where |
|---|---|---|
| **Data pipeline** | Scrapes official and third-party feeds about every 15 minutes, validates, merges sources per station, keeps last-known-good data, publishes static JSON | `src/main.py`, `src/scrapers/`, `src/merge_engine.py`, `.github/workflows/scrape.yml` |
| **Web app (PWA)** | Price map with grade/age badges, per-country lists, favourites, tank-size fill cost, share links/pictures, navigation hand-off, route planner (cheapest pumps along a route), border-run and road-trip calculators, My car (fuel, electric, plug-in hybrid), EV charging posts, install nudge, 5 languages, light/dark | `web/index.html`, `web/sw.js` |
| **SEO pages** | Static town pages for SE, AT, DE, CH, FR, ES, PT, DK, NL (+ Swedish cheapest-towns ranking), sitemaps, JSON-LD | `src/seo_pages.py` |
| **Europe index** | Country ranking (petrol/diesel, 7-day change), 37 border-pair pages with share pictures, translated index (sv/de/da), open data (JSON/CSV), free widget | `src/europe_index.py`, `web/widget.html`, `web/embed.html` |
| **Search engines** | Sitemaps in Google Search Console and Bing Webmaster Tools, daily IndexNow ping | `src/indexnow.py`, `web/<key>.txt` |
| **Facebook routine** | One post a day + hourly replies to "comment your town", from the Page itself, running on GitHub Actions | `.github/workflows/facebook.yml`, `tools/fb_*.py` |
| **Reliability** | Stale-data alarm (Cloudflare Worker → phone notification), health report, regression guards | `worker/watchdog/`, `health.json` |

## Documentation map

Start here, then follow the links. A complete index of all documents is in [docs/INDEX.md](docs/INDEX.md).

| Read this | When |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the system works: components, data flow, file formats, repository map |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Running it: schedules, secrets, accounts, monitoring, runbook for common failures |
| [docs/GROWTH.md](docs/GROWTH.md) | The traffic strategy, what is automated, what is still manual, KPIs |
| [docs/facebook/GRAPH_API_SETUP.md](docs/facebook/GRAPH_API_SETUP.md) | Facebook automation setup (done) and how to repeat it |
| [docs/PERMISSIONS.md](docs/PERMISSIONS.md), [docs/REGULATORY_REPORTING.md](docs/REGULATORY_REPORTING.md) | Which sources may be reused and which governments force price reporting |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Product, data and monetisation roadmap |

## Source grades

| Grade | Meaning | Examples |
|---|---|---|
| **A** | Official feed; stations are legally obliged to report price changes | France, Spain, Portugal, Austria |
| **B** | Official feed, daily/periodic or regulated prices | Italy (daily CSV) |
| **C** | Third-party aggregator (ANWB/xavvy/Appitup), **no price timestamps**, unofficial | NL, BE, PL, CZ, GB, IE, DE, CH … |
| **D** | Community-reported estimates | Sweden (bensinpriser.nu), Finland (Hintatutka.net), Iceland |
| **L** | Locations only | Norway (partly), Kosovo |

Germany uses the ANWB baseline (grade C) until an official MTS-K source is available (see [docs/GERMANY_SOURCE_DECISION_2026-11-06.md](docs/GERMANY_SOURCE_DECISION_2026-11-06.md)).
Sweden and Norway: authorities discourage chains from publishing list prices, so there is no official feed; Sweden relies on crowd data on top of an
OpenStreetMap location backbone.

## Reliability design

* **Last known good:** a failing, empty or suddenly-shrunk source never overwrites good data; the previous file is kept and marked
  `status: "stale"` with `stale_since` and the error.
* **Validation:** per-currency price bands, coordinate sanity, duplicate-id removal, no timestamps from the future, implausible-price flags.
* **Honest timestamps:** `updated_at` = the source's time, or `null`. `fetched_at` = when we really fetched.
* **Merging:** per-price `source`, `alt` and `disagree` fields; newer timestamp wins, otherwise source priority; regulated maximum prices only fill gaps and are never ranked.
* **Cadence:** GitHub's cron is best-effort, so the scrape workflow **re-dispatches itself ~12 minutes after each run**; each source has its own refresh interval.
* **Alarm:** a Cloudflare Worker reads `meta.json` every 30 minutes and pushes a phone notification (ntfy) when prices stop updating.
* **Health report:** `health.json` (per source) and `meta.json` (per country, incl. `stats_eur` medians used by the Europe index and posts).

## Quick start (local)

```bash
pip install -r requirements.txt
python src/main.py                      # fetch + publish into data/ (needs network; some sources need API keys)
python src/seo_pages.py                 # build town pages + sitemaps from data/
python src/europe_index.py              # build /europe/ pages, share pictures, open data (needs data/meta.json)
# serve data/ and web/ together (copy web/* into data/), e.g.:  python -m http.server -d data 8000
```

Full CI-equivalent test run:

```bash
cd src && python -m unittest discover -s tests -q            # 190+ Python tests, no network
cd .. && node tools/check_page_syntax.js && for f in tools/test_*.js; do node "$f"; done
node tools/check_fares.js && node tools/check_ac_tariffs.js && node tools/check_data_versions.js
```

`web/vehicles.json` and `web/fares.json` are fetched as `?v=<N>` and cached by the service worker: after editing one, run
`node tools/check_data_versions.js --fix` to bump the version.

## Configuration (GitHub → Settings → Secrets and variables → Actions)

| Name | Kind | Used for |
|---|---|---|
| `FB_PAGE_ID`, `FB_PAGE_TOKEN` | secrets | Facebook routine (Page access token; see GRAPH_API_SETUP) |
| `GOON_API_KEY` | secret | Denmark (Go'on) prices |
| `OCM_API_KEY`, `NOBIL_API_KEY` | secrets | EV charging data |
| `TANKERKOENIG_API_KEY` + `TANKERKOENIG_MODE` (`off`/`test`/`commercial`) | secret + variable | Optional German upgrade, off by default |
| `ROMANIA_SOURCE` (`peco`/`official`/`both`) | variable | Romanian source ([docs/ROMANIA_SETUP.md](docs/ROMANIA_SETUP.md)) |
| `NTFY_TOPIC` | Cloudflare Worker secret | Stale-data alarm topic (random, acts as password) |

Never commit keys or tokens. The Facebook token is only ever stored as a GitHub secret.

## Data format

`data/meta.json` is the index; each country has `data/{cc}.json`:

```json
{
  "meta": { "country": "FR", "currency": "EUR", "source": "data.economie.gouv.fr", "grade": "A",
            "status": "ok", "fetched_at": "…", "station_count": 9358, "priced_count": 9358,
            "with_timestamp_pct": 100.0, "newest_price_at": "…" },
  "stations": [ { "id": "fr_…", "name": "…", "brand": "…", "city": "…", "lat": 48.18, "lon": 3.31, "source": "…",
                  "prices": [ { "fuel_type": "DIESEL", "price": 2.429, "currency": "EUR", "unit": "L",
                                "updated_at": "2026-09-28T11:45:27+00:00" } ] } ]
}
```

More formats (health.json, index_history.json, open-data files): [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#data-formats).

## Sources and permissions

Status per source (granted, pending, open) is in [docs/PERMISSIONS.md](docs/PERMISSIONS.md). Permission granted by the owners on 2026-11-07:
Hintatutka.net (Finland, keep the attribution "Hintatutka.net") and the unofficial ANWB feed. The open data published under `/open-data/` contains
country medians only and is "free to reuse with a link"; no formal licence has been chosen.

## Known limitations

- The unofficial ANWB feed (many countries, incl. DE) can change without notice and has no price timestamps. It is grade C everywhere.
- Sweden's prices are community estimates (grade D, ~20% of stations). They are shown and posted as estimates.
- Cloudflare may serve a stale copy of `sw.js` for hours after a deploy (a purge needs a Cloudflare token); pages and data are unaffected.
- Facebook reply-reading depends on Meta's permission rules for apps in Development mode (see GRAPH_API_SETUP).
- Licence: **not yet chosen (all rights reserved until then).** There is no LICENSE file.

## Roadmap (summary — details in [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/GROWTH.md](docs/GROWTH.md))

- [x] Honest timestamps, last-known-good, validation, health report, 15-minute cadence, stale-data alarm
- [x] Multi-source merge with provenance; route planner with Cloudflare routing proxy; My car and EV charging
- [x] Programmatic SEO (nine countries), Europe index, border pages, share pictures, open data, widget, Search Console + Bing + IndexNow
- [x] Facebook Page with autonomous daily post and opt-in local replies (GitHub Actions)
- [ ] Price-drop alerts (needs a Cloudflare Worker with Web Push), weekly short video, more town-page countries (BE, PL, IT)
- [ ] Official German source (MTS-K / Tankerkönig), UK Fuel Finder, Spain relay, Romania official API
- [ ] Licence register per source and a formal licence for the open data; monetisation only after the licence gates ([docs/ROADMAP.md](docs/ROADMAP.md))
