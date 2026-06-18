import asyncio
import aiohttp
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from scrapers import ALL_SCRAPERS


OUTPUT_DIR = Path(__file__).parent.parent / "data"


async def run_all():
    OUTPUT_DIR.mkdir(exist_ok=True)

    meta_summary = []

    async with aiohttp.ClientSession() as session:
        tasks = [scraper(session).fetch_stations() for scraper in ALL_SCRAPERS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for scraper_cls, result in zip(ALL_SCRAPERS, results):
        country = scraper_cls.COUNTRY
        if isinstance(result, Exception):
            print(f"[{country}] FAILED: {result}")
            continue

        stations = result
        print(f"[{country}] {len(stations)} stations")

        country_data = {
            "meta": {
                "country": country,
                "currency": scraper_cls.CURRENCY,
                "source": scraper_cls.SOURCE,
                "confidence": scraper_cls.CONFIDENCE,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "station_count": len(stations),
            },
            "stations": stations,
        }

        # Per-country file — frontend lazy-loads these by country code
        with open(OUTPUT_DIR / f"{country.lower()}.json", "w", encoding="utf-8") as f:
            json.dump(country_data, f, ensure_ascii=False, separators=(",", ":"))

        meta_summary.append(country_data["meta"])

    total = sum(m["station_count"] for m in meta_summary)

    # meta.json: lightweight index the frontend loads first to discover available countries
    meta = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_stations": total,
        "countries": meta_summary,
    }
    with open(OUTPUT_DIR / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))

    # all.json kept for backward compatibility
    all_stations = []
    for m in meta_summary:
        cc = m["country"]
        try:
            with open(OUTPUT_DIR / f"{cc.lower()}.json", "r", encoding="utf-8") as f:
                all_stations.extend(json.load(f).get("stations", []))
        except OSError:
            pass

    combined = {
        "meta": meta,
        "stations": all_stations,
    }
    with open(OUTPUT_DIR / "all.json", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nDone — {total} stations total → {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(run_all())
