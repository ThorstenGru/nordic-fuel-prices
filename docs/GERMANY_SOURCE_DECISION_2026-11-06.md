# Decision memo: live German fuel prices (E5/E10/Diesel)
Date: 2026-11-06. Research only. Nothing was registered, emailed or called with credentials.

## Bottom line
- No free, clean, bulk, live German source exists today. Every German source found derives from MTS-K, the official Bundeskartellamt feed, and most come via Tankerkönig.
- The only stable and legally clean long-term answer is to become an approved MTS-K consumer information service (VID). Approval usually takes 6 to 12 months (Bayernportal, opened). Filed now, it lands around mid to late 2027, about the same time as the claimed Tankerkönig reopening.
- Keep ANWB running as the bridge. Send four emails this week to shorten the gap.

## Ranking

| # | Option | Verdict | Why |
|---|---|---|---|
| 1 | Direct MTS-K VID approval (Mobilithek feed) | Viable, slow. Best long-term primary. | Official source, no cost, no deadline. The regulation allows retrieval at most every 1 minute (MTSKraftV §5, per one researcher; the verifier did not re-open it). Unknown: whether a Swedish hobby operator is accepted, and the Mobilithek technical mechanics. |
| 2 | Tankerkönig paid or dedicated feed | Viable if they agree. | Their page (opened) offers a dedicated server and regular full-data delivery (JSON/XML/CSV) for a monthly fee, and says mirroring all stations needs contact first. Price, hobby rate and whether it works while registration is paused are unknown. It does not remove dependence on Tankerkönig. |
| 3 | TankPuls API (api.tankpuls.de) | Viable with conditions. Possible interim primary. | Opened all four pages. It is the closest drop-in. It has an `/api/stations/all` endpoint (~15k stations, one call per 10 min) that needs a Business or Partner key. Keys are manually reviewed and individually priced. It is a single-person operator, and its docs conflict on whether the data comes via Tankerkönig or directly from Mobilithek. |
| 4 | kraftstoffbilliger.de MTS-K API | Viable with conditions. Better for route planning than for bulk. | 30-day free trial by email. The radius cap is 20 km and there is no bulk endpoint. Terms and rate limits are not published. It is a sole operator, and its MTS-K approval is self-claimed. It offers route search, which fits the roadmap. |
| 5 | Tankerkönig free API | Not viable for bulk. | Their page (opened) says mass queries are blocked and keys deactivated, the radius cap is 25 km, and the limit is 1 request per minute. Registration is paused. |
| 6 | benzinpreis-aktuell.de | Not viable as a source. Use only for national-average checks. | Keyless, but per-station URLs only, with no terms and no bulk endpoint. Written permission would be needed for anything systematic. |
| 7 | Tankerkönig history dump | Not viable. | It is updated daily, so it is not live. The licence is BY-NC-SA 4.0, not CC BY 4.0 as the brief said. Access needs a verified account. |
| 8 | InfraNode, fuel-prices.eu, Fuelo, OSM, brand feeds, consumer apps, TomTom, HERE | Ruled out for Germany. | InfraNode forbids background polling and storage. fuel-prices.eu has no German station data. Fuelo's German data is crowd-sourced and unlicensed. OSM has no prices. TomTom is sales-only. HERE is unverified, and no credentials were allowed. |

## Recommended design
- **Primary (target):** the direct MTS-K feed after VID approval.
- **Primary (interim, only if a reply is positive):** a Tankerkönig paid feed or a TankPuls Business key. Add whichever source arrives as another alt reading in `merge_engine`.
- **Fallback:** ANWB, unchanged, every 15 min. It is unofficial with no timestamps, so legal risk remains.
- **Cross-check (all in-house, no new licence needed):**
  - Track per-station "last changed" by hashing each fetch. Flag a station if it has not changed for more than 48 h.
  - Check price bands, such as zero, below 1.0 EUR or above 3.5 EUR, and the E5/E10 slot order. Apply the slot-order test to Germany first because of the known mislabelled ANWB petrol slots.
  - Compare ANWB's national mean with the benzinpreis-aktuell nationwide endpoint, which is a plain number rather than station data. One researcher read it on 2026-11-06: E5 2.015, E10 1.959, Diesel 2.199. The thresholds are heuristics from the researcher, not sourced.
  - Keep each MTS-K value as published and show other readings separately. §7 requires station data not to be altered.

## What the owner must do
1. **Email MTS-K** (mts-kraftstoffe@bundeskartellamt.bund.de). Ask:
   - Can a Swedish individual running a free hobby map be approved?
   - Is a German representative needed, and can the application be in English?
   - What are the Mobilithek access details, polling limits and licence?
   - May other sources be shown alongside MTS-K values?
   - Then file the informal application by email. It is free.
2. **Email info@tankerkoenig.de.** Ask for the paid or dedicated feed price, a hobby rate, a full-Germany delivery at 15-minute cadence, and the real registration status. Ask what the AGB mean for a public map.
3. **Email admin@tankpuls.de.** Ask for a free or low-cost key for a non-commercial map using `/api/stations/all`, and where its data really comes from.
4. **Optional:** request the kraftstoffbilliger.de trial (support@codemec.com) for route-planning tests.
5. Add the required attribution wherever a source's data is shown.

Do not scrape TankPuls anonymously at 15-minute full-Germany scale. It breaches their AGB §10.

## Effort
- Emails: about 1 hour.
- Change-tracking and sanity guards: a few days. They reuse the existing trust-guard flags.
- Adding a new source as an alt reading: small if it returns JSON.
- MTS-K onboarding: unknown. It is certificate-based DATEX II XML (snippet-level only), about 14.5k stations to parse.

## Risks
- A 6 to 12 month approval can also be refused or revoked if the rules are broken.
- Single-person upstreams: Tankerkönig, TankPuls and kraftstoffbilliger.
- ANWB provenance and licence are unknown.

## Unknown or unverified
- **Q2 2027 date:** not found on any page. The creativecommons page says registration is paused for maintenance. The onboarding page appeared to show an open form. The live state is unclear.
- **Tankerkönig AGB:** the PDF text was read by one researcher and was unreadable for the verifier. The "no passing on datasets" clause is unconfirmed, and it sits in tension with CC BY 4.0 on the licence page.
- **Other unknowns:**
  - ANWB's German source and terms.
  - MTS-K price timestamps and latency in practice.
  - Whether a non-German applicant is accepted.
  - Mobilithek mechanics (push or pull, certificates).
  - TankPuls and Tankerkönig prices, and whether a TankPuls free Community key exists.
  - The terms of kraftstoffbilliger and benzinpreis-aktuell.
- **Not searched:** data.europa.eu, state portals, and the Mobilithek catalogue in a real browser.

## Other items from the request
- **Italy and Romania:** this memo does not cover them. The research only noted that TomTom lists both, and that fuel-prices.eu station data covers Italy and Romania but needs its Pro plan. Quality was not checked.
- **Vehicle:** "Santa Fe MX5" is most likely a typo. The pasted data shows a 2025 Hyundai Santa Fe plug-in hybrid (petrol 1.6 L, 72 kW electric motor, 54 km WLTP electric range, 1.7 l/100 km WLTP weighted). Route planning needs to price petrol and electricity separately for it.

## Addendum 2026-11-06 (afternoon): Tankerkoenig replied
Reply from Hermann Kurz, Tankerkoenig UG (received 2026-11-06 11:47 CET). It corrects the research above:
- Registration is NOT paused: free keys via https://onboarding.tankerkoenig.de/ (the "paused" text on the creativecommons page was stale).
- Free API: 25 km radius and 1 request/minute per key are imposed by the Bundeskartellamt; bulk access to master or price data for all stations is not permitted on the free API. Over the limit: HTTP 503, then a one-hour IP block. No availability guarantee.
- Commercial API (contract, no rate limit or radius limit, ZIP and radius search, history, averages, access to a Git repository with historical data): regular EUR 200/month; first 2 months free; special low-traffic rate EUR 50/month; the regular tariff only applies above 10,000 search requests (radius < 25 km) per day; cancellable at the end of any month. A dedicated server is possible at a price depending on needs.
- Their offer is conditional on the owner accepting and receiving a contract.

Open questions to ask before signing: may prices be republished in our public per-country JSON with attribution (redistribution/caching terms); what counts as "low traffic"; does the commercial API give a full-Germany snapshot (bulk) or only many radius queries, and how many requests a 15-minute full cover needs; Bundeskartellamt VID status of Tankerkoenig for this use; data licence for the history repository.
