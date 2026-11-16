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
