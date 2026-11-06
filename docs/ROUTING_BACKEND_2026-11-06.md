# Routing backend: research and recommendation (2026-11-06)

Roadmap items N1 (stable routing, proxy) and N2 (ferry-aware). Probed with plain GET/OPTIONS from the owner's machine on 2026-11-06. "Verified" = I saw it answer; "unverified" = from documentation or the earlier design doc, re-check before relying on it.

## Current state

`web/index.html` called `router.project-osrm.org` directly (CSP `connect-src` allowed only that host). Ferries are not routed: Malmo to Hamburg = 503 km.

## Test: Malmo (55.605, 13.0) to Hamburg (53.551, 9.993)

| Provider | Answer | Distance | Ferry | CORS | Needs key |
|---|---|---|---|---|---|
| OSRM demo `router.project-osrm.org` | 200 | 503.1 km, 5.5 h | No (`exclude=ferry` unsupported; car profile avoids ferries) | `*` | No |
| OSRM FOSSGIS `routing.openstreetmap.de/routed-car` | 200 | 503.1 km (same data and profile) | No | not checked | No |
| BRouter `brouter.de` (car-fast) | 200 | 502.7 km | No (car profile has no ferries) | `*` | No |
| **Valhalla FOSSGIS `valhalla1.openstreetmap.de`** | 200 | **373.9 km, 4.7 h** | **Yes: "Rodby (DK) - Puttgarden (D) / E 47 Ferry", `has_ferry: true`** | `*` | No |
| GraphHopper `graphhopper.com/api/1` | 401 "No API key specified" | not tested | documented yes (unverified) | `*` | Yes |
| OpenRouteService `api.openrouteservice.org` | 401 "Authorization field missing" | not tested | documented yes in driving-car (unverified) | OPTIONS answered, `*`, Authorization header allowed (verified) | Yes (free key) |

Valhalla polyline decodes cleanly: 3,809 points from (55.6056, 13.0000) to (53.5511, 9.9936), 373.9 km, ferry flag true (checked with the adapter code below in Node against the live server).

## Per option: policy, rate limit, privacy

- **OSRM demo**: usage policy is non-commercial, about 1 request/s, no uptime promise (policy text not re-fetched today; from ROUTE_PLANNER_DESIGN.md). Wrong for ferry trips. Keep only as fallback.
- **Valhalla FOSSGIS (public)**: free, no key, community-run by FOSSGIS e.V.; fair-use for non-commercial/hobby, no SLA, no published numeric limit that I verified. Ferries work. CORS open, so the browser can call it directly. Privacy: route endpoints go from the phone to a German non-profit server (same exposure class as today's OSRM, one third party either way).
- **OpenRouteService free tier**: needs a key. Figures in the design doc: about 2,000 requests/day, 40/min (unverified, re-check). Key must not be shipped in the page, so it needs the Worker. Good fallback and handles the X2 detour refinement only tightly.
- **GraphHopper**: key required; free tier is small and for non-commercial use only. No advantage over ORS here.
- **BRouter**: hobby server, bicycle-focused, car profile has no ferries. Not suitable.
- **Self-hosted Valhalla/OSRM on a small VPS**: ferries and no third party, but needs RAM and disk for a Nordic plus central Europe extract (several GB), monthly OSM updates and patching. Roadmap L3 says not for a solo owner now. Not recommended.
- **Cloudflare Worker proxy + Cache API**: not a router, a layer in front of one. It hides any API key, rounds coordinates to about 100 m for the cache key, caches repeated routes, enforces an Origin check, and means the browser talks to only one host we control (CSP stays tight when the provider changes). The Worker sees the endpoints in transit, so the note must say so and the Worker must not log coordinates.

## Recommendation

1. **Now (no accounts, no cost)**: switch to public Valhalla FOSSGIS for ferry-correct routes. It is the only keyless option that answered with the ferry route. This is a one-constant change (`ROUTER = 'valhalla'`) plus a text update to the `rtNote` string (all languages mention OSRM and "ferries not considered"). I did not flip it: it changes who receives the owner's users' route endpoints and needs the note rewritten and an owner decision. The CSP already allows the Valhalla host (added, see below).
2. **Next (when traffic or reliability bites)**: Cloudflare Worker `route.<domain>` in front of Valhalla FOSSGIS with ORS as automatic fallback. The Worker holds the ORS key, rounds coordinates, caches via the Cache API, checks Origin.
3. Do not self-host (L3) until limits are actually hit.

## What the owner must create (nothing needed for step 1)

For step 2 only, owner actions, Claude creates no accounts:

1. A free OpenRouteService account and API key (openrouteservice.org, dev dashboard). Check current free-tier limits and the terms for a non-commercial public app.
2. A Cloudflare Worker (existing Cloudflare account, site already uses Cloudflare) with a route like `route.eurofuelprices.com/*`, the ORS key stored as a Worker secret (`ORS_KEY`), and no logging of request URLs/bodies. Add the Worker host to the CSP `connect-src` and drop hosts no longer called.
3. Decision: confirm the site counts as non-commercial for ORS and FOSSGIS terms.

## What changed in the code (not committed)

`web/index.html`:
- New adapter `rtRoute(a, b)` returns `{ pts, km, min, ferry }`. `rtGo` calls only this. Provider chosen by `const ROUTER = 'osrm'` (default, behaviour unchanged) or `'valhalla'`.
- `decodePoly6` for Valhalla's 6-decimal polyline.
- CSP `connect-src` now also allows `https://valhalla1.openstreetmap.de`.
- `rt.res.ferry` is stored but not yet shown in the UI (roadmap N2 asks to display "via ferry"; left for the UI step).

Switching to Valhalla = set `ROUTER = 'valhalla'` and update `rtNote` in the EN/SV/DE/FR/ES blocks (lines near 1130, 1134, 1138, 1206, 1214), and bump `SHELL_CACHE` in `web/sw.js` so the new page is picked up. Adding a Worker later = a third branch in `rtRoute` pointing at the Worker URL.

## Not verified

- Published usage policies and numeric limits were not re-read today; confirm before launch.
- ORS and GraphHopper routing results (no keys); their ferry behaviour is from documentation.
- The Valhalla path was tested through the adapter code in Node, not in the Browser pane with the full Route tab (corridor search, map line).
- Valhalla's `time` (4.7 h) includes the ferry crossing as modelled by Valhalla; waiting time at the port is not included.
