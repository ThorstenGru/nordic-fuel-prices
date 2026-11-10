"""Weekly growth check for eurofuelprices.com that needs no account or API key.

Counts the URLs we ask Google/Bing to index, samples pages for HTTP 200 + canonical + title, and appends one
row to docs/growth_kpis.csv so the trend is visible. Impressions/clicks/backlinks live in Google Search Console
and Bing Webmaster Tools (owner login) - add them to the CSV by hand in the last columns.

    python tools/growth_kpis.py            # prints and appends
    python tools/growth_kpis.py --no-write # prints only
"""
import csv
import random
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

SITE = "https://eurofuelprices.com"
CSV = Path(__file__).resolve().parent.parent / "docs" / "growth_kpis.csv"
SAMPLE = 25


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "efp-growth-check/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.read().decode("utf-8", "replace")


def sitemap_urls(url: str):
    try:
        _, body = get(url)
    except Exception:
        return []
    locs = re.findall(r"<loc>([^<]+)</loc>", body)
    if "<sitemapindex" in body:
        return [u for sm in locs for u in sitemap_urls(sm)]
    return locs


def main() -> int:
    urls = sorted(set(sitemap_urls(SITE + "/sitemap.xml") + sitemap_urls(SITE + "/sitemap-seo.xml")))
    by_section = {}
    for u in urls:
        seg = u.replace(SITE, "").strip("/").split("/")[0] or "home"
        by_section[seg] = by_section.get(seg, 0) + 1
    random.seed(date.today().toordinal())
    ok = canon = title = 0
    sample = random.sample(urls, min(SAMPLE, len(urls)))
    for u in sample:
        try:
            st, html = get(u)
        except Exception:
            continue
        ok += st == 200
        canon += bool(re.search(r'<link rel="canonical" href="%s"' % re.escape(u), html))
        title += bool(re.search(r"<title>[^<]{10,}</title>", html))
    row = {"date": date.today().isoformat(), "sitemap_urls": len(urls), "sample": len(sample), "http200": ok,
           "canonical_ok": canon, "title_ok": title, "sections": ";".join(f"{k}={v}" for k, v in sorted(by_section.items())),
           "gsc_impressions_7d": "", "gsc_clicks_7d": "", "indexed_pages": "", "backlinks_domains": ""}
    print(row)
    if "--no-write" not in sys.argv:
        new = not CSV.exists()
        with CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
