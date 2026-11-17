"""Static share card (1200x630 PNG) for every town page: town name, country, a one-line tagline in the page language, the site name.
No price on it, so a card never goes stale and is drawn only once; it is the og:image of /<cc>/<slug>/.

Cards live in <data_dir>/og/town/<cc>/<slug>.png. The scrape workflow restores that folder from the Actions cache, so only cards that
do not exist yet are drawn, at most MAX_NEW per run (the first runs fill the gap, later runs draw a few). Pillow is optional: without
it, or when the budget is used up, the page keeps the generic og-image.png.
"""
import os
from pathlib import Path
from typing import Optional

MAX_NEW = int(os.environ.get("OG_TOWN_MAX", "400"))
TAGLINE = {
    "en": "Fuel prices today", "sv": "Bränslepriser idag", "de": "Spritpreise heute", "da": "Brændstofpriser i dag",
    "nb": "Drivstoffpriser i dag", "fi": "Polttoaineiden hinnat tänään", "fr": "Prix des carburants aujourd'hui",
    "es": "Precios de combustible hoy", "nl": "Brandstofprijzen vandaag", "it": "Prezzi dei carburanti oggi",
    "pl": "Ceny paliw dzisiaj", "pt": "Preços dos combustíveis hoje",
}
_made = 0


def card_path(root: Path, cc: str, slug: str) -> Path:
    return Path(root) / "og" / "town" / cc / f"{slug}.png"


def draw(path: Path, town: str, country: str, lang: str) -> bool:
    """Write the card; False (nothing written) when Pillow is missing."""
    try:
        from PIL import Image, ImageDraw
        from europe_index import pil_font
    except ImportError:
        return False
    img = Image.new("RGB", (1200, 630), "#0E1A29")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, 630], fill="#0B8F6E")
    size = 96
    while size > 48 and d.textlength(town, font=pil_font(size)) > 1040:      # one line if it fits, else smaller, else two lines
        size -= 8
    lines = [town]
    if d.textlength(town, font=pil_font(size)) > 1040:
        words, cur, lines = town.split(), "", []
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=pil_font(size)) <= 1040 or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines = (lines + [cur])[:2]
    y = 150
    for ln in lines:
        while d.textlength(ln, font=pil_font(size)) > 1040 and len(ln) > 4:   # a single very long word: cut, never overflow the picture
            ln = ln[:-2].rstrip() + "…"
        d.text((80, y), ln, font=pil_font(size), fill="#F8FAFC")
        y += size + 14
    d.text((80, y + 20), TAGLINE.get(lang, TAGLINE["en"]), font=pil_font(52), fill="#5EEAD4")
    d.text((80, y + 96), country, font=pil_font(38, False), fill="#9FB0C0")
    d.text((80, 548), "eurofuelprices.com", font=pil_font(38), fill="#E9EEF3")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return True


def ensure(root: Path, site: str, cc: str, slug: str, town: str, country: str, lang: str) -> Optional[str]:
    """-> public URL of the card, or None (page keeps the generic image). Draws the card when it is missing and the per-run budget allows."""
    global _made
    p = card_path(root, cc, slug)
    if not p.exists():
        if _made >= MAX_NEW or not draw(p, town, country, lang):
            return None
        _made += 1
    return f"{site}/og/town/{cc}/{slug}.png"
