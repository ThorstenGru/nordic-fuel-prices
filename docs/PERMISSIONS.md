# Source permissions (status 2026-11-07)

Status of the right to reuse each source. "Granted" is the EuroFuelPrices owner's statement of 2026-11-07. Details of licences are in `LICENCE_OUTREACH.md`, `REGULATORY_REPORTING.md` and the per-source docstrings.

| Source | Country | Status | Note |
|---|---|---|---|
| hintatutka.net | FI | **Granted** by the site owner (2026-11-07) | Keep the attribution "Hintatutka.net". Code: `src/sources/fi_hintatutka.py` |
| ANWB POI API (unofficial feed) | many, fallback | **Granted** (2026-11-07) | Still unofficial and undocumented; can change without notice. Code: `src/scrapers/_anwb.py` |
| peco-online.ro | RO | Not asked | Default Romanian source. Answers 403 from some networks |
| monitorulpreturilor.info | RO | **Pending / not asked** | Used only with `ROMANIA_SOURCE=official\|both`, see `ROMANIA_SETUP.md` |
| MIMIT (osservaprezzi) | IT | Not asked | Official open dataset; reuse terms not confirmed in writing |
| fuel-prices.eu | IT (fallback; other markets possible) | **Granted in writing (owner holds the reply, 2026-11-11)** | Station API `/live/api.php?action=stations`, max 100 per call; credit "Data: fuel-prices.eu, CC BY 4.0" with link next to the data; station data keep the source licence (IODL 2.0 for IT); User-Agent names us; one crawl a day, ~1.5 req/s |
| Tankerkoenig free API | DE | Pending | Free API terms limit use (1 request per minute, 25 km); test mode only. Commercial API unsigned, see `TANKERKOENIG_SETUP.md` |
| bensinpriser.nu via henrikhjelm.se | SE | Not asked (mail drafted) | Community data, no published terms, see `LICENCE_OUTREACH.md` |
| fuel-prices.eu | GR (locations) | Open | CC BY 4.0, no key |
| fuelGR-scraper | GR | Removed 2026-11-07 | No licence; code deleted |
| data.economie.gouv.fr | FR | Official / open | Licence Ouverte 2.0, attribution |
| Other official government feeds (ES, PT, AT, SI, HR, LU, ...) | | Official / open | Per-country terms in `REGULATORY_REPORTING.md`; not individually confirmed in writing |
| OpenStreetMap (Overpass) | locations | Open | ODbL, attribution |
