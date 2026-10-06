# Licence outreach drafts (roadmap experiment E10)

Not sent. Review, then send from your own address. The SEO town pages (`src/seo_pages.py`) show
no ads or affiliate links, but they put each source's data in front of search engines, so the
sources below should confirm reuse in writing before any monetisation.

Country status of the SEO pages (built on every scrape):

| Country | Source | Pages | Why |
|---|---|---|---|
| FR | prix-carburants.gouv.fr / data.economie.gouv.fr | **live** | Licence Ouverte 2.0 (Etalab); attribution shown |
| SE | bensinpriser.nu via henrikhjelm.se (community, grade D) | **live, licence unconfirmed** | No published reuse terms; send mail 1 |
| AT | E-Control Spritpreisrechner | **live, licence unconfirmed** | No bulk licence found; send mail 3 |
| DE | currently ANWB (unofficial) | **live (released by owner 2026-10-06)** | Footer states the ANWB source; attribution switches to Tankerkönig automatically once `TANKERKOENIG_API_KEY` is set; send mail 2 |
| CH | ANWB (unofficial) | **live (released by owner 2026-10-06)** | No licensed source; footer states ANWB; risk accepted |

Kill switch for every ANWB-fed country (DE, CH): set `SEO_EXCLUDE_ANWB=1` in the scrape step of `scrape.yml` and the pages disappear on the next run.

---

## 1. Crownberry AB / bensinpriser.nu (Sweden)

Subject: Licence to display bensinpriser.nu price data on EuroFuelPrices

Hej,

I run EuroFuelPrices (https://eurofuelprices.com), a free fuel price map for Europe. We display
the community- and owner-reported prices published by bensinpriser.nu (via henrikhjelm.se),
always credited to bensinpriser.nu, labelled as community data with the time of the source data,
and linked back to the source. We would like your written permission to keep doing so, including
on static town pages (e.g. /se/vaxjo/), and to discuss whether commercial use (a single labelled
ad slot or affiliate links later) could be covered by a licence or partnership.

What would you need from us (attribution wording, link, fee, rate limits)?

Thorsten Grund

## 2. Tankerkönig (Germany)

Subject: Commercial use of Tankerkönig / MTS-K data on a free price site

Hallo,

EuroFuelPrices (https://eurofuelprices.com) wants to use the Tankerkönig API (CC BY 4.0,
attribution to tankerkoenig.de) for German town pages and the live map. Please confirm in
writing: (1) that a site with a single, clearly labelled, non-personalised ad slot and
affiliate links (EV charging, roadside, insurance; not fuel cards) is permitted, (2) the
request limits we should respect for ~14,000 stations, and (3) whether a paid tier is advisable.

Thorsten Grund

## 3. E-Control (Austria)

Subject: Nutzung der Spritpreisrechner-Daten

Guten Tag,

EuroFuelPrices (https://eurofuelprices.com) zeigt die Preise des E-Control Spritpreisrechners
mit Quellenangabe auf einer kostenlosen Karte und auf statischen Ortsseiten (z. B. /at/wien/).
Wir bitten um schriftliche Bestätigung, dass diese Nutzung zulässig ist, und um Auskunft, ob
eine spätere kommerzielle Nutzung (ein gekennzeichneter Werbeplatz) möglich ist.

Thorsten Grund
