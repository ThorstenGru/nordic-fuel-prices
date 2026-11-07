# Charger data design: Type 2 stations from Open Charge Map (+ optional NOBIL) (2026-11-07)

Scope: research and measurement for the "Chargers + typical prices" feature (Santa Fe PHEV, Type 2 AC only, 3.6 kW). No web/ code changed. Two standalone probes were added under `tools/analysis/`: `ocm_probe.js` (live fetch, needs env `OCM_API_KEY`, prints no key) and `ocm_compact_design.js` (offline, reads the probe output, measures the proposed filter/dedupe/compaction). Builds on `EV_PRICE_SOURCES_2026-11-06.md` and `NOBIL_TEST_2026-11-06.md`.

Legend: [M] measured today with the owner's key (2026-11-07, 18 requests in total, at least 1.2 s apart, all HTTP 200, no 429, no rate-limit headers returned). [D] documentation or search summary. [?] unverified.

## 1. Bottom line

1. **OCM works as a location layer for SE, NO, DK, DE, but it is a frozen snapshot, not a live feed.** Most imported records were last verified in 2024 (SE/NO/DK, NOBIL import of 2024-02) or 2021 (Germany, Bundesnetzagentur import). Records modified in the last 12 months (Type 2 filter) [M]: SE 4, NO 10, DK 685, DE 133. So "operational" status cannot be trusted; the UI must show the verified year and never say "available".
2. **OCM carries no price data worth parsing.** `UsageCost` is filled for 2.5% of SE and 12.6% of DE stations, free text, mixed currencies, mixed units. A per-kWh number is found for 1.0% of SE and 3.7% of DE stations. Treat it as verbatim, unverified, user-contributed text at best.
3. **The NOBIL part of OCM (79% of Swedish records) arrives stripped.** No operator, no usage type, no parking-fee flag, no status, no cost [M]. So operator-based price lookup would work for only 19% of Swedish stations through OCM alone. The optional NOBIL merge for SE/NO is what makes the operator price table useful there.
4. **Size is a non-issue.** Largest country (DE) is 160 KB gzip as a compact file, 316 KB with station titles. The budget of 1.5 MB gzip per country leaves 4 to 9 times headroom. No tiling needed.
5. **Germany: OCM covers roughly a fifth to a quarter of the real network** (41,466 Type 2 points in OCM against about 200,000 public points in the Bundesnetzagentur register in April 2026 [D from earlier doc]). For DE the Bundesnetzagentur CSV (keyless, CC BY 4.0, locations only, no price) is the better location source if DE matters; OCM DE is acceptable as a stop-gap with a "may be incomplete" label.

## 2. API test results (OCM v3 `poi`) [M]

Request shape that works: `GET https://api.openchargemap.io/v3/poi?output=json&countrycode=SE&connectiontypeid=25,1036&compact=true&verbose=false&includecomments=false&maxresults=100000` with header `X-API-Key`. Key goes in the header, never the URL, so it cannot appear in request logs.

**Reference ids** (from `/v3/referencedata/`, 497 KB, keyed): `ConnectionTypeID 25` = Type 2 (Socket Only), `1036` = Type 2 (Tethered Connector) (the id recalled in the NOBIL note is confirmed). Not wanted: `33` CCS (Type 2) (DC combo, a 3.6 kW AC car cannot use it), `32` CCS Type 1, `28` Schuko, `2` CHAdeMO, `27` NACS. Country ids: SE 216, NO 168, DK 65, DE 87. Status ids: 50 Operational, 100 Not Operational, 150 Planned, 200 Removed, 210 Removed duplicate, 0 Unknown, 10/20 automated available/in use, 30 temporarily unavailable, 75 partly operational. Usage ids: 1 Public, 4 Public membership required, 5 Public pay at location, 7 Public notice required, 2/3/6 private variants, 0 unknown. Current ids: 10 AC single phase, 20 AC three phase, 30 DC.

**Semantics found:** the `connectiontypeid` filter selects stations having at least one such connector; the station's other connectors (CCS, CHAdeMO, Schuko) are still returned, so connectors must be re-filtered client side. The set equals the Type 2 subset of an unfiltered query (SE: 4,970 POIs in total, 3,239 with Type 2, identical ids). `maxresults=100000` is honoured (one request returns the whole country). There is **no `offset` paging**: `offset=5` returned the same first 5 records. `modifiedsince=<date>` works for incremental checks. Duplicate parameters: the first `maxresults` wins.

**Counts, size and latency per country (Type 2 filter, compact + non-verbose):**

| Country | Stations | Type 2 connectors | Raw JSON | gzip -9 | brotli (wire) | Latency |
|---|---|---|---|---|---|---|
| SE | 3,239 | 21,675 (20,183 socket, 52 tethered + others) | 5.0 MB | 456 KB | 305 KB | 0.9 s |
| NO | 2,218 | 12,406 | 3.5 MB | 313 KB | 218 KB | 0.7 s |
| DK | 2,216 | 6,914 | 2.4 MB | 211 KB | 148 KB | 0.6 s |
| DE | 20,483 | 41,466 | 20.5 MB | 2.65 MB | 1.83 MB | 1.7 s |

Total transfer for the weekly job: about 2.5 MB over the wire for all four countries, four requests. The server answers with `Content-Encoding: br`. No rate limit headers, no 429 in 18 requests. Staff statements found by search [D]: a key is required for `maxresults` above 250, "many requests per second or many thousands per day" are not acceptable, repeated crawling to rebuild the dataset is discouraged, a full-country single call is how bulk use is meant. One call per country per week is far inside that. Exact quotas are not published on the pages I could open [?].

**Fields available** (compact response; field = filled / 3,239 SE stations):

- Station: `ID`, `UUID`, `DataProviderID` (19 NOBIL 2,565; 1 OCM contributors 674), `OperatorID` (643), `UsageTypeID` (391), `UsageCost` (80), `NumberOfPoints` (3,239), `StatusTypeID` (684), `DateLastVerified` (3,239), `DateLastStatusUpdate`, `DataQualityLevel`, `GeneralComments` (70), `DataProvidersReference` (2,771; for NOBIL records this is the NOBIL station id), `AddressInfo` (title, address, town, postcode, lat, lon, `AccessComments` 1,211, phone/URL rare).
- Connections (21,632 in SE): `ConnectionTypeID`, `PowerKW` (21,497), `Amps` (21,025), `Voltage` (21,024), `CurrentTypeID` (20,798), `LevelID`, `Quantity` (1,160), per-connection `StatusTypeID` (607), `Comments` (15,945, e.g. "Mode 3").
- Verbose mode adds reference objects (operator website, usage type flags, data provider licence text) at about 6 times the size; not needed because `referencedata` supplies the lookup tables once.
- OCM has **no structured fields** for start fee, idle fee, parking fee or subscription. Those exist only inside `UsageCost`, `GeneralComments`, `AccessComments`.

**Quality by provider and country (Type 2 stations) [M]:**

| | SE | NO | DK | DE |
|---|---|---|---|---|
| Main provider | NOBIL 2,565 (79%) | NOBIL 1,933 (87%) | NOBIL 1,452, PowerGo 679 | OCM contrib 10,162, Bundesnetzagentur 10,007 |
| Has operator | 19.9% | 11.4% | 34.2% | 77.9% |
| Has usage type | 12.1% | 10.3% | 33.6% | 48.8% |
| Verified in 2024 or later | 69% | 66% | 95% | 2% |
| Verified 2021 or earlier | 5% | 13% | 3% | 96% |
| Private / restricted (usage 2, 3, 6) | 38 | 7 | 6 | 1,082 |
| Not operational / planned / removed | 3 | 0 | 22 | 55 |

Status is mostly unknown: station-level `StatusTypeID` is empty on 79% of SE records and 0 on DK; so the only usable rule is to drop explicit negatives (100, 150, 200, 210) and not to claim "operational".

## 3. UsageCost fill and parseability [M]

Classes: empty; "free word" (free, gratis, kostenlos, kostenfrei, umsonst, avgiftsfri, bare `0`); numeric per kWh (a number next to kWh/kW/kw/h, in any of SEK, kr, EUR, euro, ct, c, `:-`); other number (per hour, per use, bare number such as `0,55` or `25`); text only (e.g. "As per InCharge pricelist", "Payment with Reev App").

Random samples of 200 (3 seeds each) and the whole population:

| Sample | Empty | Free word | Numeric per kWh | Other number | Text only |
|---|---|---|---|---|---|
| SE random 200, seed 1 / 2 / 3 | 97.0 / 96.5 / 97.0% | 1.5 / 1.0 / 1.0% | 1.0 / 1.5 / 1.5% | 0 / 1.0 / 0.5% | 0.5 / 0 / 0% |
| SE all 3,239 | 97.5% (3,159) | 1.1% (35) | 1.0% (32) | 0.3% (10) | 0.1% (3) |
| DE random 200, seed 1 / 2 / 3 | 89.0 / 88.0 / 89.5% | 5.0 / 3.5 / 4.0% | 2.5 / 4.5 / 3.5% | 3.5 / 3.5 / 2.5% | 0 / 0.5 / 0.5% |
| DE all 20,483 | 87.4% (17,908) | 5.0% (1,020) | 3.7% (753) | 3.3% (668) | 0.6% (132) |
| NO all 2,218 | 97.5% | 0.6% | 0.3% | 1.0% | 0.6% |
| DK all 2,216 | 98.1% | 0.5% | 0.2% | 0.9% | 0.3% |

With 3% fill, a 200-station Swedish sample holds only 4 to 7 filled records; the whole-population figures are the reliable ones.

Reading the filled Swedish records: the "free word" class is not all free electricity ("First hour is free", "Included in parking fee", "pay parking fee", "free of charge - ask first!", "50 SEK per use"). Bare `0` appears about 8 times and is ambiguous (price or "no data"). Per-kWh numbers are in mixed forms ("4 SEK/kWh", "2,5 sek / kwh", "3,5kr / kWh", "SEK 4.95 kWh", "2,35:-/kWh", "~2 SEK/kWh", one with a URL and AC/DC prices), many are old and some are per hour. German entries include start fees and blocking fees inside the text ("0,48 EUR/kWh + 0,84 EUR starting fee, 2,50 EUR blocking fee after 4 hours"), plus several ambiguous bare numbers (`25`, `0,55`, `0,79 EUR/KW`).

**Conclusion:** do not parse a price from `UsageCost`. Safe use only: (a) a `free` flag when a free word is present and no other number is in the text (SE 22 stations, DE 211 after this stricter rule; bare `0` excluded); (b) a "cost note exists" flag, with the text (cut to 80 characters) shown verbatim and labelled "contributor note, unverified, date <verified year>". Everything else: "price not published".

**Parking fee flag:** OCM has none. A text match on "parking fee / parkeringsavgift / Parkgebuehr / Parkplatzgebuehr" in UsageCost, GeneralComments, AccessComments hits 6 SE, 1 NO, 0 DK, 219 DE stations after the narrow regex. (A broad regex on "parkering" gave 16% in SE, but that is just the word "parking" in location descriptions, so the narrow one is used.) Treat it as a weak hint labelled "may charge parking" and show it only when set; absence means unknown. NOBIL has a real yes/no `Parking fee` attribute (id 7), which is the second reason for the NOBIL merge in SE/NO.

## 4. Terms and attribution

- OCM data licence: user-contributed data is CC BY 4.0; third-party imported data stays under the provider's licence and is not CC BY 4.0 [D, OCM terms page opened: https://openchargemap.org/site/about/terms]. Using the API or data in an app requires showing "the appropriate Data Provider attribution (including license terms)" to the end user. The terms page says nothing on caching limits or derived files, and gives no rate limits. OCM describes itself as non-commercial, non-profit; I found no commercial restriction stated.
- Provider licences from `referencedata` [M]: NOBIL (id 19) "NOBIL by Enova, CC BY 4.0"; Bundesnetzagentur (id 29) "Provided by Bundesnetzagentur.de under the CC-BY 4.0 license"; OCM contributors (id 1) CC BY 4.0; PowerGo (38, 54) CC0; Fount (108) CC0; **Oplaadpalen.nl (id 26) "Attribution-NonCommercial"**.
- **Licence check for the published file:** Oplaadpalen.nl records are NonCommercial-licensed. They are 3 (NO), 16 (DK), 297 (DE) stations in our filter. EuroFuelPrices is a free hobby site, but to stay clean the job should **drop provider 26** (297 DE stations, about 1.5%) unless the owner decides non-commercial is satisfied. Recommended: drop; cost is negligible.
- Attribution to show in the UI whenever the layer is on (footer or layer info sheet): "Charging stations: Open Charge Map contributors (CC BY 4.0) and data providers NOBIL by Enova (CC BY 4.0), Bundesnetzagentur (CC BY 4.0). Unverified, may be outdated." The file carries a `sources` list so the UI shows only the providers that are present for the country in view.

## 5. Design of the weekly job

**Where:** new step in `.github/workflows/scrape.yml` weekly (own `chargers` job, `continue-on-error`, own concurrency group), script `src/chargers.py` or Node equivalent following the elpris/price_cycles pattern: fetch the live previous `ev_<cc>.json`, build the new one, apply the guards below, write only if valid, else keep the previous file (last-good retention). Secret `OCM_API_KEY` via env, header `X-API-Key`; the script must not echo URLs with the key and must run a test that asserts the key string is absent from every output file.

**Per-station filter, in order (country counts [M] from `ocm_compact_design.js`):**

1. Keep connections with `ConnectionTypeID` in {25, 1036} and per-connection status not in {100, 150, 200, 210}. Station with none left: drop (SE 0, NO 5, DK 4, DE 39).
2. Drop `UsageTypeID` in {2, 3, 6} (private, notice-for-private, staff/visitors/customers): SE 38, NO 7, DK 6, DE 1,082. Unknown usage (null/0) is kept; the NOBIL-sourced majority has no usage type, so dropping it would delete almost everything.
3. Drop station status in {100, 150, 200, 210}: SE 3, NO 0, DK 22, DE 55.
4. Drop data provider 26 (Oplaadpalen.nl, licence) as above.
5. Dedupe: merge records within 30 m (grid 0.0005 deg, then haversine-style check); keep the record with more information (operator, cost text, non-NOBIL provider, newer verification), points = max of the two, never the sum. Merged: SE 13, NO 4, DK 314 (PowerGo duplicates; 14% of DK), DE 2,311 (12%).

**Kept after all rules (before dropping provider 26):** SE 3,185, NO 2,202, DK 1,870, DE 16,996.

**kW groups** (a 3.6 kW car draws at most 3.6 kW at 16 A single phase, so every Type 2 point works for it; the group only tells what the point can do and whether it is a slow 1-phase point): code 1 = at most 3.7 kW, 2 = 3.8 to 11 kW (11 kW and 7.4 dominant), 3 = above 11 kW (22 kW and up), 0 = unknown. Distribution (stations by their max Type 2 kW): SE 16 / 291 / 834 / 2,044; NO 14 / 212 / 838 / 1,138; DK 2 / 1 / 281 / 1,586; DE 74 / 393 / 3,052 / 13,477. Store the max rounded kW integer (0 unknown) and derive the group in the client, so the 7-11 versus 22 split is not frozen in the data. UI note: because the car is speed-insensitive, sort by distance and price knowledge, never by kW.

**File schema** `data/ev_<cc>.json` (one per country, SE, NO, DK, DE; others later with the same script):

```
{"v":1,"cc":"SE","generated":"2026-11-07","source":"ocm","sources":["OCM","NOBIL"],
 "ops":["MER","Incharge (SE)", ...],           // index 1..n, 0 = unknown
 "s":[[lat5,lon5,opIdx,kW,points,flags,verifiedYY,"title"], ...],
 "notes":[[stationIdx,"cost text cut to 80 chars"], ...]}
```

Flags bitmask: 1 free (source text says so), 2 membership or access key required (OCM usage 4), 4 notice required (7), 8 pay at location (5), 16 parking-fee text hint (weak), 32 cost note exists (text in `notes`), 64 tethered cable (reserved: only tethered Type 2 present, no own cable needed; not measured yet), 128 NOBIL-confirmed parking fee (reserved for the merge). "Restricted usage" in the brief = bits 2 and 4. `verifiedYY` is the two-digit year of `DateLastVerified`; the UI shows "verified 2024". Coordinates 5 decimals (about 1 m). OCM `ID` is deliberately left out (not needed; add as 9th element if a "report an error on OCM" deep link is wanted, about +4% size). `title` (NOBIL street address) is kept: it is the only name for 80% of SE stations and the list is unusable without it.

**Measured sizes of the reduced files (raw / gzip -9):**

| | Compact, no title | + title | + title + cost notes |
|---|---|---|---|
| SE | 102 KB / 29.8 KB | 175 KB / 62.8 KB | 176 KB / 63.4 KB (69 notes) |
| NO | 69 KB / 21.2 KB | 125 KB / 44.8 KB | 126 KB / 45.4 KB (51 notes) |
| DK | 59 KB / 15.0 KB | 101 KB / 33.6 KB | 102 KB / 33.9 KB (39 notes) |
| DE | 545 KB / 160 KB | 899 KB / 316 KB | 963 KB / 327 KB (2,248 notes) |

All far below 1.5 MB gzip per country. GitHub Pages serves gzip, so the browser downloads about the right-hand gzip column. Practical: load a country file only when the layer is switched on or when the destination/position is in that country; keep it in the service worker cache with the same stale-while-revalidate rule as other data. **No tiling or splitting is needed**; if Germany later grows past about 1 MB gzip (for example after a Bundesnetzagentur merge to 150k points), split by 1-degree bands or by Land, but that is a future change. Client list/map: build a coarse grid index at load time, no library.

**Job guards (fail the write, keep last-good, mark the run warning):** HTTP not 200 or JSON invalid; fewer than 80% of the previous count after the filter; station count outside a per-country sanity band (SE 2,000 to 6,000; NO 1,500 to 4,000; DK 1,000 to 4,000; DE 10,000 to 40,000); any lat/lon outside the country's bounding box; key string found in output. Keep `generated` and a `stale` computation in the client: if `generated` is older than 21 days, show "charger data not updated since <date>". Because OCM itself is stale, also expose the median verified year in the file (`medVerified`) for the info sheet.

**Weekly cadence and politeness:** one call per country per week, 1.5 s apart, a `User-Agent` naming the site. `modifiedsince` is not needed (a full SE pull is 0.3 MB on the wire).

## 6. Optional NOBIL merge (SE and NO only)

**What OCM already imports from NOBIL** (provider id 19, `Partially Automated (Ad-Hoc Import)`, `DateLastImported` empty, SE 2,565 / NO 1,933 / DK 1,452 stations) [M]: station position, title (the street address), connector type, kW, amps, voltage, current type, "Mode 3/4" comment, number of points, the NOBIL station id (in `DataProvidersReference`), and a verification date (SE: 2,032 of 2,565 dated 2024-02). **What is not carried over:** operator (0 of 2,565 in SE), usage type (0), public/visitor access beyond what filtering did upstream, parking-fee flag, time-limit flag, payment-method class, open-24h, status (0), any cost, comments. So OCM adds nothing to NOBIL except contributor-added stations and DK/DE coverage; for SE and NO a direct NOBIL pull is a strict superset with fresher data (assuming NOBIL's live data is current, which is likely since Energimyndigheten maintains Swedish data; I could not test it without a key [?]).

**Merge rule** (job runs the NOBIL step only if secret `NOBIL_API_KEY` exists, otherwise OCM only, silently):

1. Fetch `https://nobil.no/api/server/datadump.php?apikey=$KEY&countrycode=SWE&fromdate=2005-01-01&format=json&file=false` (and `NOR`), parse server-side only. Keep Type 2 value 32 (and 60 flagged), public availability only (attribute 2 = 1), drop NOBIL stations that are permanently closed.
2. Match OCM to NOBIL: first by id (OCM provider 19 `DataProvidersReference` equals the NOBIL station id; the exact form of the id, numeric versus `SWE_xxx`, is [?] until a live response is seen), else within 30 m. A match means: take operator, points, kW, parking-fee, payment class, open 24h, `Updated` year from NOBIL; keep OCM `UsageCost` text if present.
3. Unmatched NOBIL stations are added; unmatched OCM stations are kept only if provider is not 19 (a NOBIL-imported station that NOBIL no longer lists was removed upstream) or if it is OCM contributor data.
4. Output stays in the same schema. New operator names go into `ops`; NOBIL `Owned_by` strings are mapped to OCM operator names by a small alias table so the price table lookup has one key space. Flag 128 = NOBIL parking fee yes. Payment class (phone, bank card, charging card) can map to flag 2 only when it says a charging card is required.
5. **Terms:** NOBIL says its API may not be used directly in apps or services for end users and that data must be processed, cached or wrapped in an intermediate service. The job is that intermediate service. To reduce the risk: publish only the reduced tuple file above, never NOBIL raw fields, never NOBIL ids, never the key or the URL. Do not add the NOBIL `International_id` to the output. The owner should still write to NOBIL (see the NOBIL note, section 3) before the first publish of a NOBIL-derived file. Attribution "NOBIL by Enova, CC BY 4.0, https://nobil.no" is added to `sources` for SE/NO.
6. Tests: fixtures for a matched pair, an OCM-only contributor station, a NOBIL-only station, a NOBIL-removed station that is dropped; assert the output contains no field named like the NOBIL attributes and no `apikey`.

## 7. Price layer (design brief, no data collected here)

- Hand-kept, dated table `data/ev_ac_prices.json`, modelled on `docs/FARES.md` + `tools/check_fares.js`: per entry `operator` (OCM name plus aliases), `country`, `currency`, `ac_kwh` (list price for AC, no subscription), `start_fee`, `idle_fee` (with the rule text, e.g. after N minutes), `subscription` (none / required / discount with), `as_of`, `source_url`. Entries without a verified source URL are not added. Validation script fails on an entry older than 120 days or missing source/date, as with fares.
- Operator coverage that OCM gives [M]: SE top operators MER 65, Incharge 41, Recharge 27, E.ON Drive 26, VIRTA 22, eways 14, Vattenfall InCharge 7, Lidl 6; DE: Innogy/RWE 1,883, ladenetz.de 1,465, EnBW 973, Shell Recharge 674, Stromnetz Hamburg 653, Allego 535. Only 19.9% of SE and 11.4% of NO stations have an operator through OCM; that rises only with the NOBIL merge. Without operator the label is "price not published".
- Label rules in the UI: price from the table is shown as "list price <operator>, <as_of>, check operator" and is never presented as the price at that station; the user's own entered price overrides; `free` only from flag 1 (source text says so); contributor cost text only verbatim; otherwise "price not published". No average is ever shown.
- Surcharge rows the car owner cares about: start fee, idle/blocking fee, subscription needed (flag 2 plus table), parking fee hint (flag 16 or 128). OCM cannot supply these per station; they come from the operator table (start/idle/subscription) and the flags (parking).

## 8. What I did not verify

- Live NOBIL data (no key). Its id format, status field fill, and whether its Swedish station count exceeds OCM's 3,239 (Sweden has more public points than OCM lists; OCM SE 21,675 Type 2 connectors against an unmeasured real total).
- OCM rate-limit numbers (not published on any page I could open) and OCM terms on caching derived files (page silent). I made 18 calls and saw no limit.
- Whether `Oplaadpalen.nl` NonCommercial matters for a free hobby site (a legal call for the owner; the design drops it).
- Weak items: the parking-hint regex (narrow, will miss many) and the "free" classification were checked by reading only the Swedish filled records, not the German ones.
- Real-world station existence: no station was checked against the ground, and OCM `DateLastVerified` for NOBIL records reflects the import time, not a physical check.
- Reference-data id for tethered Type 2 was confirmed; the share of stations where only tethered Type 2 exists (flag 64) was not computed.
