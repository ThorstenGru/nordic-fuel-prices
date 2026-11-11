"""Autonomous Facebook routine for the Euro Fuel Prices Page. Runs on GitHub Actions; needs no computer, app or person.

    python tools/fb_bot.py post [--dry-run]      # one post a day (text + share card), logged in docs/facebook/post_log.csv
    python tools/fb_bot.py replies [--dry-run]   # answers "comment your town" comments with the cheapest stations within 10 km

Environment: FB_PAGE_ID and FB_PAGE_TOKEN (a PAGE access token, GitHub secrets). Without them the script exits quietly (exit 0), so the
workflow can be installed before the secrets exist. Every call is made with the Page token, so posts and replies come from the Page itself;
`verify_page` aborts if the token is not the Euro Fuel Prices Page. Replies: one per comment, only to comments that name a town we cover,
at most MAX_REPLIES per run, never to the Page's own comments; nothing about commenters is stored except the comment id.
"""
import csv
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fb_daily  # noqa: E402
import fb_graph  # noqa: E402
import fb_local  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG = fb_daily.LOG
REPLIED = ROOT / "docs" / "facebook" / "replied.csv"
MAX_REPLIES = 15
LOG_FIELDS = ["date", "format", "key", "post_id"]


def append_log(row: dict):
    new = not LOG.exists()
    with LOG.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, extrasaction="ignore", lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_FIELDS})


def read_replied() -> set:
    if not REPLIED.exists():
        return set()
    with REPLIED.open(encoding="utf-8", newline="") as f:
        return {r["comment_id"] for r in csv.DictReader(f)}


def append_replied(comment_id: str, outcome: str):
    new = not REPLIED.exists()
    with REPLIED.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if new:
            w.writerow(["comment_id", "date", "outcome"])
        w.writerow([comment_id, date.today().isoformat(), outcome])


def creds():
    pid, tok = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    if not pid or not tok:
        print("fb_bot: FB_PAGE_ID / FB_PAGE_TOKEN not set - nothing to do")
        return None
    return pid, tok


def run_post(dry: bool, graph=fb_graph, today=None) -> int:
    today = today or date.today()
    c = creds()
    if not c and not dry:
        return 0
    pid, tok = c or ("", "")
    audience = graph.follower_cities(pid, tok) if c else {}
    res = fb_daily.build(today, Path("."), audience=audience, download=False)
    if "skip" in res:
        print(f"fb_bot: skip - {res['skip']}")
        if res["skip"] != "already posted today":
            if not dry:
                append_log({"date": today.isoformat(), "format": "skip", "key": res["skip"]})
        return 0
    print(f"fb_bot: {res['format']} / {res['key']}\n{res['text']}")
    if dry:
        return 0
    graph.verify_page(pid, tok)
    post_id = graph.post_photo(pid, tok, res["text"], res["image_url"])
    append_log({**res, "post_id": post_id})
    print(f"fb_bot: posted {post_id}")
    return 0


def run_replies(dry: bool, graph=fb_graph, fetch=fb_daily.fetch, today=None) -> int:
    today = today or date.today()
    c = creds()
    if not c:
        return 0
    pid, tok = c
    asks = [r for r in fb_daily.read_log() if r.get("format") == "local-ask" and r.get("post_id")
            and (today - date.fromisoformat(r["date"])).days <= 7]
    if not asks:
        print("fb_bot: no recent 'comment your town' post")
        return 0
    graph.verify_page(pid, tok)
    done, sent = read_replied(), 0
    for post in asks:
        for cm in graph.get_comments(post["post_id"], tok):
            cid = cm.get("id")
            if not cid or cid in done or str((cm.get("from") or {}).get("id", "")) == str(pid):
                continue
            m = fb_local.match_comment(cm.get("message", ""))
            text = fb_local.answer_for(m[0], m[1], fetch) if m else None
            if not text:
                if not dry:
                    append_replied(cid, "no-match")
                continue
            if sent >= MAX_REPLIES:
                return 0
            print(f"fb_bot: reply to {cid}: {text[:80]}...")
            if not dry:
                graph.reply(cid, tok, text)
                append_replied(cid, "replied")
            sent += 1
    print(f"fb_bot: {sent} replies")
    return 0


def main() -> int:
    a = sys.argv[1:]
    dry = "--dry-run" in a
    mode = next((x for x in a if not x.startswith("--")), "")
    try:
        if mode == "post":
            return run_post(dry)
        if mode == "replies":
            return run_replies(dry)
    except fb_graph.GraphError as e:
        print(f"fb_bot: {e}")
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
