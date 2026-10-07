# EV charging and alternative energies in EuroFuelPrices: research (2026-10-07)

Legend: [V] = verified by fetching an endpoint today; [D] = from docs or search results only; [?] = unverified or conflicting.

## 1. Recommendation

**Phased, with a hard stop after Phase 1.**
1. Do NOT build a general EV charger map. It is a crowded, solved problem (Google/Apple Maps, PlugShare, Zap-Map, ABRP), and the one thing a fuel-price app could add, live charging PRICES, is not reliably available in open data.
2. Do build a small "cost per 100 km: petrol / diesel / EV (home vs public)" comparison on the existing country data. It is cheap (S), honest and differentiating.
3. Optionally add a country-tiled "fast chargers" layer later, static locations only, with no availability or price claims.
4. Keep and extend the alt-fuel filters (LPG, CNG, E85, HVO100, hydrogen) where your existing sources already carry them.
5. Biggest reason: location data is free, but price and live-status data are the product, and those are patchy. Shipping a map that implies "live" would break your honesty rule.

## 2. User value

New-car and car-parc facts:
- EU 2025: BEV 17.4% of new registrations, hybrids 34.5%, petrol+diesel 35.5% ([ACEA via newmobility.news](https://newmobility.news/2026/01/27/eu-car-registrations-up-1-8-in-2025-bev-market-share-grew-to-17-4/)) [D].
- Norway 2025: BEV 95.9% of new cars ([electrive](https://www.electrive.com/2026/01/03/battery-electric-cars-dominate-norway-and-its-fleets)) [D].
- Sweden 2025: BEV 36.5%, plug-ins (BEV+PHEV) about 61% ([EAFO](https://alternative-fuels-observatory.ec.europa.eu/general-information/news/sweden-reaches-15-ev-car-fleet-2025), search summary) [D][?]. Sweden's EV fleet reached about 15% in 2025 per EAFO's headline [D].
- Germany: 1 Jan 2026 fleet of 49.5M cars, 2.0M BEV (about 4.1%) and 1.12M PHEV (about 2.3%) ([electrive](https://www.electrive.com/2026/02/27/germany-tops-two-million-battery-electric-cars-in-circulation/)) [D].
- NL, FR, GB: EU-level growth confirmed (DE +43%, NL +18%, FR +12.5% BEV registrations in 2025). I did not retrieve exact per-country shares [?].

**Implication:** the parc is still 85-95% ICE or hybrid in every big market except Norway. Petrol and diesel drivers remain the core audience for 5+ years. Norway is a special case where a fuel-price app has a shrinking audience anyway.

Do EV drivers use fuel-price apps? I found no data. Assume mostly no, except households with a mixed fleet, PHEV owners and drivers still deciding what to buy. [?]

Existing competitors: PlugShare, Chargemap, Zap-Map, Google/Apple Maps (live status via partners), ABRP (route planning with charging). Chargemap and ChargePrice already target price transparency. A newcomer on location data alone has no edge.

Real angles for you:
- Cost per 100 km comparison, which neither fuel apps nor charging apps show side by side.
- Mixed-fleet and PHEV households.
- "Should I switch?" content, which is also SEO-friendly.

## 3. EV data sources

| Source | Coverage | Live vs static | Prices? | Licence | Key-free from Actions? |
|---|---|---|---|---|---|
| Open Charge Map | Global, aggregator | Mostly static, some status | Patchy, free text | Contributions CC BY 4.0, but imported records may carry their own terms ([OCM](https://www.openchargemap.org/about)) [D] | **No.** [V] unauthenticated request returned HTTP 403. API key needed. Free for non-profit/personal; commercial heavy use should contact OCM [D] |
| Germany, Bundesnetzagentur Ladesäulenregister | DE: about 156k normal + 55.7k fast points (1 Aug 2026) ([BNetzA](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/start.html)) [D] | Static, CSV (51 MB) updated roughly monthly, plus web service | No | CC BY 4.0 per OCM thread ([OCM community](https://community.openchargemap.org/t/open-data-government-sources-for-germany/120)) [D][?] | Yes, no registration [D] |
| France, data.gouv.fr IRVE | FR national consolidation | Static; a separate "dynamique" schema exists (availability and price in schema, but operator uptake unverified) | Schema allows it [D] | Licence Ouverte ([dataset API](https://www.data.gouv.fr/api/1/datasets/5448d3e0c751df01f85d0572/)) | **Yes** [V]: updated 2026-10-07, CSV 158 MB, GeoJSON 572 MB, no key |
| Norway/Sweden, NOBIL | NO, SE (dropped other countries) ([OCM forum](https://community.openchargemap.org/t/nobil-dropps-support-for-all-countries-except-sweden-and-norway/1788)) | Mostly static | Limited | CC BY 3.0, API key required ([OSM wiki](https://wiki.openstreetmap.org/wiki/Import/Catalogue/Nordic_Charging_Station_Import)) [D] | Key needed, free |
| NAPs under AFIR Art. 20 (Trafikverket SE, NDW NL, Mobilithek DE, etc.) | Mandatory since 14 Apr 2025: static and dynamic data via API ([Nationale Leitstelle](https://nationale-leitstelle.de/en/bestand-ausbau/afir/)) [D] | Both, in principle | In principle yes; in practice inconsistent (see below) | Varies by country; often registration needed | Varies; not verified per country |
| OpenStreetMap (`amenity=charging_station`) | Good in DE, NL, Nordics | Static | No | ODbL (share-alike, attribution) | Overpass is key-free but rate-limited. [V] attempt: HTTP 504 timeout today, so it is unreliable for CI. Geofabrik extracts are the safer route |
| EAFO (EU Observatory) | EU statistics: about 1.16-1.17M public points in the EU27, June to Sept 2026, partly preliminary ([EAFO](https://alternative-fuels-observatory.ec.europa.eu/general-information/news/eafo-data-update-news-flash-july-2026)) [D][?] | Statistics, not a station feed | No | EU reuse | Not a map source |
| Operator feeds (Tesla, Ionity, Fastned) | Per operator | Some live | Own prices | Mostly no open public feed [?] | Not recommended; scraping is a ToS risk |

Note: the brief's "~700k charge points" is outdated. EAFO reports about 1.16M public points in the EU27 alone, so the full-Europe dataset is larger still.

**State of price data (key finding):** AFIR Art. 5 requires price transparency at the point of use, and Art. 20 requires data via NAP. BEUC's 2026 report says availability is inconsistent across Member States, fragmented, and only a handful of countries (NL, BE, DE, FR partial) have meaningful price datasets ([BEUC](https://www.beuc.eu/sites/default/files/publications/BEUC-X-2026-073_EV_charging_prices_and_data_report.pdf), summarised by fetch tool [D][?]). The Commission started an AFIR review in March 2026, and Germany drafted heavy fines for incomplete price info ([electrive](https://www.electrive.net/2026/03/26/afir-vorgaben-gesetzentwurf-sieht-hohe-strafen-bei-unvollstaendigen-preisinformationen-vor/)) [D]. That tells you compliance is not there yet. A "cheapest charger nearby" feature would be built on sand in 2026. I did not verify the actual price-field fill rate in any NAP.

## 4. Other alternative fuels

- **Your existing sources:** I did not inspect the codebase. Per your project notes, the ANWB POI feed covers about 30 countries and national feeds cover the rest. Check which fuel types they expose (LPG, CNG, E85, HVO100, hydrogen). Action item for the owner or an implementer. [?]
- **Hydrogen:** EU27 had 303 active stations at end 2025: DE 128, FR 79, NL 50 ([UNEM via hydronews](https://www.hydronews.it/en/in-ue-active-303-hydrogen-supply-stations-unem-in-italy-only-3/?amp=1)) [D]. Germany closed 36 first-generation stations in 2025 as H2 Mobility pivots to trucks ([electrive](https://www.electrive.com/2025/03/03/h2-mobility-to-shut-down-22-hydrogen-fuel-stations-in-germany)) [D]. The H2-Stations platform (h2-stations.eu, launched May 2026) is the official EU source ([Clean Hydrogen JU](https://www.clean-hydrogen.europa.eu/media/news/h2-stations-platform-launched-strengthen-europes-hydrogen-refuelling-network-2026-05-20_en)) [D]. I did not verify its API or licence. h2.live is a private service whose terms I did not check, so do not scrape it. Hydrogen is tiny (about 300 stations) and shrinking for cars. It is fine as a filter on whatever data you already have, but not worth a dedicated integration.
- **LNG, CNG, biogas:** Not researched in depth. Likely available through national feeds or ANWB POI, and EAFO/NAP static data under AFIR. [?]
- **E85, HVO100, LPG:** Highest value for your existing audience (Sweden: E85 and HVO100 are mainstream). Prices for these are what a fuel-price app can truly add. Prioritise them over EV.

## 5. Options

| Option | Effort | Value | Risks |
|---|---|---|---|
| (a) Charger map layer | **L** (M if only DE+FR open CSV) | Low to medium: duplicates Google/Maps | 1M+ points. A country-tiled static JSON of about 5-10 MB gzipped per big country, loaded only when the layer is on, and restricted to fast chargers (≥50 kW, roughly 20-25% of points), keeps 4G usable. No prices, so a "price-free" map is a weak differentiator. The OCM key and NOBIL key add ops burden |
| (b) Cost per 100 km calculator | **S** | Medium to high, differentiating | Needs electricity prices: Eurostat household prices (EU open) for home charging, and a clearly labelled "public fast charging" assumption range. Label as estimate with date and source. No station-level claim |
| (c) Route planner integration | **L+** | Low | Competes with ABRP and Google; out of scope for solo, free-tier stack |
| (d) Do nothing on EV | none | Preserves focus | Opportunity cost is small given point 2 |

The charger layer design, if built: Python job in Actions, nightly or weekly rather than every 15 min (location data does not change quickly), writing `chargers/{cc}.json.gz` with `[lat, lon, kW, operator]`. The frontend fetches only when the toggle is on. Show "last updated" and the source. Do not show availability.

## 6. Legal and honesty constraints

- **OSM/ODbL:** share-alike on derived databases plus attribution. A derived charger dataset published on GitHub Pages would have to be offered under ODbL. Manageable but a real obligation. Prefer government sources (CC BY, Licence Ouverte) over OSM or OCM, which mixes licences.
- **CC BY / Licence Ouverte:** attribution only. Keep a `SOURCES` panel per country, as you do for fuel.
- **No availability promise:** never say "free now" or "working" unless the feed gives a timestamp under 15 min. Static feeds say "listed, not verified".
- **Prices:** only show tariff data if the feed gives it with a timestamp. Otherwise use clearly labelled estimates.
- **Sustainability for a solo maintainer:** every extra country adds a feed that can break (you already have RO failing). Cap at 3-5 open government feeds (DE, FR, NO/SE, NL) and treat anything else as out of scope.

## 7. Roadmap

- **Phase 1 (S, about 1-2 days):** Cost per 100 km calculator. Inputs: consumption l/100 km and kWh/100 km, current country fuel price from your data, electricity price from Eurostat (home) plus a public DC range. Output a labelled estimate. Also audit which alt-fuel types (LPG, CNG, E85, HVO100, H2) your current feeds already carry and expose them as filters.
- **Phase 2 (M, decision gate):** Only if Phase 1 sees usage, add a static "fast chargers" layer for DE and FR (verified key-free open CSV), tiled per country, lazy-loaded. No prices, no availability.
- **Phase 3 (conditional):** Revisit price integration only after the AFIR review lands and a NAP such as NL or DE demonstrably carries tariffs with acceptable fill rate.

**Open questions for the owner**
1. Is the target audience still petrol/diesel drivers, or do you want to chase EV and PHEV owners (a different product and competitors)?
2. Are you willing to publish an ODbL-licensed charger dataset (if OSM-based), or restrict yourself to CC BY / Licence Ouverte government sources?
3. Is a cost-per-100-km tool acceptable even though the public electricity price can only be a range, not live?

**Verified today:** OCM API returns 403 without a key; data.gouv IRVE static dataset is live (Licence Ouverte, updated 2026-10-07); the Overpass test timed out (504). Everything else is from docs or search summaries.
