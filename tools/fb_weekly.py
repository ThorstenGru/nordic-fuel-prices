"""Weekly video for the Euro Fuel Prices Facebook Page: ~24 s, 1080x1920 (9:16), captions only, English, no sound.

Built from the same public data as the daily post (open-data/national-averages.json): cheapest and dearest petrol 95,
cheapest diesel, the biggest border-run saving, then a link card. Frames are drawn with Pillow, joined with ffmpeg
(preinstalled on GitHub's ubuntu runners). Posted by the Page itself with the Page token, once per ISO week
(docs/facebook/post_log.csv, format "weekly-video").

    python tools/fb_weekly.py [--dry-run] [--out DIR]     # dry run = render the mp4, post nothing
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import fb_daily  # noqa: E402
import fb_graph  # noqa: E402
from europe_index import BORDER_PAIRS, NAMES, pil_font as font  # noqa: E402

W, H = 1080, 1920
SECONDS = 4
SAFE_X = 90                        # side margin: no text gets closer to the edge than this
BAND_TOP, BAND_BOT = 340, 1560     # the feed shows the middle 4:5 of the 9:16 video (y 285-1635) and Reels covers the bottom ~350 px with its own buttons
MIN_PX, MIN_NOTE_PX = 40, 36       # 40 px of 1080 is about 14 px on a 375 px wide phone
BG, FG, DIM, GREEN, BAR = (14, 26, 41), (255, 255, 255), (150, 165, 185), (74, 222, 128), (38, 70, 104)


def scenes(doc: dict) -> list:
    """List of scenes from the national medians; [] when there is too little data.
    Data scenes: {title, rows[(name, value, bar 0..1)], note}. Border scene: {title, border{label, cheap, dear, d}, note}."""
    m = fb_daily.medians(doc)
    out = []

    def ranked(fuel, label, highest):
        r = sorted(((v[0], c, v[2]) for (c, f), v in m.items() if f == fuel), reverse=highest)[:5]
        if len(r) < 5:
            return
        lo, hi = min(x[0] for x in r), max(x[0] for x in r)
        rows = [(NAMES[c], f"€{p:.2f}", 0.45 + 0.55 * ((p - lo) / (hi - lo) if hi > lo else 1)) for p, c, _ in r]
        grades = [g for _, _, g in r]
        out.append(dict(title=label, rows=rows, note="Median station price per litre" + ("; some figures are estimates or from unofficial sources" if set(grades) - {"A", "B"} else "")))

    ranked("p95", "Petrol 95: cheapest", False)
    ranked("p95", "Petrol 95: most expensive", True)
    ranked("diesel", "Diesel: cheapest", False)
    best = None
    for a, b in BORDER_PAIRS:
        for fuel, label in (("p95", "Petrol 95"), ("diesel", "Diesel")):
            if (a, fuel) in m and (b, fuel) in m:
                d = abs(m[(a, fuel)][0] - m[(b, fuel)][0])
                if best is None or d > best[0]:
                    cheap, dear = (a, b) if m[(a, fuel)][0] < m[(b, fuel)][0] else (b, a)
                    best = (d, label, cheap, dear, m[(a, fuel)][2], m[(b, fuel)][2])
    if best:
        d, label, cheap, dear, ga, gb = best
        out.append(dict(title="Border run of the week", border=dict(label=label, cheap=NAMES[cheap], dear=NAMES[dear], d=d),
                        note="Median station prices" + ("; some figures are estimates or from unofficial sources" if {ga, gb} - {"A", "B"} else "")))
    return out if len(out) == 4 else []


class Pen:
    """Draws text and remembers where each piece landed, so a test can prove nothing leaves the safe area."""

    def __init__(self, im):
        from PIL import ImageDraw
        self.d, self.log = ImageDraw.Draw(im), []

    def width(self, t, f):
        return self.d.textlength(t, font=f)

    def text(self, xy, t, f, fill, anchor="la"):
        self.d.text(xy, t, font=f, fill=fill, anchor=anchor)
        x0, y0, x1, y1 = self.d.textbbox(xy, t, font=f, anchor=anchor)
        self.log.append((t, x0, y0, x1, y1, f.size))


def _wrap(pen, text, f, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if pen.width(t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def fit(pen, text, max_w, size, min_size=MIN_PX, bold=True, max_lines=1):
    """Largest font (<= size) in which `text` fits `max_w` in at most `max_lines` lines; wraps on spaces, shrinks 4 px at a time.
    Measured with the font that really draws, so it holds on any machine. Last resort: cut with an ellipsis, never overflow."""
    for sz in range(size, min_size - 1, -4):
        f = font(sz, bold)
        lines = _wrap(pen, text, f, max_w)
        if len(lines) <= max_lines and all(pen.width(l, f) <= max_w for l in lines):
            return f, lines
    f = font(min_size, bold)
    out = []
    for l in _wrap(pen, text, f, max_w)[:max_lines]:
        while pen.width(l, f) > max_w and len(l) > 1:
            l = l[:-2].rstrip() + "…"
        out.append(l)
    return f, out


def _block(pen, x, y, lines, f, fill, gap=1.18):
    for l in lines:
        pen.text((x, y), l, f, fill)
        y += int(f.size * gap)
    return y


def _draw(kind, scene, headline, sub, k):
    """One try at laying a scene out at size factor k (1.0 = full size). Returns (image, pen)."""
    from PIL import Image
    im = Image.new("RGB", (W, H), BG)
    pen = Pen(im)
    wide = W - 2 * SAFE_X
    sz = lambda v, lo=MIN_PX: max(int(v * k) // 2 * 2, lo)   # noqa: E731

    def note(y, text):
        for part in text.split("; "):
            nf, nl = fit(pen, part[:1].upper() + part[1:], wide, sz(40, MIN_NOTE_PX), MIN_NOTE_PX, bold=False, max_lines=2)
            y = _block(pen, SAFE_X, y, nl, nf, DIM)
        return y

    pen.text((SAFE_X, BAND_TOP), "EuroFuelPrices", font(44), GREEN)
    if kind == "data" and scene.get("rows"):
        f, lines = fit(pen, scene["title"], wide, sz(84), max_lines=2)
        y = _block(pen, SAFE_X, BAND_TOP + 90, lines, f, FG) + int(50 * k)
        card_h, gap, vf = int(140 * k), int(24 * k), font(sz(56))
        for name, val, bar in scene["rows"]:
            pen.d.rounded_rectangle((SAFE_X, y, W - SAFE_X, y + card_h), 24, fill=BAR)
            vw = pen.width(val, vf)
            pen.text((W - SAFE_X - 28, y + card_h * 0.4), val, vf, GREEN, anchor="rm")
            nf, nl = fit(pen, name, wide - 28 - vw - 28 - 28, sz(52))
            pen.text((SAFE_X + 28, y + card_h * 0.4), nl[0], nf, FG, anchor="lm")
            pen.d.rounded_rectangle((SAFE_X + 28, y + card_h - 26, SAFE_X + 28 + int((wide - 56) * bar), y + card_h - 16), 5, fill=GREEN)   # the bar sits under the text, never behind a number
            y += card_h + gap
        note(y + 16, scene["note"])
    elif kind == "data":                                       # border run: a sentence, not a table
        b = scene["border"]
        f, lines = fit(pen, scene["title"], wide, sz(84), max_lines=2)
        y = _block(pen, SAFE_X, BAND_TOP + 90, lines, f, FG) + int(70 * k)
        for text, size, fill, bold in ((f"{b['label']}: {b['cheap']}", 64, FG, True), (f"€{b['d']:.2f} cheaper", 120, GREEN, True),
                                       (f"than in {b['dear']}", 64, FG, True), (f"≈ €{b['d'] * fb_daily.FILL_L:.0f} on a {fb_daily.FILL_L} L fill-up", 52, DIM, False)):
            f, lines = fit(pen, text, wide, sz(size), bold=bold, max_lines=2)
            y = _block(pen, SAFE_X, y, lines, f, fill) + int(30 * k)
        note(y + int(30 * k), scene["note"])
    else:
        f, lines = fit(pen, headline, wide, sz(100), max_lines=3)
        y = _block(pen, SAFE_X, 700, lines, f, FG) + 40
        nf, nl = fit(pen, sub, wide, sz(56), bold=False, max_lines=2)
        _block(pen, SAFE_X, y, nl, nf, GREEN if kind == "outro" else DIM)
    return im, pen


def render(scene: dict, path: Path, kind: str = "data", headline: str = "", sub: str = "", log=None) -> None:
    """Draw one frame. If the content does not fit the safe band at full size, everything is scaled down (never below MIN_PX) until it does."""
    for k in (1.0, 0.92, 0.84, 0.76, 0.7):
        im, pen = _draw(kind, scene, headline, sub, k)
        if max((e[4] for e in pen.log), default=0) <= BAND_BOT:
            break
    im.save(path)
    if log is not None:
        log.extend(pen.log)


def week_key(today: date) -> str:
    y, w, _ = today.isocalendar()
    return f"{y}-W{w:02d}"


def encode(frames: list, out: Path) -> None:
    clips = []
    for i, f in enumerate(frames):
        clip = f.with_suffix(".mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(SECONDS), "-i", str(f), "-vf",
                        f"fade=in:0:8,fade=out:st={SECONDS - 0.3}:d=0.3,format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "medium", str(clip)], check=True)
        clips.append(clip)
    lst = out.parent / "clips.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)], check=True)


def build(today: date, outdir: Path):
    """-> {"skip": reason} or {"video": Path, "text": caption, "key": ISO week}."""
    if any(r.get("format") == "weekly-video" and r.get("key") == week_key(today) for r in fb_daily.read_log()):
        return {"skip": "already posted this week"}
    raw = fb_daily.fetch(fb_daily.SITE + "/open-data/national-averages.json")
    if not raw:
        return {"skip": "site unreachable"}
    doc = json.loads(raw)
    upd = datetime.fromisoformat(doc["updated"].replace("Z", "+00:00").replace(" ", "T"))
    upd = upd if upd.tzinfo else upd.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - upd > timedelta(hours=36):
        return {"skip": "data older than 36 h"}
    sc = scenes(doc)
    if not sc:
        return {"skip": "not enough data"}
    outdir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, (kind, s, head, sub) in enumerate([("title", None, "Europe fuel prices this week", f"Week {today.isocalendar()[1]}, {today:%d %b %Y}")]
                                             + [("data", s, "", "") for s in sc]
                                             + [("outro", None, "Full ranking and live map", "eurofuelprices.com")]):
        p = outdir / f"f{i}.png"
        render(s, p, kind, head, sub)
        frames.append(p)
    video = outdir / f"weekly_{week_key(today)}.mp4"
    encode(frames, video)
    text = (f"Europe’s fuel prices this week: petrol 95 is cheapest in {sc[0]['rows'][0][0]} ({sc[0]['rows'][0][1]}/L) and dearest in "
            f"{sc[1]['rows'][0][0]} ({sc[1]['rows'][0][1]}/L), median station prices. Full ranking and live map: {fb_daily.SITE}/europe/")
    return {"video": video, "text": text, "key": week_key(today), "date": today.isoformat(), "format": "weekly-video"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="weekly_out")
    a = ap.parse_args()
    res = build(date.today(), Path(a.out))
    if "skip" in res:
        print(f"fb_weekly: skip - {res['skip']}")
        return 0
    print(f"fb_weekly: rendered {res['video']} ({res['video'].stat().st_size // 1024} KB)\n{res['text']}")
    pid, tok = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    if a.dry_run or not pid or not tok:
        return 0
    import fb_bot
    fb_graph.verify_page(pid, tok)
    vid = fb_graph.post_video(pid, tok, res["text"], str(res["video"]))
    fb_bot.append_log({**res, "post_id": vid})
    print(f"fb_weekly: posted {vid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
