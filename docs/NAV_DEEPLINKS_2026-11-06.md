# R13 navigation export: deep-link research (2026-11-06)

Goal: from a planned route with 1-3 fuel stops plus a final destination, hand the plan to the owner's navigation app. The owner uses Waze.

## Pages opened (read in full via fetch on 2026-11-06)

| Page | Opened | Notes |
|---|---|---|
| developers.google.com/maps/documentation/urls/get-started (Google Maps URLs) | yes | Source for all Google Maps facts below |
| developers.google.com/waze/deeplinks (Waze deep links) | yes | Source for all Waze URL facts below |
| developers.google.com/maps/documentation/navigation/connect/launch-navigation-app | yes | Explicit "don't use multiple waypoints" rule for Google Maps and Waze |
| developer.apple.com/documentation/mapkit/unified-map-urls ("Adopting unified Maps URLs", fetched as .md) | yes | Source for all Apple Maps facts below |
| developer.apple.com/forums/thread/784030 | yes | Apple DTS says the schema came in iOS 18.4; old `daddr=lat,long` link reported as regressed |
| waze.com/discuss/t/set-starting-point-and-stopping-points-via-deep-link-parameters/284817 | yes | Community answer only (not staff): app has no multi-stop |
| developer.apple.com/library/archive/.../MapLinks.html (legacy Map Links) | opened, body empty | Content not retrievable; legacy `saddr/daddr/dirflg` facts come from a web search summary, treated as unverified |

Not verified by any page I could read: the legacy `+to:` multi-stop syntax for Apple Maps. Do not use it.

## Waze (waze.com/ul)

Base: `https://waze.com/ul?param=value&param=value`. Values must be URL-encoded (space = `%20`).

- `ll=lat,lon` destination coordinates (Live Map share links encode the comma as `%2C`).
- `navigate=yes` start navigation to the `ll` or `q` (or `favorite`) destination.
- `q=search%20terms` address or place search. `q` with `ll` and `navigate=yes` searches and navigates.
- `zoom=17` (Navigate section) and `z=8` (Show-on-map section): the docs are inconsistent. We do not need either.
- `favorite=home|work`, plus routing options `avoid_tolls`, `avoid_ferries`, `avoid_freeways`, `avoid_dangerous_turns`, `avoid_trails`, `vehicle_type=private|taxi|motorcycle` (true/false or t/f).
- `utm_source` is a partner attribution tag. We omit it (no tracking).
- Behaviour: desktop opens the web app; phone with Waze installed opens the app; without it opens the web page. `waze://` scheme skips the web hop but does nothing if Waze is missing, so the https form is safer.
- Not documented: any origin/`from`, any waypoint or via, any second destination. Google's own guidance (launch-navigation-app page) says: "Don't use multiple waypoints. If you pass multiple waypoints directly in the URL, Google Maps or Waze displays an error." Create separate trips instead. The Waze community thread agrees (app routes from current location, no multi-stop).

Conclusion: Waze deep links are single destination only, from the current position. This is a hard limit, not something to work around with repeated `ll`.

Waze cannot show the final destination afterwards: once the first stop is navigated, Waze knows nothing about the following stops or the end point. Nothing in the deep link carries it. The owner must tap the next link (or type it) after each stop. Say this plainly in the UI.

## Google Maps URLs

Base: `https://www.google.com/maps/dir/?api=1&...` (`api=1` mandatory, otherwise all other params are ignored).

- `origin`, `destination` (place name, address, or `lat,lon`). Omitted origin = device location.
- `waypoints` stops separated by `|`, shown in listed order. `waypoint_place_ids` optional, needs `waypoints`.
- `travelmode=driving` (also walking, bicycling, two-wheeler, transit).
- `dir_action=navigate` starts turn-by-turn if origin is omitted or near the user; otherwise a route preview opens.
- `avoid=ferries,highways,tolls` (comma separated).
- Limits: up to 3 waypoints in mobile browsers, up to 9 elsewhere; 2,048 characters per URL.
- Encoding: use a URL library. `|` is `%7C`, `,` is `%2C`, space is `%20` or `+`. Example: `Berlin,Germany|Paris,France` becomes `Berlin%2CGermany%7CParis%2CFrance`.
- iOS: opens in the Google Maps app if installed, otherwise the browser. Android: the app if installed and active, else browser.

Fit for us: 1-3 fuel stops = up to 3 waypoints plus the destination, exactly the mobile limit. With coordinates the URL stays well under 2,048 characters. A 4th stop would exceed the mobile cap, so cap the exported stops at 3 (our plans already aim for fewer stops).

Example (2 stops, destination Berlin):
`https://www.google.com/maps/dir/?api=1&origin=55.6050%2C13.0000&destination=52.5200%2C13.4050&waypoints=55.1000%2C14.0000%7C53.9000%2C13.9000&travelmode=driving&dir_action=navigate`
Omit `origin` so it starts from where the owner stands; include it only for a preview of a future trip.

Open point I could not test: whether the iOS app honours `dir_action=navigate` with waypoints versus showing a preview. Documented behaviour is "navigation if origin omitted or close", otherwise preview. Treat preview as acceptable.

## Apple Maps

Legacy `saddr/daddr/dirflg` is reported unreliable on recent iOS (forum thread 784030: `daddr=lat,long` stopped working; Apple DTS points to the new schema). Use the unified URLs, available iOS 18.4+ (the owner is on iOS 26, fine).

- `https://maps.apple.com/directions?destination=...&waypoint=...&waypoint=...&mode=driving`
- `source` (omit = current location), `destination`, repeat `waypoint` for each intermediate stop (documented: "You can specify multiple waypoints by repeating the waypoint parameter"), values are address, coordinate or place name.
- `mode=driving|walking|transit|cycling`; `avoid=tolls,highways,busy-roads,stairs` comma separated; `start=<seconds>` delays start of navigation.
- No documented waypoint count limit (the page states none). In-app multi-stop is documented elsewhere as limited, so cap at 3 anyway.
- Caution: Apple's published examples contain malformed percent-encoding (for example `1%Dr.`); do not copy them. Use `encodeURIComponent` on `lat,lon` strings only.

Example: `https://maps.apple.com/directions?destination=52.5200,13.4050&waypoint=55.1000,14.0000&waypoint=53.9000,13.9000&mode=driving`
I did not run it on a device. Verify on the owner's iPhone before shipping.

## Universal intents and schemes (summary)

- Android: `google.navigation:q=lat,lon` (single destination) and Waze via the https link; no cross-app multi-stop standard.
- iOS: `waze://`, `comgooglemaps://`, `maps://` custom schemes need `LSApplicationQueriesSchemes` in a native app. A web page cannot probe for installed apps, so we use https universal links only, which fall back to the browser.
- There is no cross-app standard for a multi-stop route. The only multi-stop formats are Google Maps `waypoints` and Apple Maps repeated `waypoint`.

(Android intent forms were not opened in this pass; they are listed for context only. R13 does not need them.)

## Recommendation for a Waze user, 1-3 fuel stops

Principle: be honest that Waze takes one destination, and make the one-destination flow as smooth as possible, while offering real multi-stop in the other apps.

1. Primary card "Navigate with Waze" for the first leg:
   - Button "Waze: go to stop 1 (Circle K Ystad)" opening `https://waze.com/ul?ll=<lat>%2C<lon>&navigate=yes` (no `utm_source`; no `q`, so the coordinate is used exactly, since a search could re-geocode).
   - One line under it: "Waze takes one destination at a time. After you fuel, come back here and tap the next button."
2. Per-leg buttons rendered as a numbered list: "1. Stop 1 (Waze) / 2. Stop 2 (Waze) / Final: Berlin (Waze)". Each is a plain link to its own `ll`. The list stays on screen (and is saved when the owner returns because the plan lives in page state), so the next leg is one tap away. Mark the leg tapped last, locally only.
3. Secondary buttons "Google Maps (all stops)" and "Apple Maps (all stops)" using the multi-stop formats above, for when the owner prefers one continuous route. Hide a button if there are more than 3 stops; show the per-leg list instead.
4. A "Copy stop list" button writing plain text via the Clipboard API with a `<textarea>` fallback, one stop per line: name, address if known, `lat,lon`, the price, and the final destination. Useful for pasting into a message or Waze search.
5. Privacy: all links are plain `<a href>` generated on the device, with `rel="noopener"`, no redirect service, no `utm_source`, no analytics. Coordinates only leave the device when the owner taps a link, and go to the chosen app.
6. State facts clearly in the UI: "Waze cannot show your final destination after the first stop." There is no workaround through a deep link.
7. Default choice: remember the last-chosen app in `localStorage` (try/catch) and put it first; first run defaults to Waze for this owner.

Risks and untested items: Apple unified URL behaviour on iOS 26 not device-tested; Google Maps iOS navigate-versus-preview with waypoints not device-tested; Waze `zoom/z` doc inconsistency is irrelevant since we do not use it.
