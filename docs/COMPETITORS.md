# EuroFuelPrices — Competitor Teardown (usability, features, layout)

Date: 2026-10-02. Author role: technical writer / UX analyst.
Inputs: `comp-fr.json`, `comp-de.json`, `comp-intl.json` (desk research dated 2026-10-01; WebFetch/WebSearch of public pages, store listings and Apple's public lookup API). Nothing here was observed by actually using the products on a phone: see section 7 (TODO). The baseline description of our own app comes from reading `web/index.html` and `web/sw.js`, not from a visual run.

Evidence conventions used throughout:

- **Confirmed** = fetched from the competitor's own page, a regulator, or Apple's API (ratings counts dated 2026-10-01).
- **Reported** = secondary press / review sites.
- **Unverified** = the researchers could not confirm. A "–" in a matrix cell means "not found in the research", NOT "confirmed absent".
- Prices of premium tiers and rating figures are as reported by the research; they were not re-checked against a live billing screen.

---

## 1. Executive summary

1. **The data is not the moat; the product is.** Where governments mandate reporting (DE, FR, IT, ES, GR, UK, AT) the same feed is free to everyone. Germany alone has 44+ registered re-users of MTS-K (confirmed, Bundeskartellamt list). Competition is fought on UX, forecasts, alerts, brand distribution and bundling.
2. **Official apps have the best data and the worst UX** (Geoportal Gasolineras ES ~1.6 stars, Osservaprezzi IT 2.4 stars on 104 ratings), while a third-party app on the same feed wins the reviews (Prezzi Benzina IT). Nobody has shipped one product that is government-grade AND well designed across several countries. That is the single clearest structural gap.
3. **Nobody makes provenance and freshness a first-class, per-station UI element.** Sources are named in marketing copy; per-price age and source type ("official feed, 4 min ago" vs "user report, 2 days ago") is not systematically shown. The closest examples are plein-moins-cher.fr (visible "last updated" timestamp + reliability FAQ), bensinpriser.nu (colour by who reported the price), fuel-prices.eu (next-update label), Geoportal (colour vs regional average). Our cards already have a freshness class and a source string; promoting them is cheap.
4. **Sweden/Nordics are weakly served.** Swedish-market tools are crowd-based and dated (bensinpriser.nu: volunteer prices that expire after 3 days; Bränsleappen: crowd, increasingly paywalled, 1.9 stars on Google Play). The one pan-European competitor that covers Sweden live, **fuel-prices.eu**, is a no-map, no-app data site that itself states Swedish prices are chain list prices ("listpris"), not pump prices. Major multi-country consumer apps (Fuel Flash / Benzinpreis-Blitz, ADAC, 1-2-3 Tanken) do not cover Sweden; Benzinpreis-Blitz adds Denmark and Croatia.
5. **Monetisation backlash is the most reliable predictor of rating collapse**: intrusive ads (clever-tanken, PetrolPrices, Essence&CO interstitials) and sudden paywalling of previously free features (Bränsleappen, Fuelio). Positioning as no-account, ad-light, PWA with free history/alerts is genuinely open, but only essencemoinscher.fr (new, unproven) and plein-moins-cher.fr (web) claim "no ads" today.
6. **Table stakes** for a credible mobile product in 2026: map + list, fuel filter, near-me with manual fallback, sort by price, brand filter, favourites, price alerts, route search, history/trend, EV charging, CarPlay. We have the first three or four; section 6 prioritises the rest.

---

## 2. Feature matrix

Legend: **Y** = evidenced; **P** = paywalled; **–** = not found in research; **?** = unverified or sources conflict. Source type: **G** = government/mandated feed, **C** = crowdsourced, **M** = mixed (official + crowd), **Ch** = chain/own-network data, **S** = scraped from chains, **?** = unstated.

### 2a. Consumer fuel finders (direct competitors)

| Product | Mkts | Src | Map | Route | Alerts | Favs | History / forecast | EV | CarPlay | Freshness shown | Brand filter | Pricing |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clever-tanken | DE | G | Y | – | Y | Y (login) | Y stats | Y | Y | – | ? | Free + ads; EUR 3.99/yr ad-free (reported) |
| mehr-tanken | DE | G | Y (map+list parallel) | Y | Y | ? | Y forecast ("Flizzi") | Y (slider) | ? | – | Y (40+) | Freemium; sub price unverified |
| ADAC Drive | DE+AT/IT/FR/ES/SI/UK | G | Y | Y (full nav) | ? | Y (account) | Y 24h/7d + best-time | Y | Y | – | operator filter | Free (club funnel) |
| benzinpreis.de | DE | G | Y | Y (detour calc) | Y | ? | Y 4-day forecast, archive, CSV | – | ? | – | ? | Free + banner ads |
| 1-2-3 Tanken | DE/FR/ES/PT/IT | G | Y | Y | Y (free: drop alerts; Plus: unlimited) | Y | P (charts) | – | ? (Watch is P) | – | ? | Free + "Plus" sub (price unverified) |
| bessertanken.de | DE | G | ? | – | – | – | – | – | Y | – | – | Free, donations |
| Tankerkönig (own app) | DE | G | – | – | – | – | Y 30/90-day | – | – | – | – | Free; value is the CC BY 4.0 API |
| Fuel Flash / Benzinpreis-Blitz | 7 / 10 countries (see note) | G (mostly) | Y | – | Y | Y | Y chart | – | – | – | – | Unverified |
| Sprit Club (AT) | AT/DE/IT/FR/ES | ? | Y | Y | ? | Y | – | – | P | – | – | Free + Premium sub (price unverified) |
| Essence&CO | FR (+BE/CH listings) | M | Y | P | ? | – (requested by users) | – | – | Y (v4.13) | – | ? | Free + interstitial ads; premium reported EUR 4.99 / 5.99 one-off or ~EUR 2/mo |
| carbu.com | BE/FR/LU | G-derived | Y | Y | ? | Y | Y trend + BE max-price forecast | – | – | – | Y | Free + ads; Pro EUR 1.99/mo or 9.99/yr; sponsored placement |
| plein-moins-cher.fr / fillgo | FR (+ES) | G | Y (heat map) | ? (sources conflict) | – | – | avg tables | – | – | **Y (last updated)** | Y | Web: no ads; app: ads |
| essencemoinscher.fr | FR | G | ? | Y | – | – | – | – | – | daily-update claim | – | Free, "no ads, no tracking" |
| carburants.org | FR | G | – (list) | – | – | – | up/down vs previous | – | – | – | – | Unverified |
| Bränsleappen / Drivstoffappen | SE/NO/DK | C | Y | Y | Y | ? | – | Y (+car wash) | – | sort by latest update | Y (chain) | Freemium; free tier cut to ~3 nearest stations |
| BensinPris | NO | C | – (list-first) | – | Y | Y | – | – | – | 24h window | – | Unverified |
| Tankille | FI | C | Y | Y | ? | Y | – | – | – | sort by update time | – | Unverified |
| bensinpriser.nu | SE | C | Y | – | – | – | – | – | – | **Y (colour by reporter; 3-day expiry)** | – | Display ads |
| Danish apps (TankBilligt, Tankpriser.dk, Brændstofpriser) | DK | S | Y | – | – | – | – | Y (Tankpriser.dk) | – | – | chain-based | Unverified |
| PetrolPrices | UK (+FR) | M | ? (postcode-first) | – | ? | – | – | – | – | – | Y | Free + ads + Pro sub |
| PumpWatch | UK | G | Y | – | – | – | – | – | – | – | – | Unverified |
| Prezzi Benzina | IT | G | Y (price preview on map) | – | – | – | – | – | – | – | – | Unverified |
| TuTankuj / e-petrol.pl | PL | ? | ? | – | – | – | Y analyst forecast | – | – | – | – | Unverified |
| mBenzin.cz | CZ | C | ? | – | – | – | Y graph | – | – | – | – | Unverified |
| fuelGR / FuelDaddy | GR (+CY) | G | Y | – | – | – | – | – | – | 30-min cadence stated | Y | Unverified |
| fuel-prices.eu | 27 EU weekly; 12 live | G? (SE = list prices) | – | – | – | – | Y (1w to annual, since 2005) | – | – | **Y (next-update label)** | – | No ads; paid API (unverified) |

Note on Fuel Flash vs Benzinpreis-Blitz: the Play Store package of "Fuel Flash" is `de.mwwebwork.benzinpreisblitz`, so these are very probably the same app marketed under two names with differing country lists (7 vs 10, the latter adding Denmark, UK and Croatia). Treated here as one product; unverified.

### 2b. Official portals, embedded features, chain apps, B2B

| Product | Type | Src | Notable features | Verdict for us |
|---|---|---|---|---|
| prix-carburants.gouv.fr (FR) | Government | G, ~10 min | Map, route search, amenity filters (EV, WiFi, ATM), shortage flags, open-data API | Best-in-class data; French-only, web-only, RGAA accessibility gap on the map |
| Geoportal Gasolineras (ES) | Government | G, 5 min | Colour vs provincial average, sort cheapest-first, favourites, EV points | ~1.6 stars: mandatory GPS, login failures, broken route tool |
| Osservaprezzi Carburanti (IT) | Government | G | Price vs regional average, self/full-service split | 2.4 stars (104 ratings): no cheapest-first, single-select filters, no price on map |
| Spritpreisrechner (AT) | Government | G | Location/town/district search, favourites, 3 fuel types | Minimal; third parties supply the UX |
| fuelprices.gr (GR) | Government | G | Prefecture drill-down | Third-party apps supply the UX |
| TCS Benzinpreis-Radar (CH) | Club | C (gamified) | Map, points + monthly prizes | No mandate in CH found; crowd, 4.28 stars overall app |
| RAC Fuel Watch / myRAC (UK) | Club | ? | Duty/VAT/margin breakdown, history since 2000, free cap 9 searches/day | Cost-breakdown is a trust feature nobody else has |
| Google Maps | Embedded | G for DE (reported) | Price strip on station card, in-nav "add stop" | Mobile only, no history/alerts, patchy |
| Waze | Embedded | C | Sort by price, in-route cheapest | Feature hidden behind settings (French press: "little known") |
| Yanosik (PL) | Embedded | C | Along-route list, area alerts | Fuel is a side feature |
| Fuelio | Log + prices | ? | Fuel log, CarPlay, premium route planning | 2023 paywall backlash |
| GasBuddy (US benchmark) | Dedicated | C | Gamified reporting, pay-with-card, B2B licensing | 100M+ downloads; proves the crowd + B2B model |
| TomTom Fuel Services | B2B / OEM | ? | In-dash prices along route, 10 min refresh | Reaches users who never install a fuel app; forum: "inconsistent" |
| Tanka, Circle K (SE) | Chain apps | Ch | Mobile BankID pay, licence-plate pay, loyalty | No cross-brand comparison |
| PACE Drive (DE) | Payments | ? | In-car payment at partner stations | Payment business, not a comparison tool |

---

## 3. Per-competitor profiles

Format: data source, features, UX/layout, strengths, weaknesses, monetisation (with traction where known). Items marked unverified were not confirmed by the research.

### 3.1 Germany and DACH

**clever-tanken.de (+ app, "Clever Laden")** — https://www.clever-tanken.de/
- Data: MTS-K (Bundeskartellamt), confirmed re-user "supplemented by independent research".
- Features: "Magic Map" plus city/list ranking; very wide fuel taxonomy (E10, E5, Super Plus, Premium Diesel, HVO, GTL, LKW-Diesel, LPG, CNG, LNG, bioethanol, AdBlue, hydrogen); radius 1 to 25 km; push price alarm; favourites (needs registration); price statistics; EV locator (plug type/power, remote start); landscape mode; CarPlay.
- UX: classic map/list hybrid; EV is a separate mode via toggle.
- Strengths: operating since 1999, media halo (Axel Springer orbit), multiple test-winner awards, 10M+ Android installs, 4.60 stars / ~250k ratings (iOS).
- Weaknesses: ad clutter (Trustpilot: "Werbemüll en gros", ad-blocker "definitely" needed), site reportedly lags real-time updates, high data usage on some devices, Google Play 3.5 stars vs App Store 4.6, login gate on favourites.
- Monetisation: ads (Media Impact), EUR 3.99/yr ad-removal (reported; older source cites EUR 1.99), "Clever Deal" partner offers, partner leads.

**mehr-tanken.de (+ "Flizzi")** — https://www.mehr-tanken.de/
- Data: MTS-K partner (confirmed).
- Features: full-screen map OR list OR both in parallel; Flizzi assistant with live comparison, price forecast and refuel recommendation weighing price against distance; route planner; price alarm; consumption calculator; fuel/electricity slider on one surface; 40+ brand filters.
- UX: menu top-right; single-surface fuel/EV toggle (cleaner than clever-tanken's separate mode).
- Strengths: Motor Presse Stuttgart backing, awards (FAZ Institut 2022, FOCUS-MONEY 2021 per own store text), 4.62 stars / 361,642 ratings, the highest count profiled.
- Weaknesses: premium naming inconsistent ("mehr-tanken+" vs "PUR"), free/paid split unclear.
- Monetisation: freemium subscription (price unverified), media cross-promotion.

**ADAC Spritpreise / ADAC Drive** — https://www.adac.de/verkehr/tanken-kraftstoff-antrieb/deutschland/spritpreise/
- Data: MTS-K for DE; other countries' sourcing not detailed. Markets: DE, AT, IT, FR, ES, SI, UK.
- Features: search by postcode/city/GPS; fuel filter incl. HVO100, CNG; favourites via free account (membership not required); 24h and 7-day history with "best time to refuel" forecast; full navigation with CarPlay, eco routes, parking, weather, tolls; 120,000+ EV stations.
- UX: fuel is one tile in a super-app.
- Strengths: trust, free, broadest feature set; 4.50 stars / 251,829 ratings.
- Weaknesses: heavy and unfocused; fuel-type coverage inconsistent per country.
- Monetisation: club funnel (membership, insurance, "Vorteilswelt" partner discounts).

**benzinpreis.de** — https://www.benzinpreis.de/de/
- Data: MTS-K. Features: map, 4-day forecast (updated several times daily), alerts, archive with "Preisfixing" analysis, route planner with detour calculator, CSV export, widget.
- UX: power-user / data-nerd; cluttered, AUTODOC banner ad seen directly.
- Traction: 4.43 stars / 2,853 ratings. Monetisation: display ads.

**1-2-3 Tanken** — https://www.123tanken.de/
- Data: MTS-K and the other countries' central reporting pipelines. Markets DE/FR/ES/PT/IT.
- Features: map+list, route search, favourites, price-drop alerts (free); interactive price statistics, home-screen widget, Apple Watch app, unlimited alerts and ad-free are "Plus".
- Strengths: simple freemium split that leaves base data free; 4.56 stars / 30,463 ratings.
- Weaknesses: price history paywalled (cuts against transparency positioning).

**bessertanken.de** — https://www.bessertanken.de/
- MTS-K "every few minutes"; postcode/city search, 10 km default radius, best-price highlight, opening hours, CarPlay; deliberately lacks alerts, history, brand filter, route ("planned"). No registration, no ads seen, optional donations. 4.53 stars / 664 ratings.

**Tankerkönig** — https://www.tankerkoenig.de/
- CC BY 4.0 open API over MTS-K; the de-facto backbone for German indie apps. Own app has 30/90-day trends but only 123 ratings. Structural, not experiential, competitor.

**Benzinpreis-Blitz / Fuel Flash** — https://apps.apple.com/de/app/benzinpreis-blitz/id1212144168
- Data: "mostly from the national authorities". Up to 10 countries (DE, AT limited to Diesel/Super/CNG, LU, FR, PT, ES, IT, DK, UK, HR).
- Features: location or manual search, list or map, opening hours/services/payment methods and fuel-card acceptance per station, alerts, price chart, favourites, "report wrong price", saved search templates. Multi-language UI (EN/FR/DE/IT/PT/ES).
- Strengths: solo developer with parity to media-backed apps; 4.63 stars / 37,052 (DE iOS), 4.7 on Play with 92,913 ratings (per FR research); explicit about per-country gaps (e.g. Portugal excludes Madeira/Azores).
- Weaknesses: no Nordics/Sweden; Android design reported weaker than iOS. Monetisation unverified.

**PACE Drive** — in-car payment at partner stations, 4.66 stars / 25,189 ratings. Payment model; partner-only coverage; needs card on file. Not a direct competitor, but shows a revenue path we cannot replicate quickly.

**Austria: Spritpreisrechner (E-Control), Sprit Club, Spritpreise Österreich**
- Official tool is a minimal government utility (location/town/district, favourites, Diesel/Benzin/CNG only); legal basis for mandatory reporting NOT confirmed in the research.
- Sprit Club (5 countries) adds route/destination search; Premium adds ad-free, Siri, CarPlay, widgets (price unverified). Ratings 4.55 / 4.57 / 4.48.

**Switzerland: TCS Benzinpreis-Radar, Comparis Benzinpreis Schweiz**
- No mandatory reporting regime found. TCS is explicitly crowd + gamified (points, monthly prizes) inside a large club app (4.28 stars / 16,147). Comparis standalone app: 3.0 stars / 10 ratings. A rigorous, clearly labelled model for CH is an opening.

**Google Maps** — price strip on station cards, in-navigation "add stop"; DE data reported to come from MTS-K; mobile only; coverage patchy, a 2026 Android outage of prices was reported. No alerts, history or favourites.

### 3.2 France and francophone

**plein-moins-cher.fr + fillgo (Android)** — https://plein-moins-cher.fr/en/index.html
- Data: French government feed, "every 10 minutes". Markets FR (+ES per the site).
- Features: heat map (colour = price level), list/map toggle, brand/region/department filters, geolocation, min/max/mean per fuel and area, **visible last-updated timestamp**, FAQ on data reliability, press-credibility strip, embeddable widget, 6 UI languages (FR/EN/DE/NL/ES/IT). Whether route filtering exists is conflicting between research files.
- UX: desktop-first, responsive; fillgo shows station name + price on the pin.
- Weaknesses: no alerts, favourites, history, route (per English page); Android-only app with ads; split brand web/app.
- Monetisation: none on the web (zero ads claimed); app has ads. This is the owner's layout reference.

**prix-carburants.gouv.fr** — https://www.prix-carburants.gouv.fr/
- Primary source (Licence Ouverte; retailers above 500 m3/yr must declare; ~10 min feed, daily feed, archives since 2007). Map with geolocation, department/city/postcode search, fuel and station-type filters, amenity filters (EV, restaurant, ATM, WiFi, truck), journey search, shortage/outage flags, API/CSV/GeoJSON.
- Weaknesses: French-only, no native app, map has a confirmed RGAA accessibility gap (no non-JS alternative); a related portal page reported stale since 2026-06-25 (unverified whether fixed).

**carburants.org / prixcarburant.org** — registered data.gouv.fr reuse; list/table-first (not a map); national average, up/down vs previous, department drill-down. Useful note: cited for cross-border residents who re-check prices several times a day.

**Essence&CO (Ripple Motion)** — https://apps.apple.com/fr/app/essence-co/id459724569
- Hybrid official + community prices. Map and fuel filters, geolocation, premium "Route", community updates, CarPlay (reported v4.13). Since 2008; 8M+ downloads; 4.5 stars / 46,000 (App Store), Play 3.3 to 4.4 depending on source / ~20,400. iOS 18.6+ required, 67.3 MB.
- Weaknesses: full-screen interstitial ads; no favourites despite long incumbency; route is paywalled.
- Monetisation: ads + premium (reported EUR 4.99, EUR 5.99, or ~EUR 2/mo; sources disagree).

**Mappy** — fuel is one module of a trip-cost estimator (tolls + fuel + ride-share, Crit'Air/ZFE handling). Price on map pins, brand filter. Daily refresh (slower than the 10-min feed). Mappy blog publishes recurring regional-average SEO content.

**carbu.com (Fuel Media Service S.A.)** — https://carbu.com/
- BE/FR/LU. Map or list, geolocation/province/city/brand search, sort, favourites, route search, price evolution, cost calculator, **forecast of Belgium's next government maximum-price change**. Sister site mazout.com.
- Weaknesses: Trustpilot 3.5/5 (FR); iOS "Carbu" app shows 1 review; pay-for-placement may undermine ranking objectivity.
- Monetisation: sponsored position ~EUR 1.5/day + IAB 300x250 banner; email list (100,000+); Carbu Pro EUR 1.99/mo or EUR 9.99/yr after 7-day trial. Self-reported ~400,000 monthly sessions.

**essencemoinscher.fr** — https://essencemoinscher.fr/
- Launched 2026 (unproven). Official data only, daily update, city pages (Paris, Lyon, Marseille, Toulouse, Nice, Nantes, Bordeaux, Lille) plus department/region pages, route comparison, "add to home screen". Explicit "no advertising, no tracking" positioning; names Waze, Google Maps and Zagaz as stale/ad-supported. A direct emerging competitor on our positioning (in France only).

**Waze** — crowd-only; sort by Price instead of Distance and set fuel type in vehicle settings; in-route cheapest; French press reports 10 to 15 cents/L savings. Weakness: hidden, no dedicated fuel UI.

**Fuelio** (Sygic) — fuel/expense log with nearby prices; 6.2M downloads, 4.27 stars / ~130K; users say prices "can be outdated"; premium introduced June 2023 after 10 years free (route planning, receipts, reports), with reported backlash.

### 3.3 Nordics, UK, Southern and Eastern Europe, global

**bensinpriser.nu (SE)** — https://bensinpriser.nu/
- 100% crowd: visitor prices (black), station-owner prices (green), chain reference prices (olive). Map + list, fuel filter (95/E10, 98/E5, diesel, E85, fordonsgas, biodiesel), sort by price. **Each price expires after 3 days** then shows "no current price". Legacy desktop-first UI, unofficial third-party iOS wrapper ("BensinPris"). Display ads. Well ranked for "bensinpriser". No city landing pages.

**Drivstoffappen / Bränsleappen (NO/SE/DK)** — https://www.drivstoffapp.no/
- Crowd; fuel + EV + car wash; alerts; route planner; sort by chain/price/location/latest update; reward = free subscription for reporting. 1M+ users claimed.
- Weakness: free tier reduced to ~3 nearest stations; 4.5 stars iOS (~39,000) vs 1.9 stars Google Play (~14,500), driven by the subscription push.

**BensinPris (NO)** — crowd, 1,900+ stations (95%+ claimed), 24h window, alerts, favourites, list-first.

**Tankille (FI)** — https://www.tankille.fi/ — crowd with **voice price reporting**, route search, favourites, colour-coded comparison, station photos, per-city static pages (/helsinki, /tampere, /suomi) for SEO.

**Danish apps (TankBilligt, Tankpriser.dk, Brændstofpriser)** — chain scraping (6 to 9 chains); TankBilligt links membership cards so the map shows the user's **net price after loyalty discount**; Tankpriser.dk covers 2,000+ stations and 10,000+ EV locations. Fragmented market.

**Tanka (SE) / Circle K** — chain-only apps (Mobile BankID pay, licence-plate pay, loyalty). No cross-brand transparency; Circle K splits into three apps.

**PetrolPrices (UK)** — mix of retailer feeds and user data; postcode-first; reviews, garage/MOT, exclusive offers; 4.5 stars / ~11,300 (Play). Complaints: ads "blocking most of the screen", an inappropriate ad, login failures, no out-of-stock flag.

**PumpWatch (UK)** — free map over the UK mandatory Fuel Finder scheme (8,211 stations claimed); new, shallow.

**RAC Fuel Watch / myRAC** — history since 2000, duty/VAT/margin breakdown per litre; myRAC free users get 5 cheapest results and max 9 searches/day.

**Osservaprezzi Carburanti (IT, MIMIT)** — law-backed (Law 99/2009) feed; compares to regional average, self vs full-service. Per reviews: no live cheapest-first ranking, full national reload on each filter change, single-select filters, no price preview on map, default list not filtered by region. 2.4 stars / 104 ratings. **Prezzi Benzina** reuses the same data and is preferred: live ranking, price on map, multi-select filters.

**Geoportal Gasolineras (ES, MITECO)** — https://geoportalgasolineras.es/ — SIPP data, 5-minute updates, price colour-coding vs provincial/municipal average, cheapest-first default, favourites, EV. Reviews: mandatory GPS, login/registration failures, crashes, broken route tool, web faster than app. ~1.6 stars.

**e-petrol.pl / TuTankuj, Yanosik, mBenzin.cz (PL/CZ)** — analyst price-direction forecast (TuTankuj); crowd prices on map pins plus along-route list (Yanosik, embedded in nav app); crowd history graph and Europe-average page (mBenzin).

**fuelprices.gr + fuelGR / FuelDaddy (GR/CY)** — official observatory with basic UX; third-party apps add map/filters (30-minute sync; Cyprus dual-country sync).

**GasBuddy (US)** — crowd at scale, gamification, pay-with-card cashback, ads + referral + subscriptions (USD 7.99 to 9.99/mo reported) + B2B data and white-label licensing; 4.7 stars / ~447,000 ratings (iOS).

**TomTom Fuel Services (B2B)** — in-dash prices along route, 10-minute refresh, OEM bundling; forum complaints of inconsistent prices.

**fuel-prices.eu (Fuelo)** — https://www.fuel-prices.eu/ — **closest positioning overlap with us.** 27 EU states weekly (EC Weekly Oil Bulletin), live per-station data in 12 markets incl. **Sweden**, Croatia, Denmark, France, Greece, Iceland, Italy, Romania, Slovenia, Spain, UK, Austria; 58,633+ stations; history since 2005; JSON/Markdown exports, natural-language API; per-update freshness labels ("next update expected ..."). Weaknesses: **Swedish prices are chain list prices (listpris), not pump prices (site's own statement)**; no map, no app, no favourites/alerts/route; surprisingly omits Germany and Switzerland from live tier. No ads or consumer premium found; paid API unverified.

---

## 4. Patterns to adopt vs anti-patterns

### 4.1 Adopt

| # | Pattern | Evidence |
|---|---|---|
| A1 | Visible freshness timestamp plus source on every price/station; reliability FAQ | plein-moins-cher.fr; fuel-prices.eu "next update"; bensinpriser.nu provenance colours |
| A2 | Price shown on the map pin; colour gradient or colour vs area average | fillgo, Mappy, Prezzi Benzina vs Osservaprezzi; Geoportal (vs average); plein-moins-cher heat map |
| A3 | Map and list together (parallel or one-tap toggle) | mehr-tanken; universal across the set |
| A4 | Cheapest-first one tap; do not bury it | Geoportal default; Waze hides it; Osservaprezzi cannot do it (anti-example) |
| A5 | Favourites and price alerts as the retention loop; keep base data free, no sign-up | near-universal (clever-tanken, mehr-tanken, 1-2-3, Bränsleappen); bessertanken no registration |
| A6 | Route / along-the-way search | mehr-tanken, ADAC, carbu.com, Tankille, Yanosik, Waze, benzinpreis.de detour calculator |
| A7 | History/trend and a short-horizon "best time" view, honestly labelled | ADAC 24h/7d, benzinpreis.de 4-day, mehr-tanken Flizzi, mBenzin graph, fuel-prices.eu since 2005 |
| A8 | City/region static landing pages | clever-tanken city ranking, essencemoinscher.fr, carburants.org, Tankille, carbu.com paths, mehr-tanken "Regional Tanken" |
| A9 | Manual location fallback; installable PWA instead of forced app install | Geoportal (GPS mandatory = complaint); essencemoinscher.fr "add to home screen" |
| A10 | Per-station extras that matter: opening hours, payment/fuel-card acceptance, services, shortage flags | Benzinpreis-Blitz, prix-carburants.gouv.fr |
| A11 | Multi-language UI | plein-moins-cher (6), Benzinpreis-Blitz (6) |
| A12 | Gentle monetisation: micro ad-removal or none; sponsored offers outside the lookup flow | clever-tanken EUR 3.99/yr; PetrolPrices offers; GasBuddy diversified model |
| A13 | Loyalty-aware "your net price" idea | TankBilligt (DK) |
| A14 | Trust through cost transparency (duty/VAT/margin) | RAC Fuel Watch |

### 4.2 Anti-patterns to avoid

| # | Anti-pattern | Evidence |
|---|---|---|
| X1 | Silent staleness: prices linger with no age cue, or vanish abruptly | bensinpriser.nu (3-day cliff), BensinPris (24h, weak cue) |
| X2 | Sudden paywalling of previously free features | Bränsleappen 1.9 stars Play; Fuelio 2023 |
| X3 | Login/registration to see basic data | Geoportal Gasolineras (top complaint); clever-tanken gates favourites |
| X4 | Mandatory GPS with no manual fallback | Geoportal |
| X5 | Intrusive ads: interstitials, banners over content, unsuitable ads | Essence&CO, clever-tanken, PetrolPrices, benzinpreis.de |
| X6 | Not ranking by price live; single-select filters; full reload on filter change | Osservaprezzi |
| X7 | Paywalling price history | 1-2-3 Tanken Plus |
| X8 | Presenting crowd data with the same visual confidence as official data | TCS Benzinpreis-Radar |
| X9 | Silently inconsistent fuel taxonomy across countries | Austria in several apps; Benzinpreis-Blitz notes |
| X10 | Bloating into a super-app or splitting into several apps | ADAC Drive, TCS; Circle K's three apps |
| X11 | Overlapping premium tier names | mehr-tanken+ vs PUR |
| X12 | Presenting opinion-based forecasts as fact | analyst forecasts (TuTankuj); our "honest data" rule |
| X13 | Pay-for-placement that can reorder "cheapest" results undisclosed | carbu.com sponsored position |
| X14 | iOS/Android quality gap | Essence&CO, clever-tanken, Bränsleappen, Fuel Flash (a PWA avoids two codebases) |

---

## 5. Gaps we can exploit

1. **Government-grade data AND good UX in one multi-country product.** Every time a government has the best data (IT, ES) its own app has the worst reviews and a third party wins. Nobody spans countries.
2. **Provenance + freshness as a first-class UI element, per station**, across all countries: "Official feed (MTS-K), 4 min ago" vs "Chain list price" vs "User-reported, 2 days ago, unconfirmed".
3. **Sweden with real pump prices.** Competitors: crowd (bensinpriser.nu, Bränsleappen), list prices (fuel-prices.eu), or none (DE/FR apps). Caveat from our own audit: the bensinpriser.nu feed parser is buggy and only ~20% of Swedish stations have crowd prices, so we must label coverage honestly rather than claim completeness.
4. **True cross-border map**: nobody lets a driver compare live station-level prices across, e.g., the SE/NO/DK, FR/ES or DE/PL borders in one map, and no one normalises currencies (SEK/NOK/DKK/CHF/PLN/CZK/HUF to EUR) for road-trip comparison. We already store per-price `currency` and render local symbols.
5. **No-account, ad-light, privacy-first PWA.** Only essencemoinscher.fr (new, FR-only) and plein-moins-cher.fr web claim it. All big apps are ad-funded, club funnels, or payment businesses. Install friction: every major competitor is a native store install, often 50 to 100 MB; ours is a static PWA with a service worker.
6. **Consistent fuel taxonomy and explicit per-country coverage notes** (which fuels, which regions, what cadence); most competitors silently drop grades.
7. **Honest, history-based "best time to refill"** built on real feed history instead of analyst opinion; only one Polish product ships a forecast, DE apps ship it behind logins/paywalls.
8. **Offline/low-signal resilience**: no competitor claimed it; our service worker already caches the shell and data (network-first with fallback).
9. **Accessibility**: even the French reference portal fails RGAA on its map; a keyboard- and screen-reader-usable list alternative is an easy win.
10. **Timing**: prices are rising across Europe on 2026-10-02, so demand for trustworthy comparison and alerts is cyclically high; features that can ship fast (provenance badges, sort, favourites) beat slow ones.
11. **Open lane: B2B data/API** (GasBuddy and TomTom show it works; fuel-prices.eu sells an API). Not a UI item, noted for later.

---

## 6. Prioritised UI/UX changes for EuroFuelPrices (mobile-first)

Our current baseline, read from `web/index.html` (not visually verified): Leaflet map with marker clustering and per-station price tooltips only from zoom 13; fuel chips ("All fuels" default); a tab bar (Map / Nearby / Search / List / Filter); a "Near Me" button; a sort button that cycles Default / Price / Distance; station cards with a freshness class, source text, last-updated time and a "Go" navigation button; country and fuel selects; Nominatim place search; an admin "Stats" link on the map; PWA manifest and service worker.

Effort: S = days or less, M = about a week, L = multi-week. All changes are UI/UX only; items needing new data are flagged.

### P0 — ship first (trust and basics; high leverage, low effort)

| # | Change | Rationale | Competitor evidence | Effort |
|---|---|---|---|---|
| 1 | **Provenance + freshness badge on every price/card/popup**: source type icon (official feed / chain list price / crowd), age as "4 min ago", amber after a per-source threshold, grey with explicit "possibly outdated" instead of silently dropping or hiding. Link the badge to a one-line "how we get this data" sheet per country. | Our core promise is "data is king"; honest labelling beats everyone and prevents the stale-data complaints that sink crowd apps. Cards already carry freshness class and `source`, so this is mostly presentation. | plein-moins-cher.fr (timestamp + FAQ), bensinpriser.nu (colour per reporter, 3-day cliff as the anti-example), fuel-prices.eu (next-update label), TCS (anti: crowd shown with same confidence) | S |
| 2 | **Cheapest-first as a visible, one-tap control**: replace the cycling "Default / Price / Distance" button with a two-option segmented control (Price / Distance); default to Price within the current radius/viewport after Near Me. | Cycling hides the options; the product's purpose is saving money. | Geoportal (cheapest-first default), Waze (hidden = criticised), Osservaprezzi (cannot rank = 2.4 stars), ES/IT reviews | S |
| 3 | **Manual-location-first onboarding**: never block on GPS; "Near Me" falls back to the place search with a clear message; remember last area. | GPS-mandatory and login-gated flows are the top complaints of the worst-rated apps. We already have search and no login: protect that. | Geoportal (GPS mandatory, login failures, 1.6 stars), bessertanken (no registration) | S |
| 4 | **Always show price on the pin and colour by relative price** (green to red against the visible-area or regional median, with legend), at lower zoom than 13 where density allows, instead of tooltip-only at zoom 13+. Keep clusters but show "from X.XX" (min price) per cluster, which the code already computes. | At-a-glance scanning is the main mobile job; heat/relative colour removes mental ranking. | plein-moins-cher (heat map), fillgo and Mappy (price on pin), Geoportal (colour vs average), Prezzi Benzina (price preview) vs Osservaprezzi (none) | M |

### P1 — core table stakes

| # | Change | Rationale | Evidence | Effort |
|---|---|---|---|---|
| 5 | **Mobile map + list in one view**: bottom sheet (peek / half / full) over the map that lists the visible stations sorted by price, tap syncs map and card. Reduce reliance on switching tabs. | Fewer taps to compare; mehr-tanken's parallel mode is cited as a plus. | mehr-tanken; list/map toggle universal | M |
| 6 | **Multi-select filters, instant, no reload**: fuel (single primary) plus brand multi-select, open-now, max distance, "official data only" toggle; show active-filter count on the Filter tab. | Single-select and full reload are named complaints; brand filter is near universal in FR/DE. | Osservaprezzi (anti), mehr-tanken (40+ brands), plein-moins-cher, carbu.com, Waze | M |
| 7 | **Favourites without an account** (localStorage; star on card; "Favourites" chip/section; export/import code optional). | Retention loop without a login wall; Essence&CO users explicitly miss favourites, clever-tanken gates them. | Essence&CO (missing), clever-tanken (login), Spritpreisrechner, carbu.com, Tankille | S |
| 8 | **Price alerts (opt-in web push)** on a favourite station or area/fuel with a target price, also "price rose/fell more than X". Needs a push backend decision; mark as design now, build later. Verify current iOS constraints for web push in installed PWAs before committing (not covered by the research). | Near-universal retention feature and rising prices make it timely; no free robust alerts confirmed among the French set. | clever-tanken, mehr-tanken, benzinpreis.de, 1-2-3 Tanken (free drop alerts), Bränsleappen, BensinPris | L |
| 9 | **Coverage and fuel-type transparency panel** per country (source, cadence, fuel grades available, known gaps such as "Swedish prices: X% of stations have a current price") reachable from the badge in change 1 and the Filter tab. Normalise fuel naming across countries (E10/95, E5/98, Diesel, HVO100 already in chips). | Fragmented taxonomies and silent gaps are an acknowledged anti-pattern; also guards our own known data gaps (Sweden coverage, Germany key pending, Spain runner blocks). | Austria 3-fuel apps, Benzinpreis-Blitz per-country notes, plein-moins-cher FAQ | S |
| 10 | **Cross-border comparison**: currency toggle (local / EUR equivalent with rate date shown) and a "Compare nearby countries" card when within ~50 km of a border (e.g., cheapest within 30 km across the border). | Unclaimed gap; supports our pan-EEA positioning and Sweden-NO-DK use case. Needs an FX rate source (new data). | None found at station level; fuel-prices.eu only country averages; carburants.org notes border residents re-check prices | M |

### P2 — differentiation

| # | Change | Rationale | Evidence | Effort |
|---|---|---|---|---|
| 11 | **Along-route search** (enter A to B, show cheapest within X km detour with detour-cost estimate). Free, not paywalled. | Expected for long-distance Nordic driving; Essence&CO paywalls it, so free is a differentiator. | mehr-tanken, ADAC, carbu.com, benzinpreis.de (detour calculator), Tankille, Yanosik, Essence&CO (P) | L |
| 12 | **Free price history + sparkline per station/area** (7 and 30 days from our own scraped history; explicit "no forecast" label until backed by data). Later: "typically cheaper on Tue/Wed" derived from history, clearly marked as statistics, not prediction. | Transparency-first; avoid the 1-2-3 Tanken paywall mistake and the opinion-forecast risk. Needs retained history in `data/`. | ADAC, benzinpreis.de, mBenzin, fuel-prices.eu; anti: 1-2-3 Tanken, Fuelio 2023 | M to L |
| 13 | **City / municipality landing pages** (static, e.g., /stockholm, /malmo, /goteborg) with cheapest station, average and trend; Swedish first. | SEO is the main organic growth channel in the cluster; bensinpriser.nu has none. | Tankille, essencemoinscher.fr, carburants.org, carbu.com, clever-tanken city ranking, Mappy blog | M |
| 14 | **Station details that matter**: opening hours, services, payment/fuel-card acceptance, out-of-stock flag where the feed provides it. Show only what each source provides (no blanks pretending to be "no"). | Cheap trust and utility; commercial apps rarely show shortages. | Benzinpreis-Blitz, prix-carburants.gouv.fr (amenities, shortages), PetrolPrices (missing out-of-stock flag) | M |
| 15 | **Accessible non-map path**: list view fully keyboard- and screen-reader-operable (landmarks, labels, contrast AA, focus states, 44 px targets); `aria-live` for status badge. | Even the official French portal is non-compliant; cheap to beat. | prix-carburants.gouv.fr RGAA finding | S to M |
| 16 | **UI language**: add Swedish, then German/French/Spanish. Keep prices and units locale-formatted. | Our home market is Sweden; competing UIs offer 6 languages. | plein-moins-cher (6), Benzinpreis-Blitz (6) | M |

### P3 — later / needs data or business decisions

| # | Change | Rationale | Evidence | Effort |
|---|---|---|---|---|
| 17 | **EV charging layer/toggle on the same map** (single-surface slider, not a separate app). Requires an EV data source (not scoped by this research). | Now expected from the big players. | clever-tanken (Clever Laden), mehr-tanken slider, ADAC, Tankpriser.dk, Geoportal | L |
| 18 | **Report-a-wrong-price** link per station feeding a review queue (no auto-publishing; separate "unconfirmed" label). Check privacy/abuse design first. | Secondary QA on official feeds; useful where Swedish data is thin. | Benzinpreis-Blitz, Austrian E-Control complaint link, TCS and Bränsleappen (crowd, points, free premium) | M |
| 19 | **Loyalty-card-aware "my net price"** (user selects chain programmes locally). | Distinct personalisation idea. | TankBilligt (DK) | M |
| 20 | **Embeddable widget** ("cheapest in <city>") for backlinks. | SEO syndication. | plein-moins-cher.fr, benzinpreis.de | M |
| 21 | **Ad policy guardrails** (if ever monetised): no interstitials, no ads over the map or list, no unannounced paywalling; optional micro-support or an ad-free pass at a clearly stated price; B2B API/data licensing as the primary revenue idea. | The most frequent cause of rating damage in the set. | Essence&CO, clever-tanken, PetrolPrices, Bränsleappen, Fuelio; GasBuddy and TomTom (B2B) | policy |

Items intentionally not copied: CarPlay/Android Auto native integration (a PWA cannot ship it; "Go" hand-off to the user's maps app already exists), payment/pay-at-pump, club-style super-app bundling, pay-for-placement in ranking.

---

## 7. TODO: visual mobile-layout inspection NOT yet done

All layout statements about competitors in this document come from text sources (their own pages, store descriptions, reviews, press); no screenshots were taken and no product was used on a phone. Before treating the layout items in section 6 as final:

- [ ] Capture screenshots at 375 x 812 (and a mid-size Android viewport) of: plein-moins-cher.fr (heat map, timestamp, FAQ placement), clever-tanken, mehr-tanken (parallel map+list, fuel/electricity slider), ADAC Drive fuel tile, Essence&CO, carbu.com, Waze fuel list, Geoportal Gasolineras web, bensinpriser.nu, Bränsleappen, Tankille, fuel-prices.eu near-me page, essencemoinscher.fr.
- [ ] Record where each puts the primary controls (fuel filter, sort, radius, search, locate-me) relative to the thumb zone and the bottom navigation, and how many taps to reach "cheapest diesel near me".
- [ ] Inspect pin design: price-on-pin density, cluster behaviour at country zoom, colour scales and legend placement.
- [ ] Inspect ad placements and trust elements (press strips, data source statements) on the free tiers.
- [ ] Run our own app (`web/index.html`) at the same viewports and compare: tab bar, chip row, Near Me button, bottom panels, cards, popups, tap-target sizes, safe-area handling, dark/light contrast.
- [ ] Re-verify uncertain data points before external use: Essence&CO premium pricing, 1-2-3 Tanken / Sprit Club / mehr-tanken subscription prices, whether plein-moins-cher.fr offers route filtering, Fuel Flash vs Benzinpreis-Blitz identity, TCS, and the current state of prix-carburants.gouv.fr accessibility fixes.
- [ ] Verify current constraints for web push and installed-PWA behaviour on iOS and Android before committing to change 8.

---

## Appendix: key sources

- Regulator / government: Bundeskartellamt MTS-K app registry https://www.bundeskartellamt.de/DE/Aufgaben/MarkttransparenzstelleFuerKraftstoffe/TankApps/tankapps_node.html ; § 47k GWB https://www.gesetze-im-internet.de/gwb/__47k.html ; https://www.prix-carburants.gouv.fr/rubrique/opendata/ ; https://geoportalgasolineras.es/ ; https://www.mimit.gov.it/it/notizie-stampa/mimit-da-lunedi-20-7-disponibile-la-nuova-app-osservaprezzi-carburanti ; https://www.e-control.at/konsumenten/spritpreisrechner ; http://www.fuelprices.gr/ ; https://www.gov.uk/government/news/fuel-finder-now-helping-drivers-shop-around-for-the-best-deals
- Competitors: https://plein-moins-cher.fr/en/index.html ; https://essencemoinscher.fr/ ; https://www.clever-tanken.de/ ; https://www.mehr-tanken.de/ ; https://www.adac.de/verkehr/tanken-kraftstoff-antrieb/deutschland/spritpreise/ ; https://www.benzinpreis.de/de/ ; https://www.123tanken.de/ ; https://www.bessertanken.de/ ; https://www.tankerkoenig.de/ ; https://carbu.com/ ; https://fuelmediaservice.com/fr/publicite/ ; https://www.fuel-prices.eu/ ; https://www.fuel-prices.eu/Sweden/ ; https://bensinpriser.nu/ ; https://www.drivstoffapp.no/ ; https://www.tankille.fi/ ; https://www.petrolprices.com/ ; https://www.pumpwatch.app/ ; https://www.rac.co.uk/drive/advice/fuel-watch/ ; https://www.gasbuddy.com/ ; https://www.tomtom.com/products/fuel-services/
- App-store listings and ratings (Apple lookup API, 2026-10-01): clever-tanken id300763441, mehr-tanken id395965464, ADAC Drive id675634893, benzinpreis.de id420369180, 1-2-3 Tanken id688981330, bessertanken id6475733055, Benzinpreis-Blitz id1212144168, PACE Drive id1483917851, TCS id962678119, Comparis id6446243567, Essence&CO id459724569.
- Accessibility finding: https://github.com/datagouv/explore.data.gouv.fr/issues/221 ; https://www.prix-carburants.gouv.fr/rubrique/accessibilite/
