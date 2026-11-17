# Next steps: recommendations for the owner (2026-11-17)

Status: decision document. Research and recommendations only; nothing below is built until the owner decides. One exception, reported in section 9.
Scale: impact 1-5, effort S (hours) / M (days) / L (a week or more), cost always 0 EUR (rule: everything free).
Labels: **[verified]** = read today in the vendor's own documentation or measured on live data; **[known]** = from my general knowledge, to be checked in your dashboard before relying on it.

---

## 1. Security and reliability (including GitHub)

### 1a. GitHub (repo `ThorstenGru/nordic-fuel-prices`, **public**) - measured today
| Finding | Why it matters | Fix | Effort | Return |
|---|---|---|---|---|
| Dependabot alerts and security updates are **off** [verified: API said "disabled"] (a `dependabot.yml` for pip exists, so version updates are planned, alerts are not) | A known-vulnerable library would go unnoticed | Settings > Code security: enable Dependabot alerts + security updates | S (1 min) | 4 |
| No code scanning (CodeQL) [verified: "no analysis found"] | Free for public repos; finds injection and unsafe patterns in Python/JS | Enable CodeQL default setup | S | 3 |
| `main` has no protection [verified] and every bot pushes straight to it | A leaked token or a mistake can rewrite history | Ruleset: block force-push and deletion of `main`; do NOT require pull requests (the bots commit data) | S | 4 |
| Actions allowed: "all", SHA pinning not required [verified]. Current workflows already pin every action by commit SHA (8x checkout, 6x setup-python, 2x upload-artifact, 1x gh-pages) - good | A new, unpinned third-party action could slip in | Allow only GitHub-owned actions + `peaceiris/actions-gh-pages`; switch on "require SHA pinning" | S | 3 |
| Default workflow permission is `read` [verified] and each workflow asks for `contents: write` only where it commits - good | - | none | - | - |
| 7 secrets: `FB_PAGE_TOKEN` (a Page token that **never expires**), `FB_PAGE_ID`, `TANKERKOENIG_API_KEY`, `CHARGEFINDER_KEY`, `NOBIL_API_KEY`, `GOON_API_KEY`, `OCM_API_KEY` [verified] | The Page token is the crown jewel: whoever holds it can post as the Page. `OCM_API_KEY` is for a source we dropped | Delete `OCM_API_KEY`; note the Page-token rotation procedure in `docs/facebook/GRAPH_API_SETUP.md` (rotate yearly and after any suspicion) | S | 3 |
| Secret scanning + push protection are **on**, 0 alerts [verified] - good | - | none | - | - |
| Repo has no licence file (`licenseInfo: null`) and no `SECURITY.md` [verified] | No licence = all rights reserved, yet the site says data is "free to reuse"; researchers have no way to report a hole | Add `SECURITY.md` (contact + 2 lines). Licence: owner decision (code: MIT or keep closed; data pages: attribution already stated) | S | 2 |
| Owner account hygiene (2FA/passkey, personal tokens) - cannot be read from here | The repo is only as safe as the account | Check: passkey or authenticator 2FA on, old personal access tokens revoked; the local `gh` login wanted an extra `admin:repo_hook` scope - do not grant it | S | 5 |
| The scrape chain re-starts itself with `workflow_dispatch` and can die [known from the project notes] | Prices go stale silently | The Cloudflare watchdog already alerts on stale countries; add a "chain alive" check there (last scrape < 40 min) | S | 4 |

### 1b. Website, Cloudflare and Workers
- **Security headers are missing** [verified live: the response has no `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy` or `Permissions-Policy`]. GitHub Pages cannot add headers, but Cloudflare can for free (Transform Rules / response header modification) [known]. The CSP is only a `<meta>` tag; `frame-ancestors` is ignored in meta tags, so clickjacking protection is not active today. **Fix:** one rule set at Cloudflare: HSTS, `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (geolocation only for self), CSP header incl. `frame-ancestors 'self'`. Effort S, return 4.
- **WAF/rate limiting** at the edge in front of `/api/*`: Cloudflare Free has custom WAF rules and one rate-limiting rule [verified for rate limiting: one rule on Free per Cloudflare's announcement; custom-rule count 5 = [known]]. The Worker already limits 20 uncached requests per visitor per minute (best effort per data centre); an edge rule is a second layer. Also switch on Bot Fight Mode [known]. Effort S, return 3.
- **Inline scripts:** the CSP needs `'unsafe-inline'` because the app's scripts are inline in `index.html`, so it gives little XSS protection. Real fix = move scripts to a file and use hashes. Effort M, return 2 (no user-generated content is rendered; shared-plan links are escaped). Park it.
- **Workers free plan limits** [verified]: 100,000 requests/day, 10 ms CPU per request; D1: 5 GB, 5M reads and 100k writes per day; KV: 100k reads and 1k writes per day. If a post goes viral, `/api/route`, `/api/fac`, `/api/poll` could hit 100k/day and then fail. Mitigation: caching is already used; keep the app working when the API answers an error (route falls back to the public engines). Test that fallback.
- `admin.html` is a public, noindex "data health" page with no secrets. Leave it public or put it behind Cloudflare Access (free for up to 50 users [known]). Not urgent.
- Privacy of the Worker: it uses `CF-Connecting-IP` only as a short-lived rate-limit key in the cache and stores no IP or user agent in D1 (code comment + code reading). Good; mention it in the privacy text.

### 1c. Reliability (single points of failure)
1. **GitHub Pages hosting** (no SLA). Mitigation = Cloudflare cache in front (already). A real fix is Cloudflare Pages, but see section 6: the site has ~16.8k objects and Pages free allows **20,000 files** [verified], so there is little headroom.
2. **Unofficial feeds** (ANWB, Overpass mirrors): can change or vanish. Per-country fallback and last-known-good retention exist; Hintatutka already broke silently on 2026-11 (fixed with a log line). Add a daily "source has fewer stations than yesterday by 30 %" alert to the watchdog. Effort S, return 4.
3. **Tankerkoenig test key**: one request per minute; the rotation design now keeps data for 8 to 12 hours. If the key is blocked, Germany falls back to ANWB. OK.
4. **Single owner / single machine**: tokens and notes live in one person's account. Document the restore steps (repo + secrets list + Cloudflare account) in `docs/OPERATIONS.md`. Effort S, return 3.
5. **Backups**: the repository is the source of truth; D1 holds only counters. Nothing to back up beyond an export of the D1 tables once a month. Effort S, return 1.
6. **No uptime check**. A free external ping (UptimeRobot/Better Stack free tier [known]) or a GitHub Action cron that fetches `/health.json` and fails when older than 60 minutes. Effort S, return 4.

**My recommendation for section 1:** do all S items in one sitting (about 2 hours, return high): Dependabot, CodeQL, ruleset, Actions allow-list, delete OCM key, SECURITY.md, Cloudflare response headers, one rate-limit rule, uptime check, watchdog "chain alive". Park the inline-script refactor.

---

## 2. Route function as a new tab

**What exists:** a "Preview" route planner inside `index.html` (about 80 route functions), a Worker proxy (`/api/route*`, cache, origin check), notes in `docs/ROUTE_RECOMMENDATIONS_2026-11-06.md`. Its weak point is data (dated prices), not routing speed.

**Recommendation: build it new as its own tab, in four phases; each phase is shippable.**
1. **P1 (M):** tab with start, destination, optional via-points, car from "My car" (fuel type, consumption, tank, start fuel, reserve). Result card: distance, time, **cost range** (fuel + tolls + ferries/bridge), "stop needed?" answer, share link (state in the URL hash, nothing stored on a server). Routing via the existing Worker (OpenRouteService behind the proxy, public Valhalla as fallback). Reuse the tested cost model in `tools/test_route_model.js`.
2. **P2 (M):** multi-stop fuel plan with litres to buy and one-line reasons ("fill 22 l in Lübeck, 9 cents cheaper than at the border"); prices below the trust bar (undated, `chain_price`, `uncertain`) widen the range instead of being ranked as exact.
3. **P3 (M):** PHEV/EV logic (battery for the first km, then fuel; chargers on the way from the charger layers already built), border-run suggestion.
4. **P4 (S-M):** compare alternatives, "leave now / later" using the price-cycle data (`price_cycles`).
- **Why a separate tab:** the map stays fast and simple; the planner can have its own state and its own tests; you decide the tab order.
- **Effort:** L overall (P1 alone M). **Return:** 5 - it is the feature competitors lack on top of honest prices.
- **Risks / decisions needed from you:** (a) free routing quotas (ORS free tier about 2,000 route requests/day [known, from earlier notes, not re-verified today]); at 100+ planned trips a day we need caching by rounded coordinates (exists) and the public Valhalla fallback; (b) a route is the most personal thing the app handles: keep "no logging of coordinates" and say so in the privacy text; (c) which countries first (Nordics + DACH are the natural set).

---

## 3. "My car": top-100 per kind, four kinds

**Today:** `web/vehicles.json` has 20 petrol, 20 diesel, 20 PHEV and 38 Hyundai entries; **there is no HEV category** (categories: petrol, diesel, phev) [verified in the file].

**Best free source: the EEA register of new passenger cars (CO2 monitoring, Regulation 2019/631)** [verified: the data is queryable and each row has make `Mk`, commercial name `Cn`, fuel type `Ft`, fuel mode `Fm`, WLTP CO2 `Ewltp`, **fuel consumption `Fc` in l/100 km**, electric energy `Z` in Wh/km, registrations `R`, member state `MS`, year, engine size and power]. One real example row (Citroën Berlingo diesel 2021) returned `Fc = 5.2`. It is an official EU dataset, so the "top sold in Europe" ranking comes from real registrations summed across countries, not from a magazine.
- **Gaps found:** (1) the table has **no electric range and no tank size** - PHEV electric range and tank litres need a second source or a class-based default shown as "typical, adjust to your car" (the existing UI note does that already); (2) the meaning of `Fm` for non-plug-in hybrids vs plug-in hybrids must be confirmed before building (I did not get to verify it); (3) the EEA's gateway blocked my grouped queries (HTTP 403 on `GROUP BY`), so the practical route is a one-off bulk download of the yearly CSV and a local script; (4) the newest year may be provisional.
- **Licence:** EEA data is published for reuse; the exact licence text was not shown on the pages I could read - confirm before shipping and credit "EEA".
- **Plan:** `tools/vehicles/build_from_eea.py` (stdlib only like the existing builder): sum registrations per make+model+kind, keep the 100 best per kind (petrol, HEV, PHEV, diesel = 400), average Fc/Z, mark every value with source and year, validate ranges (reuse `build_vehicles.py` checks). UI: search box + brand filter instead of a long list; "my car isn't here" falls back to manual entry (exists).
- **Effort:** M for data + L if the electric-range second source needs hand work. **Return:** 4 (the page "My car" becomes believable and the route tab uses it).
- **Decision needed:** accept "typical" tank and electric range where no official source exists? (my recommendation: yes, labelled).

---

## 4. Tighter Facebook integration

Today: daily post, 2 Reels a week, weekly video, hourly comment replies (now in 8 languages, 14 countries), weekly insights, follow card in the app, `visit_fb` counter. Reach is the problem (1 follower). Options, best first:
1. **"Share on Facebook" on every town page, station sheet and route result** (Facebook share dialog link, no Facebook script on our pages, so no tracking and no extra weight) with proper Open Graph images per page (today every town page shares one generic `og-image.png` [repo], so a shared link looks the same everywhere; a per-town card with the cheapest price would make shares worth clicking). Effort S-M (buttons S, per-town cards M), return 4 - every user becomes a distribution channel.
2. **Instagram cross-post**: the Page's Reels can be published to a linked Instagram business account through the same Graph API and token family (extra permission `instagram_content_publish`) [known]. Same video, new audience. Effort M, return 3. Needs you to link an Instagram account to the Page.
3. **News-hook posts generated from data** ("Diesel +6 ct in Sweden this week", "Germany cheapest on Tuesdays"): new formats in `fb_daily.py` using `price_cycles` and the weekly history. Effort S-M, return 3.
4. **Messenger auto-answer** (same town lookup via the Page inbox). Needs Meta App Review and business verification for `pages_messaging` to serve the public [known]; while the app is in development mode it only works for admins/testers. Effort L, return 3 -> **later**.
5. **Facebook Group** for the community: the Groups posting API has been shut down [known]; manual only. Owner's call, effort 0 for us.
6. **Not recommended:** Facebook Login, Facebook Pixel/Conversions API, the Page plugin/Like button (all load Meta scripts into the page, which breaks the cookieless/slim promise and needs a consent banner).
- **Fix first (done today):** replies were silently not running because of a log-header bug; thresholds and wording are aligned.
- **Recommendation:** 1, then 3, then 2 when you have linked Instagram.

---

## 5. Events to track - remove from the page, track with Cloudflare

**Where the text is:** `web/admin.html`, the block "Recommended events to track" (six boxes). **Remove it** (small edit, no risk).

**How to track the events without making the app heavier** - three layers, all free:
1. **Cloudflare Web Analytics (already on every page, token in place).** Covers: visits, countries, device/OS/browser, referrers (Facebook), top pages (town and country pages), Core Web Vitals - i.e. "Device & platform" and "Geographic" blocks, no code change. [Web Analytics is available on all plans per the docs; whether it supports custom events was not stated in the docs I read, so I do not rely on it.]
2. **Edge counters from the Worker we already run** (`/api/poll`, `/api/route`, `/api/fac`): route planned, facilities opened, trips computed are known server-side without any page code. Tables `events(day,name,n)` already exist in D1 and the app already sends 10 cookieless events with one `sendBeacon` line.
3. **A few new events through the same beacon**, each with one small dimension (never free text): `fuel_filter` {p95|diesel|e10|...}, `country_view` {country}, `nav_go` {google|waze|apple|here}, `search_used` (count only, **never the search text**), `app_installed`. The Worker keeps the allow-list, so the page carries only a name and a dimension. To keep the page lean: queue the events and send them in **one** beacon on `pagehide`.
- **Reporting:** a weekly GitHub Action (like the Facebook insights job) exports the D1 counters to `docs/usage/*.csv` and adds one "Usage" panel to `admin.html` fed by that CSV. No dashboard code on the public page.
- **Cloudflare Zaraz** (1,000,000 events/month free [verified]) would also work but injects its own script and is built to forward events to third-party tools; **not recommended** here.
- **Workers Analytics Engine** would be a neater store than D1 for dimensions, but I could not confirm from the docs that it is included on the Workers **Free** plan (the pages I read gave limits - 250 data points per invocation, 3 months retention - but no plan statement). Check in the dashboard (Workers & Pages > Analytics Engine) before choosing; D1 works today.
- Privacy by design: no IP, no user agent, no precise location, no search text, counts per day only. Update the privacy text accordingly.
- **Effort:** S-M. **Return:** 4 (the first real data about use). **Decision:** which of the new events you want first (my pick: `fuel_filter`, `country_view`, `nav_go`).

---

## 6. Additional free Cloudflare services (or similar)

| Service | Free allowance | Use for us | Verdict |
|---|---|---|---|
| Transform / header rules | free [known] | security headers (section 1b) | **do** |
| WAF custom rules + 1 rate-limit rule, Bot Fight Mode | free [rate limit: verified; counts of custom rules: known] | protect `/api/*` | **do** |
| Web Analytics | free [verified available on all plans] | already on | keep |
| Workers (we use) | 100k requests/day, 10 ms CPU [verified] | API proxy, watchdog | keep; watch the 100k |
| D1 | 5 GB, 5M reads and 100k writes/day [verified] | event counters, later usage tables | keep |
| KV | 100k reads / 1k writes per day, 1 GB [verified] | watchdog state | keep |
| R2 | 10 GB storage, 1M Class A + 10M Class B ops/month, free egress [verified] | **map tiles (PMTiles)**, price-history archive, large files, the `gh-pages` object overflow | **consider** |
| Queues | 10,000 operations/day [verified] | not needed now | skip |
| Durable Objects (SQLite) | free tier exists [verified] | not needed now | skip |
| Pages | 20,000 files per site, 500 git builds/month, unlimited direct-upload deployments, 100 domains [verified] | host the site instead of GitHub Pages | **only with a plan** (see below) |
| Zaraz | 1M events/month [verified] | forward events to tools | skip |
| Turnstile (captcha) | free [known] | only if we ever add a form | skip |
| Access (zero trust) | free up to 50 users [known] | protect `admin.html` | optional |
| Email Routing | free [known] | a `contact@`/`security@` address on our domain forwarding to you, for `SECURITY.md` and the legal contact | **do** (S) |
| Workers AI | small daily free allowance [known] | not needed | skip |

- **Cloudflare Pages instead of GitHub Pages:** gives header control, unlimited bandwidth and no "no commercial use" clause; but our site is ~**16.8k objects** (measured on the `gh-pages` branch) against **20,000 files** [verified]. Pages is therefore only safe if town pages are first reduced or rendered on demand by a Worker from the data JSON (then there is no file ceiling). Effort L, return 3 today -> **not now**; revisit when GitHub Pages limits or terms hurt.
- **Map tiles - see the IP report.** The app loads tiles from the public OpenStreetMap server, whose policy warns that heavy or commercial-looking use can be blocked without notice [verified]. Free alternatives: **OpenFreeMap** (no key, no limits on views, commercial use allowed, attribution required, no SLA [verified]) or self-hosted PMTiles on R2. Switching tiles is a one-line URL + attribution change plus a CSP edit. Effort S, return 4.

---

## 7. IP check (intellectual property and licences)

Full bullet report: `docs/IP_CHECK_2026-11-17.md`. Headlines: (1) OSM public tile server and Nominatim/OSRM demo servers are used by the app - fair-use policies, no SLA; (2) ANWB is an unofficial feed with the owner's permission but no contract; (3) e-Control (Austria) has no written reuse terms and our request volume had to be cut today; (4) no imprint/contact on the site; (5) licence of the repo undefined; (6) fonts (OFL) and Leaflet (BSD) are fine.

---

## 8. Decision table

| # | Item | Why | Effort | Return | My recommendation |
|---|---|---|---|---|---|
| 1 | Security quick wins (section 1 S-items) | closes real gaps, mostly 1-minute switches | S (about 2 h) | 4-5 | **do first** |
| 2 | Cloudflare headers + rate-limit rule + email routing | headers missing, clickjacking CSP inactive | S | 4 | **do first** |
| 3 | Swap OSM public tiles for OpenFreeMap (or PMTiles on R2) | removes the biggest policy risk | S | 4 | **do first** |
| 4 | Uptime + "chain alive" + source-drop alerts | silent staleness is the main reliability risk | S | 4 | **do first** |
| 5 | Remove "events" block; new events via beacon + D1 + weekly CSV + admin panel | first real usage data, slim page | S-M | 4 | do next |
| 6 | Imprint / contact page + privacy text update | legal hygiene (DE/AT/SE) | S | 3 | do next |
| 7 | My car: EEA-based 4 x 100 models | believable "My car", feeds the route tab | M-L | 4 | do next |
| 8 | Route tab P1 then P2 | biggest differentiation | L | 5 | after 7 |
| 9 | Facebook: share buttons, then news-hook posts, then Instagram | distribution | S-M each | 3-4 | in parallel, small steps |
| 10 | Cloudflare Pages migration | headers, limits | L | 3 | not now (file ceiling) |
| 11 | Messenger bot | needs Meta review | L | 3 | later |
| 12 | Inline-script refactor for a strict CSP | marginal today | M | 2 | park |

## 9. What I changed today (outside the plan, because it was my own regression)
While checking licences I found that my Austria top-up (built yesterday) asked e-Control about 2,700 times per run, and the scrape runs every 15 minutes: that is roughly a quarter of a million requests a day to a public API without written reuse terms. I reduced it to about 1,350 requests per run (an answered area is not asked again) and set Austria to refresh hourly (about 30,000 requests a day, still to be discussed with e-Control - see the IP report). Station count: 1,947 (was 2,088 with the heavy version, 788 originally). Tests pass, pushed (commit "Austria: fewer e-control requests").
