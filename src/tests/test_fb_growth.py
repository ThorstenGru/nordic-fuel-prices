import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import fb_daily  # noqa: E402
import fb_graph  # noqa: E402
import fb_insights  # noqa: E402
import fb_reels  # noqa: E402


class Reels(unittest.TestCase):
    def test_three_reels_a_week_on_tue_thu_sat(self):
        self.assertEqual([fb_reels.kind_for(date(2026, 11, d)) for d in range(16, 23)], ["", "border", "", "cheap95", "", "diesel", ""])
        self.assertEqual(fb_reels.kind_for(date(2026, 11, 16), "diesel"), "diesel")

    def test_caption_has_no_link_and_asks_for_a_town(self):
        rows = dict(title="Petrol 95: cheapest", rows=[("Poland", "€1.38", 0.5)], note="")
        border = dict(title="Border run of the week", border=dict(label="Diesel", cheap="Poland", dear="Germany", d=0.43), note="")
        for kind, sc in (("cheap95", rows), ("border", border)):
            t = fb_reels.caption(kind, sc)
            self.assertNotIn("http", t)
            self.assertIn(fb_daily.CTA_TOWN, t)
            self.assertIn("Poland", t)

    def test_reels_api_failure_falls_back_to_a_normal_video(self):
        calls = []

        class G:
            GraphError = fb_graph.GraphError

            @staticmethod
            def post_reel(*a):
                raise fb_graph.GraphError("no permission")

            @staticmethod
            def post_video(*a):
                calls.append("video")
                return "v1"
        self.assertEqual(fb_reels.publish("1", "t", "x", "f.mp4", G), "v1")
        self.assertEqual(calls, ["video"])


class ReelApi(unittest.TestCase):
    def test_start_upload_finish(self):
        steps = []

        def call(method, path, token, params=None):
            steps.append((path, (params or {}).get("upload_phase")))
            return {"video_id": "99", "upload_url": "https://rupload/x"} if params["upload_phase"] == "start" else {"success": True}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.mp4"
            p.write_bytes(b"0123")
            up = []
            vid = fb_graph.post_reel("P", "T", "desc", str(p), call_fn=call, upload_fn=lambda u, b: up.append((u, len(b))) or {"success": True})
        self.assertEqual(vid, "99")
        self.assertEqual(steps, [("P/video_reels", "start"), ("P/video_reels", "finish")])
        self.assertEqual(up, [("https://rupload/x", 4)])

    def test_missing_upload_url_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.mp4"
            p.write_bytes(b"0")
            with self.assertRaises(fb_graph.GraphError):
                fb_graph.post_reel("P", "T", "d", str(p), call_fn=lambda *a, **k: {})


class Insights(unittest.TestCase):
    POSTS = [
        {"id": "1_a", "created_time": "2026-11-14T08:00:00+0000", "reactions": {"summary": {"total_count": 5}}, "comments": {"summary": {"total_count": 3}}, "shares": {"count": 1}},
        {"id": "1_b", "created_time": "2026-11-03T08:00:00+0000", "reactions": {"summary": {"total_count": 1}}},
        {"id": "1_c", "created_time": "2026-11-13T08:00:00+0000"},
    ]

    def test_rows_weekly_and_formats(self):
        rows = fb_insights.rows_for(self.POSTS, {"1_a": "ranking-link", "1_b": "feature"})
        self.assertEqual([r["interactions"] for r in rows], [9, 1, 0])
        wk = fb_insights.weekly_row(date(2026, 11, 15), {"followers_count": 120, "fan_count": "110"}, rows)
        self.assertEqual((wk["followers"], wk["fans"], wk["posts"], wk["reactions"], wk["comments"], wk["shares"]), (120, 110, 2, 5, 3, 1))   # only the last 7 days
        fm = fb_insights.by_format(rows)
        self.assertEqual(fm[0], ("ranking", 1, 9.0))                                     # "-link" does not split a format
        self.assertIn(("?", 1, 0.0), fm)                                                # post of unknown format

    def test_run_writes_csv_once_per_day(self):
        class G:
            @staticmethod
            def recent_posts(*a, **k):
                return Insights.POSTS

            @staticmethod
            def page_stats(*a, **k):
                return {"followers_count": 10}
        with tempfile.TemporaryDirectory() as d:
            old = fb_insights.WEEKLY, fb_insights.POSTS
            fb_insights.WEEKLY, fb_insights.POSTS = Path(d) / "w.csv", Path(d) / "p.csv"
            try:
                fb_insights.run("1", "t", date(2026, 11, 15), G)
                fb_insights.run("1", "t", date(2026, 11, 15), G)                          # same day again: no second weekly row
                self.assertEqual(len(fb_insights.WEEKLY.read_text(encoding="utf-8").strip().splitlines()), 2)
                self.assertEqual(len(fb_insights.POSTS.read_text(encoding="utf-8").strip().splitlines()), 4)
            finally:
                fb_insights.WEEKLY, fb_insights.POSTS = old


if __name__ == "__main__":
    unittest.main()
