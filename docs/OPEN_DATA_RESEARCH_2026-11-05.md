# Open data research, 2026-11-05

Read-only research for EuroFuelPrices. Method: public web pages and plain GET requests only. No POST to government APIs, no account creation, no e-mails, `carburanti.mise.gov.it/ospzApi` not called. Dates are the date checked (2026-11-05). Confidence: H = confirmed first-hand today, M = from a reasonably reliable secondary source, L = unverified or inferred.

## Recommended actions

| # | Who | Action | Why |
|---|-----|--------|-----|
| 1 | Owner | Retry the Tankerkönig key at onboarding.tankerkoenig.de (it showed a maintenance notice today). If it stays closed, e-mail info@tankerkoenig.de and ask politely for a key for a free, non-commercial map. | Registration was closed for maintenance on 2026-11-05. Turnaround is not documented. |
| 2 | Owner | Register for UK Fuel Finder: GOV.UK One Login, then the developer portal "Start now" at gov.uk/guidance/access-the-latest-fuel-prices-and-forecourt-data-via-api-or-email. About 10 minutes. | Individuals are listed as eligible users. Free. |
| 3 | Claude | Italy: do not add new scraping. Keep status "stale" with honest provenance. Prepare a small EU relay design (Cloudflare Worker is NOT sufficient, see B) only if the owner wants Italy back. | mimit.gov.it does not answer from the owner's Swedish network either, so it is not only a GitHub-runner problem. |
| 4 | Claude | Romania: re-probe with the working GET actions (catalog endpoints answer 200 today) and find the price-listing request format from the official site's network calls. | The 500 "Error mapping types" was not reproduced on any endpoint tested today. |
| 5 | Owner | Sweden petrol 95: send more pump photos (brand, station, slot price) so the ANWB slot mapping can be decided on evidence. No new legitimate public source exists. | See E. |
| 6 | Claude | Later PHEV feature: evaluate NOBIL (Nordic charging database) for charger locations. Check whether it carries prices before committing. | See F. |

## A. Germany

**A1. Tankerkönig key process (checked 2026-11-05, M/H)**
- Source: https://creativecommons.tankerkoenig.de/ (fetched today). Keys are requested at onboarding.tankerkoenig.de. Today the page said registration is temporarily unavailable due to maintenance (H, for today only).
- A working e-mail address is required. Whether a postal address is needed is unclear: one app description says name plus e-mail only; one unreliable page says a German postal address (L). The key is activated manually by the user via a link, which accepts the terms (https://onboarding.tankerkoenig.de/static/img/AGB-Tankerkoenig.pdf).
- Turnaround: not documented anywhere I could find (L). Forum reports mention confirmation e-mails landing in spam, and a key outage in June 2026 (ioBroker forum, M).
- Rate limit per the site: one request per minute for the free API; at most 10 station IDs per prices call; nearby search radius at most 25 km; apps and sites should call on user action, not on a schedule; mass retrieval is blocked and may deactivate the key; bulk needs are a paid service. Live data is CC BY 4.0 per the page, with attribution, and the page says results may not be filtered unless the user asks (M/H).
- Consequence: the live API is not designed for crawling all ~14k stations from a scheduled job. It fits per-user, on-demand lookups, which a static map does not do. This reduces its value for us.

**A2. Alternatives, ranked for a non-commercial free map**
1. Keep ANWB (about 14.8k German stations today). Zero effort, already in the pipeline. Gap: provenance and lag are those of ANWB.
2. Tankerkönig history data. Per the site, daily CSV files since 2014 in a git repository hosted by Tankerkönig (third-party sources name `dev.azure.com/tankerkoenig/_git/tankerkoenig-data`, layout `year/month/year-month-day-prices.csv` plus `stations.csv`; I could not fetch it, L). Access requires a verified account at onboarding.tankerkoenig.de; if already registered, ask info@tankerkoenig.de (H, from the site text). Licence for history: CC BY-NC-SA 4.0, fits a non-commercial map but share-alike applies to derived datasets. Lag: daily, so at best a day behind, which is fine as a cross-check but not as live price. A GitHub Action could only fetch it with credentials, and committing a key to the repo is not allowed by their terms, so it would need a GitHub secret (their terms say keys must not be published). Effort: medium.
3. Bundeskartellamt MTS-K approval as "Anbieter von Verbraucher-Informationsdiensten" (§ 6 MTSKraftV; https://www.gesetze-im-internet.de/mtskraftv/__6.html). Application online or informally in writing; approval if the applicant credibly shows the data is used to inform consumers about current nationwide fuel prices, plus a second condition I could not read. Approved providers receive data at least every minute via a standard interface (M). Turnaround and fees: unknown (L). Highest quality, but heavy for a hobby project and legal obligations follow. Effort: high.
4. Other German open sources: none found that are both station-level and licence-clean. Not exhaustively searched (L).

## B. Italy

- Checked 2026-11-05 from the owner's Windows machine (Sweden): `https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv`, `.../anagrafica_impianti_attivi.csv` and the site root all time out on connect after about 21 s (H). DNS resolves www.mimit.gov.it to 81.126.92.6, and the WebFetch tool also got "connection refused" for mimit.gov.it pages. So the host does not answer from at least two non-Italian vantage points (H). I did not test from an Italian IP, so geo-blocking versus plain outage is unproven (L).
- I found no announcement of a new URL, geo-block or rate limit (searches returned nothing relevant). The only documented change is the pipe separator since 2026-02-10 (M, from MIMIT notes).
- Official dataset pages (could not be fetched today, titles from search): "Carburanti - prezzi praticati e anagrafica degli impianti" (licence IODL 2.0, experimental) and "Carburanti - archivio prezzi" (quarterly tar.gz archives, M). Metadata PDF: https://www.mimit.gov.it/images/stories/documenti/Metadati_prezzi_carburanti_20260128.pdf. I did not find a separate dati.gov.it entry (L). Archives are quarterly, so too slow for live prices.
- Alternatives: the Osservaprezzi app API is excluded by the owner's instruction. Regional sources: not researched in depth (L).
- What works from GitHub runners: nothing confirmed, since the host itself is not reachable. What would work: an EU or Italian relay. A Cloudflare Worker is a poor fit (it runs on Cloudflare's network, no region guarantee, and CSVs are large). A small EU VPS (cron that downloads, then serves or pushes a compressed file) is the realistic option. Effort: about half a day, plus a monthly cost and upkeep. First check from an Italian-region VPS whether the host answers at all.

## C. Romania

- Checked 2026-11-05 with GET only against `https://monitorulpreturilor.info/pmonsvc/Gas/` (H):
  - Bare `/Gas/` returns an ASP.NET "multiple actions match" error (this is a routing error, not a data error).
  - `GetGasNetworks`, `GetGasProductsFromCatalog`, `GetGasServicesFromCatalog`, `GetUATByName?uatname=Cluj`: HTTP 200 with XML.
  - `GetGasProductsByCatId?CatId=11`: HTTP 200, 47 products, but all `Price` fields are 0 (a product catalogue, not station prices).
  - Guessed names (`GetGasItems`, `GetGasStationsByUat`, `GetGasItemsByUat`) gave 404.
- "Error mapping types" 500 was not seen today. The actual station-price action name and parameters are not documented, and `GetGasItemsByUat` exists in some form (its 404 says "no action matches the request", not "no such name", which suggests it needs different parameters) (L). Station-level price listings may need a POST or other parameters, which I did not attempt. The scraper in the repo currently uses peco-online.ro, not this host.

## D. UK Fuel Finder

Sources: https://www.gov.uk/guidance/access-the-latest-fuel-prices-and-forecourt-data-via-api-or-email and https://www.gov.uk/guidance/fuel-finder/signing-up (fetched today, M/H).
1. Eligible users listed: comparison sites, app and website developers, academics, journalists and individuals, so a hobby site qualifies (H).
2. Create a GOV.UK One Login (e-mail plus a mobile number or authenticator app). It can be created on first use of the service.
3. Click "Start now" on the guidance page to reach the developer portal, then create an application to get a client ID and secret. The API uses OAuth 2.0 client credentials and GET requests with JSON (H for the OAuth statement; the application step comes from a community post, M).
4. No-key alternative: a CSV download updated twice a day, or an e-mail subscription with a link to the latest CSV (H). This may be the fastest route for a scheduled GitHub Action (L, not tested).
- Turnaround, rate limits and non-commercial terms: not stated on the public pages (L). One forum user reported a 403 until the account was approved (M). The note about a letter with an activation code applies to price reporters (retailers), not to data users.
- Licence: the gov.uk page footer says content is under OGL v3.0, but this is not a specific statement about the fuel data (M). Please confirm in the portal terms, and keep attribution.
- Does not cover EV charging or LPG.

## E. Sweden

- Konkurrensverket accepted commitments (decision file 23-0382, 2024) from Circle K, OKQ8 and Preem: they stop publishing recommended prices for private customers and delay business list prices. https://www.konkurrensverket.se/en/news/commitments-from-fuel-companies-improve-conditions-for-price-competition/ (M). Sources differ slightly on "stop" versus "postpone" for list prices.
- I found no official or open per-station petrol 95 source in Sweden (no public API, no "bensinpriskollen"-type official service found; L for completeness). Aggregators such as fuel-prices.eu claim "official open data" for Sweden but I could not verify what their Swedish source is, so do not rely on or copy them (L).
- Honest conclusion: nothing additional and legitimate is known. Best next step is ground truth. Measure ANWB slot behaviour against pump prices rather than changing the mapping now. A neutral note in the UI that petrol 95 is missing or uncertain at some stations is better than guessing.

## F. Plug-in hybrid: EV charging data (max 5)

1. NOBIL (Nordic charging database, Energimyndigheten responsible for Sweden): station locations through an API; licence reported as CC BY 4.0 (OSM page says CC BY 3.0, older); API access and whether prices are included are unverified. Effort: low to evaluate. (M/L)
2. Open Charge Map (https://openchargemap.org): open, crowd-sourced locations, API key needed, licence per record (mostly CC BY 4.0). Prices are inconsistent. Effort: low. (M)
3. OpenStreetMap `amenity=charging_station`: ODbL, locations and sometimes `fee` or `charge` tags, no live prices. Effort: low via Overpass. (M)
4. Operator price pages (Ionity, Mer, Recharge and others): prices are tariff pages, not open data, and scraping terms are unchecked. Effort: manual. (L)
5. Nothing confirmed that offers a live open per-charger price feed for Sweden or the Nordics. A "charge versus petrol" feature would realistically use a user-entered tariff. (L)

## Not verified

Tankerkönig key turnaround; Tankerkönig git repository contents; MTS-K fees and second approval condition; Fuel Finder approval time, rate limits and data licence; whether mimit.gov.it blocks non-Italian IPs; Romanian price endpoint format; NOBIL price data. No source was copied beyond short facts.
