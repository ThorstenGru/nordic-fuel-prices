# Tank sizes of the EEA top-100 petrol and diesel models (2026-11-26)

Researched from manufacturer documents only (press kits, technical data sheets, handbooks, price lists). Aggregator sites (auto-data.net, ADAC, ultimatespecs, cars-data, autotijd) were excluded because their terms forbid copying. Values are for the usual version of each model; other versions can differ by several litres (`tank_min` / `tank_max`). Only **high** and **medium** confidence is stored in `tools/vehicles/tank_sizes.json` and shown in the picker; the driver can always change the value.

- Models researched: 161 (200 catalogue ids). Stored: 149 ids. Not stored: 44 models (no manufacturer value found, or confidence low).
- Confidence: high = manufacturer data sheet read for a clear version; medium = manufacturer page or search excerpt of it, version less clear; low = unclear version or generation (not stored).
- Several manufacturer sites (Mercedes, Opel/Stellantis, Ford, Audi/BMW PDFs) returned 403 to the researchers: those values come from search excerpts of the official pages, not from a document that was opened.

## Not stored (to research again later, ideally by hand from the manufacturer's own sheet)

| Make | Model | Found value | Confidence | Note |
|---|---|---|---|---|
| Audi | A1 Allstreet |  | none | No Audi data sheet for allstreet found; A1 Sportback is 40 l but not confirmed for allstreet |
| BMW | 116D |  | none | No current-generation BMW sheet found for 116d |
| BMW | 118D |  | none | Official sheets found conflict (42/50/52 l, older generations); unresolved |
| BMW | 118I |  | none | No official 118i sheet for current generation found (only third-party 49 l) |
| BMW | 218D Active Tourer |  | none | No explicit 218d U06 sheet found; 218i U06 is 45 l |
| BMW | 218I | 51 | low | 218i Coupe (G42) sheet 06/2024, figures 51/52 hard to assign; model could also be Active Tourer |
| Citroen | C3 Origin Blue HDI 100 S&S 6V Plus | 42 | low | Old C3 BlueHDi 100: UK guide 42 l (column mapping unclear); handbook says 42 or 50 |
| Citroen | Spacetourer |  | none | No Citroen source with Spacetourer tank volume found |
| DS | DS4 | 53 | low | BlueHDi 130 EAT8; only seen in search snippet, page not read |
| DS | DS7 | 55 | low | BlueHDi 130; only seen in search snippet, page not read |
| Fiat | 500X |  | none | No official page readable (Stellantis blocks fetch) |
| Fiat | Tipo |  | none | No official source found |
| Ford | Kuga | 54 | low | Petrol/hybrid 54 L, PHEV 42.7 excl.; only from search snippet (PDF blocked) |
| Ford | Tourneo Connect |  | none | Official sheets unreadable/conflicting |
| Ford | Tourneo Courier |  | none | Official page has no figure |
| Ford | Tourneo Custom | 55 | low | EcoBlue diesel std 55 L (70 L option); snippet only (PDF blocked) |
| Ford | Transit |  | none | No official figure found |
| Ford | Transit Custom | 55 | low | EcoBlue diesel std 55 L (70 L option); snippet only (PDF blocked) |
| Jeep | Avenger |  | none | Only e-Hybrid 44 L found; petrol not found |
| Jeep | Compass |  | none | Only US 2026 model found; no EU figure |
| Mercedes-Benz | B 180 D |  | none | B-Class: only petrol 43 L found on Mercedes UK, no diesel value |
| Mercedes-Benz | B 200 D |  | none | B-Class: only petrol 43 L found on Mercedes UK, no diesel value |
| Mercedes-Benz | CLA 180 D |  | none | No diesel tank figure found; new CLA has no diesel |
| Mercedes-Benz | CLA 200 D |  | none | No diesel tank figure found; new CLA has no diesel |
| Mercedes-Benz | CLA 220 D |  | none | No diesel tank figure found; new CLA has no diesel |
| Mercedes-Benz | Citan TOURER/T-CLASS |  | none | Mercedes site pages gave no tank figure (403/none) |
| Mercedes-Benz | GLB 200 D 4MATIC | 52 | low | UK page gives 52 L for diesel section; 4MATIC not named explicitly |
| Mercedes-Benz | GLB 220 D 4MATIC |  | none | No diesel 220 d 4MATIC tank figure found (hybrid page shows 60 L, not diesel) |
| Mercedes-Benz | Sprinter |  | none | Tank options 50-93 L (93 L RWD only); no clear base variant |
| Omoda | OMODA5 |  | none | Only third-party sites found (51 l); no manufacturer page retrievable |
| Opel | Astra | 52 | low | ICE/MHEV per Opel price list 2026; seen in search excerpt only (PDF 403) |
| Opel | Astra Sports Tourer | 52 | low | ICE/MHEV per Opel price list 2026; PHEV 42 excl.; search excerpt only |
| Opel | Combo Life |  | none | No retrievable Opel source |
| Opel | Corsa |  | none | Opel page range 40-44 l; base variant unknown; search excerpt only |
| Opel | Corsa GS 1.2T XHL MT6 S/S 100 CV (74KW) |  | none | Corsa range 40-44 l; specific variant unknown; search excerpt only |
| Opel | Crossland | 45 | low | Opel page lists 45 l; search excerpt only (page 403) |
| Opel | Grandland | 55 | low | New gen hybrid 55 l; older ICE price list 2024 said 53; search excerpt only |
| Opel | Mokka |  | none | Opel page range 41-44 l; base variant unknown; search excerpt only |
| Peugeot | 408 |  | none | No 408 handbook/spec found |
| Renault | Megane | 50 | low | Owner manual Megane IV: petrol ~50 l, 4-door diesel 49, 5-door/estate diesel 45 |
| SEAT | Leon SP | 45 | low | Assumed Leon Sportstourer/Estate; hatch list 45 l; 4Drive diesel may be 55 l |
| Volkswagen | Arteon | 66 | low | Swedish brochure 66 l; engine mapping unclear |
| Volkswagen | Caddy | 50 | low | UK Caddy Life brochure 50 l; engine mapping unclear |
| Volkswagen | Kombi | 55 | low | T6.1 Transporter diesel std 55 l; 63/70 l options |
