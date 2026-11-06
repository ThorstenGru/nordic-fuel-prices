# Route planner ideas E: delight and utility UX (research, 2026-11-06)

Status: research only. No code changed, nothing committed. Owner decides what to build.

## 0. How to read this

- "Opened" = I fetched the page this session. "Search result only" = a web search snippet, not opened. "Own knowledge" = from memory, not verified today; test before relying on it.
- Facts about the existing code come from reading `web/index.html` (route section, lines ~4043-4368) and `web/sw.js`/`web/manifest.json` heads. Inventions are labelled "Idea".
- Wow = how much a user says "oh nice". Effort = S (under 1 day), M (2-5 days), L (1-2 weeks) for one developer.

## 1. What the planner does today (facts from code)

- State lives in one global `rt` object: from/to text and coordinates, corridor width `w` (2/3/5 km), `fuelPct` (25/50/75/100), `battPct` (0/50/100, PHEV only), `reserve` (litres), `hideUnknown`. Nothing is persisted and nothing is in the URL, so a reload loses the trip.
- Route comes from Valhalla (FOSSGIS) with OSRM fallback; one route only, no alternatives, no via points, no speed input.
- `rtPlan` is a pure energy walk (electric km, kWh, petrol litres, arrival litres, `needStop`, `reachKm`). `rtCand` prices each pump: detour cost vs saving against a reference price, litres bought = burn from the pump to the destination. So there is no return leg, no "fill to X" choice, and no total trip cost number shown to the user.
- Output: verdict card (stop needed or not), up to 10 ranked pumps with net saving, "Go" and "Via" buttons. `rtVia` opens Google Maps with exactly one waypoint; no Apple Maps path.
- Service worker: shell network-first, country data cache-first by versioned URL. So stations already loaded work offline, but the route itself (Valhalla call, Nominatim geocode) does not, and the result is not stored.
- Pure functions are marked `RT-PURE-BEGIN/END` and tested by `tools/test_route_model.js`. Good: what-if sliders and multi-route compare can reuse `rtPlan`/`rtCand` without touching the DOM.

Key observation: the engine already computes almost everything a "before you go" card needs. Most of the delight below is presentation, persistence and hand-off, not new modelling.

## 2. External facts checked

| Topic | Finding | Source / status |
|---|---|---|
| Google Maps directions URL | `waypoints` separated by `%7C`; "up to three waypoints supported on mobile browsers, and a maximum of nine otherwise"; URL cap 2,048 chars; waypoints ignored on some Google products | https://developers.google.com/maps/documentation/urls/get-started (opened) |
| Apple Maps multi-stop | Not officially documented. Community reports repeating `daddr=` once per stop in `maps://?dirflg=d&daddr=A&daddr=B&daddr=C` works since iOS 16; an ABRP report suggests `saddr` plus several `daddr` on maps.apple.com; one report of CarPlay-connected quirk | https://abrp.upvoty.com/b/report-a-bug/sharing-route-with-multiple-stops-on-ios-only-shows-directions-to-first-stop/ and https://lr.sudovanilla.org/r/shortcuts/comments/xnpdg9/apple_maps_multistop_directions/iqx38on/?context=3 (search result only, community, unverified) |
| iOS web push | Home Screen web apps can use Web Push from iOS/iPadOS 16.4; permission must be requested on a user tap; Declarative Web Push (no service worker needed) from 18.4, installed web apps only | https://webkit.org/blog/16574/digital-credentials-api/ and https://webkit.org/?p=13878 (search result only; secondary summaries, not opened) |
| ntfy | Free hosted ntfy.sh needs no account or key; a `curl -d "msg" ntfy.sh/<topic>` from a GitHub Action delivers to the ntfy iOS/Android app; topic names are a shared namespace, so use a long random name (privacy caveat is the search summary's inference) | https://themenonlab.blog/blog/ntfy-free-push-notifications (search result only) |
| CarPlay | Third-party apps must fit a fixed Apple category with an entitlement; categories include EV charging and fueling (`com.apple.developer.carplay-fueling`); UI is Apple templates only; a web page cannot be shown | https://developer.apple.com/documentation/carplay/requesting-carplay-entitlements.md and https://developer.apple.com/forums/thread/825705 (search result only) |
| Android Auto and web apps | Search returned nothing. Own knowledge: Android Auto runs only apps built to its templates (navigation, media, messaging, POI/charging categories); a PWA/TWA cannot render there. Unverified | own knowledge |

Reality check conclusion (CarPlay/Android Auto): a static web app cannot appear on either screen. Realistic in-car path is "export the stops to Apple/Google Maps and let that app navigate", plus an audio-free glance card on the phone. A native CarPlay fueling app would need a native iOS app plus Apple entitlement approval: out of scope for one developer with static hosting.

## 3. Full idea list with wow vs effort

Scale: Wow 1-5, Effort S/M/L. Priority = judgement of wow per effort.

| # | Idea | Wow | Effort | Notes |
|---|---|---|---|---|
| 1 | Before-you-go summary card (one screen: total cost, time, fill-up plan, arrival state, where to stop, data-freshness badge) | 5 | S-M | Reuses `rtPlan`, `rtCand`; adds one total-cost formula |
| 2 | Shareable plan link (state in `#fragment`, no server) | 4 | S | Serialise `rt` inputs + coordinates; recompute on open |
| 3 | What-if sliders (start fuel %, battery %, reserve, speed) with live re-rank | 4 | S-M | Replace chips with ranges; `rtSet` already re-ranks. Speed needs a consumption factor (see 4.4) |
| 4 | Compare 2-3 routes by total cost and time (Valhalla alternates) | 5 | M | Valhalla `alternates` param (own knowledge, verify on FOSSGIS); cost = fuel + electricity + stop detours + ferry fee if known |
| 5 | Saved trips and commute presets, weekly/monthly cost (Billeberga-Malmo) | 5 | M | localStorage only; recompute daily with fresh prices; "this week you would spend X" |
| 6 | Export with via points to Google Maps and Apple Maps | 4 | S | Fix current single-waypoint limit; mobile cap is 3 waypoints (opened) |
| 7 | Return-leg and round-trip fill planning (Sweden-Germany-Sweden) | 5 | M | Plan leg 2 starting from leg-1 arrival state; "fill in Germany, arrive home with minimal litres"; fuel-tourism logic |
| 8 | Border-run improvements: "fill here vs there" break-even by country | 5 | M | Extends existing per-country-best-first logic; show EUR saved per full tank and the km at which crossing stops paying |
| 9 | Price-alert via scheduled GitHub Action + ntfy topic | 4 | M | Needs a place to keep the user's rule: see 4.7 privacy tension |
| 10 | Offline route pack (cache last route + corridor stations) | 3 | M | SW cache for the route object; stations already cached by country file |
| 11 | Local-only savings tracker | 3 | M | Log "I filled X l at Y"; compare with route median. Honest, private, but needs user input effort |
| 12 | Print/PDF trip sheet | 2 | S | `window.print()` + print CSS; low usage on phones |
| 13 | Spoken summary (speechSynthesis) | 2 | S | Web Speech synthesis is widely available (own knowledge); gimmick unless hands-free in car |
| 14 | Accessibility pass on route UI (labels on ranges, live region for results, 44 px targets, non-colour cues) | 3 | S | Not flashy but required; chips currently plain buttons without group labels |
| 15 | iOS Shortcuts / Android intents via URL params (`?from=..&to=..&auto=1`) | 3 | S | Deep links into the app; a "Billeberga to Malmo" Shortcut becomes one tap; no API needed |
| 16 | Home-screen widget | 1-2 | L | Web cannot do true widgets; skip |
| 17 | CarPlay / Android Auto app | 1 | L+ | Not feasible without native app and entitlement (section 2) |
| 18 | Web push without own backend | 2 | L | Needs push service and VAPID keys and a subscription store; conflicts with no-backend and privacy |

## 4. Detail on the main ideas

### 4.1 Before-you-go summary card (idea 1)
Content, top to bottom, all derived from existing outputs:
1. Headline: "Billeberga to Hamburg: 640 km, 6 h 50, about 58 EUR, 1 stop".
2. Cost breakdown: electricity (kWh x tariff, already `elecCost`), petrol (litres x chosen pump price), detour cost.
3. The recommended stop with a plain reason ("14 cents below the route median, 2.1 km detour, price 38 min old, 2 sources").
4. Arrival: litres left, battery left, margin over reserve; red/amber/green.
5. A data honesty line using the existing tier system (`rtTier`): "Prices on this route: 7 fresh, 3 unverified".
Total cost formula (Idea): `cost = elecCost + petrolL_burned * pumpPrice_for_litres_bought_there_or_start_price + detourCost`. Needs one decision: price of fuel already in the tank. Simplest honest choice: value tank fuel at the route median, show it as an assumption.
Value: this is the screenshot users will share. Risk: false precision; keep ranges ("about 55-61 EUR") if price age is high.

### 4.2 Shareable plan link (idea 2)
Encode `#r=` plus compact params: from/to coordinates (4 decimals), labels (URL-encoded, truncated), `w`, `fuelPct`, `battPct`, `reserve`, fuel type. On open, populate `rt` and run `rtGo()`; prices are always recomputed fresh, so a shared link never shows stale numbers. Fragment is never sent to the server, which fits the privacy promise. Keep under ~500 chars so it survives messengers. Same mechanism powers Shortcuts (idea 15) and saved trips (idea 5): one serialiser, three features. Risk: coordinates of a home address in a link; warn on share ("this link contains your start point") and offer "round to 1 km".

### 4.3 Compare 2-3 routes (idea 4)
Valhalla supports alternate routes (own knowledge: `alternates` option in the route request; confirm the FOSSGIS instance allows it and what the usage policy says about request volume). Show a three-row table: time, km, total cost, stops, ferry. Hook: "Fastest is 22 min quicker and 9 EUR dearer." The corridor search and ranking run per route; the existing grid code is per `R.pts`, so run it in a loop. Cost: three corridor passes on ~100k stations is the main CPU risk on older phones; measure. Also useful as a Sweden-Germany choice: Oresund bridge versus ferry (Helsingborg-Helsingor, Trelleborg-Travemunde): the existing `ferry` flag helps; ferry price is not in the data (needs a small static table, hand-maintained, flagged as indicative).

### 4.4 What-if sliders (idea 3)
Convert chips to sliders for start fuel and battery (0-100), reserve (litres) and add a speed slider (90-130 km/h). Speed changes consumption: Idea, a simple multiplicative curve (consumption factor about 1.0 at 90, roughly +25 to +30 % at 130 for a heavy SUV) labelled as an estimate. The Santa Fe PHEV model docs (`docs/PHEV_TEMPERATURE_MODEL_2026-11-06.md`) already have a temperature factor; a speed factor fits the same `phevF` shape. Keep the pure functions untouched by multiplying `cons`. Show a live "cost delta" next to the slider ("-5 km/h saves 2.4 EUR on this trip"). That sentence is the delight.

### 4.5 Saved trips and commute presets (idea 5)
Store in `localStorage` (try/catch; may be blocked): name, from/to, options. Home screen shows saved trips as cards with today's cost computed in the background when the app opens (route geometry cached from last run to avoid a Valhalla call; refresh weekly). Commute extras: trips per week setting gives "about 31 EUR per week", and a "best day to fuel this week" hint if the existing electricity outlook plus fuel trend makes one available. Billeberga-Malmo daily is mostly electric for a PHEV, so the card should show the electric share and the cost per day ("0.9 kWh/km-equivalent, 2.10 EUR"). Risk: privacy expectations; state "stored only on this device" and add export/import as a JSON file or via the link in idea 2 so trips survive a phone change.

### 4.6 Export with via points (idea 6)
Today: Google link, one waypoint. Improve:
- Google: `waypoints=A%7CB%7CC`, max 3 on mobile browsers (opened), so the plan must cap at 3 chosen stops; add `travelmode=driving`.
- Apple: repeated `daddr` (community-reported, unverified). Build it behind a feature test on the owner's iPhone before shipping; fall back to destination-only plus "add stop" message.
- Also `geo:` URIs for Android (own knowledge; no multi-stop). Offer a "copy stops as text" fallback.
- One catch: Google/Apple will re-route their own way; the stops are honoured but the road between them may differ from Valhalla. Say so in one line.

### 4.7 Price alerts (idea 9) and the privacy tension
Mechanics that fit the constraints: a GitHub Actions cron already refreshes the data. An alert job could read a rule list and `curl` ntfy. Problem: where do rules live? A static site cannot store user rules; putting them in a public repo or a per-user file breaks privacy and scale. Options:
- A. Per-user ntfy topic, rule encoded in the topic: not possible without server logic.
- B. Owner-only alerts (the owner's own commute): rules in a private repo secret/config, Action posts to the owner's ntfy topic. Works today, zero privacy issue, serves one person. Cheap and genuinely useful for dogfooding.
- C. Public "daily cheap fuel" ntfy topics per country (broadcast, not per-user): users subscribe in the ntfy app themselves; the app only shows a "Subscribe" link. No user data touches the site. Low effort, honest, moderate wow.
- D. True web push: needs subscription storage and a sender with VAPID keys; iOS requires installed Home Screen app (search result, https://webkit.org/?p=13878). Not feasible without a backend; skip.
Recommendation: B for the owner now, C as a public feature later. Limit to state plainly: no personal threshold alerts for the public.

### 4.8 Return leg, round trip, border run (ideas 7, 8)
The best-differentiated idea for this owner (Sweden-Germany). Currently `litres` bought equals the burn to the destination only. Round-trip logic (Idea):
1. Leg 1 plan as today, with an option "fill extra for the return leg here".
2. Leg 2 starts with the leg-1 arrival state (fuel, battery if the owner charges at the destination: input "charge at destination yes/no").
3. Compare policies: "fill in Germany to the brim and skip Swedish stops" versus "fill both sides". Price difference per country is already in the data (`fxRank`, EUR conversion), so the result is a single sentence: "Filling 38 l in Germany instead of Sweden saves about 11 EUR, 0 km detour."
4. Border-run view for commuters near a border: break-even distance = (price gap per litre x tank litres) / (cost per km of the detour). Show it as "worth it if the border pump is within N km of your route". The detour cost model (`detourKm * cons * price`) already exists.
Risk: mixed-quality prices (Germany via ANWB now, Tankerkoenig planned, see roadmap). A cross-country comparison is only as trustworthy as the weaker feed; keep the existing trust tiers and show "unverified" on the recommendation instead of hiding it. Currency: uses the ECB rate and card fee from the currency decision; include the card fee in the foreign price or the saving is overstated.

### 4.9 Offline/PWA (idea 10)
Service worker already caches the shell and country files. Add: store the last computed `rt.res` (polyline simplified, ranked rows, timestamp) in IndexedDB or `localStorage` (size: polyline of 600 km at ~1 point per 300 m simplified is roughly 100-200 KB; use Douglas-Peucker). Offline behaviour: open app, show "last plan, computed 14:02, prices may be older" with Go buttons that work through the maps hand-off. Map tiles are not covered by the current cache (own assumption; check `sw.js` tile handling). Honest limit: a fully offline re-plan is not possible because routing is remote.

### 4.10 Shortcuts and intents (idea 15) and widgets (16)
URL parameters make the app Shortcut-friendly: an iOS Shortcut "Open URL" with `https://eurofuelprices.com/#r=...` is a one-tap "Billeberga-Malmo today". This needs idea 2 only. Real widgets are impossible from a static page; a Shortcut widget on the iOS Home Screen opening that link is the closest honest substitute (own knowledge). Android: Chrome "Add to Home screen" shortcut for a deep link, same mechanism.

### 4.11 Accessibility and spoken summary (13, 14)
Quick wins: group the chips with `role="group"` and `aria-labelledby`, put the verdict in an `aria-live="polite"` region so results are announced, ensure colour is never the only signal (tier uses a heading "unverified" already, good), 44 px touch targets for chips, sliders with `aria-valuetext` ("50 percent, 23 litres"). Spoken summary via `speechSynthesis` is a nice side effect of a clean summary string (idea 1): one button "Read aloud". Low wow, near zero cost once the summary text exists, and useful for the driver.

## 5. Top 8 ideas for EuroFuelPrices (recommended order)

1. **Before-you-go summary card with total trip cost**
   - Impact: very high. Turns a pump list into an answer; most shareable screen.
   - Effort: S-M.
   - Needs: existing `rtPlan`/`rtCand`; one decision on valuing fuel already in the tank; ferry fee table optional.
   - Risk: false precision; show ranges when prices are old or unverified.

2. **Shareable plan link (fragment) plus deep-link entry (Shortcuts)**
   - Impact: high; also the foundation for saved trips and Shortcuts.
   - Effort: S.
   - Needs: a serialiser/parser for `rt`; no server, no new data.
   - Risk: home coordinates leaking in links; round or warn.

3. **Saved trips and commute presets with weekly cost (Billeberga-Malmo)**
   - Impact: high for daily users; this is the retention feature and fits the owner's own use.
   - Effort: M.
   - Needs: localStorage (guarded), cached geometry, a trips-per-week input; JSON export/import for device changes.
   - Risk: storage may be blocked; clearly say "on this device only".

4. **Round trip and return-leg fill planning with border-run break-even**
   - Impact: very high for Sweden-Germany drivers; the unique selling point versus generic route planners.
   - Effort: M.
   - Needs: leg-2 start state, "charge at destination" input, card fee in foreign price, German price quality (Tankerkoenig pending).
   - Risk: cross-country comparison rests on uneven data quality; keep trust tiers visible.

5. **Compare 2-3 routes by total cost and time**
   - Impact: high; "fastest vs cheapest" is intuitive.
   - Effort: M.
   - Needs: Valhalla alternates (verify on the public instance and its usage policy), three corridor passes (measure phone CPU), ferry price table for Oresund/ferry choices.
   - Risk: public router load and CSP; unknown alternates quality.

6. **What-if sliders including speed, with live cost delta**
   - Impact: medium-high; makes the model feel alive and teaches economy.
   - Effort: S-M.
   - Needs: speed-to-consumption curve (assumption, label as estimate); sliders accessible.
   - Risk: pseudo-exactness of the speed factor; keep it coarse.

7. **Export with up to 3 via points to Google and Apple Maps**
   - Impact: medium-high; closes the "now drive there" gap, and is the realistic in-car story given the CarPlay/Android Auto reality check.
   - Effort: S.
   - Needs: Google `%7C` waypoint format (opened docs); Apple repeated `daddr` must be tested on the owner's iPhone first.
   - Risk: Apple format unofficial; cap of 3 waypoints on mobile Google.

8. **Owner-only price alert (GitHub Action to ntfy), later a public daily "cheap fuel" topic**
   - Impact: medium (one user now), delight for the owner; the public version is low-effort broadcast.
   - Effort: M for owner version, S-M for public topics.
   - Needs: private repo secret for the owner's rule and random topic name, ntfy app on the phone.
   - Risk: ntfy topics are guessable if short; per-user public alerts are not feasible without a backend and conflict with the privacy stance.

Honourable mentions, low priority: offline last-plan view (M), accessibility pass (S, do it alongside item 1 and 6), print/PDF and spoken summary (S, trivial once the summary text exists).

Explicitly not recommended: CarPlay/Android Auto app (needs native app and Apple entitlement), home-screen widget (not possible on the web), per-user web push (needs a backend and stores a subscription per user).

## 6. Suggested build order for decision

- Slice A (about 1 week): ideas 1, 2, 7 and accessibility. Everything reuses current pure functions; shippable and testable with the existing `tools/test_route_model.js`.
- Slice B (about 1 week): ideas 3 and 6.
- Slice C (1-2 weeks): ideas 4 and 5; depends on Tankerkoenig for best results.
- Slice D: idea 8 owner alert as a side task.

## 7. Open questions for the owner

1. Is total trip cost allowed to value tank fuel at the route median, or should it show only "money you still have to spend"?
2. Does he charge at the destination in Germany (changes round-trip logic a lot)?
3. Accept a hand-maintained ferry/bridge price table, flagged "indicative"?
4. Should saved trips be exportable (file or link) so they survive a phone change?
5. Apple Maps multi-stop: can he test the repeated-`daddr` format on his iPhone (iOS 26) before it ships?

## 8. What I did not verify

- Valhalla `alternates` support and policy on the FOSSGIS public instance.
- Whether Safari/iOS 26 still honours the Apple Maps URL formats above.
- Android Auto limits (own knowledge only).
- Map-tile caching behaviour in `sw.js` (read only the head of the file).
- Web push and ntfy details are search-result summaries, not official docs.
