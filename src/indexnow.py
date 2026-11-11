"""Tell Bing/Yandex (IndexNow, free) which pages are new or fresh: the Europe index/border pages and the country hubs.

Runs from the scrape job, but only in the 07:00-07:14 UTC window (once a day); ``--force`` overrides. Never fails the deploy.
The key file is web/<KEY>.txt (public by design - IndexNow checks that it matches).
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://eurofuelprices.com"
KEY = "9de760974b2bdc3ec308ea9adc970583"
DATA = Path(__file__).resolve().parent.parent / "data"
HUBS = ["se", "at", "de", "ch", "fr", "es", "pt", "dk", "nl", "be", "be-fr", "pl", "it"]


def urls():
    out = [f"{SITE}/{cc}/" for cc in HUBS if (DATA / cc / "index.html").exists()]
    sm = DATA / "sitemap-europe.xml"
    if sm.exists():
        out += re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
    return out[:10000]


def main() -> int:
    now = datetime.now(timezone.utc)
    if "--force" not in sys.argv and not (now.hour == 7 and now.minute < 15):
        print("indexnow: outside the daily window - skipped")
        return 0
    ul = urls()
    if not ul:
        print("indexnow: nothing to send")
        return 0
    body = json.dumps({"host": "eurofuelprices.com", "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt", "urlList": ul}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"indexnow: {len(ul)} urls, HTTP {r.status}")
    except Exception as e:  # 202 = accepted; anything else is logged, never fatal
        print(f"indexnow: {len(ul)} urls, {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
