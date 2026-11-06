# My car tab: clarity audit (2026-11-06)

Scope: audit only, no code changed. Tested on a scratch copy of `web/` (with `data/*.json`) in the Browser pane at 375 px, first with an empty profile (first visit), then with the Santa Fe profile (Hyundai Santa Fe 1.6 T-GDi PHEV MY25: tank 47 L, 7.5 L/100 km, battery 13.8 kWh, 54 km WLTP range; home price entered 2.50 kr/kWh; country Sweden; map centred near Malmo so the 5 nearest stations resolve).

The target reader is an ordinary driver who has never seen the tab, on a phone, with no idea what kWh/100 km, a tariff or break-even is.

## 1. What a first-time driver sees today

Measured on the phone layout (Santa Fe profile, tariff open):

| Block | Height (px) | Screens (812 px) |
|---|---|---|
| Car profile box (`#car-box`) | 1121 | 1.4 |
| Petrol or electricity? (`#ev-card`) | 1712 | 2.1 |
| Electricity price outlook (`#op-card`) | 1159 | 1.4 |
| My home electricity (`#tf-card`, open) | 1407 | 1.7 |
| Whole tab | 6130 | 7.5 |

Empty profile: the tab opens with a search box, a select with about 110 vehicles, "Vehicle type: Not set", three empty number fields, a card-fee field and a one-line "Choose petrol or plug-in hybrid under Vehicle type above to compare." Nothing says what the tab is for, what to do first, or what the user gets for doing it. The sheet also opens at peek height (only the title "My car" is visible until the user drags it up).

The valuable answer ("is it cheaper to charge or to fill up, and by how much?") appears only after about 1100 px of form, and then as a table of six numbers. The most important facts exist in two places with different values (see section 3, "Conflicts").

## 2. Findings by section and control

Format per item: purpose (one plain sentence), what confuses, replacement wording EN / SV.

### 2.0 Tab header and sheet

- Purpose: set up your car once so every price in the app can be translated into "what it costs me".
- Confusing: title "My car" alone; no intro; no hint of what happens next; sheet opens collapsed.
- Replace:
  - EN intro: "Tell us about your car and what you pay for electricity. We then show whether charging or filling up is cheaper, and what a trip costs."
  - SV intro: "Berätta om din bil och vad du betalar för el. Då visar vi om det är billigast att ladda eller tanka, och vad en resa kostar."
- Implementation hint: open the sheet at full height when the tab is opened from the tab bar (or at least once per profile).

### 2.1 Find your car (`#veh`, `#veh-q`, `#veh-sel`, `#veh-note`)

- Purpose: pick your model so we fill in tank, consumption and battery for you.
- Confusing: two controls (search plus a select with 110 options) and the first option "Custom (enter values below)". The note "Example values (typical WLTP figures) from hyundai.news: please adjust to your car." uses the unexplained term WLTP and sounds like a warning; the user does not know which of the following fields were filled and which are theirs.
- Replace:
  - Label EN "Pick your car model" / SV "Välj din bil".
  - Placeholder EN "Type a make or model, e.g. Santa Fe" / SV "Skriv märke eller modell, t.ex. Santa Fe".
  - First option EN "My car is not listed (enter values myself)" / SV "Min bil finns inte med (fyll i själv)".
  - Note EN "We filled in the fields below with the manufacturer's official figures. Check them against your car's papers; official figures are usually a bit better than real life." / SV "Vi har fyllt i fälten nedan med tillverkarens officiella siffror. Jämför med bilens handlingar; de officiella siffrorna är oftast lite bättre än verkligheten."
  - Drop the source site name from the visible note (keep it in a "Where do these numbers come from?" help item).

### 2.2 Vehicle type (`#car-type`)

- Purpose: say how the car gets its energy.
- Confusing: "Not set" as the default hides that this one choice switches the whole tab on or off. "Plug-in hybrid" is not self-evident to some; Swedish "Laddhybrid" is fine. The user cannot tell that selecting "Petrol" disables the electricity comparison ("Choose petrol or plug-in hybrid...").
- Replace:
  - Label EN "What does your car run on?" / SV "Vad drivs din bil med?"
  - Options EN "Choose..." / "Petrol" / "Diesel" / "Plug-in hybrid (petrol and a battery you charge from a socket)" ; SV "Välj..." / "Bensin" / "Diesel" / "Laddhybrid (bensin och ett batteri du laddar i ett vägguttag)".
  - Helper under the field EN "Only plug-in hybrids can be compared with electricity." SV "Bara laddhybrider kan jämföras med el."

### 2.3 Fuel tank (litres) (`#car-tank`)

- Purpose: how much fuel fits, used to cost a full tank and plan stops.
- Confusing: no hint of a typical value; duplicated by the "Tank size" chips lower down (20/30/40/50/70 L) which set the same value (`efp_tank`) but sit in a different section with no explanation.
- Replace: label EN "Fuel tank size (litres)" / SV "Tankens storlek (liter)"; helper EN "Most cars: 40 to 60 litres." / SV "De flesta bilar: 40 till 60 liter." Remove the separate "Tank size" chip row or move it directly under this field and label it "Quick pick".

### 2.4 Fuel consumption (L/100 km) (`#car-cons`)

- Purpose: how much petrol the car burns per 100 km.
- Confusing: "L/100 km" is a unit, not a meaning. For a plug-in hybrid the number to enter is ambiguous: the official mixed figure (Santa Fe: 1.7 L/100 km) or the figure with an empty battery (7.5 L/100 km). The app uses the empty-battery value (7.5), which is right for the calculation, but the user is not told so and may overwrite it with 1.7 and get wrong results.
- Replace:
  - Label EN "Petrol use (litres per 100 km)" / SV "Bensinförbrukning (liter per 100 km)".
  - Helper EN "Example: 7 means the car uses 7 litres of petrol to drive 100 km. For a plug-in hybrid, use the figure for when the battery is empty." / SV "Exempel: 7 betyder att bilen drar 7 liter bensin på 100 km. För en laddhybrid: ange värdet när batteriet är slut."
  - Add Santa Fe example in the help item: "Santa Fe: 7.5 (battery empty)" / "Santa Fe: 7,5 (tomt batteri)".

### 2.5 Battery, usable (kWh) (`#car-batt`)

- Purpose: how much electricity the battery can hold; sets how far you get on electricity per charge.
- Confusing: "usable", "kWh" unexplained. The Santa Fe value 13.8 is the gross figure (usable unknown, see memory note), so "usable" is misleading.
- Replace: label EN "Battery size (kWh)" / SV "Batteriets storlek (kWh)"; helper EN "kWh is a unit of energy, like litres for fuel. Plug-in hybrids have about 10 to 25 kWh." / SV "kWh är energi, ungefär som liter för bensin. Laddhybrider har ca 10 till 25 kWh."

### 2.6 Electric range (km) (`#car-range`)

- Purpose: how far the car drives on a full battery.
- Confusing: the official figure (54 km) is optimistic; the app silently scales it (RT_REAL factor, and temperature curve), so results later show "41 km" with no explanation of why that differs from the 54 the user entered.
- Replace: label EN "Range on a full battery (km)" / SV "Räckvidd på fullt batteri (km)"; helper EN "The official figure. In daily driving you get less, and in winter much less; the results below take that into account." / SV "Det officiella värdet. I vardagen får du mindre, och på vintern mycket mindre; resultaten nedan räknar med det."

### 2.7 Home electricity price per kWh (`#car-elec`, also `#ev-price` in the ev card)

- Purpose: what you pay for one kWh at home; the single most important number for the result.
- Confusing: (a) it is asked in two places (profile and inside the ev-card, mode "Home"), (b) it is a long way from the result and not marked as the one required input, (c) there is no hint of what a typical value is or where to find it, (d) the tariff section further down computes a separate "4.86 SEK/kWh" that is not connected to this field, so the user sees 2.50 here and 4.86 there with no explanation.
- Replace:
  - Label EN "What you pay for electricity at home (per kWh, including VAT)" / SV "Vad du betalar för el hemma (per kWh, inkl. moms)".
  - Helper EN "Find it on your electricity bill, or use our estimate for your area (button below). Sweden is roughly 1.50 to 3.50 kr/kWh including grid fees and tax." / SV "Hittar du på elfakturan, eller använd vår uppskattning för ditt elområde (knappen nedan). I Sverige ligger det ofta på 1,50 till 3,50 kr/kWh inklusive nätavgift och skatt."
  - Button EN "Use my tariff estimate: 4.86 kr" / SV "Använd min elavtalsuppskattning: 4,86 kr" (fills the field from `tf` so the two sections agree; this changes input convenience only, not the calculations).
  - Keep one input only (profile). In the result card show "You pay 2.50 kr/kWh" with a "change" link that focuses the field.

### 2.8 Charging efficiency (%) (`#car-eff`)

- Purpose: how much of the electricity from the wall ends up in the battery.
- Confusing: "efficiency" with placeholder 90 and no explanation; the same concept appears again as "Charging loss factor (1.15 = 15% lost)" in the ev card, a different representation (factor vs percent) of the same idea in two places.
- Replace: move to "Advanced". Label EN "Charging loss" with value shown as "10 % lost (default)"; help item "What is charging loss?" EN: "Some electricity is lost as heat when charging. If you buy 10 kWh from the wall, about 9 kWh reach the battery. We assume 10 percent lost unless you change it." SV: "En del av elen blir värme vid laddning. Köper du 10 kWh från elnätet når ungefär 9 kWh batteriet. Vi räknar med 10 procent förlust om du inte ändrar det."
- Use one representation only (percent lost). The factor 1.15 field in the ev card goes.

### 2.9 My card adds on foreign payments (%) (`#car-cardpct`) and card hint

- Purpose: add your bank card's currency fee when prices are shown in another currency.
- Confusing: sits between car data and results though it has nothing to do with the car; label sounds like a sentence fragment; hint is long and repeats "approximate card cost".
- Replace: move to Advanced settings (or into the Settings area with currency). Label EN "Card currency fee (%)" / SV "Kortets valutapåslag (%)"; helper EN "Only matters when you buy abroad. Check your bank; 0 to 3 percent is common. Stored on this device only." / SV "Spelar bara roll när du handlar utomlands. Fråga din bank; 0 till 3 procent är vanligt. Sparas bara på den här enheten."

### 2.10 Car card (`#car-card`): "On electricity / On petrol / One full charge / Break-even / Estimate from your own inputs..."

- Purpose: quick cost per 100 km from the profile.
- Confusing: it is a second, older result block that duplicates the ev-card and disagrees with it (see "Conflicts"). "Break-even electricity price: 6.50 SEK per kWh (electric costs the same as petrol per km)" is jargon plus a number out of context. "Estimate from your own inputs: petrol 95 18.49 SEK per litre (country median), 21.3 kWh/100 km electric, 90% charging efficiency" is a wall of unexplained units. The embedded line "Petrol or electricity? To calculate this, add: ..." also repeats the ev-card heading.
- Replace/retire: fold into the new summary card (section 4). If kept, rename lines: EN "Electric driving: about 53 kr per 100 km" / SV "Köra på el: ca 53 kr per 100 km"; "Petrol driving: about 139 kr per 100 km" / "Köra på bensin: ca 139 kr per 100 km"; "One full battery charge costs about 38 kr" / "En full laddning kostar ca 38 kr".

### 2.11 Petrol or electricity? card (`#ev-card`)

#### Heading and verdict (`#ev-v`)
- Purpose: tell which fuel is cheaper per km.
- Confusing: heading is a question with the answer coming later in a different font weight; verdict "Electric is 54% cheaper per km" followed by "54% below petrol" says the same twice; the table below it shows "Per km 0.552 kr / 1.20 kr" and "Per 100 km 55.20 SEK / 120 SEK" and "100 km trip 93.79 SEK / 120 SEK": six numbers, two units for one currency (kr and SEK), and three different electric figures (0.552 km-rate -> 55.20, but trip 93.79) that look contradictory to a layperson. Percent difference is less useful than kronor.
- Replace verdict (EN): "Charging is cheaper. On a 100 km trip you save about 26 kr." / "Charging is more expensive right now." (SV): "Det är billigare att ladda. På en resa på 10 mil sparar du ca 26 kr." / "Just nu är det dyrare att ladda."
- Show one primary pair only: "Per 100 km: electricity 55 kr, petrol 120 kr". Hide "Per km" (drop) and keep the trip row only in the trip section. Use one currency label per screen (kr in Swedish UI, SEK in English UI, consistently).
- Break-even sentence EN: "Charging stays cheaper as long as you pay less than 5.44 kr per kWh. You pay 2.50 kr." SV: "Det är billigare att ladda så länge du betalar under 5,44 kr per kWh. Du betalar 2,50 kr."

#### Temperature block (`OUTSIDE TEMPERATURE`, Automatic/Manual, Open-Meteo paragraph, "Fetch the temperature", "No temperature yet, so no adjustment is applied.")
- Purpose: cold weather shortens electric range, so the cost per trip goes up.
- Confusing: a privacy paragraph (position rounded to 0.1 degree, IP address) sits in the middle of the result as the second element; "Automatic/Manual" is not explained; the empty-state line "No temperature yet" has no action beside it other than a small button; later "at – °C" appears with a bare dash when no temperature is known.
- Replace: heading EN "Weather: cold makes electric driving shorter" / SV "Väder: kyla gör att elen räcker kortare". Buttons EN "Use today's weather near me" / "Type a temperature" / SV "Använd dagens väder där jag är" / "Skriv in en temperatur". Move the privacy text into a "What data is sent?" help item. Empty state EN "No weather yet. The result below assumes mild weather (about 20 degrees)." SV "Inget väder än. Resultatet nedan antar milt väder (ca 20 grader)." Never print "–" as a degree value.

#### "To work out the mix, add: Public charger, a petrol 95 price for ..."
- Purpose: tells what is missing for the blended result.
- Confusing: lists "Public charger" as if it were a field name (it is the charging-mode label, a bug in the message: it is reused as a missing-input name); "petrol 95 price" assumes the user knows what 95 is and where to enter it (it comes from stations, not from a field).
- Replace: EN "To see this, enter what you pay for electricity (step 2). Petrol prices come from stations near you." / SV "För att se detta, ange vad du betalar för el (steg 2). Bensinpriser hämtar vi från stationer nära dig."

#### Trip table (TRIP / ELECTRIC / PETROL / PER 100 KM) and "A 100 km trip by outside temperature"
- Purpose: what 20, 50, 100 and 300 km trips cost, because the battery only covers the first part.
- Confusing: column "ELECTRIC" holds km driven on battery while "PETROL" holds litres and the last column kronor; column headers do not say units; the temperature table has row labels "Per 100 km" and "Electric" (km). Very dense.
- Replace: one sentence per row, or a header row with units: "Trip / On battery / Petrol used / Total cost". Example row: "100 km: 41 km on battery, 4.5 litres of petrol, about 94 kr". SV "100 km: 41 km på batteriet, 4,5 liter bensin, ca 94 kr". Put the temperature table in an expandable "How cold weather changes this".

#### Typical km per day
- Purpose: estimate monthly cost for daily driving.
- Confusing: the field label is a bare "TYPICAL KM PER DAY" with the sentence "With 40 km a day the battery covers about 64 % of your km at – °C. About 958 SEK per month now." No context for "958 SEK" (electricity plus petrol? per month of what?).
- Replace EN: "How far do you drive on a normal day? 40 km. At that distance the battery covers about 64 percent of your driving, and your fuel and electricity cost about 958 kr per month (30 days)." SV: "Hur långt kör du en vanlig dag? 40 km. Då räcker batteriet till ca 64 procent av din körning, och bränsle och el kostar ca 958 kr per månad (30 dagar)."

#### "How this is calculated" disclosure with Charging mode / price / loss / trip distance
- Purpose: inputs of the calculation.
- Confusing: the name hides that this holds the controls for "where do you charge" and "how long is your trip"; "CHARGING: Home / Public charger / Forecast" is jargon (Forecast of what?); the price label changes with the mode; "Charging loss factor (1.15 = 15% lost)" is a factor; "Trip distance (km)" has no default shown as a default.
- Replace: rename the section EN "Change the assumptions" / SV "Ändra antagandena" and split into three labelled groups. Mode labels EN "Charging at: Home / At a public charger / Home (forecast price for a month)" SV "Jag laddar: Hemma / Vid publik laddare / Hemma (prognospris för en månad)". Default marks EN "Default: 100 km" SV "Standard: 100 km" next to each field, with a "Reset" link.

#### 5 nearest petrol 95 stations
- Purpose: shows which petrol price the comparison uses.
- Confusing: "95" unexplained; "age unknown" on every row; mixed "kr" vs "SEK"; "Measured from the map centre" (the user did not know the map centre mattered); "3 nearer station(s) with unverified prices were set aside" is cryptic; this block comes after the controls, so users never connect it to the verdict.
- Replace: EN heading "Petrol price we compared with: average of the 5 closest stations (Eurosuper 95, normal petrol)" / SV "Bensinpris vi jämförde med: snitt av de 5 närmaste stationerna (bensin 95, vanlig bensin)". Footer EN "Measured from where the map is centred. Move the map or tap 'Use my location' to change. 3 closer stations were skipped because their prices could not be verified." SV "Mätt från mitten av kartan. Flytta kartan eller tryck 'Använd min position' för att ändra. 3 närmare stationer hoppades över eftersom deras priser inte kunde bekräftas." Replace "age unknown" by nothing (hide) or "age not shown".

### 2.12 Electricity price outlook (`#op-card`)

- Purpose: when and how cheaply to charge in the coming days, and what electricity may cost over the next year.
- Confusing:
  - Heading "Electricity price outlook" is fine to a finance reader but vague.
  - "NEXT DAYS (EXACT DAY-AHEAD PRICES)": "day-ahead" is trading jargon.
  - "Cheapest 5 h window for a full charge: Fri, Nov 6 19:00-00:00, 5.05 SEK per kWh, 77 SEK (full charge 15 kWh)". It shows a price (5.05) that is higher than the user's own 2.50 and the page does not say why (spot plus grid, tax, VAT, in the example tariff); "5 h" appears with no reason; "FULL CHARGE (15 KWH)" does not explain 15 kWh (13.8 kWh battery divided by 0.9 efficiency).
  - The 12-month list (Nov 26 ... 2.57 SEK) is 12 rows of unexplained "Nov 26" (November 2026 or the 26th of November?), the bar notation and range explanation are in a long paragraph.
  - "PRICE PER KWH AGAINST PETROL: SPOT / PER KWH / PER 100 KM" with spot rows 0.30, 0.60, 1.00, 1.50, 2.00: "spot" unexplained, and the table duplicates the break-even idea.
- Replace:
  - Heading EN "When is electricity cheap?" / SV "När är elen billig?"
  - Intro EN "Prices for the next days come from the power exchange. Charging in the cheapest hours saves money." SV "Priserna för de närmaste dagarna kommer från elbörsen. Att ladda när det är billigast sparar pengar."
  - Window line EN "Cheapest time to charge tonight: 19:00 to 00:00. A full charge (about 15 kWh) costs about 77 kr then." SV "Billigast att ladda ikväll: 19:00 till 00:00. En full laddning (ca 15 kWh) kostar då ca 77 kr."
  - Month labels EN "Nov 2026", SV "nov 2026" (full year, never "Nov 26").
  - 12-month heading EN "Roughly what electricity may cost over the next 12 months (estimate from past years, not a promise)" SV "Ungefär vad elen kan kosta de kommande 12 månaderna (uppskattning från tidigare år, inget löfte)".
  - The "price per kWh against petrol" table goes under a "What if the price changes?" help item with plain labels: "If the power exchange price is... / you pay... per kWh / driving 100 km costs...".
  - Unit consistency: the outlook is in SEK while the page shows kr; use the same word as the rest of the screen.

### 2.13 My home electricity (`#tf-card`, `<details>`)

- Purpose: work out what you really pay per kWh, including the grid fee, tax and VAT, from your own bill.
- Confusing: it is collapsed at the bottom, so most users never find it, yet it holds the key number. The intro says "an example tariff ... Replace every number" (an instruction that implies a lot of work); 14 fields use invoice jargon ("Retail variable costs", "Retail markup", "Grid transfer", "Energy tax", "Grid subscription", "Discount runs until", "Retail fee waived until"); the result "4.86 SEK/kWh One more kWh incl. VAT, at a spot price of 3.20 SEK ex VAT (average of the days published)" is not tied to anything above, and it differs from the user's 2.50. The formula paragraph and "All-in average at 500 kWh a month: 6.50 SEK" are two more prices.
- Replace:
  - Summary title EN "Work out my real electricity price (optional)" / SV "Räkna ut mitt verkliga elpris (valfritt)".
  - Intro EN "Not sure what you pay per kWh? Fill in the amounts from your electricity bill and we calculate it. The boxes hold an example; change what differs." SV "Osäker på vad du betalar per kWh? Fyll i beloppen från elfakturan så räknar vi ut det. Rutorna innehåller ett exempel; ändra det som skiljer sig."
  - Field labels EN: "Your price area (SE1 to SE4)" / "Extra cost per kWh from your electricity company" / "Electricity company markup per kWh" / "Your discount per kWh" / "Discount valid until" / "Electricity company monthly fee" / "Fee waived until" / "Grid fee per kWh" / "Energy tax per kWh" / "Grid subscription per month" / "VAT (%)" / "Electricity used per month (kWh)". SV: "Ditt elområde (SE1 till SE4)" / "Rörlig kostnad per kWh hos elhandlaren" / "Elhandlarens påslag per kWh" / "Din rabatt per kWh" / "Rabatten gäller till" / "Elhandlarens månadsavgift" / "Månadsavgiften efterskänkt till" / "Nätavgift per kWh (elöverföring)" / "Energiskatt per kWh" / "Elnätsabonnemang per månad" / "Moms (%)" / "Förbrukning per månad (kWh)". Add "ex VAT" as a short suffix "(excl. VAT)" / "(exkl. moms)" at group level, not on every label.
  - Result sentence EN "Your next kWh costs about 4.86 kr including VAT right now. Averaged over a month with all fixed fees you pay about 6.50 kr per kWh. [Use 4.86 kr as my price]" SV "Din nästa kWh kostar just nu ca 4,86 kr inklusive moms. Som månadssnitt med alla fasta avgifter betalar du ca 6,50 kr per kWh. [Använd 4,86 kr som mitt pris]"
  - The formula goes in a "Show the formula" help item.
- Note for the maintainer: the example result (4.86) currently depends on the shared-example spot average (3.20 ex VAT); check whether that average is plausible before shipping a button that copies it into the car profile (it is far above the owner's recorded actuals of 1.87 to 2.99 kr/kWh incl. VAT). Calculations are not to be changed in this pass; if the example is misleading, say "Example, from today's prices in SE4" next to it.

### 2.14 Lower settings: Tank size chips, Navigation app, Language, Appearance, Show prices in, Tip, Install, How we grade sources

- Purpose: app settings, unrelated to the car.
- Confusing: they sit under the car result with the same label style, so a driver may think "Tank size" chips belong to the result; "Show prices in: Local / EUR" is a currency switch with no explanation; the tip about the cheapest station card is off-topic.
- Replace: put under a collapsed "App settings" group (Tank size quick-pick folded into the car field, see 2.3). Currency switch EN "Show prices in: the country's own currency / euro" SV "Visa priser i: landets valuta / euro". Keep install and grading links.

## 3. Cross-cutting problems

### Conflicts (priority, even though calculations are not to change)

1. Two break-even prices: car card says 6.50 kr/kWh (country-median petrol 18.49 kr), ev card says 5.44 kr/kWh (average of 5 nearest stations 16.01 kr). Both are right for their own petrol price, but the user sees two answers to "when is electric cheaper?". Show one (the nearby-stations one, falling back to the median) and say which petrol price it uses.
2. Two electric costs per 100 km: 53.33 kr (car card, 21.3 kWh/100 km) vs 55.20 kr (ev card, with its own loss factor and temperature handling). Show one.
3. Two home-price inputs (profile and ev card), plus a third computed price in the tariff.
4. "kr" and "SEK" mixed on the same screen (stations show "15.98 kr", the table shows "55.20 SEK", per-km "0.552 kr").
5. Charging loss expressed as percent (profile) and as factor 1.15 (ev card).
6. Missing-input message names "Public charger" as a field.

### Jargon list (each needs a "What does this mean?" item, see section 4)

kWh, kWh/100 km, WLTP, usable battery, electric range, charging efficiency/loss, loss factor, break-even, spot price, day-ahead, tariff, grid transfer, energy tax, price area, ex VAT / incl. VAT, charge-sustaining, 95.

### Too many numbers at once

The ev card shows (Santa Fe, one scroll): 2 verdict lines, 6 table figures, 1 break-even, 12 trip-table cells, 8 temperature cells, 1 daily sentence with 3 numbers, 5 station rows. About 40 figures before the first input. The user needs three: electric per 100 km, petrol per 100 km, and the electricity price at which they break even.

### Unclear defaults

Defaults exist (efficiency 90, trip 100 km, 40 km/day, loss 1.15, charger price from a reference, petrol average) but are invisible: empty-looking fields with placeholder "90"/"0", values that appear after other inputs change (loss 1.15 pre-filled in one place, empty in another). Nothing says "we assume X, change here".

### Unclear next step

No numbered flow, no progress, no empty-state hint that says what one action will unlock. The only guidance is a grey note "To calculate this, add: ...".

### Order of sections

Today: car data, card fee, result, outlook, tariff, settings. The tariff (needed to know the price) is after the outlook (which uses it) and after the result (which needs it). The card fee interrupts the car data.

### Accessibility

- Several `<label>` elements have no `for` (charging chips, temperature chips); they are announced without a group name. Use `role="group"` with `aria-labelledby`.
- The privacy text and the formula are always visible walls of text; help must be tap-to-open and keyboard operable (`<details>`), never hover-only. Current `<details>` are already keyboard friendly; reuse them.
- The verdict is a live region but its text changes with every input; keep it, but make it one short sentence.
- Colour: verdict state is shown by `.e` class (green); also keep the word ("cheaper"/"dearer") so it works without colour.

## 4. Proposed information architecture (implementable in one pass)

Use existing tokens and components (`.car-box`, `.ev-verdict`, `.ev-note`, `.tchips`, `<details>`). No new calculations: every number below already exists in `evCompare`, `carKwh100`, `phevBlend`, `tfRender`, `opRender`.

### 4.1 Page skeleton

```
My car
[intro, 2 lines]
[Summary card: the answer in words]          <- new, always first
[Setup progress: 1 Your car  2 Your electricity price  3 Result  4 Outlook]
1  Your car
2  Your electricity price
3  Result: charging or filling up?
4  Outlook: when is electricity cheap?
Advanced settings (collapsed)
App settings (collapsed)
```

### 4.2 Summary card ("summary in words")

A single card at the top, `aria-live="polite"`, one plain paragraph and one action. States:

1. No car yet: EN "Start by picking your car. It takes about a minute, and then we can tell you whether charging or filling up is cheaper." SV "Börja med att välja din bil. Det tar ungefär en minut, sedan kan vi säga om det är billigare att ladda eller tanka." Button: EN "Pick my car" / SV "Välj min bil" (focuses `#veh-q`).
2. Car set, no electricity price: EN "Your car is set. One thing is missing: what you pay for electricity at home." SV "Din bil är angiven. En sak saknas: vad du betalar för el hemma." Button: EN "Enter electricity price" / SV "Ange elpris" (focuses `#car-elec`).
3. Complete, charging cheaper (Santa Fe, 2.50 kr/kWh, nearby petrol 16.01 kr/L): EN "Right now, driving your Santa Fe on electricity costs about 55 kr per 100 km. On petrol it costs about 120 kr. Charging is cheaper as long as you pay less than 5.44 kr per kWh. You pay 2.50 kr." SV "Just nu kostar det ca 55 kr per 100 km att köra din Santa Fe på el. På bensin kostar det ca 120 kr. Det är billigare att ladda så länge du betalar under 5,44 kr per kWh. Du betalar 2,50 kr."
4. Complete, petrol cheaper: EN "Right now, petrol is cheaper: about X kr per 100 km against Y kr on electricity. Electricity would win below Z kr per kWh. You pay P kr." SV "Just nu är bensin billigare: ca X kr per 100 km mot Y kr på el. El vinner under Z kr per kWh. Du betalar P kr."
5. Not a plug-in hybrid: EN "Electricity can only be compared for plug-in hybrids. Your petrol car uses about X kr per 100 km." SV "El kan bara jämföras för laddhybrider. Din bensinbil kostar ca X kr per 100 km."
6. Cold: append one sentence when a temperature is set: EN "At -5 degrees the battery covers fewer km, so electric driving costs about X kr per 100 km." SV "Vid -5 grader räcker batteriet kortare, så det kostar ca X kr per 100 km på el."

Under the paragraph a small trust line: EN "Based on petrol prices at the 5 closest stations and the electricity price you entered." SV "Baserat på bensinpriser vid de 5 närmaste stationerna och elpriset du angav."

Every figure comes from the already-computed `r.elec100`, `r.petrol100`, `r.breakEven`, `car.elec`.

### 4.3 Numbered setup flow

Four numbered section headings with a step chip (`<ol>` of `<h3>` is fine). A status per step: done (check text "Done: Santa Fe"), needs input ("Needs one number"), or optional. A one-line progress hint under the progress strip: EN "Step 2 of 4: enter your electricity price" / SV "Steg 2 av 4: ange ditt elpris".

**1 Your car** (EN "1  Your car" / SV "1  Din bil")
- Intro, max two lines: EN "Pick your model and we fill in the details. Or type your own." / SV "Välj din modell så fyller vi i detaljerna. Eller skriv in själv."
- Content: model picker, "What runs your car", tank, petrol use, battery, range (the last two only for plug-in hybrids).
- Defaults made visible: after a pick, each filled field shows a small "from your Santa Fe model" tag and a "change" link (focus the input); after manual edits the tag reads "your value".
- Empty-state: "Nothing chosen yet. Pick a model above." / "Inget valt än. Välj en modell ovan."

**2 Your electricity price** (EN "2  Your electricity price" / SV "2  Ditt elpris")
- Intro: EN "This is the number that decides the result. Find it on your bill." SV "Det här är siffran som avgör resultatet. Du hittar den på elfakturan."
- Content: one price field with helper and example (EN "Example: 2.50 kr per kWh incl. VAT"), buttons "Use my tariff estimate" and "I charge at a public charger" (price field switches to the public price; default shown with note "Typical public price in Sweden: 5.05 kr, as of date"), then the optional collapsed tariff calculator ("Work out my real electricity price"). Spell out "Where do I charge: home / public / home with forecast price".
- Empty-state: "Add your price to see the result." / "Lägg till ditt pris för att se resultatet."

**3 Result: charging or filling up?** (EN "3  Result" / SV "3  Resultat")
- Intro: EN "What 100 km costs on electricity and on petrol, and what a trip costs." SV "Vad 100 km kostar på el och på bensin, och vad en resa kostar."
- Content order: verdict sentence; two numbers side by side ("Electricity 55 kr, Petrol 120 kr per 100 km"); "What does 100 km, 50 km, 20 km, 300 km cost?" trip rows as sentences; "Your normal day" sentence (km per day); temperature control; petrol stations used. Everything else behind "Change the assumptions".
- Empty-state: "Waiting for step 1 and 2." / "Väntar på steg 1 och 2."

**4 Outlook: when is electricity cheap?** (EN "4  Outlook" / SV "4  Utblick")
- Intro: EN "Plan your charging: cheapest hours in the next days and a rough 12-month view." SV "Planera laddningen: billigaste timmarna de närmaste dagarna och en grov bild av 12 månader."
- Content: "Cheapest time to charge" sentence first, then the days table, then 12 months (full month names with year), the "price vs petrol" table under a help item.
- Empty-state: "Shown when price data for your area is available." / "Visas när prisdata för ditt område finns."

### 4.4 Help: "What does this mean?" per term

An expandable `<details class="help">` directly under the field or sentence, with summary text "What does this mean?" / "Vad betyder det?". Plain text, max 2 sentences, one example with the owner's numbers. Same component everywhere, tap target at least 44 px, focus ring from existing tokens, no hover-only content.

| Term | EN | SV |
|---|---|---|
| kWh | "A kWh (kilowatt-hour) is the unit electricity is sold in, like a litre of petrol. Your Santa Fe battery holds about 14 kWh, roughly a 2.5 kr/kWh x 14 = 35 kr fill-up." | "En kWh (kilowattimme) är enheten som el säljs i, som en liter bensin. Batteriet i din Santa Fe rymmer ca 14 kWh, alltså ungefär 2,5 kr/kWh x 14 = 35 kr för en full laddning." |
| kWh per 100 km | "How much electricity the car uses to drive 100 km. Santa Fe: about 21 kWh per 100 km, so 100 km costs 21 x 2.50 = about 53 kr." | "Hur mycket el bilen drar på 100 km. Santa Fe: ca 21 kWh per 100 km, alltså kostar 100 km 21 x 2,50 = ca 53 kr." |
| Charging loss | "Some electricity is lost as heat while charging. For 10 kWh from the wall about 9 kWh reach the battery. We assume 10 percent lost." | "En del el blir värme vid laddning. Av 10 kWh från uttaget når ca 9 kWh batteriet. Vi räknar med 10 procent förlust." |
| Break-even price | "The electricity price where charging and filling up cost the same per km. Below it, charging is cheaper. Santa Fe at today's petrol price: 5.44 kr per kWh." | "Elpriset där det kostar lika mycket att ladda som att tanka per km. Under det är det billigare att ladda. Santa Fe med dagens bensinpris: 5,44 kr per kWh." |
| Battery range | "How many km the car drives on a full battery before the petrol engine helps. The official figure for the Santa Fe is 54 km. In daily driving, and in cold weather, you get less (about 41 km in our example)." | "Hur många km bilen kör på fullt batteri innan bensinmotorn hjälper till. Officiellt värde för Santa Fe: 54 km. I vardagen, och i kyla, blir det mindre (ca 41 km i vårt exempel)." |
| WLTP | "The official test used to measure range and consumption. Real life is usually a bit worse." | "Det officiella testet för räckvidd och förbrukning. I verkligheten blir det oftast lite sämre." |
| Spot price | "The hourly price on the power exchange, before grid fees, tax and VAT." | "Timpriset på elbörsen, före nätavgift, skatt och moms." |
| Price area | "Sweden has four electricity price areas, SE1 (north) to SE4 (south). Your bill shows yours." | "Sverige har fyra elområden, SE1 (norr) till SE4 (söder). Din faktura visar ditt." |
| Petrol 95 | "Normal petrol (95 octane), the most common grade." | "Vanlig bensin (95 oktan), den vanligaste sorten." |

### 4.5 Advanced settings (collapsed `<details>`, title EN "Advanced settings" / SV "Avancerade inställningar")

Contents: charging loss (percent, "Default: 10 % lost"), trip length ("Default: 100 km"), km per day ("Default: 40 km"), card currency fee, charging at public charger price override, temperature source details with the Open-Meteo privacy text. Each row shows "Default: X" and a "Reset" link. The summary line shows the active non-default values, e.g. "All standard".

### 4.6 Defaults with a "change" affordance

Pattern `<value> <small>(standard) <button class="link">Change</button>`: e.g. "Charging loss: 10 % (standard) Change". When the user changes it: "(your value) Reset". Applies to charging loss, trip length, km per day, public price, temperature. Defaults come from existing constants; no new numbers.

### 4.7 Units spelled out

Replace L/100 km with "litres per 100 km", kWh/100 km with "kWh per 100 km (energy per 100 km)", always `kr`/`SEK` as one chosen token per UI language, "per kWh" (not "/kWh"), "including VAT" (not "incl."), month labels with year, no bare dashes for missing values ("not known yet").

### 4.8 Examples with the owner's numbers

Use the Santa Fe in every help item and empty state: tank 47 litres, 7.5 litres per 100 km with battery empty, battery about 14 kWh, range 54 km (about 41 km in practice), 21 kWh per 100 km on electricity, home price 2.50 kr per kWh, petrol about 16 kr per litre nearby. Example result: electricity 55 kr and petrol 120 kr per 100 km; break-even 5.44 kr per kWh. Mark them "Example" so they are not mistaken for the user's data; do not store the registration number or any invoice data in the repo.

## 5. Implementation notes (one pass)

- New DOM: `#mc-summary` (summary card), `#mc-steps` (progress), wrap existing blocks into four `<section class="mc-step">` with `<h3>` + intro `<p class="ev-note">` + status; one `<details id="mc-adv">`, one `<details id="mc-app">`. Reuse `.car-box`, `.ev-verdict`, `.ev-note`, `<details>` styles; step chip is a small token-coloured `<span>`.
- Moves, not rewrites: `#car-card` content folds into `#mc-summary` (remove duplicate break-even and 53.33 kr line); `#ev-price` for mode "Home" becomes a link to `#car-elec`; `#car-cardpct` and `#car-eff`/`#ev-loss`/`#ev-km` to `#mc-adv`; tank chips merged next to `#car-tank`; lower settings into `#mc-app`.
- `evRender` already computes everything the summary needs (`r.elec100`, `r.petrol100`, `r.breakEven`, `elec`, `st.avg`, `miss`); expose them in one object `_mcAns` and render the summary from it (display only). The summary state logic is a pure function of (car, elec, r) and gets a small node test next to `tools/test_ev_compare.js`.
- Fix the message bug: when mode is `home` use `carElec`, for `pub` use `evPricePub` text, never the mode label `evPub`.
- i18n: EN and SV written in full for every string in this document; DE/FR/ES fall back (existing mechanism via `Object.assign(I18N.en/sv, ...)`). Add `data-i18n` attributes; keep existing keys for removed text until tests pass, then delete unused keys.
- Accessibility: `<details>` for every help item, `aria-live="polite"` on the summary only, groups for chips with `role="group"` + `aria-labelledby`, min 44 px touch targets, text plus colour for the verdict, no hover-only help.
- Constraints: no calculation changes; tests to keep green: `node tools/test_*.js` (currency, ev_compare, phev_blend, route_model, tariff) and `cd src; python -m unittest discover -s tests -q`; `web/sw.js` cache version bump when `index.html` changes; no commit or push.

## 6. Suggested acceptance check (after implementation)

At 375 px with an empty profile: a first-time reader can say within 10 seconds what the tab is for and what to press first. With the Santa Fe profile: the top card reads as one plain paragraph with 55 kr, 120 kr and 5.44 kr, the first screen shows no table, every grey term has a "What does this mean?" item, nothing is shown in two different values, and the page is at most about 4 screens long with Advanced and App settings collapsed.
