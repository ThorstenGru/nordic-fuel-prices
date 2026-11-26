# Close call: minimum gain and the "too close to call" band (My car)

From the Where-to-charge research (`RESEARCH_2026-11-18.md`, decision 2026-11-18). Added to My car on 2026-11-26.

- **Gain per kWh** = break-even price (what 1 kWh is worth in petrol, heat petrol included) minus the price you pay.
- **Minimum gain** 0.30 SEK/kWh: below this, plugging in is not worth the effort.
- **Band** 0.45 SEK/kWh around the minimum: when the gain is within 0.30 ± 0.45 the answer is "Close call" (prices, consumption and temperature are estimates). Above 0.75 charging is clearly worth it, below -0.15 petrol clearly wins.
- Other currencies: the same figures converted with the ECB rate (`rateOf`). Without a rate for the currency there is no close-call logic and the old verdict (electric / petrol / same) is shown.
- Pure function `mcWorth(gain, minGain, band)` in the MC-PURE block, tested in `tools/test_mycar_summary.js`.
- Applies to plug-in hybrids and electric cars. The earlier verdict "same" (difference below 0.5 %) is kept.
- The figures are the owner's rule of thumb, not measurements. Tune `MC_MIN_SEK` / `MC_BAND_SEK` in `web/index.html` after real use.
