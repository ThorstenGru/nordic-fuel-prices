# ANWB as a data source: rating and cross-checks (2026-11-16)

Grade in code: C (aggregator, no price timestamps), confidence 0.80-0.85. Own rating by measurement, not by assumption:

| Country | Reference | Result | Rating |
|---|---|---|---|
| DE | Tankerkoenig (MTS-K), 54k checks | 95.5 % within 1 ct | B- |
| AT | e-Control (statutory), 3.4k checks | 53 % within 1 ct, p90 8 ct, petrol median +1..3 ct | C- |
| DK | OK feed (diesel, n=700) / Shell (diesel, n=221) | 97 % / 90 % within 1 % | diesel B-; petrol not conclusive (only 14 / 7 pairs; Shell petrol differs by -13.6 %, cause not found) |
| SE | bensinpriser.nu (crowd) | ANWB median +1.9 % on diesel (2 % within 1 %), +10.5 % on petrol (n=10) | open: which side is stale is not known |
| FI | polttoaine.net | 17 matched stations only | no verdict |
| others | EU Weekly Oil Bulletin, national level only | within the +-10 ct noise band that official sources show too | C, unverified |

Source order: unchanged. Where a second source with timestamps exists (DK chains, FI, SE, UK) it already wins and ANWB (priority 9) fills gaps; the measurements do not justify swapping that. Re-run `tools/anwb_crosscheck.py` to repeat the Nordic comparison.

## Follow-up the same day: why DK and SE petrol looked odd

- The first petrol figures were partly a measurement error: 98-octane (typed E5) was compared with 95. Fixed in `tools/anwb_crosscheck.py`.
- ANWB lists 95 petrol for only 567 of 2,167 Danish stations (diesel for 2,047); where both exist they agree (15.893 vs 15.89 DKK). ANWB Sweden lists mostly 98 (318) and 95 (298).
- Real finding: in several countries ANWB gives ONE price per chain, not per station. Share of ANWB stations that sit at their brand's most common diesel price (brands with 15+ stations, 2026-11-16): DE 17 %, CH 7 %, NL 15 %, FI 3 % (per station); DK 61 %, SE 57 %, NO 65 %, BE 69 %, HU 62 %, IE 67 %, PL 44 %, EE 77 %, LV 87 % (chain list price).
- Sweden example: ANWB shows 21.593 SEK diesel and 17.039 for 98 at every St1; the crowd source has 20.39-21.29 at the same stations. List price versus real pump price: ANWB runs about 2 % high there.

## Chain-price flag (built 2026-11-16)

`src/chain_price.py` (called from `main.py` after cleaning) sets `chain_price = true` on a station when its ANWB price (no timestamp) is the most common one of its brand (brand with >= 15 stations, >= 50 % at that price). The app shows a note on the station sheet (`chainPrice`, 5 languages). Prices with timestamps or from other sources are never flagged. Run `python src/chain_price.py data` to see the share per country.

Share of ANWB-priced stations flagged (2026-11-16): AL 100, MK 97, LV 90, RS 85, LU 82, SK 75, CZ 73, EE 69, BE 59, LT 57, HU 54, NO 48, DK 44, SE 40, IE 39, AD 28, BA 23, PL 20, CY 17, BG 5, GB 2; none in DE, CH, NL, FI, GR, LI, MC, ME, MT. Luxembourg, Albania and Macedonia have regulated or capped prices, so a shared price there can be the legal price rather than a list price; the note is worded neutrally ("probably the list price").
