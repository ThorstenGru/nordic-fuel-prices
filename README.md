# EuroFuelPrices

Live fuel price aggregator covering **all of Europe + EEA** — 38 countries, 80,000+ stations. Data is scraped every 30 minutes via GitHub Actions and served as static JSON on GitHub Pages.

**Live map:** `https://thorstengru.github.io/nordic-fuel-prices/`  
**Data dashboard:** `https://thorstengru.github.io/nordic-fuel-prices/admin.html`

---

## Coverage — 38 Countries

### Tier 1 — Official mandatory government APIs (highest accuracy)

| Country | Source | Stations | Update |
|---------|--------|----------|--------|
| 🇩🇪 Germany | [Tankerkönig / MTS-K](https://creativecommons.tankerkoenig.de) | ~14,000 | ~15 min |
| 🇫🇷 France | [data.economie.gouv.fr](https://data.economie.gouv.fr) | ~12,000 | Near real-time |
| 🇪🇸 Spain | [MINETUR](https://sedeaplicaciones.minetur.gob.es) | ~12,000 | Near real-time |
| 🇮🇹 Italy | [MIMIT](https://www.mise.gov.it) | ~20,000 | Daily (8 AM) |
| 🇵🇹 Portugal | [DGEG](https://precoscombustiveis.dgeg.gov.pt) | ~4,000 | Regular |
| 🇦🇹 Austria | [e-Control](https://api.e-control.at) | ~2,500 | Real-time |
| 🇭🇷 Croatia | [MZOE](https://mzoe-gor.hr) | ~900 | Daily |
| 🇸🇮 Slovenia | [goriva.si](https://goriva.si) | ~550 | Real-time |

### Tier 2 — Chain & community APIs

| Country | Source | Stations | Notes |
|---------|--------|----------|-------|
| 🇸🇪 Sweden | OSM + [bensinpriser.nu](https://henrikhjelm.se) | ~1,800 | Major chains omit prices (Konkurrensverket) |
| 🇩🇰 Denmark | Shell geoapp + Q8 API + ANWB | ~1,500 | Three sources merged |
| 🇫🇮 Finland | [polttoaine.net](https://polttoaine.net) + ANWB | ~1,000 | Community-reported |
| 🇮🇸 Iceland | [gasvaktin](https://github.com/gasvaktin/gasvaktin) | ~75 | Community |
| 🇷🇴 Romania | [peco-online.ro](https://peco-online.ro) | ~1,200 | ANPC-backed |

### Tier 3 — ANWB POI API (22 countries)

NL · BE · LU · CH · LI · PL · CZ · HU · SK · EE · LV · LT · GR · BG · RS · ME · MK · AL · BA · XK · AD · MD · MT · CY

### Locations only (no prices — regulatory)

| Country | Reason |
|---------|--------|
| 🇳🇴 Norway | Anti-cartel law bans Circle K, YX, Uno-X, ST1, Shell from publishing list prices until 2030 |

---

## Data Format

**`data/meta.json`** — lightweight index (fetched first by the frontend)  
**`data/{cc}.json`** — per-country stations (lazy-loaded by viewport)

```json
{
  "meta": {
    "country": "SE",
    "currency": "SEK",
    "source": "OSM + bensinpriser.nu",
    "confidence": 0.85,
    "fetched_at": "2026-10-01T12:30:00Z",
    "station_count": 1823
  },
  "stations": [
    {
      "id": "se_Shell_Stockholm_59.33_18.07",
      "country": "SE",
      "name": "Shell Stockholm",
      "brand": "Shell",
      "city": "Stockholm",
      "address": "Sveavägen 1",
      "lat": 59.33,
      "lon": 18.07,
      "confidence": 0.85,
      "source": "bensinpriser.nu",
      "prices": [
        {
          "fuel_type": "E10",
          "price": 19.50,
          "currency": "SEK",
          "unit": "L",
          "updated_at": "2026-10-01T12:30:00Z"
        }
      ]
    }
  ]
}
```

---

## Mobile-First PWA

The frontend is a Progressive Web App designed for on-the-road use:
- **Near Me** — GPS-based nearest stations with cheapest-price summary
- **Offline support** — service worker caches data for offline browsing
- **Install prompt** — add to home screen on iOS/Android
- **Bottom tab bar** — Map, Near Me, Search, List, Filter
- **Safe area handling** — notch/Dynamic Island support

---

## Setup

### 1. Fork / clone this repo

### 2. Enable GitHub Pages
- Go to **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: **gh-pages** / root

### 3. Add secrets (required for Germany)
- **Settings → Secrets → Actions → New repository secret**
- Name: `TANKERKOENIG_API_KEY`
- Value: free key from [creativecommons.tankerkoenig.de](https://creativecommons.tankerkoenig.de)
  (Without this, Germany falls back to ANWB with lower confidence)

### 4. Run the scraper manually first
- **Actions → EuroFuelPrices — Scrape → Run workflow**

### 5. Automatic updates
Runs every 30 minutes. Frontend deploys instantly on any `web/` push.

---

## Local Development

```bash
pip install -r requirements.txt
python src/main.py
# writes to data/
```

Serve `data/` + `web/` together (e.g. `python -m http.server 8080 --directory data`), then open `http://localhost:8080`.

---

## Adding Analytics

The admin dashboard (`admin.html`) includes setup guides for:
- **GoatCounter** — free, open-source, GDPR-compliant
- **Plausible** — €9/mo, EU-hosted, best dashboard
- **Cloudflare Web Analytics** — free, Core Web Vitals

---

## Roadmap

- [ ] Greece: migrate from ANWB → official fuelprices.gr mandatory API
- [ ] Belgium: add carbu.com parallel source
- [ ] Price trend deltas (↑/↓ vs previous scrape)
- [ ] Per-station price history chart
- [ ] Cross-country EUR price comparison layer
- [ ] Push notifications for price drops near saved locations
