# PHEV temperature and season model (2026-11-06)

Purpose: a codable model of how outside temperature changes a plug-in hybrid's electric range, electricity use and petrol use, for a mid-size SUV PHEV (reference: Hyundai Santa Fe PHEV, WLTP electric range 54 km, 192 Wh/km, 7.5 l/100 km charge-sustaining). Also: blended-trip cost formula, utility factor, and how to get monthly temperatures cheaply.

Honesty note. Almost no public source measures the Santa Fe PHEV itself at fixed temperatures. The curve below is an engineering synthesis anchored on BEV and PHEV measurements, plus labelled assumptions. Treat every number as a default that the owner's own logged data should override. Marked: **[A]** = my assumption, **[S]** = taken from a source.

## 1. Sources and what was actually opened

"Opened" = the page was fetched and read this session. "Snippet" = only seen in a web-search summary, not opened; weaker evidence.

| Source | URL | Status | Used for |
|---|---|---|---|
| Open-Meteo terms | https://open-meteo.com/en/terms | opened | non-commercial rule, limits, CC-BY 4.0 |
| Open-Meteo archive docs | https://open-meteo.com/en/docs/historical-weather-api | opened | archive endpoint, ERA5 from 1940, 5-day delay |
| Open-Meteo forecast docs | https://open-meteo.com/en/docs | opened | `temperature_2m_mean`, `forecast_days` 0-16 |
| Cars.com RAV4 Prime vs Tucson PHEV at 37 F | https://www.cars.com/articles/toyota-rav4-prime-and-hyundai-tucson-plug-in-hybrid-testing-ev-range-efficiency-in-colder-temperatures-462054 | opened | Hyundai-family PHEV behaviour in cold (Tucson PHEV engine started often with charge left) |
| AAA 2019 dynamometer study (5 BEVs) | https://www.eenewseurope.com/en/cold-temperatures-shrink-electric-car-range-aaa-study-finds/ | snippet | -7 C: -12% no HVAC, -41% with heat; 35 C: -4% / -17% with A/C |
| Geotab, 4,200 EVs / 5.2 M trips | https://www.geotab.com/uk/blog/ev-range/ and https://www.automotive-fleet.com/359666/how-extreme-cold-and-heat-affect-ev-range | snippet (geotab.com/blog/ev-range-temperature returned 404) | peak 115% of rated at 21.5 C; 54% at -15 C |
| Recurrent winter range | https://www.recurrentauto.com/research/winter-ev-range-loss | snippet | fleet winter average about 70% of normal range |
| NAF El Prix winter test | https://www.naf.no/elbil/elbil-nytt/ev-range-and-charge-test | snippet | 2026 test: avg -38% vs WLTP at down to -32 C; earlier test avg -18.5% (mild winter) |
| INL/AVTA Chevrolet Volt cold test | https://avt.inl.gov/sites/default/files/pdf/phev/2012VoltColdWeatherTestReport.pdf | snippet | engine starts itself at or below 27 F (-3 C); EV range 42.0 mi at 70 F to 19.7 mi at -15 F (-53%) |
| JRC (EU) PHEV/EREV at 23 C vs -7 C | https://publications.jrc.ec.europa.eu/repository/handle/JRC107955 | snippet | heating hurts electric range and emissions more than cold alone |
| ICCT / Fraunhofer ISI PHEV fact sheet | https://www.isi.fraunhofer.de/content/dam/isi/dokumente/cce/2022/PHEV_ISI-ICCT_Fact_Sheet_ENG-Update-2022.pdf | snippet | real-world electric share about half of WLTP UF |

Not opened or not found: Hyundai owner's manual (engine-start thresholds for heat), ADAC Ecotest winter, SAE papers, Fleetcarma, Transport & Environment briefing (https://www.transportenvironment.org/uploads/files/2025_09_TE_briefing_PHEV_gap_growing.pdf, appeared in results only). No claim below depends on them. Recommend the owner reads the Hyundai manual section on heating/"Hybrid mode" before trusting the engine-heat share.

## 2. Physics in one paragraph

Cold hurts a PHEV three ways: (1) cabin heating (PTC electric heater or engine waste heat), the largest term; (2) battery and drivetrain losses (cold cell resistance, thicker lubricants, higher air density); (3) in heat, A/C compressor load. Unlike a BEV, a PHEV can heat the cabin with the engine: the electric km shrink less, but petrol use rises, and the engine may start while the battery still has charge (Tucson PHEV observed at 37 F, Cars.com opened). BEV data (AAA, Geotab, Recurrent, NAF) therefore gives the upper bound on electric loss; PHEV engine heating moves part of that loss from kWh into litres.

## 3. Parametric model (code as lookup + linear interpolation)

Reference conditions T_ref = 20 C: f = 1, WLTP values. WLTP is tested around 23 C **[S, WLTP definition, from memory, not opened]**. Real-world highway is worse than WLTP at any temperature; this model only handles temperature, not speed.

Anchors used: AAA at -7 C: range x0.88 without HVAC, x0.59 with heat **[S, snippet]**; 35 C: x0.96 no A/C, x0.83 with A/C **[S, snippet]**; Geotab -15 C: x0.54 **[S, snippet]**; Volt -15 F (-26 C): x0.47 incl. engine **[S, snippet]**; Recurrent fleet winter about x0.70 **[S, snippet]**. Mapping to the table is my interpolation **[A]**.

### 3.1 All-electric bound (heater fully electric, engine never helps)

f_elec(T) = fraction of WLTP electric range; m_e = 1 / f_elec = Wh/km multiplier.

| T (C) | -20 | -15 | -10 | -5 | 0 | 5 | 10 | 15 | 20 | 25 | 30 | 35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f_elec | 0.45 | 0.50 | 0.58 | 0.66 | 0.74 | 0.84 | 0.92 | 0.98 | 1.00 | 0.97 | 0.90 | 0.82 |
| m_e | 2.22 | 2.00 | 1.72 | 1.52 | 1.35 | 1.19 | 1.09 | 1.02 | 1.00 | 1.03 | 1.11 | 1.22 |

### 3.2 Engine-heat share s(T) [A]

Share of the excess (cold) energy that the engine supplies as heat instead of the battery. Default values; Hyundai software thresholds unverified. Volt started its engine at or below -3 C **[S, snippet]**; Tucson PHEV started often at 3 C (about 37 F) **[S, opened]**. Above 10 C, s = 0; for hot weather A/C is always electric (s = 0).

| T (C) | -20 | -15 | -10 | -5 | 0 | 5 | 10 and up |
|---|---|---|---|---|---|---|---|
| s | 0.65 | 0.60 | 0.55 | 0.45 | 0.35 | 0.20 | 0 |

### 3.3 Resulting PHEV factors (use these defaults)

Base electric use E0 = 192 Wh/km = 19.2 kWh/100 km.

- m_el(T) = 1 + (m_e(T) - 1) * (1 - s(T))   (electric consumption multiplier while battery is being used)
- extra petrol during the electric phase: g(T) = (m_e(T) - 1) * E0[kWh/100km] * s(T) * k_heat, with k_heat = 0.2 l per kWh of heat supplied by the engine **[A]** (engine at light load, about 1 l/h giving about 5 kW usable heat)
- electric-phase distance factor f(T) = 1 / m_el(T);  R(T) = R_wltp * f(T)

| T (C) | -20 | -15 | -10 | -5 | 0 | 5 | 10 | 15 | 20 | 25 | 30 | 35 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| m_el | 1.43 | 1.40 | 1.32 | 1.29 | 1.23 | 1.15 | 1.09 | 1.02 | 1.00 | 1.03 | 1.11 | 1.22 |
| f (range factor) | 0.70 | 0.71 | 0.76 | 0.78 | 0.81 | 0.87 | 0.92 | 0.98 | 1.00 | 0.97 | 0.90 | 0.82 |
| R for 54 km (km) | 38 | 38 | 41 | 42 | 44 | 47 | 50 | 53 | 54 | 52 | 49 | 44 |
| Wh/km | 275 | 269 | 254 | 247 | 236 | 221 | 209 | 196 | 192 | 198 | 213 | 234 |
| g extra petrol, electric phase (l/100 km) | 3.0 | 2.3 | 1.5 | 0.9 | 0.5 | 0.15 | 0 | 0 | 0 | 0 | 0 | 0 |

Note: f is nearly flat between -20 and -15 because the engine takes over more heating; this is intended, not a bug. The honest bounds for "electric km before the battery is empty" are therefore f (engine helps) down to f_elec (engine never helps), e.g. at -10 C between 0.58 and 0.76 of WLTP.

### 3.4 Charge-sustaining petrol multiplier m_p(T) [A]

Once the battery is depleted the engine runs anyway; cabin heat is then nearly free, but cold engine, friction, idling-for-defrost and A/C add consumption. No PHEV-specific measurement found. Values are a conservative engineering guess of a +10-20% winter penalty typical of small-car ICE winter consumption literature (not opened).

| T (C) | -20 | -10 | 0 | 10 | 20 | 30 | 35 |
|---|---|---|---|---|---|---|---|
| m_p | 1.20 | 1.13 | 1.08 | 1.03 | 1.00 | 1.04 | 1.07 |

### 3.5 Uncertainty (state it in the UI)

- f(T): about +/- 0.05 between 10 and 30 C; +/- 0.10 between -5 and 5 C; +/- 0.15 below -10 C (BEV spread is wide at any temperature, Geotab; individual PHEV software unknown).
- m_p: +/- 0.05 mid-range, +/- 0.10 at extremes.
- g: factor 2 either way.
- Drive style, speed, preconditioning while plugged in (reduces the cold penalty), seat/steering heating, and a battery-heating strategy are not modelled. Pre-heating from the grid shifts heating to cheap kWh and is the single biggest user lever.

Suggested band in UI: show low/high using f_elec (pessimistic electric range) and f + 0.05 (optimistic).

## 4. Blended trip formula

Inputs: d (km), T (C), R_wltp, E0 (kWh/km), C0 (l/100 km, charge-sustaining), prices p_kwh (SEK per kWh incl. VAT), p_l (SEK per l), charge efficiency eta (about 0.88 if E0 is battery-side; 1.0 if E0 is already measured at the wall, **owner to confirm which the 192 Wh/km is**).

```
R   = R_wltp * f(T)                      // electric-phase distance, km
e   = min(d, R)                          // electric km
p   = d - e                              // charge-sustaining km
kWh = e * E0 * m_el(T) / eta
l   = e * g(T)/100 + p * C0 * m_p(T)/100
cost_per_100km = 100 * (kWh * p_kwh + l * p_l) / d
```

Starting battery is assumed full. If the battery starts partly charged with fraction soc_use of usable energy, replace R by R * soc_use. Consistency check: R * E0 * m_el = R_wltp * E0 = usable battery energy, about 10.4 kWh for 54 km x 192 Wh/km (gross 13.8 kWh per owner profile).

Worked example (illustrative prices 2.2 SEK/kWh, 17 SEK/l, eta = 1):

| Case | e km | p km | kWh | petrol l | SEK per 100 km |
|---|---|---|---|---|---|
| 100 km trip, 20 C | 54 | 46 | 10.4 | 3.45 | about 82 |
| 100 km trip, -10 C | 41 | 59 | 10.4 | 5.6 | about 118 |
| 30 km trip, 20 C | 30 | 0 | 5.8 | 0 | about 43 |
| 30 km trip, -10 C | 30 | 0 | 7.6 | 0.45 | about 80 |

(Check -10 C 100 km: R = 54*0.756 = 40.8; kWh = 40.8*0.254 = 10.4; l = 0.408*1.5 + 59.2*7.5*1.13/100 = 0.61 + 5.02 = 5.6.) Cold rows are 25-45% dearer per km than mild rows, the sign and size the model should convey.

## 5. Utility factor (UF) concepts

- WLTP UF is the distance share assumed to be driven electrically, a function of the cycle-based electric range; weighted consumption C = UF * C_CD + (1 - UF) * C_CS (secondhand summary; regulation text not opened: Regulation (EU) 2017/1151 Annex XXI as amended). One source says WLTP assumes more than 80% electric share for a 60 km PHEV (snippet). I did not verify the polynomial coefficients; do not hard-code them.
- Real use: ICCT/Fraunhofer find real-world electric share about half of the WLTP UF on average (snippet). The EU is lowering the UF assumption (figures for 2025-26 and 2027-28 quoted in snippets; not verified).
- For the app, a self-derived share is cleaner and exact under an assumption: if daily driving distance is exponentially distributed with mean D (km/day) and the car is charged fully every night, expected electric share = 1 - exp(-R / D). Example: R = 54, D = 40 gives 0.74; R = 40, D = 40 gives 0.63. D is a user input **[A: default 40 km/day, owner should set]**. This gives a monthly "typical" cost per 100 km: cost_month = share * electric_cost_per_km + (1 - share) * petrol_cost_per_km, with the temperature factors for that month.
- Mixture caveat: exponential distance is a modelling convenience. Commuters have bimodal days. If trip-by-trip data is not available, offer the "single trip of length d" mode (section 4) as the primary view and the UF share as the "typical month" view.

## 6. Months-ahead and monthly temperature sources (Open-Meteo)

Facts opened this session:
- Forecast: `https://api.open-meteo.com/v1/forecast`, `daily=temperature_2m_mean`, `forecast_days` up to 16 (default 7).
- Archive: `https://archive-api.open-meteo.com/v1/archive`, params `latitude`, `longitude`, `start_date`, `end_date`, `daily`, `timezone` (must be set for daily; `auto` allowed). ERA5 from 1940 (0.25 degree, about 25 km), ERA5-Land from 1950 (0.1 degree, about 11 km), data lags about 5 days.
- Terms: free API is **non-commercial only**: no ads, no subscriptions, no commercial products; donations allowed. Limits: under 10,000 calls/day, 5,000/hour, 600/min per IP (300,000/month in the pricing table). Data is CC-BY 4.0.

Not verified (flag, test in browser): CORS headers on both hosts (docs pages say nothing; Open-Meteo is widely called from browsers, so likely `Access-Control-Allow-Origin: *`; confirm with one fetch from the scratch copy before shipping); the `models=era5_land` selector on the archive API (not on opened page text); exact attribution wording (page only says CC-BY 4.0, so credit "Weather data by Open-Meteo.com" with link to https://open-meteo.com/ and a CC-BY 4.0 mention; ERA5 origin credit is prudent but unconfirmed).

Licence risk: if eurofuelprices.com shows ads, affiliate links or any paid tier, the free API is not permitted and a paid key is needed. The owner must decide before turning this on.

### Cheap "normal monthly temperature" recipe

1. Round position to 0.1 degree (privacy and cache key).
2. One archive request: last 5 full calendar years, `daily=temperature_2m_mean&timezone=auto`. About 1,826 numbers, roughly 20-30 KB. Three years works but the standard error on a monthly mean is then about 1-1.5 C in a Swedish winter; five years about 1 C **[A, from typical interannual SD of 2 C]**.
3. Cache in localStorage keyed by lat,lon (0.1) for 30+ days; fetch at most once per month per user. No server is needed; keeps the privacy-first design.
4. Do not apply the curve to the monthly mean (curve is nonlinear). Apply f(T), m_el(T), g(T), m_p(T) to each daily value, then average per calendar month. Add a low/high band from the coldest and warmest of the 5 years (or mean +/- 1 SD of yearly monthly means).
5. Days 0-16: use the forecast API (`past_days` optional) for exact near-term values; beyond 16 days use the normal. Label clearly: "estimate from 5-year average".
6. Daily mean is not driving-time temperature (daytime is a little warmer in winter, cooler at night). Offset is small; ignore, but mention in the footnote **[A]**.
7. Manual override input (degrees C) replaces all of the above.
8. CSP: add `https://api.open-meteo.com` and `https://archive-api.open-meteo.com` to `connect-src`. Privacy text: rounded coordinates (0.1 degree, about 11 km) are sent to Open-Meteo, nothing else.

## 7. Implementation checklist for the node test

- Lookup arrays for T = [-20..35 step 5]: f, m_el, g, m_p; linear interpolation; clamp outside range.
- Tests: f(20) = 1; R * E0 * m_el = R_wltp * E0 at each knot (within rounding); monotone non-increasing f below 20 and above 25; d <= R gives zero petrol-from-charge-sustaining; d = 0 guarded; cost at 20 C 100 km equals the worked example within 1 SEK.
- Parameters from the car profile (`efp_car`: range, kwh100, cons, batt) feed R_wltp, E0, C0, usable kWh; the table is fixed.
- Show the uncertainty band and an "estimate" label whenever temperature is not a measurement.
