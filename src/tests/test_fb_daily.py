import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import fb_daily as fb  # noqa: E402


def doc(rows):
    return {"updated": "2026-11-11 06:30Z", "rows": [dict(country=c, name=c, fuel=f, median_eur_per_litre=v, stations=n, source_grade=g)
                                                    for c, f, v, n, g in rows]}


class Posts(unittest.TestCase):
    def test_medians_drop_thin_data_but_keep_estimates(self):
        m = fb.medians(doc([("DE", "p95", 1.9, 500, "C"), ("SE", "p95", 1.4, 900, "D"), ("PL", "p95", 1.4, 10, "C")]))
        self.assertEqual(sorted(m), [("DE", "p95"), ("SE", "p95")])       # grade D is quoted, thin data is not

    def test_grade_d_is_marked_as_estimate(self):
        m = fb.medians(doc([("SE", "p95", 1.4, 900, "D"), ("NO", "p95", 2.2, 900, "C")]))
        text = fb.pair_post(m, "SE", "NO")[0]
        self.assertIn("estimates from community reports", text)

    def test_pair_post_names_cheaper_country_and_notes_grade(self):
        m = fb.medians(doc([("DE", "p95", 2.0, 500, "C"), ("PL", "p95", 1.5, 500, "A")]))
        text, img, url = fb.pair_post(m, "DE", "PL")
        self.assertIn("cheaper in Poland than in Germany", text)
        self.assertIn("€25.00", text)
        self.assertIn("unofficial source", text)
        self.assertTrue(img.endswith("fuel-prices-germany-vs-poland.png"))

    def test_quiz_does_not_give_the_answer(self):
        m = fb.medians(doc([("DE", "p95", 2.0, 500, "A"), ("PL", "p95", 1.5, 500, "A")]))
        text = fb.pair_post(m, "DE", "PL", quiz=True)[0]
        self.assertIn("Quick quiz", text)
        self.assertNotIn("cheaper in", text)

    def test_links_only_for_link_formats_and_only_twice_a_month(self):
        today = date(2026, 11, 16)
        text, fmt = fb.compose("Body.", "https://x/europe/", "Full ranking: ", "ranking", [], today)
        self.assertEqual(fmt, "ranking-link")
        self.assertIn("https://x/europe/", text)
        self.assertTrue(any(a in text for a in fb.TOWN_ASKS))
        used = [{"date": "2026-11-02", "format": "ranking-link"}, {"date": "2026-11-09", "format": "spotlight-link"}]
        text, fmt = fb.compose("Body.", "https://x/europe/", "Full ranking: ", "ranking", used, today)
        self.assertEqual(fmt, "ranking")                                              # allowance used up: no link, the Page button instead
        self.assertNotIn("http", text)
        self.assertIn(fb.CTA_NOLINK, text)
        text, fmt = fb.compose("Tip.", "https://x/", "", "feature", [], today)
        self.assertEqual(fmt, "feature")
        self.assertNotIn("http", text)                                                # tips never carry a link
        used = [{"date": "2026-10-02", "format": "ranking-link"}, {"date": "2026-10-09", "format": "ranking-link"}]
        self.assertEqual(fb.compose("B.", "https://x/", "", "ranking", used, today)[1], "ranking-link")   # last month's links do not count
        text, fmt = fb.compose("Ask.", "https://x/", "", "local-ask", [], today)
        self.assertFalse(any(a in text for a in fb.TOWN_ASKS))                  # the ask itself is not asked twice

    def test_pick_skips_recent_keys(self):
        used = [{"date": "2026-11-10", "key": "a"}, {"date": "2026-10-01", "key": "b"}]
        self.assertEqual(fb.pick(["a", "b", "c"], used, date(2026, 11, 11)), "b")   # a is recent, b is old
        self.assertEqual(fb.pick(["a"], used, date(2026, 11, 11)), "a")             # nothing else: fall back, never crash

    def test_every_feature_has_a_question_and_no_bait(self):
        for key, title, body, path in fb.FEATURES:
            self.assertIn("?", body, key)
            self.assertNotIn("like and share", body.lower())


class News(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.f = os.path.join(tempfile.mkdtemp(), "medians.csv")

    def seed(self, d, rows):
        fb.record_history({(c, f): (v, 500, "A") for c, f, v in rows}, d, self.f)

    def test_history_is_written_once_per_day(self):
        d = date(2026, 11, 10)
        self.seed(d, [("SE", "diesel", 1.5)])
        self.seed(d, [("SE", "diesel", 9.9)])
        self.assertEqual(sum(1 for _ in open(self.f)), 2)                       # header + one row
        fb.record_history({("SE", "diesel"): (1.5, 500, "A")}, d, None)         # None = local run, nothing written

    def test_biggest_weekly_move_becomes_the_news(self):
        self.seed(date(2026, 11, 10), [("SE", "diesel", 1.50), ("DE", "p95", 1.80)])
        now = {("SE", "diesel"): (1.58, 500, "A"), ("DE", "p95"): (1.81, 500, "A")}
        text, key = fb.week_news(now, date(2026, 11, 17), self.f)
        self.assertIn("Diesel in Sweden: up 8 cents per litre in a week (€1.50 to €1.58", text)
        self.assertEqual(key, "SE-diesel-2026-11-17")

    def test_no_news_without_history_or_for_small_moves(self):
        now = {("SE", "diesel"): (1.51, 500, "A")}
        self.assertIsNone(fb.week_news(now, date(2026, 11, 17), self.f))        # no file yet
        self.seed(date(2026, 11, 10), [("SE", "diesel", 1.50)])
        self.assertIsNone(fb.week_news(now, date(2026, 11, 17), self.f))        # +0.7 %: not news
        self.assertIsNone(fb.week_news({("SE", "diesel"): (1.58, 500, "A")}, date(2026, 11, 14), self.f))   # only 4 days of history


if __name__ == "__main__":
    unittest.main()


class SameThresholdAsCard(unittest.TestCase):
    def test_post_text_and_europe_card_quote_the_same_countries(self):
        import europe_index
        self.assertEqual(fb.MIN_N, europe_index.MIN_N)   # 2026-11-16: text said Poland, picture said Malta (300 vs 30)


class Variety(unittest.TestCase):
    def test_town_ask_and_questions_change_from_day_to_day(self):
        days = [date(2026, 11, d) for d in range(16, 23)]
        asks = [fb.rotate(fb.TOWN_ASKS, d) for d in days]
        self.assertTrue(all(a != b for a, b in zip(asks, asks[1:])))               # never the same twice in a row
        self.assertGreaterEqual(len(set(asks)), 5)
        self.assertGreaterEqual(len({fb.rotate(fb.RANKING_ASKS, d) for d in days}), 4)
        self.assertTrue(all("“" in a for a in fb.TOWN_ASKS))                        # every ask shows the format of an answer ("Town, Country")

    def test_post_days_are_the_reduced_plan(self):
        self.assertEqual(fb.POST_DAYS, (0, 2, 4, 5))
