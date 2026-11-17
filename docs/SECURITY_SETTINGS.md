# Security settings in place (set 2026-11-17)

## GitHub (ThorstenGru/nordic-fuel-prices, public)
- Dependabot alerts and security updates: **on** (version updates for pip and github-actions via `.github/dependabot.yml`).
- Secret scanning and push protection: on. Private vulnerability reporting: on (`SECURITY.md`).
- CodeQL default setup: on (actions, javascript/typescript, python).
- Ruleset "main: no force-push, no deletion": active. Pull requests are NOT required (the bots commit data straight to main).
- Actions: only GitHub-owned actions plus `peaceiris/actions-gh-pages@*`; **commit-SHA pinning required**; default workflow permission read-only (each workflow asks for `contents: write` only where it commits).
- Secrets now: CHARGEFINDER_KEY, FB_PAGE_ID, FB_PAGE_TOKEN, GOON_API_KEY, NOBIL_API_KEY, TANKERKOENIG_API_KEY (OCM_API_KEY deleted). `FB_PAGE_TOKEN` does not expire: rotate yearly and after any suspicion (`docs/facebook/GRAPH_API_SETUP.md`).
- Open for the owner: passkey/2FA on the GitHub account; revoke old personal access tokens.

## Cloudflare (zone eurofuelprices.com, Free plan)
- Response Header Transform Rule "Security headers (all pages)": `Strict-Transport-Security: max-age=31536000`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` (OSM tiles need a valid Referer, so no stricter policy), `Permissions-Policy: geolocation=(self), camera=(), microphone=(), payment=(), usb=()`.
- Response Header Transform Rule "Frame protection (all except widget)": `X-Frame-Options: SAMEORIGIN` and `Content-Security-Policy: frame-ancestors 'self'` on every path **except `/widget.html`**, which other websites embed in an iframe.
- Rate limiting rule "API rate limit (/api/*)": 40 requests per 10 seconds per IP, block for 10 seconds (the Free plan allows one rule and only these values). The Worker keeps its own limit (20 uncached requests per visitor per minute).
- Not enabled on purpose: Bot Fight Mode. GitHub runners (datacenter IPs) download state files from the site with curl; a bot challenge could break the scrape and the Facebook bot. Test first.
- Still to do by the owner: Email Routing (a `contact@` / `security@` address on the domain; needs a click in the verification mail).

## Monitoring
- Cloudflare Worker `efp-watchdog` (every 30 min, ntfy push): data older than 60 minutes or `meta.json` unreachable (chain dead or site down), stale countries, stale charger files, and (new) a country whose station count falls under 70 % of its remembered level.
