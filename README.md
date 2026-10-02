# EuroFuelPrices

Live fuel prices at every station across **Europe + EEA** — 42 countries/territories, 100,000+ stations, mobile-first PWA, Sweden-first.
A GitHub Actions job scrapes official and third-party feeds about every 15 minutes and publishes static JSON to GitHub Pages.

**Live map:** `https://eurofuelprices.com/` (custom domain; also reachable at `https://thorstengru.github.io/nordic-fuel-prices/` during DNS cutover)
**Data health dashboard:** `https://eurofuelprices.com/admin.html` (per-country status, source grade, real price age)

> **Data is king.** Every price carries its **source grade** and its **real age**. Where a source gives no timestamp we say
> "price time unknown" instead of faking freshness. See the research behind the choices:
> [docs/REGULATORY_REPORTING.md](docs/REGULATORY_REPORTING.md) (which governments force stations to report prices, and how fast),
> [docs/COMPETITORS.md](docs/COMPETITORS.md), [docs/ROADMAP.md](docs/ROADMAP.md) (incl. monetization).

---

## Source grades

| Grade | Meaning | Examples |
|---|---|---|
| **A** | Official feed; stations are legally obliged to report price changes (minutes–hours) | France, Spain, Portugal, Austria, Germany (with Tankerkönig key) |
| **B** | Official feed, daily/periodic or regulated prices | Italy (daily CSV) |
| **C** | Third-party aggregator (ANWB/xavvy/Appitup), **no price timestamps**, unofficial | NL, BE, PL, CZ, GB, IE, … (and DE/ES fallback) |
| **D** | Community-reported | Sweden (bensinpriser.nu), Finland, Iceland |
| **L** | Locations only | Norway, Kosovo (no legitimate price source) |

Sweden and Norway: authorities discourage/ban chains from publishing list prices, so there is no official feed; Sweden relies on crowd
data (~20 % of stations) on top of an OpenStreetMap location backbone.

## Reliability design

* **Last known good:** a failing, empty or suddenly-shrunk source never overwrites good data; the previous file is kept and marked
  `status: "stale"` with `stale_since` and the error (shown in the app and on the dashboard).
* **Validation:** per-currency price bands, coordinate sanity, duplicate-id removal, no timestamps from the future.
* **Honest timestamps:** `updated_at` = the source's time, or `null`. `fetched_at` = when we really fetched.
* **Cadence:** GitHub's `cron` is best-effort (median gap measured: 262 min), so the workflow **re-dispatches itself ~12 min after each run**;
  each source has its own refresh interval (`REFRESH_MINUTES`) to stay polite towards upstream APIs.
* **Health report:** `health.json` (per-source status, counts, newest price, errors) and `meta.json` (index used by the app).

## Setup

1. Fork/clone, enable **Settings → Pages → Deploy from branch → gh-pages**.
2. **Germany (statutory MTS-K, 5-minute reporting duty):** register a free key at <https://onboarding.tankerkoenig.de>, add it as
   repository secret `TANKERKOENIG_API_KEY`. Without it Germany uses the ANWB fallback (~14.9k stations, grade C).
3. Run **Actions → EuroFuelPrices — Scrape → Run workflow** once; it then keeps itself running.
4. Local: `pip install -r requirements.txt && python src/main.py` (writes `data/`), serve `data/` + `web/` together.

## Roadmap (summary — details and numbers in [docs/ROADMAP.md](docs/ROADMAP.md))

**Data**
- [x] Honest timestamps, last-known-good, validation, health report, 15-minute cadence
- [x] Sweden parser fixed (crowd prices), Germany/Spain via tiled ANWB, France/Portugal/Italy real timestamps, UK/IE interim
- [ ] Tankerkönig key (DE grade A), UK Fuel Finder registration (30-min statutory feed), Spain relay (MINETUR blocks GitHub IPs)
- [ ] Denmark statutory operator APIs (real-time since 2026-01-01), Lithuania LEA, Romania monitorulpreturilor, Greece ministry feed
- [ ] EU Weekly Oil Bulletin as independent price-sanity validator; monthly OSM snapshot per country as location backbone
- [ ] Licence register per country (gate monetization per source)

**Product (from competitor teardown)** — freshness/grade badges ✔, then: SEO city & station pages, price alerts, price history, cross-border comparison, offline last-known data.

**Monetization (phased, Sweden first; all figures are assumptions in the roadmap)**
1. *Phase 0 — trust & growth:* fix data, badges, SEO pages, move serving to Cloudflare Pages (GitHub Pages ToS forbids commercial use).
2. *Phase 1 — light monetization:* affiliate module (EV charging, fuel card, insurance, roadside) and one labelled, non-personalised ad slot behind a certified CMP.
3. *Phase 2 — premium (~€9.99/yr):* price alerts, history, trip planner, ad-free. Never paywall what is free today.
4. *Phase 3 — B2B:* normalised price API/history for fleets, insurers, media; sponsored stations (labelled, kept out of ranking); white-label widgets.
5. **Licence gates:** the unofficial ANWB feed, Portuguese prices and the Swedish bensinpriser proxy must be licensed or replaced before any monetization on them.

## Data format

`data/meta.json` index → `data/{cc}.json` per country:

```json
{
  "meta": { "country": "FR", "currency": "EUR", "source": "data.economie.gouv.fr", "grade": "A",
            "status": "ok", "fetched_at": "…", "station_count": 9358, "priced_count": 9358,
            "with_timestamp_pct": 100.0, "newest_price_at": "…" },
  "stations": [ { "id": "fr_…", "name": "…", "lat": 48.18, "lon": 3.31, "source": "…",
                  "prices": [ { "fuel_type": "DIESEL", "price": 2.429, "currency": "EUR", "unit": "L",
                                "updated_at": "2026-09-28T11:45:27+00:00" } ] } ]
}
```
