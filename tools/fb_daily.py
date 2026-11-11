"""Builds today's Facebook post for the Euro Fuel Prices Page: text, link and a share-card image.

Deterministic on purpose: the daily automation only *posts* what this prints, so the wording and numbers can be reviewed
and tested. Prints one JSON object: {"skip": "<reason>"} or {"text", "image", "format", "key"}.

    python tools/fb_daily.py [--date YYYY-MM-DD] [--out DIR]

Rules baked in: one post a day (the log in docs/facebook/post_log.csv is checked), data older than 36 h -> skip,
no engagement bait ("like/share"), figures are always "median station price", the data grade is mentioned when it is not A/B,
a pair/country is not repeated within 14 days. Weekday plan: Mon ranking, Tue border pair, Wed price quiz, Thu feature tip,
Fri weekend border run, Sat reader question, Sun feature tip.
"""
import csv
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from europe_index import BORDER_PAIRS, NAMES, pair_slug  # noqa: E402

SITE = "https://eurofuelprices.com"
LOG = ROOT / "docs" / "facebook" / "post_log.csv"
CF_IP = "104.21.74.127"   # fallback only: this machine's DNS has failed for the domain before
MIN_N = 300               # a country needs this many priced stations to be quoted in a post
FILL_L = 50

FEATURES = [
    ("cheapest-in-view", "Tip: find the cheapest pump on your screen", "Pan or zoom the map and the “Cheapest in view” card shows the lowest price among the stations you can see. Which fuel do you fill most: petrol 95 or diesel?", "/"),
    ("tank-size", "Tip: see what a full tank really costs", "Set your tank size once and every station shows the cost of a fill-up, not just the price per litre. What size is your tank?", "/"),
    ("favourites", "Tip: save your usual stations", "Tap the star on a station to keep it in your Saved list, so your regular pumps are one tap away. How many stations do you usually choose between?", "/"),
    ("border-run", "Tip: is the border run worth it?", "The “Border run” calculator compares filling up here with driving to another country and includes the extra kilometres, so you see the real saving. Which border do you cross?", "/"),
    ("road-trip", "Tip: plan fuel for a road trip", "“Road trip: where to fill up?” takes your distance and the countries on the way and shows where the fuel is cheapest. Where is your next trip?", "/"),
    ("route-planner", "Tip: cheapest pumps along your route", "Open the Route tab, enter a start and a destination, and the app lists priced pumps along the way with the detour for each. Where would you plan a route first?", "/"),
    ("my-car", "Tip: set up your car", "Enter your car’s consumption and tank once and the app works out costs for your car (plug-in hybrids are supported). What do you drive?", "/"),
    ("share-station", "Tip: share a price with one tap", "Use Share on a station to send a picture of its price and a link, handy for a friend or the family group chat. Who would you send it to?", "/"),
    ("navigate", "Tip: one tap to navigate", "Go opens your favourite navigation app: Google Maps, Waze, Apple Maps or HERE. Which one do you use?", "/"),
    ("home-screen", "Tip: add it to your home screen", "Add EuroFuelPrices to your home screen and it opens like an app, with the last prices saved if the signal drops. Have you tried it yet?", "/"),
    ("source-age", "Tip: every price shows its source and age", "We label where a price comes from and how old it is, and dim stale ones, so you can tell a fresh price from an old guess. Would you like to see anything else on the label?", "/about.html"),
    ("widget", "For website owners: a free fuel price widget", "One line of HTML puts today’s median petrol or diesel price for a country on your site, free and without sign-up. Which country would you show?", "/embed.html"),
    ("open-data", "Open data: country medians for download", "We publish the country medians as JSON and CSV, free to reuse with a link. What would you build with them?", "/europe/"),
    ("languages", "Tip: dark mode and your language", "The app follows your device’s light or dark theme and speaks Swedish, German, French, Spanish and English. Which language should we add next?", "/"),
]


def fetch(url: str, dest: Path = None, timeout: int = 30):
    """Download with curl: direct first, then through the known Cloudflare address if DNS fails."""
    for extra in ([], ["--resolve", f"eurofuelprices.com:443:{CF_IP}"]):
        cmd = ["curl", "-sS", "-f", "-m", str(timeout)] + extra + (["-o", str(dest)] if dest else []) + [url]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0:
            return dest if dest else r.stdout.decode("utf-8")
    return None


def read_log():
    if not LOG.exists():
        return []
    with LOG.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pick(options, used, today, days=14):
    recent = {r["key"] for r in used if r.get("key") and (today - date.fromisoformat(r["date"])).days < days}
    for o in options:
        if o not in recent:
            return o
    return options[0]


def medians(doc):
    out = {}
    for r in doc["rows"]:
        if r["stations"] >= MIN_N and r["source_grade"] in ("A", "B", "C"):   # crowd-sourced (D) figures are never quoted in a post
            out[(r["country"], r["fuel"])] = (r["median_eur_per_litre"], r["stations"], r["source_grade"])
    return out


def grade_note(grades):
    g = {x for x in grades if x not in ("A", "B")}
    return "; unofficial source, so indicative" if g else ""


def pair_data(m, a, b):
    rows = []
    for fuel, label in (("p95", "Petrol 95"), ("diesel", "Diesel")):
        if (a, fuel) in m and (b, fuel) in m:
            rows.append((label, m[(a, fuel)], m[(b, fuel)]))
    return rows


def pair_post(m, a, b, quiz=False):
    rows = pair_data(m, a, b)
    if not rows:
        return None
    label, va, vb = max(rows, key=lambda r: abs(r[2][0] - r[1][0]))
    d = vb[0] - va[0]
    cheaper = NAMES[a] if d > 0 else NAMES[b]
    dearer = NAMES[b] if d > 0 else NAMES[a]
    url = f"{SITE}/europe/{pair_slug(a, b)}/"
    note = grade_note([va[2], vb[2]])
    if quiz:
        text = (f"Quick quiz: {label.lower()} in {NAMES[a]} or in {NAMES[b]}, where is it cheaper today? "
                f"Answer in the comments, then check the numbers: {url}")
    else:
        text = (f"{label} is about €{abs(d):.2f} per litre cheaper in {cheaper} than in {dearer} today (median station price{note}), "
                f"about €{abs(d) * FILL_L:.2f} on a {FILL_L} L fill-up. Would you drive across the border for that? {url}")
    return text, f"{SITE}/og/{pair_slug(a, b)}.png", url


def build(today: date, out: Path):
    used = read_log()
    if any(r["date"] == today.isoformat() for r in used):
        return {"skip": "already posted today"}
    raw = fetch(SITE + "/open-data/national-averages.json")
    if not raw:
        return {"skip": "site unreachable"}
    doc = json.loads(raw)
    upd = datetime.fromisoformat(doc["updated"].replace("Z", "+00:00").replace(" ", "T")) if "T" in doc["updated"] or " " in doc["updated"] else None
    if upd is not None and upd.tzinfo is None:
        upd = upd.replace(tzinfo=timezone.utc)
    if upd is None or datetime.now(timezone.utc) - upd > timedelta(hours=36):
        return {"skip": "data older than 36 h"}
    m = medians(doc)
    wd = today.weekday()   # Mon=0
    pairs = [p for p in BORDER_PAIRS if pair_data(m, *p)]
    result = None
    if wd == 0:   # ranking
        p95 = sorted((v[0], c) for (c, f), v in m.items() if f == "p95")
        if len(p95) >= 8:
            lo, hi = p95[0], p95[-1]
            note = grade_note([m[(lo[1], "p95")][2], m[(hi[1], "p95")][2]])
            text = (f"Petrol 95 across Europe today: cheapest {NAMES[lo[1]]} at €{lo[0]:.2f}/L, most expensive {NAMES[hi[1]]} at €{hi[0]:.2f}/L "
                    f"(median station prices{note}). Does your country’s price surprise you? Full ranking: {SITE}/europe/")
            result = (text, f"{SITE}/og/europe.png", "ranking", "europe")
    elif wd in (1, 2, 4):   # border pair / quiz / weekend border run
        ranked = sorted(pairs, key=lambda p: -max(abs(r[2][0] - r[1][0]) for r in pair_data(m, *p)))
        keys = [pair_slug(*p) for p in ranked]
        key = pick(keys, used, today)
        a, b = next(p for p in ranked if pair_slug(*p) == key)
        built = pair_post(m, a, b, quiz=(wd == 2))
        if built:
            result = (built[0], built[1], {1: "border-pair", 2: "quiz", 4: "weekend-border"}[wd], key)
    elif wd in (3, 6):   # feature tips (how to use)
        key = pick([f[0] for f in FEATURES], used, today, days=len(FEATURES) - 1)
        f = next(x for x in FEATURES if x[0] == key)
        result = (f"{f[1]}. {f[2]} {SITE}{f[3]}", f"{SITE}/og-image.png", "feature", key)
    else:         # Saturday: reader question
        result = (f"Spotted a price on the map that looks wrong or a station that is missing? Tell us the town in the comments and we will check it. "
                  f"The map is free, with no account: {SITE}", f"{SITE}/og-image.png", "reader-question", "reader-question")
    if not result:
        return {"skip": "not enough data for today's format"}
    text, img_url, fmt, key = result
    out.mkdir(parents=True, exist_ok=True)
    img = out / f"fb_{today.isoformat()}.png"
    if not fetch(img_url, img):
        return {"skip": f"image not available: {img_url}"}
    return {"text": text, "image": str(img), "format": fmt, "key": key, "date": today.isoformat()}


def main():
    today = date.today()
    out = ROOT / "docs" / "facebook" / "daily"
    a = sys.argv
    if "--date" in a:
        today = date.fromisoformat(a[a.index("--date") + 1])
    if "--out" in a:
        out = Path(a[a.index("--out") + 1])
    print(json.dumps(build(today, out), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
