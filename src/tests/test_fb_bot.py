import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import fb_bot  # noqa: E402
import fb_daily  # noqa: E402
import fb_graph  # noqa: E402
import fb_local  # noqa: E402


def station(i, city, lat, lon, p95, diesel):
    return {"id": f"s{i}", "brand": f"Brand{i}", "address": f"Str. {i}", "city": city, "lat": lat, "lon": lon,
            "prices": [{"fuel_type": "E10", "octane": 95, "price": p95, "currency": "EUR", "unit": "L", "updated_at": None},
                       {"fuel_type": "DIESEL", "price": diesel, "currency": "EUR", "unit": "L", "updated_at": None}]}


STATIONS = [station(i, "Hamburg", 53.55 + i * 0.005, 10.0, 1.8 + i * 0.01, 2.0 + i * 0.01) for i in range(6)]
STATIONS += [station(99, "Hamburg", 54.6, 10.0, 1.0, 1.0)]          # ~120 km away: outside 10 km, must never be quoted
DE_JSON = json.dumps({"stations": STATIONS})


def fetch(url, dest=None, timeout=30):
    return DE_JSON if url.endswith("/de.json") else None


class Graph:
    def __init__(self, comments=()):
        self.posts, self.replies, self.comments = [], [], list(comments)

    def follower_cities(self, pid, tok):
        return {}

    def verify_page(self, pid, tok):
        return "Euro Fuel Prices"

    def post_photo(self, pid, tok, message, image_url):
        self.posts.append((message, image_url))
        return "123_456"

    def get_comments(self, post_id, tok):
        return self.comments

    def reply(self, cid, tok, message):
        self.replies.append((cid, message))
        return "r1"


class Local(unittest.TestCase):
    def test_match_comment(self):
        self.assertEqual(fb_local.match_comment("Hamburg, Germany"), ("Hamburg", "de"))
        self.assertEqual(fb_local.match_comment("Wien"), ("Wien", None))
        self.assertIsNone(fb_local.match_comment("great idea, thanks for building this tool for everybody"))
        self.assertIsNone(fb_local.match_comment("Oslo, Norway"))             # country without town pages in our supported list

    def test_answer_only_quotes_stations_within_10_km(self):
        text = fb_local.answer_for("Hamburg", "de", fetch)
        self.assertIn("within 10 km of Hamburg", text)
        self.assertIn("Brand0", text)
        self.assertNotIn("Brand99", text)
        self.assertNotIn("1,000", text)
        self.assertIsNone(fb_local.answer_for("Atlantis", "de", fetch))

    def test_ambiguous_or_unknown_town_gets_no_answer(self):
        self.assertIsNone(fb_local.answer_for("Nowhereville", None, fetch))


class Graph_(unittest.TestCase):
    def test_verify_refuses_wrong_page(self):
        with self.assertRaises(fb_graph.GraphError):
            fb_graph.verify_page("1", "tok", call_fn=lambda *a, **k: {"id": "2", "name": "Someone Else"})
        with self.assertRaises(fb_graph.GraphError):
            fb_graph.verify_page("1", "tok", call_fn=lambda *a, **k: {"id": "1", "name": "A Person"})
        self.assertEqual(fb_graph.verify_page("1", "tok", call_fn=lambda *a, **k: {"id": "1", "name": "Euro Fuel Prices"}), "Euro Fuel Prices")


class Bot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log, self.rep = Path(self.tmp.name) / "post_log.csv", Path(self.tmp.name) / "replied.csv"
        self.saved = (fb_daily.LOG, fb_bot.LOG, fb_bot.REPLIED, dict(os.environ))
        fb_daily.LOG = fb_bot.LOG = self.log
        fb_bot.REPLIED = self.rep
        os.environ["FB_PAGE_ID"], os.environ["FB_PAGE_TOKEN"] = "1", "tok"

    def tearDown(self):
        fb_daily.LOG, fb_bot.LOG, fb_bot.REPLIED = self.saved[:3]
        os.environ.clear()
        os.environ.update(self.saved[3])
        self.tmp.cleanup()

    def test_no_credentials_means_quiet_noop(self):
        os.environ.pop("FB_PAGE_TOKEN")
        g = Graph()
        self.assertEqual(fb_bot.run_post(False, g, date(2026, 11, 20)), 0)
        self.assertEqual(g.posts, [])

    def test_post_once_and_log(self):
        g = Graph()
        orig = fb_daily.build
        fb_daily.build = lambda today, out, audience=None, download=True: ({"skip": "already posted today"} if any(
            r["date"] == today.isoformat() for r in fb_daily.read_log()) else
            {"text": "hello", "image_url": "https://x/y.png", "format": "feature", "key": "k", "date": today.isoformat()})
        try:
            fb_bot.run_post(False, g, date(2026, 11, 20))
            fb_bot.run_post(False, g, date(2026, 11, 20))     # second run the same day: nothing new
        finally:
            fb_daily.build = orig
        self.assertEqual(len(g.posts), 1)
        self.assertIn("123_456", self.log.read_text(encoding="utf-8"))

    def test_replies_once_per_comment_and_never_to_the_page(self):
        self.log.write_text("date,format,key,post_id\n2026-11-21,local-ask,local-ask,123_456\n", encoding="utf-8")
        g = Graph([{"id": "c1", "message": "Hamburg, Germany", "from": {"id": "42"}},
                   {"id": "c2", "message": "thanks!", "from": {"id": "43"}},
                   {"id": "c3", "message": "Hamburg", "from": {"id": "1"}}])        # from the Page itself
        fb_bot.run_replies(False, g, fetch, date(2026, 11, 22))
        fb_bot.run_replies(False, g, fetch, date(2026, 11, 22))                      # second pass: all comments already handled
        self.assertEqual([r[0] for r in g.replies], ["c1"])
        self.assertIn("within 10 km of Hamburg", g.replies[0][1])


if __name__ == "__main__":
    unittest.main()
