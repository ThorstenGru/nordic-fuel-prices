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

    def test_pick_skips_recent_keys(self):
        used = [{"date": "2026-11-10", "key": "a"}, {"date": "2026-10-01", "key": "b"}]
        self.assertEqual(fb.pick(["a", "b", "c"], used, date(2026, 11, 11)), "b")   # a is recent, b is old
        self.assertEqual(fb.pick(["a"], used, date(2026, 11, 11)), "a")             # nothing else: fall back, never crash

    def test_every_feature_has_a_question_and_no_bait(self):
        for key, title, body, path in fb.FEATURES:
            self.assertIn("?", body, key)
            self.assertNotIn("like and share", body.lower())


if __name__ == "__main__":
    unittest.main()
