# Operations runbook

How to run, monitor and repair EuroFuelPrices. Written 2026-11-11. Architecture: [ARCHITECTURE.md](ARCHITECTURE.md). Everything runs on free tiers.

## 1. What runs automatically (nobody needs to be present)

| What | Where | When | Result |
|---|---|---|---|
| Scrape + generators + deploy | GitHub Actions `EuroFuelPrices — Scrape` | ~every 15 min (self re-dispatch; cron `13,43 * * * *` as safety net) | Fresh `data/` published to `gh-pages` |
| Frontend deploy | `Deploy Web` | on a push to `main` touching `web/**` | `web/` rsynced into `gh-pages` (generated folders protected) |
| Tests | `Tests` | every push / PR | Red = fix before relying on the next scrape (scrape also runs them) |
| Facebook daily post | `Facebook — daily post and replies` | 07:00 UTC (retry 11:00 UTC) | One post on the Page; log committed to `docs/facebook/post_log.csv` |
| Facebook weekly video | `Facebook — weekly video` | Sunday 16:00 UTC | 9:16 clip (Pillow + ffmpeg, `tools/fb_weekly.py`) posted by the Page; manual run = dry run that attaches the mp4 as an artifact. Video upload to the Page not yet exercised live (first post 2026-11-15) |
| Facebook replies | same workflow | every hour at :30 | Replies to "comment your town" comments |
| IndexNow ping | in the Scrape job | once a day (07:00–07:14 UTC window) | Bing & co. told about Europe pages and hubs |
| Stale-data alarm | Cloudflare Worker `efp-watchdog` | every 30 min | Phone notification via ntfy if prices are >3 h old; repeats every 6 h |
| Routing proxy | Cloudflare Worker `efp-route` | on request | `/api/route` |

The Claude-app scheduled task "Euro Fuel Prices: daily Facebook post" (browser based) is **disabled**; it was only a stop-gap.

## 2. Accounts and where things live

| Thing | Where | Notes |
|---|---|---|
| Code, CI, hosting, logs | GitHub `ThorstenGru/nordic-fuel-prices`, branch `main` (source), `gh-pages` (published output, regenerated) | `gh` CLI is logged in on the owner's PC |
| Domain, CDN, analytics, Workers | Cloudflare (zone `eurofuelprices.com`) | Web Analytics beacon token is in the generated pages; Worker deploy with `wrangler` |
| Facebook Page | https://www.facebook.com/eurofuelprices ("Euro Fuel Prices", Page id `1483052498219801`) | Admin: the owner's Facebook profile |
| Meta developer app | "EuroFuelPrices bot", App ID `1396421635635961`, Development mode | Use case "Manage everything on your Page"; permissions `pages_manage_posts`, `pages_manage_engagement`, `pages_read_engagement`, `pages_read_user_content`, `pages_show_list`, `read_insights` |
| Google Search Console | property `https://eurofuelprices.com/` | Verified by `web/google9b79c7d4878035d4.html`; sitemaps `sitemap-seo.xml`, `sitemap.xml` |
| Bing Webmaster Tools | imported from Search Console (2026-11-11) | IndexNow key file `web/9de760974b2bdc3ec308ea9adc970583.txt` |
| Alerts | ntfy.sh topic (secret `NTFY_TOPIC` in the Worker) | Subscribe to the topic in the ntfy app |

Secrets and variables: see the README table. **Never put a key or token in a file, commit, issue or chat.** The Facebook token exists only as the GitHub secret `FB_PAGE_TOKEN`.

## 3. Daily/weekly checks (5 minutes)

1. Site up and fresh: open https://eurofuelprices.com/admin.html (source status, age); or `meta.json` → `fetched_at` should be minutes old.
2. Actions tab: latest `Scrape` and `Tests` green; `Facebook` runs green (a skip because "already posted today" is normal).
3. Facebook Page: one new post per day; reply to comments yourself when a human conversation is needed.
4. Weekly: `python tools/growth_kpis.py` (appends to `docs/growth_kpis.csv`), then add Search Console and Bing numbers by hand.

## 4. Runbook

### The scrape chain stopped (no new data; ntfy alarm)
```bash
gh workflow run scrape.yml            # re-kick; add -f force=true to refresh every source
gh run list --workflow scrape.yml --limit 5
```
Typical cause: a GitHub 5xx during the chain job. If the run fails on a test, fix the test first (the scrape is blocked by design).

### A country shows "stale"
`health.json` / admin page show the error. The last good data stays published. Fix the scraper, or lift a regression guard for one run:
`gh workflow run scrape.yml -f allow_shrink=XX`.

### GitHub Pages deployment failed with HTTP 500
GitHub-side outage (seen 2026-11-10). The next scrape republishes; or re-run the failed `pages-build-deployment`.

### New generated folder or file disappears after a frontend push
Add it to the `--exclude` list in `deploy-web.yml` (rsync `--delete`), and to `.gitignore` if it lives in `data/`.

### Facebook: nothing posted
1. Actions → `Facebook` → latest run log (`fb_bot:` lines say why).
2. Run **Actions → Facebook → Run workflow → mode `selftest`**. Expected: token belongs to Page 'Euro Fuel Prices', feed readable, unpublished photo created/deleted, `selftest OK`.
3. If the token is rejected (password change, app removed, permissions changed): regenerate it — Graph API Explorer → app "EuroFuelPrices bot" → Generate Access Token (select the Page) → `python tools/fb_setup.py` (hidden prompts; stores `FB_PAGE_ID`/`FB_PAGE_TOKEN`). Details: [facebook/GRAPH_API_SETUP.md](facebook/GRAPH_API_SETUP.md).
4. "skip - data older than 36 h": the site data was stale; check the scrape.
5. Replies do nothing: Meta may restrict reading other people's comments for apps in Development mode; posting is unaffected. Check the replies log lines.

### Facebook: a wrong or embarrassing post went out
Delete it on the Page by hand. Fix the cause in `tools/fb_daily.py` / `fb_local.py` (tests in `src/tests/test_fb_daily.py`, `test_fb_bot.py`). Pause the routine by disabling the workflow (Actions → Facebook → ⋯ → Disable).

### Stale `sw.js` or old assets after a deploy
Cloudflare can serve an older cached copy for hours (`cf-cache-status: HIT`, large `Age`). Purge the cache in Cloudflare (Caching → Purge) or wait. Test with a query string (`sw.js?x=1`) to see the origin version.

### The owner's PC cannot reach eurofuelprices.com but others can
Local DNS problem (seen 2026-11-10: the default resolver did not answer). Fix: reconnect, `ipconfig /flushdns`, or set DNS to 1.1.1.1/8.8.8.8 (may be locked by IT). The app then shows a "No connection" page for navigations.

### Rolling back
Everything is in git. `git revert <sha>` and push; `gh-pages` is regenerated by the next scrape (≈15 min) or by `Deploy Web` for frontend changes.

## 5. Making changes safely

- Work on `main`, small commits; CI must stay green (the scrape refuses to publish with failing tests).
- Frontend: `node tools/check_page_syntax.js` and the JS tests before pushing; bump data versions with `check_data_versions.js --fix` when `vehicles.json`/`fares.json` change.
- New country scraper: add the module, register it in `src/scrapers/__init__.py`, add tests with recorded fixtures (no network in tests), check `health.json` after the first run.
- Data-source rule: **cross-check a republisher against the primary source before publishing** (a wrong North Macedonia cap came from a republisher). Respect [PERMISSIONS.md](PERMISSIONS.md).
- Post content is generated in code (`tools/fb_daily.py`), not improvised; change wording there and keep the tests passing.

## 6. Security and privacy

- No user accounts, no tracking cookies. Location is used only on request and never sent to ad vendors; the routing Worker rounds coordinates to ~100 m and does not log them.
- Secrets live only in GitHub (Actions secrets) and Cloudflare (Worker secrets). Tokens that were ever pasted into chat or a terminal that shows input must be treated as used up (Facebook user tokens expire after about an hour; the stored Page token is the only long-lived one).
- The Facebook routine posts only as the Page, never tags or contacts individuals, and stores only comment ids. Estimates (grade D) are always labelled as estimates.
- Project rule: **everything stays free** — no paid ads, no paid tiers, no cards on file.

## 7. Known issues and open items (2026-11-11)

- Cloudflare edge cache holds an old `sw.js` (the new "No connection" page is already in `gh-pages`); harmless, clears on its own or by purge.
- Not yet exercised live: the weekly video upload (permission for `/videos` unverified), the first fully automatic Facebook post (due 2026-11-12 07:00 UTC) and reading other people's comments.
- Follower-city insight needs enough Page followers; until then the Friday spotlight rotates through larger towns.
- Pending outreach (owner sends): journalist and community drafts in [GROWTH.md](GROWTH.md); source-licence emails in [LICENCE_OUTREACH.md](LICENCE_OUTREACH.md), [GERMANY_OUTREACH_DRAFTS.md](GERMANY_OUTREACH_DRAFTS.md), [ITALY_ROMANIA_OUTREACH_DRAFTS.md](ITALY_ROMANIA_OUTREACH_DRAFTS.md).
- Roadmap candidates: price-drop alerts (Cloudflare Worker + Web Push), weekly short video, BE/PL/IT town pages, official German source, UK Fuel Finder, Spain relay.
