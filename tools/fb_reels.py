"""Three short Reels a week for the Euro Fuel Prices Page (Tue border run, Thu cheapest petrol, Sat cheapest diesel): ~12 s, 1080x1920, captions only.

Why: Reels have the highest organic engagement of Facebook's formats and links in posts are pushed down, so video is the main reach format.
Same safe-area layout and data as the weekly video (tools/fb_weekly.py). Published with the Reels API; if that step fails the same file is posted as a normal
video, so a Reel is never lost. The caption has no link: it invites a town in the comments (answered by tools/fb_bot.py replies) and points to the Page button.

    python tools/fb_reels.py [--dry-run] [--kind border|cheap95|diesel] [--out DIR]     # dry run = render, post nothing
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import fb_daily  # noqa: E402
import fb_graph  # noqa: E402
import fb_weekly  # noqa: E402

# weekday (Mon=0) -> kind; index of the scene in fb_weekly.scenes(): 0 cheapest petrol, 1 dearest petrol, 2 cheapest diesel, 3 border run
SCHEDULE = {1: "border", 3: "cheap95"}   # Saturday's diesel Reel dropped 2026-11-16 (cadence 7 pieces a week); --kind diesel still works
SCENE = {"cheap95": 0, "diesel": 2, "border": 3}


def kind_for(today: date, forced: str = ""):
    return forced or SCHEDULE.get(today.weekday(), "")


def caption(kind: str, scene: dict, today: date = None) -> str:
    if kind == "border":
        b = scene["border"]
        head = f"{b['label']} is about €{b['d']:.2f} per litre cheaper in {b['cheap']} than in {b['dear']} today (median station prices)."
    else:
        r = scene["rows"][0]
        head = f"{scene['title']} in Europe today: {r[0]} at {r[1]} per litre (median station prices)."
    return f"{head}\n\n{fb_daily.rotate(fb_daily.TOWN_ASKS, today or date.today(), 3)}\n\n{fb_daily.CTA_NOLINK}"


def build(today: date, outdir: Path, forced: str = "", ignore_log: bool = False):
    """-> {"skip": reason} or {"video", "text", "key", "date", "format": "reel"}."""
    kind = kind_for(today, forced)
    if kind not in SCENE:
        return {"skip": "no Reel planned for this weekday"}
    key = f"{today.isoformat()}-{kind}"
    if not ignore_log and any(r.get("format") == "reel" and r.get("key") == key for r in fb_daily.read_log()):
        return {"skip": "already posted"}
    raw = fb_daily.fetch(fb_daily.SITE + "/open-data/national-averages.json")
    if not raw:
        return {"skip": "site unreachable"}
    doc = json.loads(raw)
    upd = datetime.fromisoformat(doc["updated"].replace("Z", "+00:00").replace(" ", "T"))
    upd = upd if upd.tzinfo else upd.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - upd > timedelta(hours=36):
        return {"skip": "data older than 36 h"}
    sc = fb_weekly.scenes(doc)
    if not sc:
        return {"skip": "not enough data"}
    scene = sc[SCENE[kind]]
    outdir.mkdir(parents=True, exist_ok=True)
    plan = [("title", None, scene["title"] if scene.get("rows") else "Border run of the week", f"{today:%d %b %Y}"), ("data", scene, "", ""),
            ("outro", None, "Where do you fill up?", "Comment your town for local prices")]
    frames = []
    for i, (k, s, head, sub) in enumerate(plan):
        p = outdir / f"r{i}.png"
        fb_weekly.render(s, p, k, head, sub)
        frames.append(p)
    video = outdir / f"reel_{key}.mp4"
    fb_weekly.encode(frames, video)
    return {"video": video, "text": caption(kind, scene, today), "key": key, "date": today.isoformat(), "format": "reel"}


def publish(pid: str, tok: str, text: str, path: str, graph=fb_graph) -> str:
    """Reel first; a normal video if the Reels API refuses (permission, format), so the post is not lost."""
    try:
        return graph.post_reel(pid, tok, text, path)
    except graph.GraphError as e:
        print(f"fb_reels: Reels API failed ({e}); posting a normal video instead")
        return graph.post_video(pid, tok, text, path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kind", default="", choices=["", "border", "cheap95", "diesel"])
    ap.add_argument("--out", default="reels_out")
    a = ap.parse_args()
    res = build(date.today(), Path(a.out), a.kind, ignore_log=a.dry_run)
    if "skip" in res:
        print(f"fb_reels: skip - {res['skip']}")
        return 0
    print(f"fb_reels: rendered {res['video']} ({res['video'].stat().st_size // 1024} KB)\n{res['text']}")
    pid, tok = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    if a.dry_run or not pid or not tok:
        return 0
    import fb_bot
    fb_graph.verify_page(pid, tok)
    vid = publish(pid, tok, res["text"], str(res["video"]))
    fb_bot.append_log({**res, "post_id": vid})
    print(f"fb_reels: posted {vid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
