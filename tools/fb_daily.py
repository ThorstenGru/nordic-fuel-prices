"""Builds today's Facebook post for the Euro Fuel Prices Page: text, link and a share-card image.

Deterministic on purpose: the daily automation only *posts* what this prints, so the wording and numbers can be reviewed
and tested. Prints one JSON object: {"skip": "<reason>"} or {"text", "image", "format", "key"}.

    python tools/fb_daily.py [--date YYYY-MM-DD] [--out DIR]

Rules baked in: one post a day (the log in docs/facebook/post_log.csv is checked), data older than 36 h -> skip,
no engagement bait ("like/share"), figures are always "median station price", the data grade is mentioned when it is not A/B,
a pair/country is not repeated within 14 days. Weekday plan: Mon ranking, Tue border pair, Wed price quiz, Thu feature tip,
Fri local spotlight (cheapest within 10 km of a town), Sat "comment your town", Sun feature tip.
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
MIN_N = 300               # a country needs this many priced stations to be quoted: the same as src/europe_index.MIN_N, so the post text and the picture (og/europe.png) always name the same countries
FILL_L = 50

# Interaction first (2026-11-15): Facebook reaches posts with external links much less (Meta tests 2 link posts a month for Pages), so a post carries its link
# only for the formats below and only LINKS_PER_MONTH times a month (logged as format "<format>-link"). Every other post ends with the invitation to
# comment a town, which the reply bot answers, and points to the Page's website button instead of printing a link.
LINK_FORMATS = ("ranking", "spotlight", "border-pair")
LINKS_PER_MONTH = 2
# Variety (2026-11-16): the town invitation and the closing question rotate by day so two posts in a row never end the same way. Examples use countries the reply bot answers.
TOWN_ASKS = [
    "Comment your town and country (e.g. “Hamburg, Germany”) and we reply with the cheapest petrol and diesel within 10 km.",
    "Where do you usually fill up? Comment “Town, Country” (e.g. “Malmö, Sweden”) and we reply with the cheapest pumps within 10 km.",
    "Curious about the cheapest pump near you? Comment your town and country, e.g. “Lyon, France”, and we reply with the cheapest petrol and diesel nearby.",
    "Drop your town and country below (e.g. “Aarhus, Denmark”) and we reply with the cheapest pumps within 10 km.",
    "Commuting or travelling? Comment a town and country (e.g. “Munich, Germany”) and we reply with the cheapest petrol and diesel there.",
    "Planning a trip? Comment where you are heading (e.g. “Zurich, Switzerland”) and we reply with the cheapest pumps within 10 km.",
    "Want a local price check? Comment “Town, Country” (e.g. “Rotterdam, Netherlands”) and we reply with the cheapest petrol and diesel nearby.",
]
RANKING_ASKS = ["Does your country’s price surprise you?", "Is your country at the cheap end or the dear end?", "Which of these would you fill up in?",
                "What do you pay per litre at home?", "Where do you think your country ranks?"]
BORDER_ASKS = ["Would you drive across the border for that?", "Is that saving worth the detour for you?", "Have you ever filled up across the border?",
               "How far would you drive to save that much?"]


def rotate(pool, today, salt=0):
    return pool[(today.toordinal() + salt) % len(pool)]


CTA_TOWN = TOWN_ASKS[0]   # kept for callers that need one fixed text
CTA_NOLINK = "The live map is behind the website button on our Page."


def link_budget_left(used, today):
    month = today.isoformat()[:7]
    return sum(1 for r in used if str(r.get("date", ""))[:7] == month and str(r.get("format", "")).endswith("-link")) < LINKS_PER_MONTH


def compose(body, url, label, fmt, used, today, allow_link=True):
    """-> (text, logged format). The link goes in only for LINK_FORMATS while the month's allowance lasts; the town invitation goes on every post except the ask itself."""
    link = allow_link and fmt in LINK_FORMATS and link_budget_left(used, today)
    parts = [body]
    if fmt != "local-ask":
        parts.append(rotate(TOWN_ASKS, today))
    parts.append(f"{label}{url}" if link else CTA_NOLINK)
    return "\n\n".join(parts), (fmt + "-link" if link else fmt)

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
        if r["stations"] >= MIN_N:   # grade D (community estimates) is quoted too, but always marked as an estimate
            out[(r["country"], r["fuel"])] = (r["median_eur_per_litre"], r["stations"], r["source_grade"])
    return out


def grade_note(grades):
    g = set(grades)
    if "D" in g:
        return "; estimates from community reports"
    return "; unofficial source, so indicative" if g - {"A", "B"} else ""


def pair_data(m, a, b):
    rows = []
    for fuel, label in (("p95", "Petrol 95"), ("diesel", "Diesel")):
        if (a, fuel) in m and (b, fuel) in m:
            rows.append((label, m[(a, fuel)], m[(b, fuel)]))
    return rows


def pair_post(m, a, b, quiz=False, today=None):
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
        text = f"Quick quiz: {label.lower()} in {NAMES[a]} or in {NAMES[b]}, where is it cheaper today? Answer in the comments."
    else:
        text = (f"{label} is about €{abs(d):.2f} per litre cheaper in {cheaper} than in {dearer} today (median station price{note}), "
                f"about €{abs(d) * FILL_L:.2f} on a {FILL_L} L fill-up. {rotate(BORDER_ASKS, today or date.today())}")
    return text, f"{SITE}/og/{pair_slug(a, b)}.png", url


# Cadence (2026-11-16): 7 pieces a week instead of 11 - posts Mon, Wed, Fri, Sat; Reels Tue and Thu; the weekly video on Sunday.
POST_DAYS = (0, 2, 4, 5)
FORCE_WD = {"ranking": 0, "border-pair": 1, "quiz": 2, "feature": 3, "spotlight": 4, "local-ask": 5}   # a forced format uses that weekday's recipe


def build(today: date, out: Path, audience=None, download=True, force=None, nolink=False):
    """force = one of FORCE_WD (a one-off post of that format, also on a day that already has a post); nolink = never print the link."""
    used = read_log()
    if not force and any(r["date"] == today.isoformat() and r.get("format") != "skip" for r in used):
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
    wd = FORCE_WD[force] if force else today.weekday()   # Mon=0
    if not force and wd not in POST_DAYS:
        return {"skip": "no post planned today (Reel or weekly-video day)"}
    if not force and wd == 2 and today.isocalendar()[1] % 2:   # Wednesdays alternate quiz / feature tip
        wd = 3
    pairs = [p for p in BORDER_PAIRS if pair_data(m, *p)]
    result = None
    if wd == 0:   # ranking
        p95 = sorted((v[0], c) for (c, f), v in m.items() if f == "p95")
        if len(p95) >= 8:
            lo, hi = p95[0], p95[-1]
            note = grade_note([m[(lo[1], "p95")][2], m[(hi[1], "p95")][2]])
            text = (f"Petrol 95 across Europe today: cheapest {NAMES[lo[1]]} at €{lo[0]:.2f}/L, most expensive {NAMES[hi[1]]} at €{hi[0]:.2f}/L "
                    f"(median station prices{note}). {rotate(RANKING_ASKS, today)}")
            result = (text, f"{SITE}/og/europe.png", "ranking", "europe", f"{SITE}/europe/", "Full ranking: ")
    elif wd == 4:   # local spotlight: cheapest within 10 km of a town (aggregate: rotating town or where followers are)
        import fb_local
        built = fb_local.spotlight(fetch, used, today, audience)
        if built:
            body, _, url = built[0].rpartition(" More: ")          # fb_local.local_text ends with "More: <town page>"
            result = (body or built[0], f"{SITE}/og-image.png", "spotlight", built[1], url if body else SITE, "More: ")
    elif wd == 5:   # opt-in: people comment their town, the bot replies with the cheapest nearby
        result = ("Where do you fill up? Comment your town (and country, e.g. “Hamburg, Germany”) and we will reply with the cheapest petrol and diesel "
                  "stations within 10 km, as listed on our map. Covered: DE, AT, CH, SE, NO, DK, FI, FR, ES, PT, NL, BE, PL, IT.", f"{SITE}/og-image.png", "local-ask", "local-ask", SITE, "")
    elif wd in (1, 2):   # border pair / quiz
        ranked = sorted(pairs, key=lambda p: -max(abs(r[2][0] - r[1][0]) for r in pair_data(m, *p)))
        keys = [pair_slug(*p) for p in ranked]
        key = pick(keys, used, today)
        a, b = next(p for p in ranked if pair_slug(*p) == key)
        built = pair_post(m, a, b, quiz=(wd == 2), today=today)
        if built:
            result = (built[0], built[1], {1: "border-pair", 2: "quiz"}[wd], key, built[2], "Numbers: ")
    elif wd in (3, 6):   # feature tips (how to use)
        key = pick([f[0] for f in FEATURES], used, today, days=len(FEATURES) - 1)
        f = next(x for x in FEATURES if x[0] == key)
        result = (f"{f[1]}. {f[2]}", f"{SITE}/og-image.png", "feature", key, SITE + f[3], "")
    if not result:
        return {"skip": "not enough data for today's format"}
    body, img_url, fmt, key, url, label = result
    text, logged = compose(body, url, label, fmt, used, today, allow_link=not nolink)
    res = {"text": text, "image_url": img_url, "format": logged, "key": key, "date": today.isoformat()}
    if download:                      # the browser route needs a local file; the Graph API route posts the public URL
        out.mkdir(parents=True, exist_ok=True)
        img = out / f"fb_{today.isoformat()}.png"
        if not fetch(img_url, img):
            return {"skip": f"image not available: {img_url}"}
        res["image"] = str(img)
    return res


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
