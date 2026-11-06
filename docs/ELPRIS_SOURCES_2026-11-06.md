# Electricity price sources, research 2026-11-06

Scope: free, keyless, legally usable day-ahead prices per Nordic price area, how to compute monthly averages, forward-price options, and a recommended data design for `data/elpris.json`.

Label key: **[opened]** = fetched/called by me today (2026-11-06); **[search]** = only seen in a search result snippet, not opened; **[not verified]** = could not confirm.

## 1. Verdict

| Need | Source | Verdict |
|---|---|---|
| SE1-SE4 day-ahead, history, tomorrow | elprisetjustnu.se API | Use. Keyless, CORS open, history to at least 2022-01-01, 15-min since 2025-10-01. Terms are informal (see 2.1). |
| DK1/DK2 | Energi Data Service (Energinet) | Use. Keyless, CC BY 4.0, commercial use allowed. Anonymous rate limit is strict (HTTP 429 hit within 2-3 calls). |
| DE-LU | SMARD.de (Bundesnetzagentur) via Energy-Charts | Probably CC BY 4.0 [not verified for DE-LU, see 2.5]. |
| NO1-NO5, FI | Energy-Charts API | Do NOT use: response carries "private and internal use only". Use ENTSO-E (token) instead. |
| Any zone, official | ENTSO-E Transparency | Usable with a free token; reuse terms not opened [not verified]. |
| Nord Pool direct | Data portal | Paid (EUR 1,200+/yr), redistribution extra. Do not use. |
| SE4 forwards | Euronext Nord Pool / EEX | Not freely usable as far as found. Use seasonal estimate instead. |

## 2. Sources in detail

### 2.1 elprisetjustnu.se (primary for SE)
- Docs: https://www.elprisetjustnu.se/elpris-api **[opened]**.
- Pattern: `GET https://www.elprisetjustnu.se/api/v1/prices/{YYYY}/{MM}-{DD}_{SE1|SE2|SE3|SE4}.json`. One file per day per area **[opened, called]**.
- Shape **[opened, called]**: array of `{SEK_per_kWh, EUR_per_kWh, EXR, time_start, time_end}`; ISO 8601 with offset (+01:00/+02:00). Prices ex VAT, no taxes. EXR is the daily EUR/SEK rate.
- Resolution **[called]**: 2022-11-01 and 2025-09-30 files have 24 hourly rows; 2026-09-15 and 2026-11-06 files have 15-minute rows (docs: 96/day from 2025-10-01). September 2026 SE4 = 2,880 rows (30 x 96).
- CORS **[called]**: `access-control-allow-origin: *`, `cross-origin-resource-policy: cross-origin`, `Cache-Control: public, max-age=604800`, served by Cloudflare. Browser fetch works directly, but a pipeline copy is preferred (section 5).
- History depth **[called]**: HTTP 200 for 2022-01-01, 2022-01-05, 2021-12-01, 2021-12-31, 2022-03-01, 2022-10-01 (24 rows each); HTTP 404 for 2021-06-01. The docs text says history only up to and including 2022-11-01, which is ambiguous; in practice data reaches back at least to 2021-12-01. Earliest exact day not pinned down. Plan for 2022-01-01 onward (3 full years plus 2026 YTD already gives 4 seasons).
- Terms **[opened]**: described as open and free; source is ENTSO-E, FX from exchangeratesapi.io; "prices may differ slightly from official figures". Attribution is requested, not required: "Elpriser tillhandahålls av Elpriset just nu.se". No formal licence text, no rate limit stated. Operator: Beneficial Apps AS. Risk: informal terms, single hobby-scale operator; keep attribution and cache aggressively.
- Gotcha: a plain urllib request without User-Agent returned 404/blocked-looking failures for me; curl and urllib with a custom User-Agent work. Send a descriptive User-Agent from the pipeline.
- Gotcha: tomorrow's file appears around 13:00 CET; before that it is absent (not tested today). Cached 7 days, so the pipeline must not cache a 404.
- Alternative proxy api.elpris.eu **[called, terms opened]**: independent non-commercial project aimed at Shelly devices, explicitly gives no re-use guarantees. Do not depend on it.

### 2.2 Does the history match Skelleftea Kraft "Medelspotpris"? (SE4, ex VAT, SEK/kWh)
I downloaded all daily SE4 files and computed the plain arithmetic mean of every price row in the month **[called]**:

| Month 2026 | Invoice | Simple mean (API) | Diff |
|---|---|---|---|
| Sep | 1.20202 | 1.20125 | +0.00077 |
| Aug | 0.80466 | 0.80452 | +0.00014 |
| Jul | 0.8644 | 0.86483 | -0.00043 |
| Jun | 1.03723 | 1.03715 | +0.00008 |
| May | 0.9464 | 0.94613 (1-31 May) | +0.00027 |

Findings:
- A simple, equal-weight mean over the whole calendar month fits to within 0.001 SEK/kWh in all five months. Variants that would differ materially do not fit: May from 7 May gives 1.0050, from 8 May 0.9867, from 15 May 0.9510. So the invoice "May" value is the full-month average, not 7-31 May, even though billing started 7 May.
- The residual (under 0.1 percent) is consistent with small data differences between the API's ENTSO-E/Nord Pool values and the retailer's own source, or rounding. A volume-weighted mean (by the whole area's load) would be expected to differ by several hundredths in a month with strong daily price shape; I could not test it (no load series), but the near-exact fit makes it the unlikely choice. Conclusion: use the simple time-weighted mean (each 15-minute or hourly slot equal weight). Since hourly months and 15-minute months both cover equal time per slot, averaging rows per month is consistent across the 2025-10-01 resolution change.
- The invoice number is ex VAT; the API is ex VAT, so no conversion.

### 2.3 Energi Data Service, DK (Energinet)
- Terms: https://www.energidataservice.dk/terms-and-conditions **[opened]**: CC BY 4.0, commercial use permitted, attribution required ("Source: Energinet (www.energidataservice.dk)"), no warranty, no availability guarantee. IP addresses stored 3 months.
- API **[called]**: no key. Dataset `Elspotprices` (DK1/DK2, hourly) ends 2025-09-30 (last record seen 2025-09-30 23:00); new dataset `DayAheadPrices` (15-minute, fields TimeUTC/TimeDK) is live. Response headers include `Access-Control-Allow-Origin: *`, `RemainingCalls`/`TotalCalls`. My repeated calls got `429 Rate limit is exceeded` after about 3 requests in a minute, so use one request per area with a date range, from a scheduled job only, never per visitor.
- Field names of `DayAheadPrices` beyond the time fields were not inspected [not verified].

### 2.4 ENTSO-E Transparency Platform
- Security token required **[search only]**: register on the platform, e-mail transparency@entsoe.eu with subject "Restful API access", then generate the token in account settings. Third-party wrappers report a one-year limit per request and about 400 requests/minute [search only].
- Official guide URL (https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html) returned HTTP 400 to my fetch tool, so reuse/redistribution terms are **[not verified]**. The token is a secret: it can live as a GitHub Actions secret in the pipeline, never in `web/`.
- Role: the upstream of elprisetjustnu.se; the fallback if that site disappears, and the route for NO1-NO5 and FI (document type A44, zone EIC codes). Needs the owner to request a token.

### 2.5 Energy-Charts (Fraunhofer ISE)
- `https://api.energy-charts.info/price?bzn=...` **[called]**, keyless. The licence text is returned inside each response and differs by zone:
  - SE4 response: "CC BY 4.0 ... from Bundesnetzagentur | SMARD.de".
  - FI and NO1 responses: "private and internal use only ... external or commercial purposes is expressly prohibited".
- So only zones whose response says CC BY may be redistributed. I did not get DE-LU's licence text (HTTP 429 after a few calls); SMARD.de is normally CC BY 4.0 but **[not verified]**. Zone code format is `NO1`, not `NO-2`. Rate limiting is aggressive.
- Note the SE4 CC BY line looks like a mislabel (SMARD covers DE/neighbours); do not rely on it for Sweden when elprisetjustnu.se exists.

### 2.6 Nord Pool official data portal
- https://www.nordpoolgroup.com/en/services/power-market-data-services/dataportalregistration/ **[opened]**: annual subscriptions, SOLO EUR 1,200, LITE 2,200, PREMIUM 4,500, ENTERPRISE 9,000, ex VAT; no free tier listed; a redistribution fee may apply on top under the Euronext Group data agreement. Search snippets mention redistribution licences from EUR 3,500-5,500/year **[search only]**. Conclusion: not usable for a free public app. Note this is also the legal reason to prefer ENTSO-E-derived sources (public under EU transparency rules) over scraping Nord Pool's own site.

### 2.7 Svenska kraftnat
- Not researched in depth: I did not find or open a keyless day-ahead price API from SvK, and SvK publishes system/market statistics rather than a per-area price feed. **[not verified]**. Not needed given 2.1.

## 3. Months-ahead prices (SE4)
- Nasdaq Commodities has exited: pages state trading/clearing ceased 30 April 2026 **[search only]**, https://www.nasdaq.com/european-market-activity/commodities/market-prices. The business moved to Euronext Nord Pool Power Futures from 2026-03-16 (System Price and EPAD futures) **[search only]**; EEX lists zonal Nordic futures including SE4 (underlying: EPEX day-ahead baseload) **[search only]**, https://www.eex.com/fileadmin/EEX/Markets/Power_Derivates_Market/Power_Nordics/2026_06-17_Nordic_Power_Presentation_Website.pdf.
- Euronext Nord Pool page **[opened]**: https://www.nordpoolgroup.com/en/trading/euronext-nord-pool-power-futures-market/ does not name SE4, does not state any free delayed data, and points contract specs to an account-only portal.
- Statement: I found no free, legally redistributable SE4 forward/EPAD price feed. Do not use one. Market data of this kind is normally a paid licence; treat as not freely usable.
- Recommended substitute (matches owner decision): seasonal estimate = for target month M, the mean of month M in the past 3-4 complete years for the area (2022-2025, optionally 2026 when complete), with a band from min and max (or the 25th and 75th percentile if 4+ years). Caveat to show in the UI: 2022 was an extreme crisis year (SE4 autumn/winter very high), so a band is wide; consider weighting recent years higher or showing the median. Label clearly as an estimate, not a forecast.

## 4. Computing monthly averages
- Per area: arithmetic mean of `SEK_per_kWh` over all rows with `time_start` in the month, local (Europe/Stockholm) month boundaries. Equal weight per slot (see 2.2). Keep `n` rows so partial months can be flagged.
- Do not use volume weighting (needs load data that is not freely redistributable and does not fit the invoice).
- Also store EUR mean for foreign areas, and per-month `hours_covered` to detect gaps.
- Cost of backfill: 1 request per day per area. 2022-01-01 to now is about 1,770 days x 4 areas = about 7,100 small requests, one time. Do it once from a developer machine or one manual workflow run with a 0.2-0.5 s delay and a User-Agent, then commit the result. Daily jobs afterwards need 2 requests per area.
- Verification already done: the same computation reproduces the owner's five invoice values (2.2). Add that as a test fixture (SE4 May-Sep 2026, tolerance 0.002).

## 5. Recommended data design
Pipeline script `src/elpris.py` (stdlib only), run from `.github/workflows/scrape.yml` on a schedule (for example 13:30 and 15:00 UTC-based cron to catch the post-13:00 CET publication, plus one nightly run), writing `data/elpris.json`:

```
{
  "updated": "2026-11-06T13:35:00Z",
  "source": "elprisetjustnu.se (ENTSO-E)",
  "areas": {
    "SE4": {
      "slot_min": 15,
      "today":    {"date": "2026-11-06", "sek": [..96 numbers..]},
      "tomorrow": {"date": "2026-11-07", "sek": [..] } | null,
      "monthly":  {"2022": [12 numbers or null], "2023": [...], "2024": [...], "2025": [...], "2026": [... to current month, partial flagged]},
      "seasonal": {"1": {"mean": 0.0, "lo": 0.0, "hi": 0.0}, ... "12": {...}}
    }
  }
}
```
Design notes:
- SEK ex VAT, 5 decimals max; round to 4 to save bytes. EUR is derivable with the day's EXR if a foreign area needs it; keep `eur` arrays only for DK/others.
- Size budget: today+tomorrow 2 x 96 values x 4 areas x about 7 bytes = about 5 KB; monthly 4 years x 12 x 4 areas = 192 values = under 2 KB; seasonal under 2 KB. Total about 10 KB per area set (about 12 KB gzip-friendly JSON), fine for a single static file. Keep full per-day history out of the repo; only monthly means are persisted. If hour-of-day profile is wanted for charging-window advice, add a 24-value mean-profile per area per season (about 1 KB).
- Monthly history is append-only: the script recomputes only the current and previous month each run, and rebuilds fully if a month is null. Past months frozen once complete.
- Failure handling: if tomorrow's file is 404, keep `tomorrow: null`; never overwrite good data with an empty fetch; keep last-good `updated` timestamp so the UI can show staleness. Do not cache 404s.
- Other countries: DK via Energi Data Service `DayAheadPrices` (CC BY 4.0, one ranged request per area per run). NO1-NO5, FI, DE-LU only after the owner obtains an ENTSO-E token (store as secret `ENTSOE_TOKEN`); until then those countries get no electricity price and the UI says so. Do not use Energy-Charts for NO/FI.
- Attribution in the app footer/privacy page: "Elpriser: Elpriset just nu.se (ENTSO-E)"; "Source: Energinet (www.energidataservice.dk)".
- Browser must read only the repo's own `data/elpris.json` (same origin), so CSP needs no new `connect-src` for price sources. Open-Meteo for temperature is a separate direct call and does need `connect-src https://api.open-meteo.com`.

## 6. Home tariff formula check
Marginal price incl VAT = (spot + variable) x 1.25 + 0.773 SEK/kWh, checked with the stated numbers: ((spot + variable) + 0.06 markup - 0.06 discount) x 1.25 + (0.2584 + 0.36) x 1.25 = (spot + variable) x 1.25 + 0.773. The markup and discount cancel, 0.6184 x 1.25 = 0.773. Consistent. Grid subscription 656 SEK/month ex VAT is a fixed cost, excluded from marginal price (owner to verify the figure). Discount applies only until 2027-05-31; after that the effective constant becomes +0.075 ex VAT (+0.06 markup, 0 discount) i.e. 0.848 SEK/kWh incl VAT, so the model needs a `valid_until` on the discount.

## 7. Not done / risks
- elprisetjustnu.se earliest available date and tomorrow-file-before-13:00 behaviour not pinned down.
- ENTSO-E official terms, DE-LU Energy-Charts licence, SvK feed, and Euronext/EEX market-data terms not opened or confirmed.
- elprisetjustnu.se has no formal licence; continuity depends on one small operator. ENTSO-E token is the contingency.
