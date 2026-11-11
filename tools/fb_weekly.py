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
from europe_index import BORDER_PAIRS, NAMES  # noqa: E402

W, H = 1080, 1920
SECONDS = 4
BG, FG, DIM, GREEN, BAR = (14, 26, 41), (255, 255, 255), (150, 165, 185), (74, 222, 128), (38, 70, 104)


def font(size: int, bold: bool = True):
    from PIL import ImageFont
    for name in ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arialbd.ttf" if bold else "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def scenes(doc: dict) -> list:
    """List of scenes {title, rows[(name, value, bar 0..1)], note} from the national medians; [] when there is too little data."""
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
        out.append(dict(title="Border run of the week", rows=[(f"{label}: {NAMES[cheap]}", f"€{d:.2f} cheaper", 1.0), (f"than in {NAMES[dear]}", f"≈ €{d * fb_daily.FILL_L:.0f} per {fb_daily.FILL_L} L", 1.0)],
                        note="Median station prices" + ("; some figures are estimates or from unofficial sources" if {ga, gb} - {"A", "B"} else "")))
    return out if len(out) == 4 else []


def render(scene: dict, path: Path, kind: str = "data", headline: str = "", sub: str = "") -> None:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((60, 70), "EuroFuelPrices", font=font(46), fill=GREEN)
    if kind == "data":
        d.text((60, 300), scene["title"], font=font(84), fill=FG)
        y = 560
        for name, val, bar in scene["rows"]:
            d.rounded_rectangle((60, y, 60 + int(960 * bar), y + 130), 24, fill=BAR)
            d.text((90, y + 36), name, font=font(48), fill=FG)
            tw = d.textlength(val, font=font(52))
            d.text((1020 - 30 - tw, y + 34), val, font=font(52), fill=GREEN)
            y += 170
        for k, line in enumerate(scene["note"].split("; ")):   # two short lines, above the Reels bottom overlay
            d.text((60, H - 400 + k * 46), line[:1].upper() + line[1:], font=font(34, False), fill=DIM)
    else:
        d.text((60, 640), headline, font=font(96), fill=FG)
        d.text((60, 900), sub, font=font(52, False), fill=GREEN if kind == "outro" else DIM)
    im.save(path)


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
