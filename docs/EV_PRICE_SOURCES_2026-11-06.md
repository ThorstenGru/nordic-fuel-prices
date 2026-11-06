# EV public charging stations with price per kWh: source research (2026-11-06)

Scope: where EuroFuelPrices can get EV charging stations WITH price per kWh, keyless or hobby-friendly, Sweden first, then Europe. Research only, no code changed. Builds on `EV_ALT_ENERGY_RESEARCH.md` (2026-10-07).

Legend: [V] verified by fetching today; [D] documentation or search summary only; [?] unverified or conflicting. In this session I did not run live calls against any feed. Everything below is [D] or [?] unless marked. Treat "price field fill rate" as unknown everywhere.

## 1. Bottom line

1. **No keyless, hobby-friendly source today gives a trustworthy per-station price per kWh for Sweden.** The only structured price channels are the AFIR national access points (NAPs). Sweden's is NOBIL (Energimyndigheten is the admin), which needs a free key and whose tariff fields and fill rate I could not confirm.
2. **Open Charge Map and OSM are location sources, not price sources.** OCM `UsageCost` is free text; OSM `charge=*` is optional and sparsely mapped.
3. **Operator list prices are the only reliable "price" signal** (Ionity, Circle K, Mer, Tesla, Recharge, OKQ8), and they are published as web pages or in-app, not as open feeds. Scraping is a ToS risk. They can serve only as a dated, cited, hand-maintained default.
4. **Europe: only NL, DE and (partly) BE/FR have a legal route to tariff data**, via NAPs (DOT-NL OCPI tariffs, Mobilithek DATEX II). Licence and fill rate unverified; the BEUC 2026 report calls availability inconsistent.
5. Recommended design: ship the **cost comparison on user-entered prices** now (matches the roadmap X7 and the owner's request), label public price as an assumption, and treat NOBIL tariffs as an optional later spike gated on a verified key and fill-rate test.

## 2. Source table

| Source | Price per kWh available? | Coverage | Access / key | Licence | Quality | Recommendation |
|---|---|---|---|---|---|---|
| **Open Charge Map** (API) | Only as free-text `UsageCost` (mostly parking/"free" notes). Not structured. [D] | Global aggregator, Sweden present (imports incl. NOBIL historically) [?] | Free key mandatory; unauthenticated returned 403 on 2026-10-07 [V from earlier doc]. Maintainers floated paid tiers for heavy use [D] | Mixed: contributions CC BY 4.0, imports carry their own terms [D] | Low for price. `DataQualityLevel` largely unused [D] | Do not use for price. Locations only, if ever. |
| **NOBIL** (info.nobil.no, "Nobil Sweden" administered by Energimyndigheten) | Possibly, via AFIR OCPI feed; NOBIL is named as Sweden's NAP by operator guides [D][?]. NOBIL's own front page mentions no tariffs [D]. | SE and NO only (DK, FI, IS dropped from Oct 2025) [D] | Free API key, registration | CC BY 3.0 per OSM wiki [D][?] | Static locations good. Price fill rate unknown. | **Best candidate for Sweden.** Spike: get a key, count stations with a populated tariff. Do not build before that. |
| **OSM / Overpass** (`amenity=charging_station`, `fee`, `charge`) | `fee=yes/no` sometimes; `charge=` optional free text; wiki gives no coverage stats [D]. Operators change tariffs; OSM goes stale. | Good locations in DE, NL, Nordics | Keyless; Overpass rate-limited, 504 timeout seen 2026-10-07 [V]. Geofabrik extracts safer | ODbL share-alike | Poor for price | Not for price. Not worth the ODbL obligation. |
| **Mer** | Yes, per station and time of day, "from 3.40-5.10 kr/kWh" (Hurbra table, 2026-08-26) [D] | Nordics | In-app / web; no public feed found | Proprietary | Accurate when read, but not machine readable | Hand-maintained default only, cited and dated. No scraping. |
| **Ionity** | Flat per-kWh by plan: Go 5.79, Direct 6.09 kr/kWh in Sweden [D, Hurbra 2026-08-26] | Pan-European fast chargers | No public price feed found | Proprietary | Good as list price; changes without notice | Default source for a "fast charging" reference value, cited. |
| **Vattenfall InCharge** | Per station, shown in app only [D] | SE, NL, DE, others | No public feed found | Proprietary | n/a | Skip. |
| **Tesla Supercharger** | Varies by site and time; no national number [D] | Europe | Tesla app only. A few Superchargers appear in NOBIL attributes (admin edited 42 stations) [D] | Proprietary | Variable | Skip as a feed. |
| **Circle K** | 5.89 kr/kWh own price (another Hurbra article says 5.79 with membership: conflicting) [D][?] | Nordics | No feed found | Proprietary | List price only | Cited default only. |
| **Eviny** | Not researched in depth. Norway-focused; no open price feed found [?] | NO | n/a | n/a | n/a | Out of scope for Sweden-first. |
| **Germany Bundesnetzagentur Ladesaeulenregister** | **No** (confirmed in earlier doc) [D] | DE, ~200k public points on 2026-04-01 [D] | Keyless CSV | CC BY 4.0 [D][?] | Good locations | Locations only. |
| **AFIR NAP Germany: Mobilithek (DATEX II profile)** | Yes in principle: ad-hoc price must be provided, free-of-charge points exempt from dynamic price [D]. DATEX II mandatory from 2026-04-14 [D][?] | DE, operators only now filling in | Registration at Mobilithek; subscription model [?] | Varies per publisher [?] | Unknown fill rate; BEUC says patchy | Phase 3 watch. Not a hobby-friendly integration today. |
| **AFIR NAP Netherlands: DOT-NL (NDW)** | **Yes**: dataset "Charging point tariffs" in OCPI 2.2.1, plus locations in OCPI and GeoJSON, via opendata.ndw.nu, cURL-able [D] | NL | Documented as open download, no key mentioned [D]; verify | **Unclear**: dexes.eu lists "Restricted, licence unknown" [D][?]; ask NDW Servicedesk | Likely best in EU for tariffs; no history, OCPI 2.2.1 only | **Best candidate for Europe.** Test one fetch and read licence before any use. |
| **AFIR NAP France** (data.gouv.fr IRVE) | Schema supports price in the dynamic dataset; static CSV has a price field in some operators [D][?] | FR | Keyless [V from earlier doc] | Licence Ouverte | Price fill rate unknown | Check the `tarification` column fill rate in a one-off test. Cheap to test. |
| **AFIR NAP Belgium** (transportdata.be, e.g. EnergyVision OCPI Tariffs) | Yes, per operator OCPI tariffs resource [D] | BE, per operator | Open download [D] | Per dataset | Operator by operator | Only if Benelux is added. |
| **Other NAPs** (Fintraffic FI, Fstyr DK, Trafikverket SE role) | In principle | FI, DK | Varies | Varies | Unknown | Out of scope. Sweden: Trafikverket's NAP role versus NOBIL is unclear [?]. |
| **Chargeprice API** | **Yes, the real thing**: computed per-kWh price per tariff per station | EU-wide | Key by contacting sales; terms: EUR 10 fine per misused price datum, no redistribution [D] | Commercial | Best in market | Not hobby-friendly; cannot redistribute in static JSON. Mention only. |
| **Chargemap / PlugShare / Zap-Map / ABRP** | Yes in apps | EU | Commercial agreements; scraping prohibited | Proprietary | Good | Not usable. |
| **Raw OICP / OCPI endpoints** | Yes, but OCPI Tariffs is a B2B interface between CPOs and eMSPs, not public. Only NAP-published copies are open (NL, BE above) | n/a | Credentials via roaming hub | Contractual | n/a | Not applicable. |
| **EAFO, Eurostat** | EAFO: statistics only. Eurostat `nrg_pc_204` has household electricity prices (not public charging) | EU | Keyless | EU reuse | Good for home price default | Use Eurostat for a home price suggestion, never labelled as a charging price. |

## 3. Observations that drive the design

- AFIR obliges operators to publish static and dynamic data incl. ad-hoc price to NAPs and show the price at the point of use. Compliance is uneven: Germany drafted fines for incomplete price info (2026-03), BEUC/T&E say outdated or missing prices are common in apps and QR flows [D]. The Commission starts a common European access point by 2026-12-31 [D][?].
- Sweden: NOBIL Sweden (Energimyndigheten admin) syncs via OCPI from operators and "strictly requires AFIR data" [D]. The 2026-04-14 DATEX II mandate cited for Germany may not apply the same way in Sweden [?]. Needs one call to the NOBIL API to settle.
- Public list prices drift by weeks. Any hardcoded number must carry its source and date and be shown as such.
- Per-station price from a legal feed is plausible only for NL (and perhaps SE via NOBIL). Elsewhere a per-station price would be unverified.

## 4. Best design

**Layer 1 (build now, no external feed): user-entered prices, clearly labelled.**
- `car.elec` (home price per kWh) stays the owner's own value. No hidden default: if empty, the card says "enter your price" and shows no EV cost. Optional suggestion later from Eurostat household price, labelled "country average, not your tariff".
- Public price: one field "public charging price per kWh", per country. **Prefilled defaults must be cited, dated reference values, never silent:** for Sweden, the Hurbra roundup of 2026-08-26 lists 5.49 (OKQ8) to 6.09 (Ionity Direct) kr/kWh for fast charging; a defensible default is "about 5.8 kr/kWh, list prices Aug 2026, Ionity/Circle K/Recharge/OKQ8" shown with the text "assumption, edit to match your network". For other countries leave the field empty until a source is added; do not translate the SE number.
- Store per-country values in `data/ev_defaults.json` with fields `price`, `currency`, `source`, `as_of`. The UI shows source and age, and greys the result when `as_of` is older than 90 days.

**Layer 2 (spike, owner action): NOBIL tariffs for Sweden.**
- Owner registers a free NOBIL key (no accounts are created by Claude). A weekly Actions job fetches Swedish stations and counts how many have a parsed tariff (price per kWh, timestamp). Gate: build only if the fill rate is high enough to make "5 nearest chargers" meaningful (suggest at least 50% of fast chargers). Parse structured tariffs only. Never parse free text with regexes into a price.
- If it passes: `chargers/se.json.gz` with `[lat, lon, kW, operator, price_per_kWh, price_date]`, loaded only when the EV-comparison "nearest chargers" option is on. Show "price as published by operator, updated <date>". No availability claims.
- CSP: the browser reads only EuroFuelPrices' own JSON, so no new third party in the client. The key stays in Actions secrets.

**Layer 3 (Europe, conditional):** test DOT-NL tariffs (NL) and the IRVE price column (FR); add a country only after (a) licence confirmed, (b) one-off fill-rate count, (c) station price carried with timestamp. Germany via Mobilithek only after a registration and subscription is acceptable. Chargeprice and the app aggregators are excluded by terms.

**Rules for the UI regardless of layer:** stations without a parsed price are shown without any price, never with an average. A station price older than the staleness cutoff is labelled "price date" and ranked below dated ones, matching the fuel rules. Calculation for "gas vs electricity": fuel price from the nearest 5 stations (95) versus electricity price per kWh (home entered, or station tariff if layer 2 exists), converted using the car profile.

## 5. Open items and what I did not verify

- No live fetch of NOBIL, DOT-NL, Mobilithek, IRVE price columns or OCM was run this session. Fill rates are unknown for all.
- NOBIL licence (CC BY 3.0) is from the OSM wiki and may be out of date.
- DOT-NL licence conflicts between sources (open data portal versus "Restricted, unknown" on dexes.eu). Ask NDW before reuse.
- Swedish prices come from one third-party roundup (Hurbra, 2026-08-26) with two conflicting Circle K figures. Re-check against operator pages before shipping the default, and set `as_of` honestly.
- The BEUC 2026 report PDF could not be text-extracted this session; its conclusions are taken from the earlier research doc and secondary summaries.

## Sources

- [Open Charge Map API key and UsageCost (Microsoft connector doc)](https://learn.microsoft.com/connectors/openchargemapip/)
- [OCM: API keys are mandatory](https://community.openchargemap.org/t/reminder-api-keys-are-mandatory/218)
- [OCM: retirement of data imports](https://community.openchargemap.org/t/retirement-of-data-imports-etc/307)
- [OCM: NOBIL drops all countries except SE and NO](https://community.openchargemap.org/t/nobil-dropps-support-for-all-countries-except-sweden-and-norway/1788)
- [NOBIL info site](https://info.nobil.no/)
- [Monta: AFIR reporting in Sweden](https://monta.com/en/help-center/charge-point-data-reporting-afir/)
- [Spirii: AFIR compliance (NAP list)](https://developer.spirii.com/docs/afir)
- [Bird & Bird: EV charging Sweden](https://evcharginginfrastructure.twobirds.com/home/sweden)
- [Drivkraft Sverige AFIR Q&A](https://drivkraftsverige.se/app/uploads/2023/10/Summering-av-fragor-och-svar-fran-AFIR-webbinarium-4-okt-2023.pdf)
- [OSM wiki: amenity=charging_station](https://wiki.openstreetmap.org/wiki/Tag:amenity=charging_station)
- [electrive: German DATEX II profile for live charging data](https://www.electrive.com/2025/08/26/germany-publishes-datex-ii-data-profile-for-live-ev-charging-station-data)
- [Nationale Leitstelle: AFIR](https://nationale-leitstelle.de/en/bestand-ausbau/afir/)
- [NDW: DOT-NL](https://english.ndw.nu/dataportals/dot-nl)
- [NDW docs: DOT-NL FAQ](https://docs.ndw.nu/en/faq/DOT-NL/)
- [dexes.eu: DOT-NL ad-hoc price dataset](https://dexes.eu/en/dataset/locatie-specificaties-adhoc-prijs-en-beschikbaarheid-van-laadpalen-in-nederland/68c223cdfd4f0276e3072c09)
- [transportdata.be: EnergyVision OCPI tariffs](https://transportdata.be/dataset/energyvision-public-charging-network-locations-afir-ocpi-2-2-1/resource/8de8ebd3-8c2b-470d-bb7b-b2c9d2d3ab0e)
- [Chargeprice API terms](https://chargeprice.github.io/chargeprice-api-docs/terms.html)
- [BEUC 2026 EV charging prices and data report](https://www.beuc.eu/sites/default/files/publications/BEUC-X-2026-073_EV_charging_prices_and_data_report.pdf)
- [Hurbra: best charging networks Sweden 2026 (price table)](https://hurbra.se/basta-laddnatverk-sverige-2026/)
