# Data accuracy notes, 2026-11-05

Factual findings from today's review, and the policy agreed with the owner. Nothing here changes a price.

## 1. Sweden: ANWB petrol slots depend on the brand

ANWB reports two petrol slots for Sweden. Their levels differ by brand (live data, 2026-11-05):

| ANWB slot | Brand | Stations | Median (SEK) | Observation |
|---|---|---|---|---|
| 98 | OKQ8 / IDS | 233 | 15.55 | Exactly 15.55 on all of them; resembles a regular 95 level |
| 98 | ST1 | 71 | 17.67 | Single value; resembles a genuine 98 |
| 95 | Preem / Circle K / Ingo | about 330 | 17.3 to 17.9 | About 1.5 SEK above bensinpriser.nu's regular-95 level (about 15.6 to 16.3) |

The bensinpriser.nu E10 median is 15.64 SEK. Reproduce the table with `tools/analysis/i_se_anwb_slots_by_brand.py <folder with se.json>`.

**Ground-truth data point (owner, at the pump):** ST1 Loddekopinge, 95 E10 = 15.64 SEK. In our live data this station (`se_xavvy_M_SWE_2078103`, ANWB) has only a diesel price (22.54 SEK) and no petrol 95 from any source.

**Decision:** the ANWB slot mapping is unchanged. More pump prices are needed before a brand-aware mapping can be justified.

## 2. Italy: stale since 2026-10-16

The mimit.gov.it CSV downloads time out from GitHub runners. `asyncio.TimeoutError` has an empty message, so the log showed only the URL. The pipeline correctly kept the last good data (status `stale`). The scraper now logs the exception type and elapsed time per attempt (for example `TimeoutError after 90s`). No source switch was made, and the official Osservaprezzi app API is deliberately not used.

## 3. Differences between ANWB and other sources

Median of (other / ANWB - 1) on the same station, as observed today:

- SE diesel: +5.1 % (n=111)
- GB E10, retailer feeds vs ANWB: +8.8 % to +12.4 %
- DK diesel: +2.2 % to +8.7 %
- FI: -3 % to -8 %

These are differences between sources, not statements about which is right. They are now published per country as `source_gap` in `meta.json` and `health.json` (entries with at least 30 differing station pairs). Only stations where the two sources differ by 2 % or more are recorded, so the median is the gap among differing stations, not across all co-covered stations; agreeing stations are not counted. Regulated-maximum and flagged primary prices are excluded, and alt readings more than 2x apart are dropped as likely mislabelled slots.

## 4. Policy agreed with the owner

- ANWB is not demoted. It matched the official ES, PT, SI and FR feeds to the cent in October 2026.
- Crowd-sourced bensinpriser.nu (grade D) is not treated as ground truth.
- Source gaps are reported neutrally ("sources differ by", among differing stations), and disagreeing prices stay visible.
- The Swedish slot mapping stays as is until more pump prices are available.
