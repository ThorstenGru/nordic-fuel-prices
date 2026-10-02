# Which governments force fuel stations to report prices, and how fast

**EuroFuelPrices - regulatory research memo**
Legal facts as of **2026-10-01** (verification pass); document written 2026-10-02.
Scope: EU/EEA, UK, Switzerland, microstates, Western Balkans, Moldova, Turkey, Ukraine.

Why this matters: the owner's rule is "data is king, and government sources are the most reliable". A government source is only *structurally* trustworthy when a law forces every station to report, sets a short deadline, and attaches penalties. Where there is no such duty, any price we show is crowd-sourced or commercially aggregated, and the UI must say so.

## How to read this document

Every claim carries a confidence tag. They come from the independent verification pass over the original researcher drafts (the `reg-*.verify.json` files, `final` arrays), not from the drafts.

| Tag | Meaning |
|---|---|
| **[P]** | Primary-confirmed: the verifier read the statute, ordinance, gazette or regulator's own page directly. |
| **[S]** | Secondary-reported: news, legal blogs, industry or aggregator sites; not read in the primary legal text. |
| **[U]** | Unverified: could not be confirmed either way. Never repeat as fact. |

"Duty class" values used below, taken from the verified data:

- **Statutory real-time**: each station (or its price-setting company) must report each price change within a fixed short window, or at least on every change.
- **Statutory daily-or-slower**: a duty to report exists, but the cadence is daily, weekly or monthly, or only distributors report.
- **Regulated price (periodic)**: the *government* calculates or sets a maximum price. Stations do not report; they must stay at or below the ceiling. Sometimes a small set of wholesalers or operators report to the government.
- **None**: no duty found. **Unknown**: could not be established.

A note on the raw `reliability_rank` fields in the source files: they mix "how useful is the data" with "how sure are we of the finding" (for example Malta is rank 1 because its "no duty" finding is well confirmed; Ireland is 5). **They are not comparable across files, so this document does not reuse them.** The ranking below is our own, built from duty class, deadline, openness of the published data, and confidence.

---

## 1. Executive summary

**Only a handful of countries combine a hard statutory per-station duty with government-published open data. These are our gold-standard sources.** Ranked for EuroFuelPrices (best first):

| Rank | Country | Why it ranks here |
|---|---|---|
| 1 | **France** | Prices must be declared and displayed "immediately" (Arrete 2006, Art. 5); ~10-minute open flux; Etalab 2.0 licence, commercial reuse allowed, no key or registration. Caveats: outlets selling under 500 m3/yr are exempt; station brand/name is withheld. [P] |
| 2 | **Germany** | The hardest legal deadline in Europe: **5 minutes** per price change (MTS-K, Bundeskartellamt), 14,000+ stations (near-census). But the data reaches the public only through approved resellers (mainly Tankerkonig): free key, ~1 request/min, 25 km radius, attribution, no petroleum-industry use; commercial or high-volume use needs a paid contract. [P] |
| 3 | **United Kingdom** | Statutory since 2 Feb 2026: **30 minutes**, every station, no small-business threshold, turnover-based fines plus criminal offences. API ~5 min latency. Needs free registration with the government's aggregator (VE3 Global); final open licence terms not confirmed. [P] |
| 4 | **Spain** | Weekly plus on every change (price submitted 1 h to 3 days before it takes effect). Open unauthenticated REST API, ~11,500 stations. Caveats: no per-station timestamp, reuse terms only "conditional", and the ministry server resets connections from our GitHub runners. [P] |
| 5 | **Denmark** | New: real-time website plus public API duty for every sales location above 250 m3/yr since **1 Jan 2026**. Verified directly, but the data is per-operator and no single central licence was found. [P] |
| 6 | **Greece** | Declare immediately on any change; unchanged prices must be re-declared at least every **30 days** (relaxed from 7 in Sept 2025). Open data under CC BY 4.0 on fuelprices.gr and data.gov.gr. [P] |
| 7 | **Italy** | Duty is real-time (on change, and at least weekly), and the dataset is open (IODL 2.0), but it is **published once a day by 08:30**, so latency can approach 24 h. "Gold duty, silver latency." [P] |

**Silver tier** (statutory duty exists but we cannot get timely, open, per-station data): Austria (30-minute duty, but only a restricted public comparison tool), Portugal (price data licence forbids commercial use), Cyprus (access by request), Lithuania (daily 10:00 collection, open-data status unverified). Bulgaria and Romania have statutory reporting duties whose data is not published at all.

**Nothing to rely on from government:** Sweden, Norway, Finland, Iceland, Estonia, Latvia, Netherlands, Belgium, Switzerland, Ireland, Malta, San Marino, Bosnia, Ukraine (no duty); Liechtenstein and Monaco (unknown). In **Sweden and Norway the authorities actively *ban* chains from publishing list prices**, so the home market has no official feed and none is on the horizon.

**A large second group publishes a government-set price ceiling, not station prices:** Luxembourg, Slovenia, Croatia, Poland, Czechia, Slovakia, Hungary, Serbia, Montenegro, North Macedonia, Albania, Kosovo, Moldova, Belgium. These are useful as a sanity bound ("no station may charge more than X") but are not station prices.

**EU level:** no EU law requires petrol-station price reporting. The Weekly Oil Bulletin carries national averages only.

**Do not repeat the verifier-overturned claims:** see section 3.4 (for example the German fine is up to EUR 1,000,000 or 10% of group turnover, not EUR 100,000; Greece's no-change renewal is 30 days, not 7).

---

## 2. Master table

Sorted by our ranking, grouped by source grade (G1 to G5, see section 5.3). "Deadline" is the statutory time slice. "Latency" is how stale the *published* data can be.

### 2.1 Grade G1 - statutory real-time duty plus open government data (gold)

| # | Country | Duty? | Legal basis | Authority | Reporting deadline / time slice | How published | Latency | Licence and commercial reuse | Access | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **FR** | Yes - statutory real-time | Arrete 12 Dec 2006 amending Arrete 8 Jul 1988; **Art. 5** (declare + immediate display), **Art. 6** (exempt below 500 m3/yr). Art. 3 is a different, highway-presignalling duty. | DGEC / Ministere de l'Economie (portal); DGCCRF (enforcement) | Any change "immediatement"; changes may be pre-scheduled with exact effective date/time | XML/ZIP open-data flux: instant (~10 min), daily, annual, archives since 2007; brand/name withheld | ~10 min; daily archive ~05:00 | Licence Ouverte / Etalab 2.0; commercial **yes** | None; free, no registration | **[P]** |
| 2 | **DE** | Yes - statutory real-time | **Sec. 47k GWB** + **Sec. 4(2) MTSKraftV** (22 Mar 2013, last amended 6 May 2024); fine basis Sec. 81(2) Nr. 5b + Sec. 81c GWB | Bundeskartellamt (MTS-K) | **Within 5 minutes** of any change (Super E5, E10, Diesel). Since 1 Apr 2026, increases allowed only once per day at 12:00 (KPAnG Sec. 2) | Only to approved consumer-information services via Mobilithek; redistributed as JSON/CSV (Tankerkonig) | Minutes | Tankerkonig real-time CC BY 4.0; historical CSV CC BY-NC-SA 4.0. Commercial: **conditional** | Free Tankerkonig key; ~1 req/min, 25 km radius, attribution; petroleum industry excluded; high-volume/commercial = paid contract | **[P]** |
| 3 | **GB** | Yes - statutory real-time | **Motor Fuel Price (Open Data) Regulations 2025, SI 2025/1356**, reg. 9(2); penalties reg. 19; offences reg. 26. Enabling powers: Data (Use and Access) Act 2025 ss.4, 5, 7, 8, 10, 18, 19, 21(1) (**not** s.22) | CMA (enforcement); DESNZ (policy); VE3 Global (aggregator) | **Within 30 minutes** of a change; every motor fuel trader, no threshold. Registration 18 Dec 2025; reporting live 2 Feb 2026 | API feed + twice-daily flat file | ~5 min (API); up to 12 h (flat file) | Government intends OGL or equivalent; **final terms not confirmed**. Commercial: yes (as intended) | Free registration with aggregator | **[P]** |
| 4 | **ES** | Yes - statutory real-time | **Orden ITC/2308/2007**, Arts. 3, 5, 6.1, 19 (BOE-A-2007-14592); technical annexes updated by BOE-A-2025-25592 (5 Dec 2025) | MITECO (Geoportal Gasolineras); CNMC (oversight) | Every Monday **plus** on every change, submitted at most 3 days and at least 1 h before it takes effect | Unauthenticated REST API (JSON/XML); also datos.gob.es | ~5 min auto-refresh reported by secondary sources **[S]**; no per-station timestamp in payload | Standard Spanish reuse terms (keep meaning, cite source, state date); no formal CC licence confirmed. Commercial: **conditional** | No key. Our CI runners get "Connection reset" (audit) | **[P]** |
| 5 | **DK** | Yes - statutory real-time | **BEK nr 1351 of 21 Nov 2025** inserting **Sec. 16a** in the Prismaerkningsbekendtgorelse (BEK 1696/2017); issued under Sec. 37(10) Markedsforingsloven; EU basis Directives 98/6/EC and 2019/2161 | KFST (Konkurrence- og Forbrugerstyrelsen) | **Real-time on every change**, for each sales location above **250 m3/yr** of petrol+diesel; 5-year retention. List-price ban from 1 Dec 2025; Sec. 16a from **1 Jan 2026** | Each operator's own website **and** a public API per KFST guidance (16 Dec 2025) | Near zero by design | No single central licence found; operator terms not reviewed. Commercial: **conditional** | No registration mentioned. Per-company endpoints | **[P]** (penalty clause: moderate confidence) |
| 6 | **GR** | Yes - statutory real-time | **Law 4177/2013**; **YA 91354/2017 Art. 114**; YA 106242/2022; **YA 71645/17.9.2025** (FEK B 5099/25-9-2025) | Ministry of Development; DIMEA (enforcement) | Immediately on every price change. **Corrected:** if unchanged, re-declare at least every **30 days** (was 7) | fuelprices.gr + data.gov.gr dataset | Near-real-time | **CC BY 4.0**; commercial **yes** | Public, no registration | **[P]** (EUR 10,000 / EUR 1,000 fine tiers **[U]**) |
| 7 | **IT** | Yes - statutory real-time | **D.L. 5/2023 art. 1** (conv. L. 23/2023); D.M. 31 Mar 2023; in force 24 Jul 2023 | MIMIT (Osservaprezzi Carburanti); Prefetti and Guardia di Finanza enforce | On every change (before or at the same time) and **at least weekly** even if unchanged | CSV dataset, daily | **Published daily by 08:30** | **IODL 2.0**; commercial **yes** | No registration | **[P]** |

### 2.2 Grade G2 - statutory duty, but publication restricted, slower, or licence-limited (silver)

| # | Country | Duty? | Legal basis | Authority | Deadline / time slice | How published | Latency | Licence and commercial reuse | Access | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 8 | **AT** | Yes - statutory real-time | Sec. 1a Preistransparenzgesetz; **Preistransparenzverordnung Treibstoffpreise 2011** (BGBl II 246/2011, as amended through 320/2025; valid to 31 Dec 2028); Standesregeln (BGBl II 484/2010) for the 12:00 rule | E-Control (Preistransparenzdatenbank); BWB (weekly tracker) | **Within 30 minutes** of a change (Diesel, Super 95/E10). Increases only at 12:00; decreases any time. The temporary Mon/Wed/Fri-only rule (16 Mar - 12 Apr 2026) has lapsed | E-Control comparison tool deliberately limited to the cheapest nearby stations; BWB weekly Spritpreistracker (since May 2026). Audit found a keyless `api.e-control.at/sprit/1.0` returning ~713 stations (~32% of ~2,200 estimated) **with no timestamps** | Unmeasurable (no time field in schema) | Licence **[U]**; commercial unknown | No key found in audit | Duty **[P]**; publication/licence **[U]** |
| 9 | **PT** | Yes - pre-notification | **Decreto-Lei 243/2008** (exact article **[U]**) | DGEG | Communicate to DGEG **before** the new price applies, with exact day and hour. The oft-quoted "24 h" is unconfirmed | precoscombustiveis.dgeg.gov.pt; separate station-location dataset on dados.gov.pt | Per-station latency unconfirmed; daily average statistic | **Prices: commercial use prohibited.** Locations: CC BY 4.0 (High-Value Dataset) | Free browsing | **[S]** |
| 10 | **CY** | Yes - statutory (cadence unclear) | **Law 152(I)/2002**: Art. 3 (duty, 5/30-day categories), Art. 5 (content), Art. 8 (penalties); K.D.P. 166/2015 | Energy Service / Consumer Protection Service (MECI) | Unresolved: official page says "continuous"; one secondary source says once each morning | XML API on request, ~300 stations, 5 fuels | **[U]** | **CC BY-SA 4.0**; commercial **conditional** (share-alike) | By request to meci.gov.cy | **[S]** |
| 11 | **LT** | Yes - daily (2026) | Order Nr. 1-52 of 25 Feb 2011 **[P]** (weekly, operators with >5 stations, EU bulletin); **new daily order in force 8 Apr 2026, order number [U]** | Lietuvos energetikos agentura (LEA) | Each working day, prices in effect at **10:00**, collected by 10:00; A95, diesel, LPG | LEA website/price map; "Atviri duomenys" link not verified | Same day | **[U]** | Public viewing; API unresolved | **[S]** (LEA's own page confirms the mechanism) |

### 2.3 Grade G3 - statutory duty, data not published (not usable directly)

| # | Country | Duty? | Legal basis | Authority | Deadline / time slice | How published | Latency | Licence | Access | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | **BG** | Yes - real-time, but for tax control | **Ordinance N-18 of 13.12.2006**, Art. 3(3), 7(3); strengthened by amendment DV issue 42 of 23.05.2025 | NAP (National Revenue Agency) | Every sale in real time via fiscal device; tank-level data ~6-hourly **[U]**; fiscal device must alert if link down >15 min **[U]** | Not published; NRA says it will publish daily average prices under a 2026 compensation scheme **[U]** | Real-time internally | n/a | None | **[S]** for article text; amendment existence **[P]** |
| 13 | **RO** | Yes - **monthly** (crisis law) | **Lege 162/2026** (MO 642 of 4 Aug 2026, in force 7 Aug 2026), Art. 15; predecessor OUG 19/2026 | Consiliul Concurentei, Min. Finantelor, ANPC, Min. Energiei | Monthly report within 20 days of month-end, "including data on prices charged"; ad hoc requests within 10 days. Retail price may rise once per day, until 12:00. Crisis runs to 31 Oct 2026, extendable | Not published. Voluntary **monitorulpreturilor.info** shows real per-station prices for participating chains only | Near-real-time (voluntary only) | Voluntary platform: commercial **no** | Web/app only; no API found | **[P]** |

### 2.4 Grade G4 - government-set maximum price (a ceiling, not station prices)

| # | Country | Duty? | Legal basis | Authority | Deadline / time slice | How published | Latency | Licence | Access | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|
| 14 | **LU** | Reverse: government fixes the max price | Loi du 30 juin 1961 (price-regulation power) + "contrat de programme" with GEML/FESS/GCSL; current text **[U]** | Min. Energy/Economy; Administration de l'energie; STATEC | Ceiling revised several times a week when volatile **[S]**, no statutory cadence confirmed | STATEC series "Prix maxima" on data.public.lu (uData API). Separate Ministry dataset: monthly national averages | Monthly/annual in the dataset, not live | **CC0**; commercial **yes** | No key | **[S]** |
| 15 | **SI** | Reverse | Zakon o kontroli cen (UL RS 51/06) + periodic Uredba; extended in June 2026 to **2026-12-15** | Government; Ministry of Infrastructure / Environment, Climate and Energy | Ceiling recalculated **weekly** (was 14 days, changed end-March 2025) | energetika-portal.si; Uradni list | Applies at start of each week | **[U]** | Public page | **[S]** |
| 16 | **HR** | Reverse (regulation re-imposed 2026) | Zakon o trzistu nafte, cl. 9(2) + Uredba (NN 24/26 of 10 Mar 2026; NN 95/26 of 28 Aug 2026; later ones) | Vlada; MINGO | Operators submit calculation one working day before. Cycle **reported as 7 days** from 29 Sep 2026 (MINGO), earlier 14 days; **exact instrument in force on 2026-10-01 not pinned [U]** | Narodne novine; government releases | Day before application | n/a | Public | **[S]** |
| 17 | **PL** | Reverse + wholesale reporting | **Art. 34a**, Act of 16 Feb 2007, inserted by Act of 27 Mar 2026 (Dz.U. 2026 poz. 599) | Minister for energy raw materials; KAS enforces | The **five largest** wholesalers report their wholesale price **each business day by 09:00**. Max retail = prior-day average wholesale + excise + fuel levy + PLN 0.30/l. Fine up to **PLN 1,000,000** | Obwieszczenie in Monitor Polski | Next calendar day | **[U]** | Gazette, free | **[P]** |
| 18 | **CZ** | Reverse | **Zakon c. 63/2026 Sb.** (in force **13 May 2026**; first price order ~20 May); government may set a **maximum only** (Sec. 2) | Ministry of Finance / government | Ministry announces the max price **every working day for the next day**; October 2026 margin CZK 2.50/l | Cenovy vestnik (PDF); mf.gov.cz | Same/next working day | **[U]** | Free | **[P]** (CZK 3M/5M fines **[S]** only) |
| 19 | **SK** | Reverse (margin cap) | **Vyhlaska MF SR c. 237/2026 Z.z.**, in force **1 Oct 2026**, supersedes 43/2026; margin cap EUR 0.10/l, standard STN EN 228/590 fuels only | Ministry of Finance; SOI enforces | No proactive reporting; inspection ex post (3-year price-formation records, Act 18/1996) | slov-lex.sk | n/a | **[U]** | Free | **[S]** (title/date **[P]**; penalty **[U]**) |
| 20 | **HU** | Reverse; narrow reporting | **Govt Decree 50/2026 (III.9.)**, companion 52/2026; Sec. 10/A | NAV | Sec. 10/A reporting (T+1 by 12:00) applies to the party handling **strategic-reserve fuel** under 52/2026 Sec. 3(4) and its wholesale resellers, **not to every station**. Fines HUF 100,000 - 150,000,000 by tier | Not published; NAV monthly average table | n/a | n/a | None | **[P]** |
| 21 | **RS** | Reverse | Uredba o ogranicenju visine cena derivata nafte (periodically renewed); current number/expiry **[U]** | Min. of Internal and Foreign Trade; Min. of Mining and Energy | Reported: wholesale price to Trade ministry by 13:00 Friday, ceiling published by 15:00 Friday **[U]** | Ministry site (unreachable in verification) | Same day | n/a | Public | **[S]** |
| 22 | **ME** | Reverse | Law on Energy + government decisions; "Regulation 40/26" **[U]** | Ministry of Energy and Mining | Recalculated weekly since 24 Mar 2026 (was fortnightly) **[S]** | Decree / press release | Same day | n/a | Public | **[S]** |
| 23 | **MK** | Reverse | ERC **Rulebook**, Decision 01-1055/1 (24 Apr 2020), OG 108/20 and 133/20 | ERC | Every **Monday**, effective **Mon 00:01** (Art. 6); Platts FOB-Med 7-day average; **no company self-reporting** | ERC decision in Official Gazette + website | Same/next working day | none | Public | **[P]** |
| 24 | **AL** | Reverse, intermittent | Council of Ministers decision reactivating the "Transparency Board"; VKM number **[U]** | Bordi i Transparences | Irregular; 2026 reactivation framed around monitoring an excise cut | Press/government announcements | Same day | none | Public | **[S]** |
| 25 | **XK** | Reverse | Administrative Instruction on regulating fuel prices (MINT, now "MINTI"); number/date **[U]** | MINTI "Department for Oil Market Regulation" (**not** ERO) | Reissued ad hoc | Announcements | Same day | none | Public | **[S]** |
| 26 | **MD** | Reverse | Legea 461/2001 (amended by Legea 54/2021); ANRE Hotarare 254 of 14.06.2021 | ANRE | Ceiling announced effectively daily, ~14-day Platts average **[S]**; not re-verified (source blocked) | ANRE releases | n/a | **[U]** | Public | **[S]** |
| 27 | **BE** | **None** for stations; ceiling set | 1945 law + historic "contrat de programme" (max price); RD 13 Apr 2019 and 9 Dec 2021 only mandate **in-station display** | SPF/FOD Economie | Next day's max price announced the evening before; stations may undercut freely | Industry sites mirroring the calculation (energiafed.be) | Daily | **[U]** | Public | **[S]** |
| 28 | **TR** | Distributors only, next-day effect | **Petrol Piyasasi Fiyatlandirma Sistemi Yonetmeligi**, OG 27024 of 14 Oct 2008, Art. 11 | EPDK (EBIS system) | Price-list change takes effect the **day after** notification | EPDK site; no API confirmed | Next day | **[U]** | Public | **[P]** |
| 29 | **EU** | National averages only | Council Decision 1999/280/EC (see section 4) | European Commission (DG ENER) | Wednesday submission, Thursday publication | XLSX/PDF + email subscription | ~1 day | **[U]**; open-data listing **not confirmed** | Free subscription | **[S]** |

### 2.5 Grade G5 - no duty, or unknown (crowd or commercial only)

| # | Country | Duty? | What the law actually does | Authority | Official feed | Confidence |
|---|---|---|---|---|---|---|
| 30 | **SE** | **None** | Prisinformationslagen (SFS 2004:347) governs forecourt signage only. Separate annual fuel-volume/GHG report to Energimyndigheten (not prices). Konkurrensverket: Circle K, OKQ8, Preem committed (decision 2 Dec 2024, binding 3 years) to stop publishing recommended/list prices; breach = SEK 100M fine per company | Konkurrensverket; Konsumentverket | None | **[P]** |
| 31 | **NO** | **None** | Konkurransetilsynet **bans** Circle K, YX and Uno-X from publishing indicative list prices: Vedtak V2025-14 (14 Oct 2025, renews V2020-27), runs to 15 Oct 2030, konkurranseloven Sec. 6(2). NOU 2025:11 has no fuel-reporting proposal | Konkurransetilsynet | None | **[P]** |
| 32 | **FI** | **None** | KKV blog says mandatory reporting to authorities "could be considered" (framed as a possibility, not a bill). KKV is collecting hourly/daily chain data in 2026 for a research study; legal basis (compulsory or voluntary) **[U]** | KKV | None (Traficom tool is informational) | **[P]** |
| 33 | **IS** | **None** (temporary) | Law (Thingskjal 1055, 607. mal): VAT cut 24% to 11% on listed fuel codes, **1 May - 31 Aug 2026**, Samkeppniseftirlitid pass-through oversight with fining power; not a reporting regime | Samkeppniseftirlitid | None (gasvaktin.is / bensinverd.is are volunteer-run) | **[P]** |
| 34 | **EE** | **None** | Konkurentsiamet's 2024 market analysis **recommends** legally required real-time price display; not enacted | Konkurentsiamet | None | **[P]** |
| 35 | **LV** | **None** | Competition Council urges a German/Austrian-style statutory system; a different Cabinet bill (solidarity payment, approved 14 Apr 2026) was rejected in the Saeima committee | Konkurences padome; PTAC | None | **[S]** |
| 36 | **NL** | **None** | CBS weekly national average from commercial Travelcard BV data (table 80416NED, Thursdays, prices through Monday). Parliament (Apr 2026) asked the cabinet to study a price cap / German-style one-increase-per-day rule; nothing enacted; motion number **[U]** | CBS; ACM | National weekly average only | **[S]** |
| 37 | **CH** | **None** | Preisuberwachungsgesetz has only reactive, general powers. 2022-23 bills for an Austrian-style platform failed (National Council rejected 2 Mar 2023, 95-81). No revived bill found, but Curia Vista not checked directly | Preisueberwacher; WEKO | None (private TCS portal) | **[P]** |
| 38 | **IE** | **None** | "PumpWatch" mandatory-reporting call by a backbench TD (9 Mar 2026) is a political proposal, no bill. CCPC investigated 900+ complaints (report 9 Apr 2026): no breach found | CCPC | None | **[S]** |
| 39 | **MT** | **None** | REWS caps only the retail mark-up over Enemed's wholesale price. Confirmed by reading REWS's decision-notice list | REWS; Enemed | Enemed price page (not a dataset) | **[P]** |
| 40 | **SM** | **None** | Only temporary excise-relief decree-laws (D.L. 39/2026 of 20 Mar 2026, extended to 31 Oct 2026). Outside EU/EEA | Congresso di Stato | None | **[S]** |
| 41 | **BA** | **None** (prices) | FBiH Law on Oil Derivatives (OG 52/14) Art. 15 requires only monthly/annual **quantity** data. No equivalent price duty identified for Republika Srpska | FERK / RERS | None | **[P]** |
| 42 | **UA** | **None** (standing) | Antimonopoly Committee uses ad hoc powers (March 2026: networks had 3 days to explain price rises and supply cost data) | AMKU | None | **[S]** |
| 43 | **AD** | **None confirmed** | IPE portal (sig.govern.ad) appears to be an administrative/sector arrangement. Temporary 2026 relief law (approved 14 Jul 2026, in force 15 Jul - 30 Sep 2026, Butlleti 056/2026) obliges importers/distributors to certify rebate pass-through (not station prices) | Govern d'Andorra | Web portal, no dataset or licence | **[S]** |
| 44 | **LI** | **Unknown** | Only a generic price-display ordinance (LGBl 1996/142) and Swiss customs-union context; gesetze.li not browsable (TLS error). An official llv.li "Treibstoffpreise" page exists but was behind a bot challenge and unread | Amt fur Volkswirtschaft | Possibly (unread) | **[U]** |
| 45 | **MC** | **Unknown** | No Monaco-specific law found; prices track France via the 1963 customs convention; ~6 stations; unclear whether stations fall under France's declaration system | none identified | None | **[U]** |

---

## 3. Notes on tricky cases

### 3.1 Regulated-price countries (the duty runs the other way)

In these markets the government *sets or calculates a ceiling*; stations do not file prices. The ceiling is a national single number (per fuel), not a station price.

- **Luxembourg**: a "contrat de programme" fixes a maximum; almost all stations sell at the ceiling, so one STATEC/ministry number is a decent proxy for every station. STATEC's CC0 dataset is a monthly/annual statistical aggregate, **not** a live feed of each ministerial order. The enabling law (30 Jun 1961) was corroborated only through search-index hits and later decrees citing it; the current contract text was not read **[S]**.
- **Slovenia, Croatia, Serbia, Montenegro, North Macedonia, Moldova**: weekly or near-daily ceilings calculated from Platts benchmarks. North Macedonia's rulebook is the only one read in full **[P]**.
- **Croatia** needs care: the government *deregulated* on 14 Jul 2025, then re-imposed regulation (NN 24/26 from 10 Mar 2026; NN 95/26 of 28 Aug 2026), and government releases dated 29 Sep 2026 describe a **7-day** cycle. A direct Narodne novine lookup for the instrument in force on 2026-10-01 is still outstanding.
- **Poland** is the odd one: stations do not report, but the five largest wholesalers must report daily by 09:00 and the minister publishes a ceiling in Monitor Polski. This is an emergency mechanism tied to the March 2026 price spike, not a permanent register; the fate of the older "centralny rejestr cen paliw" idea is **[U]**.
- **Czechia and Slovakia**: daily (CZ) or standing (SK, EUR 0.10/l margin cap from 1 Oct 2026) margin regulation. Penalty figures for SK are **[U]**, for CZ **[S]**.
- **Hungary**: the reporting duty in Decree 50/2026 Sec. 10/A is narrow (strategic-reserve fuel and its resellers), not a blanket station duty.
- **Belgium**: despite being a ceiling country, there is **no** station reporting duty; stations may sell below the maximum with no disclosure obligation. **Do not assume Belgian stations charge the ceiling.**
- **Albania and Kosovo**: intermittent, discretionary mechanisms; legal citations are missing.
- **Austria and Germany add a second rule on top of the reporting duty**: price *increases* only once a day at **12:00** (AT: since 2010/11 under the Standesregeln; DE: KPAnG since 1 Apr 2026). Romania (until 12:00) and Lithuania (10:00-to-10:00 window, cabinet-endorsed but **not yet law**) are moving the same way. Decreases remain unrestricted everywhere.

### 3.2 Countries with NO duty (SE, NO, NL, BE, CH and others) - what that means for us

- There is no government feed and none is imminent. All prices for these markets are **crowd-sourced or commercially aggregated** and must be labelled as such (section 5.3).
- **Sweden and Norway go the opposite way**: competition authorities restrict public price information. In Sweden the three largest chains (Circle K, OKQ8, Preem) are bound by commitments (decision 2 Dec 2024, three years, SEK 100M fine per company) to stop publishing recommended/list prices. In Norway the equivalent prohibition (V2025-14) runs to 15 Oct 2030. Expect **thin official-chain data for the home market for years**; do not plan around a Swedish government API.
- Sweden's only legitimate price signal remains crowd/owner-submitted data (bensinpriser.nu, which itself shows each report for at most 3 days and disclaims accuracy) plus whatever the chains still show. Audit evidence: our current parser drops all of it and only ~20% of Swedish stations carry a crowd price even when parsed correctly (see the data-source audits).
- **Netherlands**: CBS gives only a weekly national average from Travelcard fuel-card data; useful as a sanity check, not a station price.
- **Switzerland**: consumer transparency rests on the private TCS portal. Parliament rejected a mandatory scheme in March 2023 on the strength of that portal; no revival found.
- **Pending legislation worth watching** (none enacted, all **[S]** unless stated): Finland (KKV "could consider" mandatory reporting [P]), Estonia (regulator recommendation [P]), Latvia (regulator urges German/Austrian model), Lithuania (one-increase-per-day, cabinet-endorsed), Ireland ("PumpWatch", no bill), Netherlands (motions to study a cap), Hungary (7 Sep 2026 press report of a Fidesz-KDNP bill to make the price cap permanent **[U]**), Switzerland (none found). Denmark (Jan 2026) and the UK (Feb 2026) show that the wave is real and recent; the verified Latvian regulator quote explicitly cites Germany and Austria as models.

### 3.3 Duty exists but the data is not for us

- **Bulgaria**: real-time sales and tank-level transmission to NAP, built for VAT-fraud control; not public.
- **Romania**: monthly statutory reports to four authorities; only a voluntary, chain-limited consumer site exists (commercial reuse "no").
- **Austria**: the strongest *duty* in the German-speaking world, deliberately paired with a restricted public view ("cheapest nearby" only, to limit upward price signalling). Audit-found API covers only ~32% of stations with no timestamps.
- **Portugal**: statutory pre-notification, but the price data's own terms forbid commercial use.

### 3.4 Corrections: where verifiers overturned the researchers

These corrections are authoritative. Earlier drafts and any notes derived from them should be updated.

| Country | Draft said | Verified correction |
|---|---|---|
| **DE** | Failure to report fined up to EUR 100,000 | **EUR 1,000,000** for a natural person (Sec. 81c(1) GWB), up to **10% of worldwide group turnover** for an undertaking (Sec. 81c(2)). EUR 100,000 is the *separate* KPAnG Sec. 3 cap for breaking the once-daily-noon rule. Full uninterrupted read of Sec. 81(2) and 81c(3)/(4) still advisable before citing publicly |
| **AT** | Only the first "Spritpreisbremse" | Added: an "erweiterte Spritpreisbremse" (Nationalrat 28 Sep, Bundesrat 29 Sep 2026): extra tax cut up to 6.7 ct/l plus a new 3.5 ct/l margin cap, **October-November 2026**, effective 1 Oct 2026. Does not change the reporting duty. BGBl number not yet located |
| **LU** | No open licence or bulk feed | STATEC "Prix maxima" dataset **exists on data.public.lu under CC0** (uData API, last synced 30 Sep 2026), but it is a periodic aggregate, not live |
| **LI** | (unknown) | Still unknown; extra circumstantial evidence only |
| **FR** | Art. 3 and 5 as the declaration duty; Art. 7 = E85 timing; amended 7 Apr 2009 | **Art. 5 and Art. 6 are confirmed.** Art. 3 is a separate highway-presignalling duty. "Art. 7 = E85" **[U]** (possible renumbering). The 2009 amending instrument may be 18 Mar 2009 rather than 7 Apr 2009 **[U]**. The "~48 h disappearance of undeclared prices" claim is also **[U]** |
| **ES** | RD-ley 7/2026 "tightens Geoportal monitoring" | **False.** RD-ley 7/2026 (20 Mar 2026, BOE-A-2026-6544) is a temporary VAT cut (21% to 10%, 21 Mar - 30 Jun 2026) plus a hydrocarbons-tax reduction. BOE-A-2025-25592 changes only the technical annexes |
| **PT** | Licence conflict (commercial prohibited vs CC BY 4.0) | Not a conflict: CC BY 4.0 applies to the **location** dataset; the **price** data on the DGEG portal prohibits commercial use |
| **NL** | Unconfirmed 2026 parliamentary motion | Confirmed as an event (debates 31 Mar/1 Apr and 22-23 Apr 2026, majority motions asking the cabinet to study a cap and a German-style daily-increase limit); nothing enacted; motion number **[U]** |
| **AD** | BOPA citation missing | Law approved 14 Jul 2026, Butlleti del Consell General 056/2026 (24 Jul 2026); BOPA number still missing |
| **HR** | 14-day cycle; status "pending/unclear" | Regulation **active** on 2026-10-01 but government announcements describe a **7-day** cycle; EUR conversion of old kuna fines (1 EUR = 7.5345 HRK) is the general rule, exact figures **[U]** |
| **GR** | No-change renewal every 7 days | **30 days** (YA 71645/2025). Only the EUR 3,000 base fine is confirmed |
| **CY** | URL for Law 152(I)/2002 and "Arts. 3-4" | The old URL was Cap. 272 (unrelated). Correct text at cylaw.org `.../2002_1_152/full.html`; duties in **Arts. 3, 5, 8** |
| **SM** | Decree-law number missing | D.L. **39/2026**, extended repeatedly, most recently to 31 Oct 2026 |
| **SE** | Commitments effective from 2 Feb 2025 | Binding for three years from **2 Dec 2024** (decision/announcement date) |
| **EU (NO/IS)** | Norway and Iceland not bound by Decision 1999/280/EC | It was incorporated into the EEA Agreement (EEA JC Decision 31/2000), but the Commission's current bulletin lists **EU-27 only**; whether NO/IS ever report is **[U]** |
| **LT** | One-increase-per-day "being discussed" | Cabinet has **endorsed** it; still needs an Energy Law amendment. A claimed "three increases per week" cap is **unconfirmed** and should not be repeated |
| **LV** | Bill rejected in committee | Cabinet approved it on **14 Apr 2026** before the committee rejected it |
| **DK** | Legal authority unspecified | Added: Sec. 37(10) Markedsforingsloven, Directives 98/6/EC and 2019/2161. Sec. 16a does not appear in the order's fineable list (Sec. 18) as rendered, so no decree-specific fine is confirmed (moderate confidence) |
| **CZ** | Act in force 19 May 2026 | Act in force **13 May 2026**; ~20 May is the first price order |
| **HU** | All stations selling at the capped price must report | Narrower: strategic-reserve fuel and its wholesale resellers (Sec. 10/A) |
| **BG** | 23 May 2025 amendment cited via a private site only | Amendment existence/date now confirmed on dv.parliament.bg; article-level wording still rests on the private reproduction |
| **GB** | Enabling power is s.22 of the Data (Use and Access) Act 2025 | **Wrong.** Powers cited are ss.4, 5, 7, 8, 10, 18, 19, 21(1). The "CMA supportive for 3 months to ~1 May 2026" claim is **[U]** |
| **EU** | Weekly Oil Bulletin is open data on data.europa.eu | **Not confirmed.** Commission distributes XLSX/PDF and email. "AccelerateEU" COM(2026)370 and a "Fuel Observatory" are **[U]**; do not repeat |
| **IE** | Link to a CCPC 9 Apr 2026 report | The URL pointed to a 2022 publication; use RTE for the 2026 report. The PumpWatch call names the UK scheme only generically |
| **MK, BA, TR** | Secondary only | **Upgraded to [P]** after reading full texts (see rows above) |
| **XK, RS** | Ministry PDF / mtt.gov.rs | XK domain moved to minti.rks-gov.net, instruction number unconfirmed; RS site unreachable, decree number unconfirmed |

---

## 4. EU-level notes

- **No EU law forces petrol stations to report pump prices to a government body in real time.** Every duty in section 2 is national. **[S/P mix: confirmed by the absence of any contrary finding across all passes]**
- **Weekly Oil Bulletin** (Council Decision 1999/280/EC, CELEX 31999D0280, with Commission Decision 1999/566/EC): Member States' authorities send **national-average** consumer prices (Eurosuper 95, diesel, heating oil, LPG; EUR/litre incl. taxes) to DG ENER every Wednesday; bulletin published Thursday. Covers the **EU-27 only**. This is government-to-Commission aggregate reporting; it is useless for station-level data but good for cross-country sanity checks.
  - Not confirmed as open data on data.europa.eu; the Commission's own page offers email subscription and XLSX/PDF.
  - Adoption date discrepancy: 22 April vs 28 April 1999 across sources (probably adoption vs Official Journal date) **[U]**.
  - Norway and Iceland: the Decision was brought into the EEA Agreement (Joint Committee Decision 31/2000, CELEX 22000D0615 series), yet current bulletin lists omit them **[U]**.
  - National compilations behind the bulletin are often informal or sample-based, so national averages can diverge from company-reported figures (Estonia's regulator flagged this).
- **AFIR (Regulation (EU) 2023/1804) Art. 20 and Implementing Regulation (EU) 2025/655**: operators of public **recharging points and alternative-fuel (hydrogen, LNG, CNG) refuelling points** must make price data available in real time from 14 April 2025. **This does not cover petrol, diesel or LPG pumps.** Carried forward from the researcher and **not re-verified** by the verification pass **[S]**. Possible future value for EV/hydrogen layers, not for the fuel map.
- **Directives touching price display, not reporting**: Directive 98/6/EC (price indication, basis for Denmark's order and Liechtenstein's general ordinance); Directive 2014/94/EU and Implementing Regulation (EU) 2018/732 (basis for Belgium's in-station comparative display). They are consumer-facing display rules, not duties to report to a government.
- **High-Value Dataset Regulation (EU) 2023/138**: the Portuguese station-location dataset is catalogued under it (location data, CC BY 4.0). Prices are not covered **[P for the dataset tag]**.
- **Not confirmed**: the Commission's "AccelerateEU" Communication COM(2026) 370 (22 Apr 2026) and the announced "Fuel Observatory". Do not cite until a primary source is found **[U]**.
- **No EU legislative proposal for station-level reporting was found.** Member states are moving individually (Denmark, UK, Lithuania in 2026). Germany and Austria are explicitly cited as models by the Latvian regulator, and Dutch/Irish politicians have pointed at the German and UK schemes.

---

## 5. Implications for our scraper strategy and source-grade labelling

### 5.1 Source priority

1. **Use statutory government feeds first, wherever the licence permits**: FR, DE (via Tankerkonig), GB, ES, DK, GR, IT. Together they cover the largest markets and are legally forced to be complete.
2. **Treat the statutory-duty countries with restricted data as "work to do"**: AT (existing e-control API, ~32% coverage, no timestamps), PT (non-commercial price terms), CY (request access), LT (check the open-data link).
3. **Ceiling countries (LU, SI, HR, PL, CZ, SK, RS, ME, MK, MD, BE...)**: use the ceiling as a plausibility bound and a fallback "price cap" overlay, not as the station price. Actual per-station prices still come from aggregators/crowd.
4. **No-duty countries (SE, NO, FI, NL, CH, IE, EE, LV...)**: aggregators and crowd data only. Nothing legally forces completeness.

### 5.2 Operational consequences of the legal findings

- **Deadlines set freshness expectations.** DE 5 min, UK/AT 30 min, FR "immediate", DK real-time: we can promise sub-hour freshness only where the law and the published feed both support it. IT publishes once a day (08:30), so label it "daily".
- **Poll around the noon price-increase window.** Germany (since 1 Apr 2026), Austria and Romania allow increases only once per day around 12:00 local (Lithuania has a 10:00 collection and a cabinet-endorsed one-increase rule). Add a refresh shortly after noon local time in those markets to catch the daily jump; decreases can happen any time.
- **Licence obligations drive UI and legal footers:** Etalab 2.0 (FR) and CC BY 4.0 (Tankerkonig realtime, GR) require attribution; **CC BY-SA 4.0 (CY) has share-alike implications**; IODL 2.0 (IT) needs attribution; Tankerkonig real-time data excludes petroleum-industry use and high-volume commercial use needs a paid contract; **PT price data may not be used commercially**; the Romanian voluntary platform is commercial "no". If the product will ever be monetised, these constraints decide which countries we can include.
- **Do not invent timestamps.** Where a source has no per-station timestamp (ES, AT, ANWB, bensinpriser.nu per record), the UI must not display our scrape time as "updated at". The audits already flagged this stamping as a known defect. Use the dataset-level date (for example ES "Fecha") or show "age unknown".
- **Access fragility:** the Spanish ministry resets connections from GitHub runner IPs (audit: same URL works from a residential IP); Germany needs a registered Tankerkonig key (audit: current German output is 0 stations because the key is unset); the UK needs registration with VE3. These are engineering items, not legal ones; this memo does not change any code.
- **Evidence-driven re-checks needed** (cheap, high value): Croatian instrument in force on 1 Oct 2026; Lithuanian 2026 order number; Slovenian Uradni list issue; Portuguese DL 243/2008 article; Cyprus update cadence; Swiss Curia Vista; Liechtenstein gesetze.li and llv.li "Treibstoffpreise" page; Austrian BGBl for the expanded brake.

### 5.3 Source-grade labels for the UI

Label the **source actually used for each station**, not the country's law. A German station served by an ANWB fallback is **not** "Official". The grade should be derived from `source` plus country and shown with text, not colour alone.

| Grade | UI label (short) | When to use | Freshness text shown |
|---|---|---|---|
| **G1** | "Official - live" | Price comes from a statutory feed we read directly or via the sanctioned reseller (FR, DE, GB, ES, DK, GR) | Source timestamp if present; otherwise dataset-level time. Legal deadline in the tooltip ("by law within 5 min / 30 min") |
| **G1-d** | "Official - daily" | IT (daily 08:30 file) | "Updated daily by 08:30" |
| **G2** | "Official - limited" | Statutory duty but restricted publication or licence (AT, PT, CY, LT) | "Reported by law; published subset" and age if known |
| **G4** | "Legal ceiling" | A government maximum price, never an actual station price (LU, SI, HR, PL, CZ, SK, HU, RS, ME, MK, MD, BE...) | Valid-from date; "Stations may charge less" (do not imply everyone charges the cap) |
| **G5a** | "Aggregator" | Commercial/aggregated data without legal completeness guarantee (for example ANWB POI in CH, NL, BE, LU) | "Third-party data, age unknown unless shown" |
| **G5b** | "Community-reported" | Crowd/owner-submitted prices (bensinpriser.nu in SE; gasvaktin.is in IS) | "Reported by users; shown up to 3 days" (SE) |
| - | "Station-reported (chain)" | Prices from a chain's own site/API where no law forces them | Chain name, age |

Rules to implement:

1. A country badge (on country selection) may say "Government-mandated reporting" for G1/G2 countries, but only the **per-station source grade** appears on the marker/popup.
2. A station with no price shows "No price" with the reason (for example "not reported" vs "source unavailable"), never a stale price with a fresh-looking timestamp.
3. Display the **statutory deadline** next to G1 prices ("legally updated within 5 minutes"), but show the *measured* age beside it whenever the source gives one. The law is a promise, not a measurement.
4. Show the **12:00 rule** hint in DE/AT/RO ("price increases only at 12:00").
5. Markers from ceiling countries must be visually and textually distinct (a cap marker), not mixed into the cheapest-station ranking without a clear label.
6. "Unverified" findings (marked **[U]**) must never appear in user-facing copy as fact.

### 5.4 Open TODOs (not done in this research)

- **TODO: visual mobile-layout inspection of competitors has NOT been done.** The competitor teardown (comp-fr, comp-de, comp-intl) is text-only research. Screenshots and real-device review of top competitors' mobile map, list, filter and price-detail layouts are still needed before finalising the UI grade chips and ceiling markers described above.
- **TODO: add a legend UI pattern** for G1-G5 and test it at phone width (cannot be validated without that inspection).
- **TODO: verification gaps** listed in section 5.2, and the unresolved items in the verification files (DE Sec. 81(2) full read, LU contract text, LT order number, SI Constitutional Court case U-I-47/23, HR/Uredba instrument, GR EUR 10,000 / 1,000 tiers, CZ CZK 3M/5M fines, SK/MD penalties, FI KKV data-collection legal basis, NO/IS Weekly Oil Bulletin status).

---

## 6. Citations

All URLs are the evidence links recorded in the `reg-*.verify.json` files. Source tags in section 2 reflect what the verifier could open. Items the verifier could not open are marked in the text, not hidden here.

**Germany**
- https://www.gesetze-im-internet.de/gwb/__47k.html
- https://www.gesetze-im-internet.de/mtskraftv/BJNR059500013.html
- https://www.gesetze-im-internet.de/gwb/__81c.html
- https://www.gesetze-im-internet.de/gwb/__81.html
- https://www.buzer.de/KPAnG.htm
- https://www.recht.bund.de/bgbl/1/2026/82/regelungstext.pdf?__blob=publicationFile&v=2
- https://www.bundeskartellamt.de/DE/Aufgaben/MarkttransparenzstelleFuerKraftstoffe/TankApps/tankapps_node.html
- https://www.bundeskartellamt.de/DE/Aufgaben/MarkttransparenzstelleFuerKraftstoffe/12-Uhr-Regel/12-Uhr-Regel_node.html
- https://www.bundeskartellamt.de/SharedDocs/Publikation/DE/Berichte/Evaluierungsbericht_MTS-K_.pdf?__blob=publicationFile&v=3
- https://creativecommons.tankerkoenig.de/

**Austria**
- https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer=20007391
- https://ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer=20007082
- https://www.parlament.gv.at/aktuelles/pk/jahr_2026/pk0884
- https://www.wko.at/transport-verkehr/garagen-tankstellen-serviceunternehmungen/spritpreisdatenbank1
- https://www.ots.at/presseaussendung/OTS_20260922_OTS0145/ueberblick-ueber-die-aktivitaeten-der-bwb-am-kraftstoffmarkt-branchenuntersuchung-ermittlung-und-spritpreistracker

**Switzerland / Liechtenstein / Luxembourg**
- https://www.preisueberwacher.admin.ch/dam/pue/de/dokumente/gesetz/preisueberwachungsgesetz.pdf.download.pdf/preisueberwachungsgesetz.pdf
- https://www.nzz.ch/schweiz/der-nationalrat-versenkt-die-idee-eines-staatlichen-vergleichsportals-fuer-benzinpreise-wohl-wegen-des-erfolg-des-privaten-tcs-portals-ld.1728515
- https://www.tcs.ch/de/tools/tcs-app/tankstellen-schweiz/
- https://www.gesetze.li/konso/pdf/1996142000?version=6
- https://guichet.public.lu/fr/entreprises/commerce/prix-horaires/prix/liberte-prix.html
- https://data.public.lu/en/datasets/economie-totale-et-prix-prix-prix-de-lenergie/
- https://transports.public.lu/fr/conduire/comparateur-prix-carburants.html

**France**
- https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000688923/2020-12-08/
- https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000000817439
- https://www.prix-carburants.gouv.fr/rubrique/opendata/
- https://www.prix-carburants.gouv.fr/rubrique/faq/

**Spain / Portugal / Belgium / Netherlands / Andorra / Monaco**
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2007-14592
- https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-25592
- https://www.boe.es/buscar/act.php?id=BOE-A-2026-6544
- https://datos.gob.es/en/catalogo/e05068001-precio-de-carburantes-en-las-gasolineras-espanolas
- https://precoscombustiveis.dgeg.gov.pt/apresentacao/
- https://dados.gov.pt/pt/datasets/postos-de-abastecimento-de-combustiveis-para-veiculos-rodoviarios/
- https://economie.fgov.be/fr/themes/energie/sources-denergie/carburants/nouvel-affichage-des-prix-des
- https://www.energiafed.be/fr/prix-maximums
- https://www.cbs.nl/nl-nl/cijfers/detail/80416ned
- https://www.tweedekamer.nl/debat_en_vergadering/plenaire_vergaderingen/details/activiteit?id=2026A02996
- https://sig.govern.ad/IPE/PreusCarburants
- https://www.consellgeneral.ad/ca/noticies/el-consell-general-aprova-noves-mesures-temporals-per-fer-front-a-l2019increment-dels-preus-dels-hidrocarburs
- https://monaco-hebdo.com/economie/carburant-monaco-baisse-aussi-ses-prix/

**Italy / Slovenia / Croatia / Greece / Cyprus / Malta / San Marino**
- https://www.normattiva.it/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta=2023-01-14&atto.codiceRedazionale=23G00007
- https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti
- https://pisrs.si/pregledPredpisa?id=URED9726
- https://www.energetika-portal.si/podrocja/energetika/cene-naftnih-derivatov/regulirane-cene-naftnih-derivatov/
- https://vlada.gov.hr/vijesti/trziste-naftnih-derivata-je-stabilno-vlada-deregulira-cijene-naftnih-derivata/44795
- https://mingo.gov.hr/vijesti/od-utorka-nize-cijene-dizelskog-goriva/10445
- https://www.teb.hr/novosti/2026/uredba-o-utvrdivanju-najvisih-maloprodajnih-cijena-naftnih-derivata-nar-nov-br-2426/
- https://www.lawspot.gr/nomothesia/kanones-dieppy/arthro-114-ypoyrgiki-apofasi-91354-2482017/
- https://www.taxheaven.gr/circulars/51056/71645-17-09-2025
- https://www.fuelprices.gr/
- http://www.cylaw.org/nomoi/enop/non-ind/2002_1_152/full.html
- https://www.data.gov.cy/el/dataset/paratiritirio-lianikon-timon-kaysimon-api
- https://www.rews.org.mt/decision-notices/
- https://www.sanmarinortv.sm/news/comunicati-c9/modifica-temporanea-delle-aliquote-dell-imposta-speciale-sulle-importazioni-di-prodotti-petroliferi-a288056

**Nordics and Baltics**
- https://www.retsinformation.dk/eli/lta/2025/1351
- https://kfst.dk/vejledninger/kfst/dansk/2025/20251216-vejledning-om-api-til-offentliggoerelse-af-prisoplysninger-for-motorbraendstof
- https://www.konkurrensverket.se/informationsmaterial/nyhetsarkiv/2024/ataganden-fran-drivmedelsbolag-ger-battre-forutsattningar-for-priskonkurrens/
- https://www.konsumentverket.se/lagar/prisinformationslagen-konsument/
- https://konkurransetilsynet.no/decisions/vedtak-v2025-14-yx-norge-as-fornyelse-av-vedtak-v2020-27-konkurranseloven-%C2%A7-6-annet-ledd/
- https://www.regjeringen.no/no/dokumenter/nou-2025-11/id3141191/
- https://www.kkv.fi/blogit/kkv-blogi/polttoaineiden-hintavaihtelut-ja-kilpailupolitiikka/
- https://www.althingi.is/altext/pdf/157/s/1055.pdf
- https://www.konkurentsiamet.ee/media/1215/download
- https://www.kp.gov.lv/lv/jaunums/konkurences-padome-skaidro-kadi-faktori-ietekme-degvielas-mazumtirdzniecibas-cenas
- https://www.lsm.lv/raksts/zinas/ekonomika/31.03.2026-valdiba-nav-vienpratibas-par-ekonomikas-ministrijas-planoto-solidaritates-maksajumu-degvielas-tirgotajiem.a641210/
- https://www.e-tar.lt/portal/lt/legalActEditions/TAR.937378434A8E
- https://www.ena.lt/degalu-kainos-degalinese/
- https://enmin.lrv.lt/lt/naujienos/vyriausybe-pritare-degalu-kainos-galetu-kilti-tik-karta-per-diena-vWNo/

**Central and Eastern Europe, Moldova**
- https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20260000599
- https://www.zakonyprolidi.cz/cs/2026-63
- https://mf.gov.cz/cs/ministerstvo/media/tiskove-zpravy/2026/vlada-obnovuje-regulaci-cen-pohonnych-hmot-a-snizu-65248
- https://www.slov-lex.sk/ezbierky/pravne-predpisy/SK/ZZ/2026/237/20261001
- https://pravnenoviny.sk/marza-na-palivo/
- https://njt.jog.gov.hu/jogszabaly/2026-50-20-22
- https://www.monitoruljuridic.ro/monitorul-oficial/642/2026-08-04/
- https://monitorulpreturilor.info/
- https://kik-info.com/normativna-baza/naredbi/h-18/
- https://dv.parliament.bg/DVWeb/showMaterialDV.jsp?idMat=235038
- https://www.legis.md/cautare/downloadpdf/126247 (not re-verified; HTTP 403)

**UK, Ireland, Balkans, Turkey, Ukraine, EU**
- https://www.legislation.gov.uk/uksi/2025/1356/made
- https://www.legislation.gov.uk/ukdsi/2025/9780348275308
- https://www.gov.uk/government/consultations/empowering-drivers-and-boosting-competition-in-the-road-fuel-retail-market/outcome/consultation-on-open-data-scheme-and-ongoing-monitoring-function-for-road-fuel-prices-government-response
- https://www.fiannafail.ie/news/brennan-calls-for-mandatory-pumpwatch-system-to-publish-live-fuel-prices-across-ireland
- https://www.rte.ie/news/business/2026/0409/1567376-ccps-report-on-fuel-price-hikes/
- https://novinite.com/articles/237459/Serbia+Caps+Fuel+Prices+and+Halts+Exports,+Impacting+Bulgaria+and+the+Region
- https://www.cdm.me/english/government-takes-maximum-measure-instead-of-31-diesel-up-by-four-cents-excise-duties-cut-by-50-prices-to-be-set-weekly/ (re-fetch blocked, HTTP 403)
- https://www.erc.org.mk/odluki/2PRAVILNIK%20ZA%20NAFTENI%20DERIVATI-ENG.pdf
- https://rtsh.al/qeveria-rikthen-bordin-e-transparences-per-cmimin-e-naftes/
- https://advokat-prnjavorac.com/zakoni/Zakon-o-naftnim-derivatima-u-FBiH.pdf
- https://minti.rks-gov.net/
- https://www.mevzuat.gov.tr/anasayfa/MevzuatFihristDetayIframe?MevzuatTur=7&MevzuatNo=12516&MevzuatTertip=5
- https://epravda.com.ua/energetika/yak-zminyuyetsya-derzhavniy-kontrol-za-cinami-na-palne-v-ukrajini-ta-yes-821198/
- https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en
- https://eur-lex.europa.eu/legal-content/en/TXT/?uri=CELEX:22000D0615(07)

**Project audits used for the implications section (data-source evidence, not part of the legal verification)**
- Sweden chains and aggregators audits (`se-chains.audit.json`, `se-agg.audit.json`), DACH audit (`dach.audit.json`), Iberia and France audit (`iberia-fr.audit.json`), and the competitor teardown files (`comp-fr.json`, `comp-de.json`, `comp-intl.json`) in the project's research scratchpad.

---

*Everything on the web was treated as data, not instructions. No code or README was modified. Items tagged **[U]** must be re-checked against primary sources before being used in user-facing copy.*
