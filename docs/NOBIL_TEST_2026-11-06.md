# NOBIL test: Swedish public chargers with tariff per kWh? (2026-11-06)

Research only. No key registered or used. No code changed. Builds on `EV_PRICE_SOURCES_2026-11-06.md`.

Legend: [O] opened and read today (fetched, content seen). [P] probed with a GET today (status only). [S] web-search summary only, page not opened. [M] from memory or unverified.

## 1. Verdict

**Not feasible for tariffs. Feasible only for locations and connector data.**

NOBIL API v3 has **no price, tariff, start-fee or idle-fee field**. The complete attribute list contains only a yes/no `Parking fee` (id 7), a `Time limit` yes/no (id 6) and a coarse `Payment method` (id 19: phone, bank card, charging card, combinations). It has no kWh price, no currency and no timestamp for a price. Source: NOBIL attribute reference, https://nobil.no/admin/attributes.php [O, keyless, 200], and the v3 API PDF rev. 16.08.2026, https://info.nobil.no/images/API_NOBIL_Documentation_v3_20260816.pdf [O, all 19 pages text-extracted; sample response shows only the attributes above].

So the requested `data/ev_se.json` with `tariff per kWh, start fee, idle fee` cannot be filled from NOBIL. Expected fill rate for tariff: **0%** (field does not exist). I found no published NOBIL statistics on tariff coverage, because there is nothing to count (NOBIL statistics page https://info.nobil.no/statistikk [O] covers counts of points per municipality in Norway only).

What NOBIL can deliver for Sweden: station id (`International_id`, e.g. `SWE_xxxxx`), position, owner (`Owned_by`), number of points, connector type (value id 32 = Type 2), capacity class (kW), open 24h, public/visitors, parking fee yes/no, payment method class, `Updated` timestamp. These come from the station and connector sections of the v3 sample response [O, PDF p.5].

## 2. Access, licence and the blocking terms

| Item | Finding | Source |
|---|---|---|
| Key | Free. Request via the form on the API page. Needs first and last name, email, mobile number and **website address where the service will run**. Admin approves, key by email, keys sent Mon/Wed/Fri, check spam. | https://info.nobil.no/api [O]; PDF p.2 [O] |
| Hobby use | Not mentioned either way. No "commercial only" restriction found; the About page says anyone can register and accept the free (Creative Commons) terms. | https://info.nobil.no/om [O] |
| Data licence | CC BY 4.0, "NOBIL by Enova", attribution required, link to https://nobil.no. The earlier note "CC BY 3.0" in the previous doc is outdated. | https://info.nobil.no/api [O] |
| **API usage terms** | "Intended for internal use only ... not permitted to use the API directly in apps or services provided to end users." API must not be exposed in web/mobile apps; end users must not see API calls, responses or keys; data must be **processed, cached or wrapped in an intermediate service**. Violation can end access. | PDF p.2 [O] |
| Keyless endpoints | None. `https://nobil.no/api/server/datadump.php?countrycode=SWE` returns 401 "Get a valid api-key" [P]; `search.php` returns "APIkey not valid" [P]. `https://nobil.no/api`, `/english`, `/nyheter` on the bare host return 403 to scripts [P]; the same pages work on `info.nobil.no` [O]. `attributes.php` is keyless [O]. | probes today |
| Limits | Rectangle search max 2000 stations; data dump supports `countrycode=SWE`, `fromdate`, `format=json`. | PDF p.4, 15 [O] |
| Sweden scope | Energimyndigheten maintains Swedish data; DK/FI/IS removed from Oct 2025. NOBIL receives OCPI data from Circle K, Current, Eviny, E.ON, Kople, Liikennevirta, Mer, Monta, Recharge, Tesla, Vattenfall. | PDF p.2 [O]; https://info.nobil.no/om [O]; https://info.nobil.no/nyheter [O] |
| AFIR NAP | Swedish NAP is described as a marketplace with three charging databases, one of them NOBIL; Energimyndigheten uses NOBIL "for now". Pages do not mention prices. | Search summary of regeringen.se Energimyndigheten remiss [S, not opened]: https://regeringen.se/contentassets/97b3bff50524404c8fb3829d142efcc6/energimyndigheten.pdf |
| Real-time | Separate product "NOBIL Real-time" at data.enova.no (WebSocket, status only: AVAILABLE, CHARGING ...). No price. | PDF p.18-19 [O] |
| GitHub projects using NOBIL tariffs | None found. Searches returned only a Go client (`go.einride.tech/nobil`, API v3 2018) [S] and ChargePanel's NOBIL guide [S]. | https://pkg.go.dev/go.einride.tech/nobil [S] |

**Risk for this project:** the "internal use only / not to end users" term is in tension with publishing a derived `ev_se.json` on a public GitHub Pages site. A weekly job that processes and caches NOBIL data is the permitted pattern, but a public file that is effectively a mirror of the station list is a grey zone. The owner should state the use when registering (static, processed, attributed, non-commercial) and ask in writing at post (at) nobil.no whether republishing a derived station file is acceptable. Do not publish raw NOBIL fields or ids that let a user query the API.

## 3. What the owner must do (if locations from NOBIL are wanted anyway)

1. Open https://info.nobil.no/api and use "Ask for an API-key" (the form; I could not see the form target in the HTML, only the section). Fill name, email, mobile and the website (eurofuelprices.com). Say: non-commercial hobby map, weekly cached processing, attribution CC BY 4.0.
2. Wait up to a few working days (Mon/Wed/Fri batches).
3. Optionally email post (at) nobil.no (address as written on https://info.nobil.no/om [O]) to ask about republishing a derived file.
4. Add the key as GitHub secret `NOBIL_API_KEY`.
5. Run one manual probe and count: stations in `SWE`, connectors with attribute 4 = 32, and check whether any attribute outside the list in section 1 appears (the live response could differ from the PDF). This takes 10 minutes and either confirms or overturns the "no tariff" finding.

## 4. Plan for the weekly Actions job (locations only, tariff left null)

Only worth building if Layer 1 in `EV_PRICE_SOURCES_2026-11-06.md` (user-entered price) needs a "nearest Type 2 charger" feature. Otherwise skip.

- Trigger: weekly cron plus manual dispatch. Secret `NOBIL_API_KEY`. No key in client code or in the JSON.
- Fetch: `GET https://nobil.no/api/server/datadump.php?apikey=$KEY&countrycode=SWE&fromdate=2005-01-01&format=json&file=false` (documented, PDF p.15 [O]; not executed). Fail the job on non-200, on empty or on a drop of more than 20 percent in station count versus last run, and keep the previous file.
- Filter: stations with at least one connector where attribute 4 (Connector) = 32 (Type 2). Keep public availability (attribute 2 = 1) only. Note value 50 "Type 2 + Schuko" and 60 "Type1/Type2" are separate ids; decide explicitly (default: 32 only, plus 60 flagged).
- Output `data/ev_se.json`, one record per station:
  `{"id","name","lat","lon","operator","kw_max","type2_points","open24h","parking_fee","payment","updated","tariff_kwh":null,"start_fee":null,"idle_fee":null,"source":"NOBIL (Enova, CC BY 4.0)","source_date":"<run date>"}`.
  Keep the three tariff fields as explicit nulls so the schema is stable if a price source arrives; the UI must show no price for null (existing rule: never an average).
- Footer attribution in the UI: "Charging data: NOBIL by Enova, CC BY 4.0, https://nobil.no".
- Tests: assert schema, lat/lon inside Sweden, no key string in the output, count within a sane band.

## 5. Open Charge Map as complement

- OCM needs a key on every call; keyless request returns 403 "You must specify an API key" [P today, https://api.openchargemap.io/v3/referencedata/]. Owner key exists as secret `OCM_API_KEY`.
- `ConnectionTypeID=25` is "Type 2 (Socket Only)"; tethered Type 2 is a separate id (1036 as I recall) [M]. Confirm both from the keyed `referencedata` call before filtering. For a Type 2 filter use `connectiontypeid=25,1036`.
- Use as location complement: query `countrycode=SE&connectiontypeid=25,1036&maxresults=...&compact=true&verbose=false` weekly in the same job. Merge with NOBIL by distance (for example 50 m) and operator; prefer NOBIL for operator/power where both exist, OCM to fill stations NOBIL lacks.
- OCM has no structured tariff: `UsageCost` is free text, not safe to parse into a price (earlier doc, https://learn.microsoft.com/connectors/openchargemapip/ [S]). OCM historically imported NOBIL, so overlap is expected and OCM adds little in Sweden [M]. OCM licence and attribution: contributions CC BY 4.0, imports carry their own terms [S, earlier doc]; show "Open Charge Map" attribution.
- Net: OCM does not solve the price gap either.

## 6. Where a Swedish tariff could come from instead

Not NOBIL. Remaining options from the earlier doc: dated, cited operator list prices as a hand-maintained default (`data/ev_defaults.json`), or the owner's own entered price. A per-station Swedish tariff feed exists only inside the AFIR flow between operators and NAP (OCPI Tariffs), which NOBIL does not expose in v3. Whether Energimyndigheten/Trafikverket plan a tariff-bearing public NAP feed is unknown [M]; worth one question to post (at) nobil.no when asking about republishing.

## 7. Not verified

- Live NOBIL response was not seen (no key). The "no tariff" finding rests on the official v3 PDF dated 16.08.2026 and the live attribute table, both opened. A newer live-only field cannot be excluded.
- The key request form target and its exact terms text were not visible; the licence page at https://creativecommons.org/licenses/by/4.0/ was not opened.
- Swedish NAP statements come from a search summary of a government remiss, not an opened page.
- OCM ConnectionTypeID values are from memory.
