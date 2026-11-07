# AC charging tariffs (web/ac_tariffs.json)

Hand-kept, dated list of operators' public AC (Type 2, up to 22 kW) list prices for the "Chargers + typical prices" feature (Santa Fe PHEV, 3.6 kW, price and surcharges matter, speed does not). Same pattern as `docs/FARES.md`. Not verified data: every entry has `check_operator: true` and the UI must say "check operator". Seen 2026-11-07.

## Rules
- A price goes in only if it was read on an opened operator or official tariff page. Otherwise `ac: null` and `notes` says why. Search snippets and third-party roundups (Hurbra etc.) never count.
- `ac.adhoc_kwh` is the no-subscription price ('from' price where the page says so, `adhoc_kwh_max` for a range). `member_kwh` needs registration, an app or a subscription, with `member_label` and `subscription_needed_for_member`.
- `start_fee` / `idle_fee` null means "not stated on the page read". The UI must say "not published", never "none". `idle_fee.unit` is "unspecified" when the page does not say per minute or per session.
- `match.ocm_names` are exact Operator titles from the OCM reference data (verified 2026-11-07 with the local key, 19 names). `match.nobil_names` are unverified hints: no NOBIL call has been made.
- Prices include VAT. Entries older than 90 days grey out (same rule as fares).
- Roaming prices (operator A's app at operator B's charger) are not recorded as the AC tariff of A.

## Read on 2026-11-07 (10 entries with an AC price)
| Entry | AC ad hoc | Member / note |
|---|---|---|
| Mer SE | 6.00 SEK | Flexible 5.60 (subscription) |
| Mer NO | 4.99 NOK (under 50 kW) | same for drop-in and registered |
| E.ON Drive SE | from 4.95 SEK | Member 4.45 (app), campaign to 2026-12-31 |
| E.ON Drive DK | from 3.25 DKK | blocking fee 2 DKK after 240 min |
| E.ON Drive DE | from 0.58 EUR | blocking fee 0.10 EUR after 240 min, unit unspecified |
| Recharge SE | 5.79 SEK | Move (79 kr/month) applies to fast only |
| Recharge NO | 5.99 NOK | activation mode not stated |
| Recharge DK | 3.79 DKK | activation mode not stated |
| Allego DE | 0.48 to 0.60 EUR | by location |
| Aral pulse DE | 0.59 EUR | Klassik 0.47 (registration); no blocking fee at own chargers |

## Not verified (price null)
- Allego SE/DK/NO: three "kr" columns, country assignment only by order, so not recorded.
- EnBW DE: tariff tiles are images. Roaming 56 to 89 ct and blocking fee 10 ct/min after 240 min (cap 12 EUR) were read.
- Circle K SE: own network DC only on the page. Vattenfall InCharge SE: no tariff published (app only). Clever DK: dynamic, app only. Eviny NO: no prices on page (only a 2022 news item, not used). Monta: platform, host sets price.
- OKQ8 SE and Shell Recharge DE: page fetch returned only a title (likely script-rendered). Re-read in a browser.
- Not attempted or not found: Spirii (guessed URL 404), Fortum Charge & Drive (now Recharge, OCM name "Recharge (Formerly Fortum Charge & Drive)"), Norway Fortum/Eviny AC list, Tesla (DC, skipped), municipal operators and German Stadtwerke typical ad hoc prices (no primary source read; OCM has many "Stadtwerke ..." operator names, so the UI should show "price not published" for them).
- A caveat for the UI: E.ON, Allego and Aral figures are 'from' or ranges and can differ per site.

## Refresh routine (about every 60 days)
1. `node tools/check_ac_tariffs.js` lists stale entries and schema errors (`--today YYYY-MM-DD` to test ahead).
2. Open each `source`, update figures, `notes`, `seen_on`. Fill the null entries by hand in a browser.
3. Re-run the check and `node tools/test_*.js`.
4. When the app loads this file, bump its cache-version constant (the service worker serves `?v=` URLs cache-first), as for fares.
