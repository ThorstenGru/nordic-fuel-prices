# Italy: why the feed is stale and what to do (2026-11-06)

Read-only research. GET/HEAD only, no credentials, no accounts, `carburanti.mise.gov.it/ospzApi` not called with POST (one bare GET to `/ospzApi/` returned HTTP 500, 122 bytes, nothing more). Tests ran from the owner's Windows machine in Sweden on 2026-11-06. "Opened" = I fetched it myself today. "Search" = seen only in a web-search snippet. Confidence: H = confirmed first-hand, M = reliable secondary, L = inferred.

## 1. Diagnosis: not a URL change, not a total outage, most likely an access block

| Check | Result | Opened | Conf |
|---|---|---|---|
| `https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv`, `anagrafica_impianti_attivi.csv`, bare `mimit.gov.it`, site root, dataset page | TCP connect timeout after 20 s on every URL, both ports 80 and 443 | yes | H |
| DNS (system, 8.8.8.8, 1.1.1.1) | www.mimit.gov.it = 81.126.92.6 everywhere | yes | H |
| Ping and tracert to 81.126.92.6 | 100 % loss; trace dies after 12 hops at 185.100.113.148 | yes | H |
| Forced IP with `--resolve` | same timeout | yes | H |
| WebFetch tool (a different, non-Swedish network) | `ECONNREFUSED 81.126.92.6:443` (active refusal, not a timeout) | yes | H |
| Wayback CDX for the price CSV: https://web.archive.org/cdx/search/cdx?url=mimit.gov.it/images/exportCSV/prezzo_alle_8.csv | daily 200-snapshots 2026-09-30 to 2026-10-16, then none. Last file I read (range request) begins `Estrazione del 2026-10-14` and pipe-separated `idImpianto\|descCarburante\|prezzo\|isSelf\|dtComu` | yes | H |
| Data is still being published: https://raw.githubusercontent.com/agapitosantangelo/carburanti/main/stato.json | `estrazione 2026-11-04`, 20,777 stations, run 2026-11-05 09:00 Rome time | yes | H (that the file exists), L (how that person gets it) |
| Data is still being published: https://www.fuel-prices.eu/live/italy/?format=json | 17,841 stations, 43,109 prices, collected 2026-11-05T10:25+02:00, source "Osservaprezzi Carburanti (MIMIT)" | yes | H |
| A GitHub-runner plus Cloudflare Worker proxy does NOT get through: https://raw.githubusercontent.com/rumentopoli-tech/mimit-carburanti-cache/main/data/prezzi_italia.json | holds a single "Placeholder ... Download MIMIT fallito" record dated 2026-11-05, though its Actions run reports success | yes | H |
| Render-hosted app https://prezzi-carburante.onrender.com/api/stato | `{"pronto":false,"impianti":0}` on two calls | yes | M (could be cold start or its own bug) |
| Official web app https://carburanti.mise.gov.it/ospzSearch/ | HTTP 200 from Sweden (Angular shell). The hostname `carburanti.mise.gov.it` is a different host and is reachable | yes | H |

Reading: the host `www.mimit.gov.it` has dropped traffic from Sweden, from the WebFetch network, from GitHub runners and from a Cloudflare egress since about 2026-10-15/16, while the same data is demonstrably still published and reachable by at least two third parties. The most likely cause is filtering of non-Italian and/or datacentre address ranges (L: I cannot prove it without an Italian IP). It is not a path change, because the site root also fails. It is not a general outage, because other collectors have an extraction dated 2026-11-04. `Wayback`'s own crawler stopping on 2026-10-16 fits the same pattern.

Consequence: tweaking `src/scrapers/italy.py` cannot fix this. The scraper code is fine (pipe format, `Estrazione` header line and `isSelf` handling match the 2026-10-14 file). The network path is the problem.

## 2. Realtime reality check

The official open-data CSV is a daily snapshot ("prices at 08:00", published once a day; metadata PDF https://www.mimit.gov.it/images/stories/documenti/Metadati_prezzi_carburanti_20260128.pdf, search only, M). Every Italian collector found is daily. Nobody offers a free per-change feed. Closest to realtime is the web app's own JSON API (`ospzApi`), which the owner has excluded and which I did not call. So the best achievable realistic target is: official data, refreshed once each morning, about 1 day behind. I found no source that is better than that and also free.

## 3. Options

| # | Option | Freshness | Quality | Licence | Cost | Effort | Risk |
|---|---|---|---|---|---|---|---|
| A | Official CSV fetched by a small relay with an Italian IP, result pushed to a private/public GitHub release or served as a gzip file; pipeline reads the relay | daily (08:00 snapshot, fetch after about 09:00 Rome) | Grade B, same as today (about 20k stations) | IODL 2.0, attribution to MIMIT (M, from https://www.fuel-prices.eu/sources/ and a search summary; verify text at dati.gov.it/iodl/2.0) | small Italian VPS, order of 3 to 6 EUR/month (estimate, not verified) | about half a day plus a 1-day test from an Italian IP first | if the block is by "datacentre" rather than country, an Italian VPS may still be refused; test before paying for a year |
| B | Same as A, but run on a residential Italian connection (a friend or relative with a Raspberry Pi, cron at 09:15) | daily | Grade B | IODL 2.0 | 0 | about 2 hours, plus a person | depends on one person and one router |
| C | fuel-prices.eu as upstream: https://www.fuel-prices.eu/live/italy/ (17,841 stations, daily, per-locality pages with `?format=json` and `?format=md`) | daily (collected about 10:25 Rome) | derivative of MIMIT, grade C | their aggregation is CC BY 4.0 (https://www.fuel-prices.eu/robots.txt, opened); the page also tells users to check MIMIT terms before redistributing raw data. Their `/export/` and `/live/_cache/` are disallowed in robots.txt, so no bulk scraping. Contact: hi@fuel-prices.eu (from their JSON-LD) | 0 for browsing, "custom bundles" quoted on request | ask first; about 1 day if they agree to a station-level feed | one-person site, no SLA, relies on the same upstream |
| D | Third-party hobby caches (agapitosantangelo, rumentopoli, dstmrk Render app) | daily at best | aggregates or broken (see section 1) | none stated for data | 0 | n/a | not suitable as a source; agapito publishes province aggregates only (`carburanti_province.csv`), the others do not deliver station data |
| E | Official archive (quarterly tar.gz, https://www.mimit.gov.it/index.php/it/open-data/elenco-dataset/carburanti-archivio-prezzi, search only) | quarterly | high, but old | IODL 2.0 | 0 | n/a | same host, same block; useless for live |
| F | Regional or municipal open data via dati.gov.it CKAN (opened: https://www.dati.gov.it/opendata/api/3/action/package_search?q=prezzi+carburanti+regione) | none are live price feeds | station registers (Milano, Piemonte, Campania, FVG, Emilia-Romagna, Lazio) and a Piemonte price file dated 31 Dec 2018 | mixed CC BY / IODL | 0 | n/a | no value for current prices; could only help with station coordinates |
| G | Official app API `ospzApi` | the freshest available (stations update on change) | best | not an open-data licence; owner excluded it | 0 | n/a | excluded, not tested |
| H | Commercial feeds (e.g. fleet or telematics providers; Quartix and Telepass pages appear in search results as consumers of MIMIT data) | unknown | unknown | commercial | unknown | n/a | not evaluated; I would not pay for a repackaged copy of free data |
| I | Keep status quo: Italy shown as stale with honest provenance | none | n/a | n/a | 0 | 0 | map shows 3-week-old prices, which erodes trust |

## 4. Recommendation (realtime + high quality, within what exists)

1. Do A or B, because they restore the official source (best quality, daily, the only licence-clean way that keeps the existing parser). Start with a 1-day test: run `curl -I https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv` from an Italian-region cloud trial or an Italian friend's connection. If it answers there, the block is geographic and A or B works. If it fails there too, it is an outage or a block on everyone with the exception of unknown allow-listed collectors, and the next step is to write to MIMIT (below).
2. In parallel, ask MIMIT politely whether non-Italian access is restricted on purpose and whether there is a supported route (an e-mail to the open-data contact named on https://www.mimit.gov.it/it/open-data/, which I could not open from here). The map is free and non-commercial, which is the situation open-data licences are meant for.
3. Until the relay exists, do not copy C or D into the pipeline. If a stop-gap is wanted, e-mail fuel-prices.eu first and show the data as grade C with their attribution.
4. Realistic expectation to tell users: Italy is a daily snapshot at best, about one day old. Do not label it "live".

## 5. What the owner must decide

1. Budget: is about 3 to 6 EUR/month (estimate) for an Italian VPS acceptable, or do you prefer a free Italian-IP volunteer (option B)?
2. Who asks: do you send the polite e-mail to MIMIT and the one to hi@fuel-prices.eu, or shall I draft both in English and Italian for you to send?
3. Public or private relay output: the CSV is open data (IODL 2.0), so a public GitHub release is fine, but you decide.
4. Meanwhile, should the map hide Italy or keep it with a "data from 2026-10-14, source unavailable" notice?

## 6. Not checked

Whether any Italian IP actually gets through (no Italian vantage point available); the exact IODL 2.0 text (not opened); the MIMIT open-data contact address; the `ospzApi` behaviour (excluded); VPS prices (estimate); the Cloudflare Worker `mimit-proxy.rumentopoli.workers.dev` (a third party's endpoint, deliberately not used).
