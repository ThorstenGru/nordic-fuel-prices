# EuroFuelPrices - Product, Data and Monetization Roadmap

Status: DRAFT v1, written 2026-10-02. Owner: Thorsten Grund. Audience: owner decision-making.
Scope: roadmap and strategy only. No code or README changes are implied by this document.

## How to read this document

- Every figure tagged **ASSUMPTION** is a guess to be replaced by measured data from the 90-day experiments (section 5). Every item tagged **UNVERIFIED** was not confirmed from a primary source in the research this document is based on. Untagged facts come from the verified regulation research or the live data audits (dates in text).
- Revenue figures are annual run-rate (ARR) at month 12 (M12, about Oct 2027) and month 24 (M24, about Oct 2028), shown as low / base / high. They are not cumulative cash. Year-1 cumulative cash is roughly 25-35% of the M12 run-rate because revenue ramps (ASSUMPTION). Currency conversion assumes 1 EUR is about 11 SEK (ASSUMPTION, not looked up).
- Source material (all on the owner's machine, scratchpad `research/` and `audit/`): `monetization.json` (numbers and assumptions kept as written), `reg-*.verify.json` (authoritative `final` arrays), `comp-fr/de/intl.json`, and `se-chains`, `se-agg`, `dach`, `iberia-fr` audits.
- **Open TODO: a visual mobile-layout inspection of competitors has NOT been done.** All competitor findings are text/store-listing based. See section 8 (TODO V1).

## Starting position (honest baseline, 2026-10-01 audits)

| Area | Finding |
|---|---|
| Sweden (home market) | 3,413 OSM station locations ship, **0 with prices** in production. Cause: parser bug in `src/scrapers/sweden.py` (`_parse_station_id` regex expects camelCase; live keys use `__` delimiters; regex returned an empty city for 615 of 619 live priced ids). The upstream feed (bensinpriser.nu via henrikhjelm.se) is healthy: 619 of 3,087 listed stations (20.1%) carry a price today. About 3,000 real stations exist (Drivkraft Sverige). |
| Germany | **0 prices** in production. `TANKERKOENIG_API_KEY` unset; ANWB fallback fails on a whole-country bounding box (`limit_exceeded`). About 14,000 stations are legally mandated reporters. |
| Spain | **0 prices** in production. MINETUR resets connections from GitHub runner IPs (5 of 5 attempts). From a residential IP: 11,472 of 12,562 stations (91.3%, CNMC census 30 Jun 2026), all priced. Also: LPG key accent typo (995 stations dropped), Diesel Renovable/HVO never read (1,621 stations). |
| Freshness | `BaseScraper.fetched_at` is stamped on every price as `updated_at`, so the UI implies freshness the sources do not prove. France exposes per-price `maj` timestamps that are fetched and discarded; Portugal has per-station timestamps; Sweden's response carries a usable `created_at` that is ignored; Andorra's government portal has a per-station date. |
| Other defects | ECB currency regex quote-style bug (CHF conversion inactive for CH/LI); Austria fuelType and GAS (LPG vs CNG) mapping bugs, ~32% reporting coverage gap; empty scrape can overwrite good data (defect #2). |
| README vs reality | README claims 38 countries / 80,000+ stations and lists DE, ES and SE as Tier 1/2 live sources. Production currently ships no prices for DE, ES, SE. README is not to be edited by this task; reconcile it after Phase 0. |
| Traffic / revenue | No analytics found. Current MAU is UNKNOWN. **Monetising before the three fixes above would be monetising an empty map.** |

---

## 1. Vision and principles

**Vision.** The most trustworthy fuel-price map for Sweden and Europe: every price shows where it came from and how old it is, on a fast no-login PWA, with Sweden covered better than anyone because we build the data nobody else has.

**Why this can win (from the competitor teardown).**
- No surveyed competitor covers Sweden/Nordics with a map PWA; fuel-prices.eu covers 27 EU states, but its Swedish values are chain list prices and it has no map, app or alerts (comp-de).
- No competitor makes per-station provenance and age a first-class UI element (comp-fr, comp-de, comp-intl).
- Where governments mandate reporting (DE, FR, IT, ES, UK, GR) the raw data is commoditised (DE alone has 44+ registered services per the Bundeskartellamt list). The moat is breadth, honesty, UX, and in Sweden our own data. Not the feed.
- Sweden has no statutory price reporting. Circle K, OKQ8 and Preem committed on 2 Dec 2024 to stop publishing recommended/list prices (binding 3 years, SEK 100m penalty each). Konkurrensverket recommends a digital tool showing actual station prices. That is both our hook and our data problem.

**Principles (in priority order).**
1. **Data trust first.** Every price carries source, source grade and age. Never display a scrape time as a price time. Stale data is dimmed and labelled, never hidden behind a fresh look. An empty fetch never overwrites last-known-good data.
2. **Government sources first, community second, estimates last** - and they never share the same visual confidence (comp-de anti-pattern: crowd data dressed as official).
3. **Licence before revenue.** No ad, premium or B2B use of a data source until the licence register (section 4) marks it allowed. Public does not mean reusable.
4. **Neutral ranking.** Default sort is price, then distance. Paid placement never alters ranking, never claims "cheapest", and is always labelled (UCPD ranking-transparency rules; see section 4b).
5. **Never take away what is free today.** Fuelio (2023) and Drivstoffappen rating collapses came from paywalling existing features. Paywall convenience and extras, never core price data.
6. **Privacy-first.** No login, on-device nearest-station, cookieless analytics until ads need consent, no precise location to ad vendors.
7. **Light and fast.** Single ad slot at most, never over the map; Core Web Vitals and WCAG 2.2 AA as release gates.

---

## 2. Roadmap: Now / Next / Later

Phases follow the monetization plan. Windows are targets for a solo founder (ASSUMPTION), gated by exit criteria rather than dates.

### NOW - Phase 0: Trust and growth foundation (Oct-Dec 2026, weeks 0-12)

Goal: be the most honest, fastest Sweden-first fuel map and reach the traffic that Phase 1 approvals need. Effort about 4-6 weeks solo.

**2a. DATA roadmap (ordered by value per effort)**

| # | Item | Why / evidence | Effort | Owner action? |
|---|---|---|---|---|
| D1 | **Fix the Sweden parser.** Key format `{lan_slug}_{brand}_{city}__{street}[__...]__{fueltype}`; `rsplit('__',1)`, then `split('_',2)`, special-case brand "Circle K". Join to OSM, else Nominatim-geocode the correctly parsed city/street. Log HTTP status instead of bare `except: return []`. | Audit recipe passed 619 of 619 live priced ids. Takes SE from 0 to roughly 600+ priced stations (~20%) on the next run. | S | No |
| D2 | **Use Swedish `created_at`; label crowd honestly** ("crowd/owner, shown max 3 days"). Treat a county feed with a stale `created_at` as dead (gotlands-lan was 3 months stale on 2026-10-01). | Payload has only a response-level `created_at`; per-record age is unknown. | S | No |
| D3 | **Tankerkoenig key (DE).** Register a free key, set `TANKERKOENIG_API_KEY`. Serialise the 40-point, 25 km grid at about 1 request/min (about 40 min per full sweep). Add the written licence question (E10) before ads in DE. | Single best government feed in DACH; 14,000+ mandated stations; demo key returns flat placeholder prices so a real key is required. | S | **Yes - owner registers key** (no-account rule) |
| D4 | **Spain transport relay.** Retry alternating `sedeaplicaciones.minetur.gob.es` and `energia.serviciosmin.gob.es`; if still reset, run that scraper from a self-hosted runner on a small EU VPS or via a Cloudflare Worker. Fix LPG accent key; add HVO ("Precio Diesel Renovable"); drop or map hydrogen out of the enum. | Source is excellent (91.3% of census, 100% priced) and the failure is egress-IP only. VPS cost about EUR 5-10/month (ASSUMPTION). | M | Maybe (VPS) |
| D5 | **ANWB tiling.** Replace whole-country bounding boxes with grids of smaller boxes (confirmed to work where the full box returns `limit_exceeded`); proof-of-concept tiled outputs exist for BG, EE, LT, LV. Fix the ECB regex (`currency=["']([A-Z]{3})["']\s+rate=["']([\d.]+)["']`) so CHF activates for CH/LI. | Restores DE fallback, NL/BE and the Tier-3 countries. ANWB is an **unofficial, undocumented** API with no developer terms found: keep it flagged experimental and **non-monetised** (section 4). | S | No |
| D6 | **Per-price timestamps.** Wire real source times where they exist: FR `maj`, PT per-station times, SE `created_at`, AD per-station date, ES file-level `Fecha` (labelled "dataset time"). Where no per-price time exists (DE list.php, AT, ANWB), store `observed_at` (our fetch time) as a separate field and display it as "checked", never as "updated". | Fixes the `fetched_at` defect; cheap and visible. | S-M | No |
| D7 | **Last-known-good retention.** Replace a country file only if the new fetch has at least about 80% of the previous station count (and priced-share does not collapse); otherwise keep the old file and flag the source degraded. | Defect #2; also protects against transport failures like Spain's. | S | No |
| D8 | **Source-grade labels.** Grades: A statutory real-time government (DE, FR, IT, ES, PT, GR, UK, DK); B government periodic/regulated (e.g. HR, SI, LU); C owner-verified; D crowd; E list/advertised price or estimate; X unverified aggregator (ANWB). Per-station badge "source + age", plus a global status page and a "how we rank and where prices come from" page. | Differentiator nobody ships; also a trust and SEO asset. | M | No |
| D9 | **UK (Fuel Finder).** Register with the appointed aggregator (VE3 Global), build an adapter. Statutory duty: every petrol station must report a price change within 30 minutes (SI 2025/1356 reg. 9(2), in force 2 Feb 2026); about 5-minute API latency. Licence: gov.uk page states OGL v3.0 for the data (the legislative text only says OGL is "intended" - confirm the final wording when registering). Comply with the aggregator's Fair Use policy. | Rank-1 reliability source with commercial reuse; very high search demand. | M | **Yes - owner registration** |
| D10 | **IE (Ireland).** No statutory reporting and no per-station open database (PumpWatch is only a political proposal; CCPC's April 2026 report was an ad hoc investigation). Ship **locations only plus national average** (EU Weekly Oil Bulletin, licence not confirmed open) clearly labelled; evaluate crowd later. | Honest "no official data" state is better than a fake price. | S | No |
| D11 | **Denmark via operator APIs.** KFST guidance (16 Dec 2025) requires real-time publication by operators; replace the ANWB fallback with per-operator APIs after reading each operator's terms (about 1 day). | Statutory real-time, rank 1; no central licence found. | M | No |
| D12 | **Cheap fixes batch.** Andorra: switch to the government portal (54 stations, per-station date, HTML parse; courtesy email suggested). Austria: DIE/SUP/GAS enum, PB-district iteration, LPG/CNG split. Portugal: add CNG (id 1143). Overpass: add a mirror fallback and 30 m de-duplication of node/way doubles. Liechtenstein: government page is bot-challenged, check manually only. | Audit-confirmed one-line to small fixes. | S | No |

Note on **Sweden beyond the fix:** even after D1, free legal coverage tops out around 20% of stations. Circle K, OKQ8 and Preem (about 40% of listed stations) are under the Konkurrensverket commitment and show only a 7-8% residual priced share, consistent with that ban. **Do not pursue price scraping of those three chains.** Further Swedish coverage must come from first-party data (Phase 1, section 7). An optional low-confidence supplement is the St1 national list price (st1.se, about 900 St1 stations) strictly labelled "advertised list price, grade E", subject to a licence check.

**2b. Product, growth and platform (Phase 0)**
- Freshness-honesty release: per-station badge, dimmed stale prices, global status page.
- SEO: pre-rendered `/country/city/` and `/station/` pages, Sweden first (290 municipalities plus top stations), schema.org, sitemap, city averages from open sources. Needed also because AdSense approval requires content-rich indexable pages.
- PWA: install prompt after the 2nd visit, offline last-known data with explicit age, share cards.
- Cookieless analytics (Plausible/Umami/Cloudflare Web Analytics) and Search Console; Core Web Vitals pass.
- **Move serving to Cloudflare Pages** (GitHub stays source of truth plus Actions cron). GitHub Pages ToS prohibits running an online business or a site primarily facilitating commercial transactions, so ads and subscriptions need this move first. GitHub Pages also has a 100 GB/month soft bandwidth limit (verified).
- **Licence register and per-country "monetisation allowed" flag** in the data manifest (gates Phase 1; section 4).
- Donation link ("no tracking" positioning).
- Reconcile the README claims with production reality once D1-D4 land.

**Exit gate (Phase 0):** 2,000+ MAU or 10k organic impressions/week; Sweden price coverage of at least 60% of stations **where a price source exists**; nothing stale without a label.
> Note: the 60% target is the monetization plan's number. The audit shows free crowd data caps at about 20%, so reaching 60% depends on first-party submissions. Treat 20% (fix) as the Phase 0 deliverable and 60% as the Phase 1-2 stretch, or restate the gate (owner decision O3).

### NEXT - Phase 1: Light monetisation, no paywall (Jan-Jun 2027)

Goal: first revenue without hurting trust; measure RPM and affiliate EPC.
- Affiliate "Spara mer" module in Sweden (EV charging, fuel card, insurance comparison, roadside, tyres/car services) via Adtraction/Awin, clearly labelled.
- One non-personalised ad slot below the list (never over the map) behind a certified CMP; only in countries that pass the licence gate; DE off until Tankerkoenig answers.
- Sponsored-station pilot (free 30 days) with 5-10 independents; labelled, excluded from ranking, DE and UK.
- Supporter ("no ads") donation tier.
- Licence outreach and the first-party Swedish data programme: approach Crownberry AB; build the station-owner portal and user submissions with price-sign photos; confidence labelling (crowd vs owner-verified).
- Price alerts MVP prototype (fake-door first, E7).

**Exit gate:** 10k+ MAU; RPM and affiliate EPC measured; retention not down more than 5% against an ads-off holdout.

### IDEA (owner, 2026-10-07) - Route-aware cheapest stops
Plan a route (A -> B, optional via points) and list the cheapest pumps *along* it for the fuel and litres the driver needs, updating as prices refresh.
- Shape: route polyline -> corridor (e.g. 3-5 km) -> stations from the already-loaded country files -> rank by `price - detour_cost` (extra km x consumption x price), honouring tank size/range so stops are spaced sensibly; show "fill up here, saves X EUR vs the average on route".
- Needs: a routing source (OSRM/Valhalla/ORS public demo is not production-grade; options: self-hosted OSRM on a small VM, or a paid/free-tier router with licence for this use), corridor search client-side (data already in browser; ~1 s for a 1,000 km route with a grid index), cross-border legs priced in EUR via the per-country stats already published.
- Honesty rules carry over: show source + age per price, never promise "live" where a feed has no timestamp.
- Builds on: Trip calculator (v1.9), tank size, nav-app chooser. Effort: M-L (routing is the cost driver). Decision needed: routing provider/budget.

### IDEA (owner, 2026-10-07) - EV charging and other alternative energy
Research report: `docs/EV_ALT_ENERGY_RESEARCH.md` (commissioned 2026-10-07; read it before deciding).

### LATER - Phase 2: Premium consumer tier (Jul-Dec 2027)
- Price alerts (web push/email): 3 free, paid unlimited, thresholds, weekly digest.
- Price history/trend: basic free, extended/export paid, built on our own archive of open feeds; wording "trend, not forecast".
- Trip/route planner: cheapest stop along a route including cross-border and currency normalisation (SEK/NOK/DKK/EUR) with a fuel-cost estimate.
- Ad-free, widgets; optional Capacitor/TWA wrapper for store discovery (15% store fee).
- Web checkout via Stripe or a Merchant of Record; EUR 9.99 / SEK 99 annual anchor.
**Exit gate:** 0.5%+ paying share of MAU; churn and refunds within benchmark.

### LATER - Phase 3: B2B API, data and white-label (2028; pilots from Q2 2027)
- Versioned API (keys, plans, SLA) for FR/IT/GR/UK/ES plus first-party Sweden; DE only after a Tankerkoenig agreement; per-record provenance and licence fields.
- Normalised fuel taxonomy, history exports, geocoded station master (ODbL-aware).
- Fleet/logistics widgets and alerts, media/data-journalism packages, consumer-organisation dashboards.
- White-label embeds with a sponsor slot.
**Exit gate:** 3 paying B2B accounts; licence audit passed by counsel.

### Geographic expansion order
Sweden -> Denmark/Norway/Finland (cross-border; needs licensed sources to replace ANWB) -> countries with clean open licences (FR, IT, GR, UK, ES with attribution) for SEO and B2B breadth -> Germany after the Tankerkoenig answer. Norway stays locations-only per the README (price-publication ban on the major chains until 2030, README claim, not re-verified here).

---

## 3. MONETIZATION

### 3a. Ranked models with revenue scenarios

Revenue = annual run-rate, EUR, low / base / high. Source: `monetization.json`; assumptions unchanged.
Traffic scenario (MAU): M12 = 15,000 / 60,000 / 150,000; M24 = 25,000 / 120,000 / 300,000 (ASSUMPTION). Anchor: carbu.com self-reports about 400,000 sessions/month and 100,000+ mailing-list members (company-stated, unaudited), roughly 130k MAU at about 3 sessions per MAU; base M24 (120k) is about carbu today. clever-tanken (10M+ Android installs) is not a realistic anchor. Traffic mix base: about 50% Sweden / 50% other; non-Swedish traffic only monetised where the licence gate passes.

| Rank | Model | M12 low / base / high | M24 low / base / high | Time to first revenue | Effort |
|---|---|---|---|---|---|
| 1 | **Phase-0 prerequisites** (trust, data fixes, SEO, hosting move) - enabler, not revenue | 0 | 0 | n/a | M (4-6 wks) |
| 2 | **Affiliate / lead module** (EV charging and fuel cards, car insurance, roadside, tyres/services), Sweden first | 720 / 14,400 / 56,200 | 1,200 / 28,800 / 112,500 | 6-10 wks | S-M |
| 3 | **Light display ads** (1 slot, non-personalised/contextual, certified CMP) | 1,620 / 20,200 / 90,000 | 2,700 / 40,300 / 180,000 | 8-12 wks | S |
| 4 | **Premium consumer tier** (alerts, extended history, route planner, ad-free, widgets); net of fees | 340 / 4,560 / 31,500 | 560 / 9,120 / 63,000 | 4-6 months | M-L |
| 5 | **Sponsored/featured stations** (labelled, never in ranking) | 0 / 8,100 / 32,400 | 3,600 / 32,400 / 108,000 | 6-9 months | M (sales-heavy) |
| 6 | **B2B data/API** (fleets, insurers/telematics, media, public bodies, EV/mobility apps) | 0 / 12,000 / 60,000 | 6,000 / 48,000 / 250,000 | 9-15 months | L |
| 7 | **White-label embeds** (media, clubs, municipalities, with sponsor slot) | 0 / 0 / 12,000 | 0 / 27,000 / 120,000 | 12+ months | M |
| 8 | **Voluntary support** (donations, sponsors, supporter badge) | 300 / 1,200 / 4,000 | 500 / 2,000 / 8,000 | 1-2 wks | XS |

**Totals (EUR/year).** The listed model values sum to about the figures below (the source file rounds them slightly differently).

| | Low | Base | High | Probability-weighted EV |
|---|---|---|---|---|
| M12 | 2,980 | about 60,400 | about 286,200 | 74,200 |
| M24 | about 14,600 | 187,600 | 841,500 | 225,100 |

Scenario weights: low 35%, base 50%, high 15% (judgement, not data).

**Reality check (keep prominent).** Base case of about EUR 60k run-rate at M12 and about EUR 190k at M24 is optimistic for a solo-run project and presumes base traffic **and** some sponsored/B2B traction. Budget against a more cautious **year-1 cash expectation of EUR 5-20k** (ads + affiliate + donations only). The high case needs about 150-300k MAU and a working sales motion. The low case is hobby-level and roughly covers hosting.

### 3b. Assumptions per model (all ASSUMPTION unless noted)

1. **Affiliate.** Module clicks per MAU per month 1% / 2% / 2.5%; click-to-lead/sale 4% / 5% / 5%; payout EUR 10 / 20 / 25 per lead or sale (benchmark: generic pay-per-lead USD 5-20; Swedish insurance, fuel-card and EV payouts NOT found, UNVERIFIED; one Swedish insurance programme on Adtraction was reported closed). Addressable pool: 5,039,431 passenger cars in traffic in Sweden at end-2025 (Trafikanalys; 475 per 1,000 inhabitants; 16% plug-in). Chains are fuel sellers, so EV-charging and car-service programmes are cleaner partners; no Circle K or Tanka affiliate programme was found.
2. **Ads.** Monetisable views per MAU per month 6 / 8 / 10 (SPA must fire refresh/virtual views, one slot only); RPM EUR 1.5 / 3.5 / 5.0. Evidence for RPM is weak and inconsistent (AdMob Sweden overall eCPM about USD 1.07; Tier-1 banner eCPM USD 0.5-1.5; W-Europe in-app banner USD 0.22; German-language AdSense often under USD 0.5; one source up to USD 15 for Sweden's best formats; low-reliability sources). Web mobile utility RPM in SE/NO/DK is probably EUR 2-6 after consent loss - UNVERIFIED. Ad-block plus consent decline can remove 30-50% of impressions (ASSUMPTION; reflected in RPM).
3. **Premium.** Paying share of MAU 0.3% / 0.8% / 1.5% (RevenueCat median freemium download-to-paid is 2.1% by day 35, verified via search, but a utility with a strong free tier converts far lower); price EUR 9.99/year (about SEK 99) anchor; net per payer per year EUR 7.5 / 9.5 / 14. Price benchmarks: carbu.com Pro EUR 1.99/month or 9.99/year after a 7-day trial (company-stated); clever-tanken ad-free EUR 3.99/year (older source EUR 1.99); GasBuddy Premium USD 9.99/month or 99/year including roadside assistance and Plus USD 7.99/month. Prices of Fuelio, mehr-tanken, 1-2-3 Tanken and Sprit Club not found (UNVERIFIED).
4. **Sponsored stations.** Paying stations at M12 0 / 15 / 60 and at M24 10 / 60 / 200; EUR 30 / 45 / 45 per station per month (benchmark: carbu.com sells a sponsored position at EUR 1.5/day plus an IAB 300x250 banner, company-stated). Sweden has about 3,000 stations (Drivkraft Sverige) including about 400 truck stops; independents and unmanned chains are the realistic buyers.
5. **B2B.** Customers at M24: low 2 x EUR 3k; base 8 x EUR 6k; high about 25 x EUR 10k. Benchmarks: TomTom Fuel Prices API is sales-only (verified); HERE pricing unpublished; OPIS is enterprise-contract with no public price (US benchmark); OilPriceAPI from USD 19/month is crude/energy data, not station-level; fuel-prices.eu offers CC BY 4.0 tables free and routes API/licensing by email; Tankerkoenig's dedicated-server tier has monthly fees (amount unknown). Customers pay for normalisation, uptime SLA, history, geocoding and Nordic coverage, not raw feeds.
6. **White-label.** EUR 3-12k per publisher per year (plein-moins-cher.fr offers embeddable widgets; GasBuddy white-labels).
7. **Donations.** 0.05-0.2% of MAU give (bessertanken.de runs on voluntary donations, no ads).

### 3c. Legal and licence constraints that shape monetisation

Full per-source table in section 4. Cross-cutting rules:

- **Data licence is the biggest monetisation risk, not demand.** Current pipeline uses sources that cannot be monetised as-is: unofficial ANWB API (DE/DK/FI/IS/NO fallbacks, NL/BE, Tier-3), Portugal price data (explicitly non-commercial), Tankerkoenig historical CSV (CC BY-NC-SA) and the bensinpriser.nu/henrikhjelm.se proxy (no published reuse terms). A per-country monetisation gate must precede any ad or premium switch-on.
- **Sweden tension (decision O2):** the Swedish price layer is the product's core, yet its only price source has unknown reuse terms and Crownberry AB (operator of bensinpriser.nu) runs ads and affiliate links itself, so it is a direct competitor for the same pool. Until Crownberry answers in writing, treat ads/affiliate on pages that display bensinpriser-derived prices as risky; mitigate by building first-party data and by showing price data from that source only with attribution.
- **Consent (GDPR + ePrivacy).** Google requires a Google-certified CMP integrated with IAB TCF to serve personalised ads in the EEA/UK (since 16 Jan 2024) and Switzerland (since 31 Jul 2024) - verified via AdSense help. Swedish cookie rule sits in the Electronic Communications Act (LEK 2022:482); section UNVERIFIED. Phase 0-1 use cookieless analytics (no banner); ads use non-personalised/contextual mode.
- **Location data.** Precise geolocation is personal data: keep nearest-station search on-device; contextual ads by country/city only; alerts store a user-chosen region or station, not live GPS.
- **Ranking neutrality and sponsored disclosure (UCPD Art. 7(4a), Omnibus).** Disclosure of main ranking parameters and paid influence is required (verified). Annex I point 11a (paid placement) is general knowledge, UNVERIFIED here. Implication: default sort is price then distance; sponsored items are a separate labelled "Annons/Sponsrad" card or pin style, never inside the price ranking.
- **DSA:** if crowd reports are public we may be a hosting service; label ads and keep a notice-and-action contact; the small-enterprise exemption likely applies (UNVERIFIED).
- **Swedish marketing law (Marknadsforingslagen):** advertising must be clearly identifiable; affiliate links disclosed (section number UNVERIFIED).
- **Subscriptions and VAT:** clear price, 14-day withdrawal for digital services unless waived, easy cancellation, VAT via OSS (UNVERIFIED). Use app stores or a Merchant of Record to avoid OSS admin (Paddle/Lemon Squeezy about 5% + fixed fee, UNVERIFIED), or Stripe direct (about 1.5% + EUR 0.25 EU cards, UNVERIFIED) and own the VAT.
- **App-store fees:** Google Play 15% on subscriptions; Apple Small Business Program 15% under USD 1m proceeds (verified via search). Plan about 15% for store revenue and 4-7% for web.
- **Hosting:** GitHub Pages ToS bars commercial/SaaS use; migrate before Phase 1 (section 2).

---

## 4. Licence matrix per data source

"Monetisable" = allowed for ads, affiliate, premium. B2B column is stricter (resale or API redistribution). Status on 2026-10-02; legal readings marked UNVERIFIED need counsel or written confirmation before relying on them.

| Source | Mandate / grade | Licence | Ads / premium | B2B resale | Constraints and required action |
|---|---|---|---|---|---|
| **Germany** - MTS-K via Tankerkoenig API | Statutory (5 min to MTS-K), A | Real-time: CC BY 4.0. Historical daily CSV: CC BY-NC-SA 4.0 | **CONDITIONAL - ask in writing first** | **No** without a Tankerkoenig contract | Free key: 1 request/min, 25 km radius, best-effort, no SLA, key disabled for abuse. Attribution link to tankerkoenig.de incl. app-store descriptions. Oil companies, station operators, affiliates and IT providers serving the petroleum industry may not use it (affects fuel-card affiliates). Results may not be filtered beyond explicit user requests: **no sponsored re-ranking in DE**. Whether ads/premium count as commercial is UNVERIFIED -> email info@tankerkoenig.de before DE ads. |
| **France** - prix-carburants.gouv.fr open data | Statutory real-time, A | Licence Ouverte / Etalab 2.0 | **Yes** | **Yes** | Cite source and last-update date; no implied endorsement. Brand withheld in feed, so brand features need OSM enrichment. Best candidate for commercial reuse. |
| **Italy** - MIMIT Osservaprezzi | Statutory (daily by 08:30), A | IODL 2.0 | **Yes** | **Yes** (attribution) | No registration. Safe. |
| **Spain** - MITECO/MINETUR SIPP | Statutory real-time, A | Standard Spanish reuse terms (keep meaning, cite source, state update date); not confirmed as a formal CC licence | **Conditional - UNVERIFIED** | Conditional | Fix transport first (runner IP block). Show "dataset time". |
| **United Kingdom** - Fuel Finder (VE3 Global) | Statutory 30 min, A | OGL v3.0 per gov.uk page (legislation says OGL "intended"; confirm) | **Yes** | **Yes** | Registration and Fair Use policy. One secondary source says data must not be selectively displayed to favour suppliers - not confirmed on gov.uk, treat as binding: **no sponsored re-ranking in UK**. |
| **Greece** - fuelprices.gr / data.gov.gr | Statutory real-time, A | CC BY 4.0 | **Yes** | **Yes** | Attribution. |
| **Cyprus** - data.gov.cy XML (on request) | Statutory daily-or-slower, B | CC BY-SA 4.0 | Display OK | **Exclude** (share-alike may bind an adapted dataset; UNVERIFIED legal view) | Access by request to meci.gov.cy. |
| **Portugal** - DGEG | Statutory real-time, A | Price data: commercial use **prohibited** (verbatim "e proibida a sua utilizacao para fins comerciais"); station-location set on dados.gov.pt: CC BY 4.0 | **NO for prices** | **No** | Gate PT prices OFF in monetised builds or obtain DGEG written permission (E10). |
| **Denmark** - KFST-mandated operator APIs | Statutory real-time, A | No central licence; each operator's terms not reviewed | **Conditional** | Unknown | Read each operator's ToS (about 1 day); current pipeline uses ANWB for DK, to be replaced. |
| **Austria** - E-Control Spritpreisrechner | Statutory 30 min, A (public API covers about 32% of stations) | No bulk/open licence found | **Unknown - hold** | Unknown | Do not use for monetised features without written permission (UNVERIFIED). |
| **Switzerland** - ANWB / TCS crowd / private portals | No mandate, C-E | Private; no government licence | **Unknown (assume NO)** | No | Database-right/ToS risk (UNVERIFIED legal view). Do not monetise CH until own data exists. fuelo.net is robots.txt-disallowed: do not use without permission. |
| **NL / BE and Nordic/Tier-3 fallbacks** - unofficial ANWB POI API | X (unverified aggregator) | No developer ToS found; ANWB is a commercial membership/insurance organisation | **Assume NO** | No | Undocumented endpoint: cease-and-desist or IP block risk; ANWB also sells roadside/insurance (affiliate competitor). Phase 0: label experimental, no ads/premium on ANWB-only countries. Phase 1: replace with licensed/official sources or drop. NL/BE have no government station feed (CBS publishes daily average only; open reuse). |
| **Sweden** - bensinpriser.nu via henrikhjelm.se | No mandate, D (crowd + owner) | No terms published on the henrikhjelm.se page; Crownberry AB site has no reuse policy on the page read | **Unknown (assume NO until written OK)** | No | Crowd+owner prices, 3-day expiry, no per-record timestamp. robots.txt allows crawling (not a licence). Ask Crownberry for a licence or partnership (E10); build first-party Swedish data in parallel. |
| **OpenStreetMap** (locations, Overpass) | Locations only | ODbL 1.0 | **Yes**, visible "(c) OpenStreetMap contributors" | Conditional | A published derived station *database* may need to be offered under ODbL (general ODbL knowledge, not re-verified): sell price service/SLA, not an exclusive station DB. |
| **EU Weekly Oil Bulletin / CBS NL / STATEC LU** (averages) | Averages | EU: not confirmed open; CBS and STATEC: open (STATEC max-price data CC0) | EU unknown; CBS/STATEC yes | - | Use for context charts and SEO pages only. |
| **Ireland** | None (no statutory duty), E | n/a | n/a | n/a | Locations + national average only. |
| **Norway, Finland, Iceland, Estonia, Latvia** | No statutory station duty found, C | Community/ANWB, terms not reviewed | **Assume NO** | No | Keep labelled community/experimental. |

**Licence register mechanics (Phase 0 deliverable).** One file in the repo (`docs/licences.json` or in the data manifest) with, per source: licence name and URL, attribution string, `monetisation_allowed` (true/false/pending), `b2b_allowed`, `sponsored_ranking_allowed`, `last_reviewed`, evidence link. The frontend and build step read it: ad and sponsor slots do not render for a country unless the flag is true. KPI: register coverage is 100% of monetised countries.

---

## 5. First 90 days: experiments and KPIs

Calendar assumes a start in the week of 2026-10-05; weeks counted from there.

### Experiments

| ID | Weeks | Experiment | Hypothesis | Metric / target | Cost |
|---|---|---|---|---|---|
| E1 | 1-3 | Freshness-honesty release (source + age badges) | Visible provenance raises return visits and press pickup | D7 return rate, share of sessions opening a station card; +10% relative return rate | dev |
| E2 | 1-2 | Baseline analytics and Search Console | We lack data to size any model | MAU, sessions/user, pages/session, country split, install rate | EUR 0-10/mo |
| E3 | 2-8 | Programmatic SEO city/station pages (Sweden first) | Local-intent queries drive 3x the organic sessions of the map home | 300 indexed city pages, 5k GSC impressions/week by week 8 | dev |
| E4 | 3-5 | Supporter link + Ko-fi test | 0.1% of MAU donate | Donation conversion, average gift | EUR 0 |
| E5 | 4-8 | Affiliate module A/B (EV charging, insurance comparison, roadside) | CTR at least 1% of sessions with a station search; EPC at least EUR 0.05/session | CTR, EPC; guardrail D7 return not worse than -3% | EUR 0 |
| E6 | 5-9 | Single ad slot on a 20% holdout with CMP | RPM at least EUR 2.5, retention loss under 5% | RPM, viewability, consent-accept rate, bounce, return rate. Precondition: AdSense approval (needs E3 content) | CMP EUR 0-30/mo |
| E7 | 6-10 | Price-alert fake-door waitlist | 3% of returning users sign up; 10% of those would pay EUR 9.99/year | Signup rate; 3-question willingness-to-pay survey | EUR 0 |
| E8 | 8-12 | Station-owner pilot: free "verified price + featured" for 30 days | 5 of 20 contacted independent Swedish stations/chains join; 2 would pay EUR 45/month | LOIs, update compliance, clicks-to-navigate per station | time |
| E9 | 8-12 | B2B discovery interviews (fleets, insurers, media, municipalities, EV apps) | At least 2 organisations would pilot a Nordic+EU price API at EUR 300/month or more | 15 interviews, 2 LOIs, must-have fields | time |
| E10 | 1-4 | Licence outreach emails | Written confirmations are obtainable | Answers from Tankerkoenig (ads/premium OK?), Crownberry AB (data licence), DGEG (PT commercial), MECI Cyprus, KFST-listed operators; 3 written answers by week 8 | EUR 0 |

Dependencies: E10 must precede any ad in DE/SE/PT; E3 precedes E6; D1-D4 precede E1/E5/E6/E8 (no point testing an empty map).

### KPIs

- **North star:** weekly active users who view a station with a price younger than 24 h (trust x usage).
- **Trust and data:** share of stations with a price per country; median price age; percent of stations with a source badge; error reports per 1,000 views; licence-register coverage (100% of monetised countries).
- **Growth:** MAU; WAU/MAU; organic share; PWA installs; D1/D7/D30 retention; indexed pages; SERP rank for "bensinpriser [stad]" and "billigaste diesel [stad]".
- **Monetisation:** RPM; consent-accept rate; affiliate CTR/EPC/lead-to-sale; paying share of MAU; ARPPU; churn; trial-to-paid; sponsored stations and renewal; B2B pipeline value; MRR/ARR; margin after fees.
- **Guardrails:** retention not worse than -5% with ads; Core Web Vitals pass; store rating at least 4.3 if wrapped; complaint rate; zero ranking disputes.

### Day-90 decision gates
- Scale ads if RPM at least EUR 2.5 and retention loss under 5%; otherwise keep affiliate-only plus donations.
- Build alerts if fake-door signup at least 3% and WTP at least 10%.
- Pursue sponsor sales if at least 2 stations would pay.
- Start B2B only with 2 LOIs.

---

## 6. Cost model

Principle: costs are tiny until ingestion or alerts need servers; the real costs are licences, legal and founder time. All euro amounts per month unless stated. UNVERIFIED items flagged.

| Phase | Line items | Recurring total |
|---|---|---|
| **0 (Oct-Dec 2026)** | Domain about EUR 1-2/mo (EUR 10-25/yr, UNVERIFIED); hosting/CDN 0 (Cloudflare Pages free: unlimited bandwidth, 500 builds/month, 20,000 files per deployment - verified via search); analytics 0-9 | **about 2-12** |
| **1 (Jan-Jun 2027)** | Cloudflare Workers paid optional about 5 (Workers free: 100,000 req/day; paid USD 5/mo incl. 10M requests - verified via search); CMP 0-30; transactional email 0 (Resend free tier); licences 0-300 (unknown). **One-off legal review EUR 1,500-4,000** (ASSUMPTION: privacy policy, terms, ranking/ad disclosures). | **about 10-50** plus one-off legal |
| **2 (Jul-Dec 2027)** | Push/email provider 0-50; alerts DB 5-25 (Supabase Pro USD 25 or Cloudflare D1; D1/R2 pricing from memory, UNVERIFIED); payments 4-7% of revenue (web) or 15% (stores); developer accounts Apple about USD 99/yr and Google Play USD 25 one-off (UNVERIFIED) | **about 50-150** |
| **3 (2028)** | API gateway hosting 50-300; monitoring 10-30; data licences 100-1,500 (UNVERIFIED); part-time support/contractor EUR 1-3k/mo if revenue justifies; company admin 50-150/mo (AB share capital SEK 25,000, UNVERIFIED) | **about 300-2,000** |

**Specific cost notes.**
- **GitHub Pages bandwidth:** soft cap 100 GB/month, site up to 1 GB (verified). If a session loads 1.5 / 3 / 5 MB of price JSON (ASSUMPTION; `se_osm_full.json` alone is 1.27 MB raw), the cap is hit at about 68k / 34k / 20k sessions/month, i.e. about 23k / 11k / 7k MAU at 3 sessions per MAU; a pan-EU load is larger. Caching, brotli and per-country sharding can raise this 3-5x, but the ToS problem starts the day ads or subscriptions go live. Recommendation: GitHub for source + Actions cron; Cloudflare Pages/CDN for serving before Phase 1.
- **Ingestion cadence:** scheduled Actions workflows are best-effort and delayed, and are auto-disabled after 60 days of repo inactivity (general knowledge, UNVERIFIED). For 5-minute freshness (DE/FR/UK) move ingestion to Cloudflare Workers cron or a small VPS (EUR 5-10/month); this also solves the Spain egress-IP problem (D4).
- **Break-even:** Phase 1-2 recurring cost of about EUR 50-150/month (EUR 0.6-1.8k/year) is covered by about 100-300 payers at EUR 9.99 or about EUR 150/month of ad + affiliate revenue. Low scenario covers infrastructure only; base funds legal and a part-time contractor from Phase 3.
- **Founder time** is the dominant cost and is not priced here (see risk R8).

---

## 7. Sweden-first go-to-market

**Why Sweden first.** Home market; regulator-recognised need; chains withdrew list prices; bensinpriser.nu is dated, ad-heavy and shows crowd prices up to 3 days old; no map PWA with Sweden exists among surveyed competitors; prices are rising across Europe (Oct 2026), raising demand.

**Positioning.** "Honest fuel prices: every price shows its source and age." Privacy-first, no login, light ads.

**Data plan (the Swedish moat is data we own).**
1. **Short term:** fix the bensinpriser.nu parser and timestamps (D1/D2); ask Crownberry AB for a written licence or partnership; do not monetise that source without an answer.
2. **First-party data:** station-owner self-service (free "verified price" badge; bulk upload/API for chains), user price submissions with a photo of the price sign, contribution rewards (Drivstoffappen model: contributing earns a premium perk - verified pattern), confidence labelling (owner-verified vs crowd vs list price).
3. **Never** present crowd data with the visual confidence of government data (comp-de anti-pattern).
4. **Do not scrape** Circle K, OKQ8 or Preem prices in any form (live Konkurrensverket commitment, SEK 100m penalty each; re-verify status periodically).

**Channels.**
- SEO city and station pages (Swedish municipalities and regions), targeting "bensinpriser [stad]" and "billigaste diesel [stad]".
- PR angle: "what the competition authority recommended, now built", with rising prices as the news hook; consumer reporters and local media; car/EV/caravan communities; motoring clubs as partners, not rivals.
- Cross-border angle (Oresund and Norway border; SEK vs DKK/NOK normalised) as a unique feature.
- Independent chains and stations for verified prices (chain names are examples only; no partner is verified).

**Sequence.** Weeks 1-4 data fixes and honesty release; weeks 2-8 SEO pages; weeks 4-8 affiliate test; weeks 8-12 station-owner pilot; then Denmark/Norway/Finland once sources are licensed.

---

## 8. Prioritised feature list (from competitor gaps)

Source: comp-fr, comp-de, comp-intl. P1 is highest.

| P | Feature | Why (competitor evidence) |
|---|---|---|
| 1 | Per-station source + age badge, confidence colours, "how we rank" page | No competitor does provenance/freshness UI; trust is the product |
| 2 | Working Sweden price layer with timestamps + first-party contributions (owner + user) | Core gap; unlocks every Swedish model |
| 3 | Fast list + map, multi-select fuel types, cheapest-first sort, no login, manual location fallback; price on map pin; heat-map colour vs average | Anti-patterns: forced login/GPS (Geoportal Gasolineras about 1.6 stars), single-select filters, no cheapest-first sort (Osservaprezzi 2.4 stars) |
| 4 | SEO city/station pages, PWA install, offline last-known | Traffic engine; install-friction advantage over native apps |
| 5 | Price alerts (web push/email) with free quota | Highest intent at rising prices; no robust alerts confirmed in the FR cluster |
| 6 | Price history/trend ("trend, not forecast") | Only e-petrol.pl predicts; fact/forecast separation is a trust edge; keep basic history free (1-2-3 Tanken paywall is an anti-pattern) |
| 7 | Cross-border currency-normalised comparison; cheapest stop along route | Nobody does station-level cross-border; route search is paywalled at Essence&CO |
| 8 | Favourites, widgets, share cards; CarPlay/Android Auto later | Essence&CO added CarPlay Sept 2026; Sprit Club premium |
| 9 | Station detail: brand, hours, payment/fuel cards, EV chargers, report-error button; EV charging layer | Feeds sponsored/affiliate slots and B2B enrichment; EV bundling is becoming expected |
| 10 | Accessibility (WCAG 2.2 AA), light weight, privacy-first, multi-language UI | Even the French reference map fails RGAA |

**Anti-patterns to avoid (checklist):** paywalling existing free features; login walls; GPS-only; ads over the core flow or the map; silent staleness; silent fuel-type gaps across countries; fragmenting into multiple apps; overlapping premium tier names.

**TODO V1 - visual mobile-layout inspection NOT done.** Spend about 2 hours taking phone screenshots at 375 px of clever-tanken, mehr-tanken, carbu.com, Essence&CO, Drivstoffappen, bensinpriser.nu, plein-moins-cher.fr and GasBuddy before finalising UI for ad, sponsored and affiliate slots. Until then, layout recommendations here are text-derived only.

**Potential scope expansion - Turkey (parked, 2026-10-02).** Not in the current 42-country set; deliberately out of scope so far (EU candidate, not EEA - same line drawn against Ukraine/Belarus/Russia). Earlier research flagged a plausible path: EPDK (the Turkish energy-market regulator) mandates distributor price notifications, and the major chains (Opet, Petrol Ofisi, BP Turkey, Shell Turkey) run their own station-finder apps with live prices - but none of this was verified live or built. If pursued, treat it like any other country: live-test EPDK's data and the chain APIs with the same rigor as the existing audits (coverage %, timestamp evidence, licence) before writing a scraper. Owner has not requested this yet.

---

## 9. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Licence breach on monetised data (ANWB, PT, DE terms, SE crowd) | High if unmanaged | High | Licence register + per-country monetisation gate; written confirmations (E10); replace ANWB |
| R2 | Swedish data stays thin; product looks empty (free coverage capped near 20%) | Medium | High | First-party portal, Crownberry licence, honest coverage labels, show locations with "no price" state |
| R3 | Ad/consent compliance failure or AdSense rejection of a thin SPA | Medium | Medium | Cookieless analytics, certified CMP, content pages before applying |
| R4 | Trust loss from sponsored content/ads (ranking neutrality) | Medium | High | Separate labelled slots, never alter ranking, publish rules, no paywalling of existing features |
| R5 | Incumbent response (clever-tanken, carbu.com, Google Maps/Waze, fuel-prices.eu) | Medium | Medium | Sweden/Nordic focus, provenance UX, first-party SE data |
| R6 | Source fragility (MINETUR IP blocking, API changes, Tankerkoenig 1 req/min, Overpass 504s) | High | Medium | Proxies/Workers/VPS, health dashboard, last-known-good retention, mirrors, per-source status flags |
| R7 | Hosting ToS (GitHub Pages) and bandwidth caps | Certain at monetisation | Medium | Cloudflare Pages migration in Phase 0 |
| R8 | Founder bandwidth (solo; sponsor and B2B sales) | High | High | Sequence by effort; automate; defer B2B until LOIs |
| R9 | Revenue forecasts too high | High | Medium | Treat as hypotheses; scale or kill at experiment gates; budget on EUR 5-20k year-1 cash |
| R10 | National limits on publishing/reusing price data (e.g. E-Control shows only cheapest nearby) | Low-Medium | Low-Medium | Monitor regulators; keep to licensed feeds |
| R11 | Swedish chain commitments change (Konkurrensverket decision, Dec 2024) | Low | Medium | Re-verify periodically; do not depend on chain prices |
| R12 | Misleading README/marketing claims (38 countries / 80k stations vs actual priced coverage) damage trust | Medium | Medium | Publish a live coverage table from the data manifest; correct README after Phase 0 |

---

## 10. Owner decisions needed

| # | Decision | Recommendation | Needed by |
|---|---|---|---|
| O1 | Register free Tankerkoenig key and (separately) the UK Fuel Finder aggregator account (no-account rule: owner action) | Yes, this week; D3 and D9 are blocked on it | Week 1 |
| O2 | Swedish monetisation stance until Crownberry answers: launch affiliate/ads in Sweden anyway (risk R1), or delay Swedish ads until a licence or first-party data exists | Delay ads on bensinpriser-derived data; affiliate module is lower risk but sits on the same pages - decide explicitly | Before Phase 1 (week 8) |
| O3 | Restate the Phase 0 Sweden gate: 60% coverage (plan) vs about 20% (free-data ceiling) | Use 20% + visible coverage label for Phase 0; 60% only with first-party data | Week 2 |
| O4 | Approve migrating serving from GitHub Pages to Cloudflare Pages before any ads/subscriptions (and the custom domain purchase) | Yes; free tier, low effort | Week 4 |
| O5 | Approve outreach emails (E10) in the owner's name: Tankerkoenig, Crownberry AB, DGEG, MECI Cyprus, KFST-listed operators | Yes; owner or explicit approval per message | Week 1-4 |
| O6 | Legal spend of EUR 1,500-4,000 for privacy policy, terms, ranking/ad disclosure (ASSUMPTION) | Yes before first ad or paid tier | Before Phase 1 |
| O7 | Spain transport: approve a small EU VPS or self-hosted runner (about EUR 5-10/month) or Cloudflare Worker | VPS also serves 5-minute ingestion later | Week 3 |
| O8 | Positioning: "no-ads/no-tracking" brand vs "light non-personalised ads"; one ad slot or none | Light ads with a supporter no-ads option, tested via E6 holdout | Week 5 |
| O9 | Prices and tiers: EUR 9.99 / SEK 99 annual anchor; free-quota boundaries (3 alerts free) | Confirm after E7 | Week 10 |
| O10 | Company form (sole trader vs AB) before taking payments or B2B contracts | Decide before Phase 2 | Q2 2027 |
| O11 | Scope discipline: remain Sweden-first with a small set of licensed countries, or keep pursuing all 38 countries in parallel | Sweden + FR/IT/GR/UK/ES/DK first; park low-value Tier-3 | Week 2 |
| O12 | Greenlight the 2-hour competitor mobile screenshot pass (TODO V1) | Yes, before slot design | Week 3 |

---

## Appendix A - Key sources (as cited in the research files)

- Regulation research: `reg-dach`, `reg-west`, `reg-south`, `reg-nordic`, `reg-central-east`, `reg-uk-west-balkans-eu` `.verify.json` (`final` arrays). Examples: SI 2025/1356 (legislation.gov.uk/uksi/2025/1356/made); gov.uk Fuel Finder guidance (OGL v3.0; interim scheme closed 1 May 2026).
- Competitors: `comp-fr.json`, `comp-de.json`, `comp-intl.json`.
- Audits (live-tested 2026-10-01): `se-chains`, `se-agg`, `dach`, `iberia-fr` `.audit.json`; `analysis_anwb.txt`; `anwb_tile.py` and `anwb_tiled_*.json` (tiling proof of concept).
- Licence and platform pages: creativecommons.tankerkoenig.de; docs.github.com Pages limits; gov.uk access-fuel-price-data; fuel-prices.eu/api; bensinpriser.nu/om-oss; henrikhjelm.se/api; data.gouv.fr Etalab 2.0; AdSense help (CMP requirement); RevenueCat state of subscription apps; gasbuddy.com premium; Trafikanalys vehicle statistics 2025; konkurrensverket.se; Cloudflare pricing summaries.

## Appendix B - Unverified summary (do not rely on these without confirmation)

- All traffic, conversion, RPM, payout, station-count and customer-count figures (ASSUMPTIONS).
- Swedish affiliate payouts and programme availability.
- Whether Tankerkoenig treats ads/premium as commercial use needing a contract; Crownberry/henrikhjelm reuse terms; ANWB ToS; Danish per-operator ToS; the UK Fair Use "no favouring suppliers" clause; formal Spanish licence; final UK OGL wording.
- Swedish statutory sections (LEK cookies, marketing-law labelling); DSA small-enterprise exemption; ODbL share-alike scope; EU database-right view; Stripe/Paddle/Apple/Google exact current fees; Cloudflare R2/D1 prices; GitHub Actions minutes policy.
- Premium prices of Fuelio, mehr-tanken, 1-2-3 Tanken, Sprit Club.
- Visual mobile layout of competitors (TODO V1).
