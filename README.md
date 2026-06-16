# Nordic Fuel Prices

Real-time fuel price aggregator for Sweden, Norway, Denmark, and Finland.
Data is pulled every 30 minutes via GitHub Actions and served as static JSON on GitHub Pages.

## Live map

`https://<your-github-username>.github.io/nordic-fuel-prices/`

## Coverage

| Country | Source | Type | Update | Stations | API Key |
|---------|--------|------|--------|----------|---------|
| 🇸🇪 Sweden | [henrikhjelm.se](https://henrikhjelm.se) | Community (curated) | 30 min | ~1,500 | No |
| 🇳🇴 Norway | [drivstoffpriser.no](https://drivstoffpriser.no) | Government-mandated | 6h | ~1,000 | No |
| 🇩🇰 Denmark | [fuelprices.dk](https://fuelprices.dk) | Commercial (8 chains) | 60 min | ~1,500 | Yes (free) |
| 🇫🇮 Finland | [polttoaine.net](https://polttoaine.net) | Community | 12h | ~1,000 | No |

## Fuel types

All fuel types are tracked — not just petrol and diesel:

| Category | Types | Unit |
|----------|-------|------|
| Fossil | E10, E5 (98), Diesel, LPG, HVO100 | L |
| Electric | AC 22kW, DC 50kW | kWh |

Every price record includes `currency` (SEK, NOK, DKK, EUR) and `unit`.

## Data format

**`data/all.json`** — combined output, all countries  
**`data/se.json`**, `no.json`, `dk.json`, `fi.json` — per-country

```json
{
  "meta": { "country": "SE", "currency": "SEK", "source": "henrikhjelm.se", "fetched_at": "..." },
  "stations": [
    {
      "id": "se_Shell_Stockholm__59.33_18.07",
      "country": "SE",
      "name": "Shell Stockholm",
      "lat": 59.33,
      "lon": 18.07,
      "prices": [
        { "fuel_type": "E10", "price": 19.50, "currency": "SEK", "unit": "L", "updated_at": "..." },
        { "fuel_type": "DIESEL", "price": 20.10, "currency": "SEK", "unit": "L", "updated_at": "..." }
      ]
    }
  ]
}
```

## Setup

### 1. Fork / clone this repo

### 2. Enable GitHub Pages
- Go to **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: **gh-pages** / root

### 3. Add secrets (optional)
Only needed for Denmark:
- **Settings → Secrets and variables → Actions → New repository secret**
- Name: `FUELPRICES_DK_API_KEY`
- Value: your key from [fuelprices.dk](https://fuelprices.dk)

### 4. Run manually first
- **Actions → Scrape Nordic Fuel Prices → Run workflow**

The first run creates the `gh-pages` branch and deploys the site.

### 5. Automatic updates
GitHub Actions runs every 30 minutes automatically after that.

## Local development

```bash
pip install -r requirements.txt
python src/main.py
# outputs to data/
```

Open `web/index.html` locally (needs data files in same dir, or run a local server).

## Roadmap

- [ ] Add Core EU countries (DE, FR, ES, IT, AT, PT, SI, UK, HR, RO)
- [ ] Price change alerts (track delta between pulls)
- [ ] Historical price charts per station
- [ ] Currency conversion to EUR for cross-country comparison
- [ ] EV charging network coverage (OCPI / Open Charge Map)
