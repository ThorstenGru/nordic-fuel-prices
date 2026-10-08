# Data accuracy findings — 2026-10-08 (frontend stress test, v1.16.0)

Found while stress-testing the frontend against the live data (snapshot of all 45 country files, meta v1.15.0, 123,169 stations).
Reproduce with the scripts in `tools/analysis/` (each takes the folder with the downloaded `<cc>.json` + `meta.json`).

## 1. ANWB petrol slots are mislabelled for some countries (pipeline: `src/scrapers/_anwb.py`, `src/plausibility.py`)

| Where | Evidence | Script |
|---|---|---|
| **SE** (home market) | ANWB "95" median 16.78 kr vs 18.74 kr from bensinpriser.nu (dated, tight band 18.5–18.8). ANWB "98" median 15.65 kr is **below ANWB's own 95** and equals the E85 level (15.69). The 12 cheapest Swedish 95 prices in the data are all ANWB, undated, 13.9–14.3 kr. Diesel agrees (22.71 vs 22.39), so only the petrol slots are wrong. | b, c |
| **SK / EE** | On the same station 98 is cheaper than 95 for **78 % (SK) and 68 % (EE)** of stations that have both. | c, d |
| **GB** | Of 119 stations where ANWB's "98" can be compared with the retailers' own prices, **71 equal the retailer's regular 95 (E10) price to within 0.5 %** and none equal its 98. ANWB's UK petrol slot (bucketed P98, ~5,000 prices) is largely 95-octane. | e |
| FI | ANWB 95/diesel are 5–8 % below the two dated crowd sources on the same stations (not conclusive which is right). | b |
| CH | 9 % of stations have 98 < 95 (probably stale per-fuel updates). | d |

The existing plausibility rules (EUR band, ±60 % of country median, diesel/petrol ratio) have **no octane-order check and no source-bias check**, so none of this is flagged.

### Recommended pipeline changes (not done yet)
1. `plausibility.py`: flag a station's 98 price when it is cheaper than its own 95 by > 0.5 % (reason `octane_order`); flag a whole (country, source) 98 slot when its median is ≤ that source's 95 median (SE/anwb, SK, EE today).
2. `_anwb.py`: GB — ANWB petrol is regular 95, not 98; either map it to P95/E10 or drop ANWB petrol where retailer feeds exist. SE — do not publish ANWB petrol next to bensinpriser.nu (or correct the slot mapping once the cause is known).
3. Country statistics (`stats_eur`, Prices tab, the opening badge) should be computed over trusted prices only: Sweden's published 95 median is 1.602 EUR (17.93 kr) but the verified median is 1.67 EUR (18.74 kr).

## 2. What the frontend does about it now (v1.16.0)
Headline claims ("Cheapest here", "Best price nearby", "Worth the drive") and the opening-badge average ignore *unverified* prices: an undated/old price cheaper than the 5th percentile of the country's fresh dated prices (only where ≥ 15 % of prices are dated), any price > 20 % below the country median, and the 98 slot of a source whose 98 median ≤ its 95 median. Those prices stay visible, marked "?", grey on the map, and the claim says how many were set aside. This is a mitigation; the root cause is the pipeline.

## 3. Checked and fine
- IDs all carry their country prefix, no duplicates, no non-numeric / non-positive prices, no future timestamps.
- Prices-tab medians (`stats_eur`) match a recomputation from the raw files exactly for all 36 euro-zone country/fuel pairs; implied FX is identical for petrol and diesel in every non-euro country (script h).
- Gaps: Moldova has no `stats_eur` (no EUR rate), so it cannot be ordered in EUR; Romania only has the counties scraped so far (west of lon 22 is empty).
