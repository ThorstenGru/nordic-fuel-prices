"""Weekly numbers from the Euro Fuel Prices Page, into two CSV files in docs/facebook/ (committed by the workflow), so decisions rest on data.

  insights_weekly.csv   one row per run: date, followers, fans, posts, reactions, comments, shares (posts of the last 7 days)
  insights_posts.csv    one row per recent post (overwritten each run): id, created, format (from post_log.csv), reactions, comments, shares, interactions

Only counts that the Page's own token returns (followers, reactions, comments, shares); no person is named or stored. Reach and impressions are not here:
Meta changed those metrics repeatedly, read them in Page Insights. The printed summary ranks formats by average interactions per post.

    python tools/fb_insights.py [--dry-run]
"""
import csv
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fb_daily  # noqa: E402
import fb_graph  # noqa: E402

DIR = Path(__file__).resolve().parent.parent / "docs" / "facebook"
WEEKLY, POSTS = DIR / "insights_weekly.csv", DIR / "insights_posts.csv"
WEEKLY_FIELDS = ["date", "followers", "fans", "posts", "reactions", "comments", "shares"]
POST_FIELDS = ["id", "created", "format", "reactions", "comments", "shares", "interactions"]


def _n(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def rows_for(posts: list, formats: dict) -> list:
    """Graph posts -> flat rows. `formats` maps a post id to our format name (from post_log.csv); unknown ids get ''."""
    out = []
    for p in posts:
        r = _n(((p.get("reactions") or {}).get("summary") or {}).get("total_count"))
        c = _n(((p.get("comments") or {}).get("summary") or {}).get("total_count"))
        s = _n((p.get("shares") or {}).get("count"))
        out.append({"id": p.get("id", ""), "created": str(p.get("created_time", ""))[:10], "format": formats.get(p.get("id", ""), ""),
                    "reactions": r, "comments": c, "shares": s, "interactions": r + c + s})
    return out


def by_format(rows: list) -> list:
    """[(format, posts, average interactions)] best first; posts of unknown format are grouped as '?'."""
    g = defaultdict(list)
    for r in rows:
        g[(r["format"] or "?").replace("-link", "")].append(r["interactions"])
    return sorted(((k, len(v), round(sum(v) / len(v), 1)) for k, v in g.items()), key=lambda x: -x[2])


def weekly_row(today: date, stats: dict, rows: list) -> dict:
    cut = (today - timedelta(days=7)).isoformat()
    recent = [r for r in rows if r["created"] >= cut]
    return {"date": today.isoformat(), "followers": _n(stats.get("followers_count")), "fans": _n(stats.get("fan_count")), "posts": len(recent),
            "reactions": sum(r["reactions"] for r in recent), "comments": sum(r["comments"] for r in recent), "shares": sum(r["shares"] for r in recent)}


def write_csv(path: Path, fields: list, rows: list, append: bool = False) -> None:
    new = not path.exists() or not append
    with path.open("a" if append else "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)


def run(pid: str, tok: str, today: date, graph=fb_graph, dry: bool = False) -> dict:
    formats = {r["post_id"]: r["format"] for r in fb_daily.read_log() if r.get("post_id")}
    rows = rows_for(graph.recent_posts(pid, tok), formats)
    wk = weekly_row(today, graph.page_stats(pid, tok), rows)
    if not dry:
        had = WEEKLY.exists() and any(r.get("date") == wk["date"] for r in csv.DictReader(WEEKLY.open(encoding="utf-8")))
        if not had:
            write_csv(WEEKLY, WEEKLY_FIELDS, [wk], append=True)
        write_csv(POSTS, POST_FIELDS, rows)
    return {"week": wk, "formats": by_format(rows), "posts": len(rows)}


def main() -> int:
    pid, tok = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    if not pid or not tok:
        print("fb_insights: FB_PAGE_ID / FB_PAGE_TOKEN not set - nothing to do")
        return 0
    fb_graph.verify_page(pid, tok)
    try:
        res = run(pid, tok, datetime.now(timezone.utc).date(), dry="--dry-run" in sys.argv)
    except fb_graph.GraphError as e:
        print(f"fb_insights: could not read the Page ({e}); the token may lack pages_read_engagement")
        return 0
    print(f"fb_insights: {res['posts']} posts read; this week {res['week']}")
    for k, n, avg in res["formats"]:
        print(f"  {k:14s} {n:3d} posts, {avg} interactions per post")
    return 0


if __name__ == "__main__":
    sys.exit(main())
