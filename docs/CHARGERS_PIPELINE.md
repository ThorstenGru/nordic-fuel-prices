# Charger pipeline: data/ev_<cc>.json (2026-11-07)

Backend for the "Chargers + typical prices" feature (Type 2 AC, Santa Fe PHEV). Design and measurements: `CHARGER_DATA_DESIGN_2026-11-07.md`. Code: `src/chargers.py`, tests `src/tests/test_chargers.py` (no network). No web/ code is touched by this step.

## What it does

- Countries: SE, NO, DK, DE. One OCM call per country (`connectiontypeid=25,1036`, compact, `maxresults=100000`, header `X-API-Key`), 1.5 s apart, plus one `referencedata` call per run for operator names and licence text.
- Filter, in order: keep Type 2 connectors (25, 1036) not marked not operational/planned/removed; drop private usage (2, 3, 6); drop station status 100/150/200/210; drop provider 26 (Oplaadpalen.nl, NonCommercial); dedupe within 30 m (richer record wins, points = max, never the sum).
- Optional NOBIL merge for SE/NO (see below). Stations outside the country box are dropped and counted.
- Cadence: no scheduler. The step runs on every scrape run but is cheap: it re-publishes the previous file (local `data/ev_<cc>.json`, else the live site) and calls the APIs only when `generated` is more than 6 days old. `FORCE_REFRESH=1` (the workflow "force" input) or `--force` overrides.
- Last-good retention: a refresh that fails or is refused keeps the previous file and stamps `attempted` with today's date, so a persistent failure retries once a day, not every 15 minutes. A second workflow step curls the live file back if the run produced none.
- Refused (previous file kept): no usable answer; count outside the band (SE 2000-12000, NO 1500-4000, DK 1000-4000, DE 10000-40000); fewer than 80% of the previous count; more than 2% of stations outside the country box; any key string present in the output; NOBIL configured but unusable (fewer than 500 stations).
- Nothing prints a URL or an exception text (both can contain a key). Tests assert the key is absent from the file.

## Schema (v1)

```
{"v":1,"cc":"SE","generated":"2026-11-07","source":"ocm"|"ocm+nobil",
 "sources":["OCM","NOBIL"],                       // providers present in the file (short names, for the UI)
 "attribution":["Open Charge Map contributors ... (CC BY 4.0 unless stated)","NOBIL (NOBIL by Enova ... CC BY 4.0)", ...],
 "medVerified":2024, "n":3185, "dropped_outside_box":0,
 "ops":["Circle K","E.ON Drive", ...],           // operator display names, index 1..n, 0 = unknown
 "s":[[lat5,lon5,opIdx,kW,points,flags,verifiedYY,"title"], ...],
 "notes":[[stationIdx,"cost text, cut to 80 chars"], ...],
 "attempted":"2026-11-14"}                        // only present after a refused refresh
```

kW = max Type 2 kW rounded (0 unknown). Flags (bitmask): 1 free (source text says free and holds no other number), 2 membership/charging card needed, 4 notice required, 8 pay at location, 16 parking-fee text hint (weak), 32 cost note in `notes` (verbatim, unverified), 64 only tethered Type 2 (own cable not needed), 128 NOBIL says parking fee. `verifiedYY` is the two-digit year of the last verification (OCM) or update (NOBIL): show "verified 2024", never "available". The client computes staleness from `generated` (older than 21 days: "not updated since <date>").

No OCM id, no NOBIL id or `International_id`, no raw NOBIL attribute and no key is written. Operator names go through a small alias table (`ALIAS` in `chargers.py`, for example "Incharge (SE)" and "Vattenfall InCharge" both become "Vattenfall InCharge") so the later price table has one key space; extend it when the price table is written.

## Sizes (live run 2026-11-07, OCM only)

| | Stations | Raw | gzip -9 | Notes |
|---|---|---|---|---|
| SE | 3,185 | 179 KB | 64 KB | 69 cost notes |
| NO | 2,197 | 127 KB | 46 KB | 3 provider-26 stations dropped |
| DK | 1,851 | 102 KB | 34 KB | 314 duplicates merged, 16 provider-26 dropped |
| DE | 16,753 | 954 KB | 324 KB | 2,257 duplicates merged, 297 provider-26 dropped |

Counts equal the design doc (SE 3,185 matches exactly). With NOBIL merged, SE/NO will differ (more stations, operators and parking flags).

## Run locally

```
set OCM_API_KEY=...            (never write it into a file or a log)
set NOBIL_API_KEY=...          (optional)
python src/chargers.py            # all four, only the ones older than 6 days
python src/chargers.py SE --force # one country now
```
Output goes to `data/ev_<cc>.json` (gitignored like the other data files). Tests: `cd src; python -m unittest tests.test_chargers -q`.

## Owner steps

1. `OCM_API_KEY` is already a GitHub secret. Nothing else is needed for the OCM-only files.
2. Optional, SE/NO only: request a NOBIL key (https://info.nobil.no/api, see `NOBIL_TEST_2026-11-06.md` section 3), add it as secret `NOBIL_API_KEY`. Without the secret the job runs OCM-only and says nothing. Before the first NOBIL-derived publish, write to NOBIL about republishing a derived file (their API terms: internal use, data must be processed or cached by an intermediate service; this job is that service and publishes only the reduced tuples).
3. First deploy: the files appear after the first scrape run following the push (no previous file exists, so every country is due). To force a later refresh run the workflow with "force".

## Not verified

- The NOBIL parsing follows the v3 documentation and has never seen a live response (no key). Unverified assumptions: `chargerstations[].csmd/attr.st/attr.conn` layout, connector value 32 = Type 2, `Position` as "(lat,lon)", availability attribute 2 value 1 = public, parking-fee attribute 7 value 1 = yes, station-status attribute 21 text for closed stations, kW read from the capacity text, and the id used for matching (`id` or `International_id` digits against the digits of OCM `DataProvidersReference`). A wrong guess degrades to "no match" (position match within 30 m, then NOBIL-only stations), and an unreadable answer keeps the last good file. Check the first NOBIL run log lines (`NOBIL {...}`, `merge {...}`): `matched` near the OCM provider-19 count means the id guess is right.
- The workflow YAML was not executed; indentation was checked by eye only.
- OCM rate limits are unpublished; one call per country per week was well within what was observed (22 calls in the design and live runs, no 429).
