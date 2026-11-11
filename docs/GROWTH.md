# Growth playbook (free, 2026-11-10)

Everything here costs nothing. Items marked **OWNER** need a login or a send button that Claude does not press.

## Shipped 2026-11-10
| Lever | What | Where |
|---|---|---|
| Programmatic SEO | Town pages for ES, PT, DK (plus existing SE, AT, DE, CH, FR) | `src/seo_pages.py`, `/es/`, `/pt/`, `/dk/` |
| Data-led PR | European price index (cheapest to dearest, 7-day change from day 8) and 18 border-pair pages ("Sweden vs Denmark") | `src/europe_index.py`, `/europe/` |
| Backlink magnet | Free iframe widget + docs page; open country medians as JSON/CSV | `web/widget.html`, `web/embed.html`, `/open-data/national-averages.{json,csv}` |
| Share | Share button now sends a price picture (canvas, on-device) where the browser can share files | `shareStation()` in `web/index.html` |
| Install | Gentle install nudge from the 2nd visit, once per 3 weeks, dismissible | `installNudge()` in `web/index.html` |
| Measure | `tools/growth_kpis.py` weekly row in `docs/growth_kpis.csv`; Cloudflare Web Analytics already on every page | `tools/growth_kpis.py` |

Already existed (not rebuilt): sitemap index + robots, JSON-LD on pages, Search Console verification file, trip/border-run calculator and route planner, PWA manifest + service worker, share links.

## Added 2026-11-11 (second pass)
- NL town pages; Europe index in sv/de/da with hreflang; Danish postal districts merged.
- 37 border-pair pages, each with its own share picture (`/og/<page>.png`, Pillow, skipped silently if unavailable).
- `/se/billigaste-orter/` ranking of Swedish towns by lowest price.
- IndexNow (`src/indexnow.py`, key file in `web/`): daily ping at 07:00 UTC for Europe pages and country hubs.
- Search Console and Bing Webmaster Tools: sitemaps submitted/imported 2026-11-11.

## Facebook and automation (2026-11-11, end of day)
- Page **Euro Fuel Prices** (https://www.facebook.com/eurofuelprices): name, bio, website, "Learn more" button, username, profile + cover, first post live. The site links to it from About, the app bar and every generated page (`sameAs` in JSON-LD).
- **Fully automatic, on GitHub (no computer, app or person):** `.github/workflows/facebook.yml` + `tools/fb_*.py` — daily post at 07:00 UTC, hourly replies to "comment your town". Posts always come from the Page (Page token, verified before every run). Weekly plan: Mon ranking, Tue border pair, Wed quiz, Thu "how to use" tip, Fri cheapest-within-10-km spotlight, Sat "comment your town", Sun tip. Grade D data is included and marked as estimates.
- Verified 2026-11-11: `selftest` (token = the Page, feed readable, unpublished photo created and deleted). First real automatic post: 2026-11-12 07:00 UTC. Details: [ARCHITECTURE.md](ARCHITECTURE.md#8-facebook-routine), [facebook/GRAPH_API_SETUP.md](facebook/GRAPH_API_SETUP.md), [OPERATIONS.md](OPERATIONS.md).
- Not automated on purpose: tagging/contacting individuals, paid ads or boosts, replies to anything but a town name.

## OWNER steps
Done 2026-11-11: Google Search Console sitemaps submitted; Bing Webmaster Tools imported; Meta app and GitHub secrets for Facebook. Still the owner's:
1. Send the outreach drafts below (journalists, communities) when `/europe/` looks right on your own device.
2. Join the conversation on the Page when a comment needs a human answer.
3. Run `python tools/growth_kpis.py` weekly and paste GSC impressions/clicks into the last columns of `docs/growth_kpis.csv`.

## Outreach drafts (OWNER sends; nothing has been sent)
Tone: professional and polite. Send from your own address.

**Journalists / motoring and consumer desks (SE, DK, NL, DE first)**
> Subject: Fuel prices across Europe today - free data for your readers
>
> Hello <name>,
>
> EuroFuelPrices tracks live petrol and diesel prices at more than 120,000 stations in 40+ European countries. We publish a free, daily-updated ranking of country medians and cross-border comparisons (for example Sweden vs Denmark, Germany vs Poland): https://eurofuelprices.com/europe/
>
> The figures are also available as JSON/CSV (https://eurofuelprices.com/open-data/national-averages.csv) and as a one-line widget (https://eurofuelprices.com/embed.html). All free to use with a link back. Every figure shows its data-source grade, and we are happy to explain the method.
>
> Kind regards,
> Thorsten Grund

**Community post (r/sweden, r/Denmark, r/germany, campervan/husbil groups; read each group's rules first, one post each, answer questions honestly)**
> I built a free fuel price map for Europe (no account, no ads). Today's comparison: <one real number from /europe/, e.g. diesel in Germany vs Denmark>. It also has a border-run calculator that includes the extra driving. Feedback on missing stations or wrong prices is very welcome: https://eurofuelprices.com

**One-off launch posts** (once each): Show HN, Product Hunt, AlternativeTo, Indie Hackers.

## Roadmap (not done in this pass)
- **Price-drop alerts (push).** Needs a Cloudflare Worker + KV (free tier) with Web Push (VAPID keys as Worker secrets) and a "tell me when diesel near X is below Y" form. iOS only delivers push to installed PWAs. Design: subscription stored by hashed endpoint, nightly check against `{cc}.json`, no account. **OWNER**: Cloudflare login for the Worker deploy and VAPID key generation.
- Per-page share image (OG PNG) per country/town; needs a render step in the scrape job.
- More town-page countries: BE (bilingual city names), PL (ANWB city names lose diacritics), IT (blocked while mimit feed is stale), NO/FI once priced share improves. NL shipped 2026-11-11.
- `hreflang` is not needed (one language per country section) but a language switcher on `/europe/` would help; add Swedish/German/Danish versions of the index.
- IndexNow ping for new pages (free, Bing/Yandex); only worth it once the weekly index has history.
- Weekly short video generated from the index (TikTok/Shorts).
- PageSpeed Insights baseline (keyless API returned HTTP 429 on 2026-11-10; run https://pagespeed.web.dev/ manually).

## Cautions
- DE, CH, NL, BE, PL and other ANWB-fed numbers are grade C and unofficial; the index shows the grade next to every country. Do not put ANWB-derived pages into press outreach as "official".
- The open-data files contain country medians only (no station rows). They are offered "free to reuse with a link"; no formal licence was chosen. Decide on CC BY 4.0 if you want one.
