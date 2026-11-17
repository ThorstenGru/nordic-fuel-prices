import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import town_cards as tc  # noqa: E402


class TownCards(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        tc._made = 0
        tc.MAX_NEW = 2

    def test_card_is_drawn_once_and_the_url_points_at_it(self):
        url = tc.ensure(self.root, "https://x", "se", "malmo", "Malmö", "Sweden", "sv")
        self.assertEqual(url, "https://x/og/town/se/malmo.png")
        p = tc.card_path(self.root, "se", "malmo")
        self.assertTrue(p.exists())
        before = p.stat().st_mtime_ns
        self.assertEqual(tc.ensure(self.root, "https://x", "se", "malmo", "Malmö", "Sweden", "sv"), url)
        self.assertEqual(p.stat().st_mtime_ns, before)           # existing card: not drawn again
        self.assertEqual(tc._made, 1)                            # and it does not use the budget

    def test_size_is_1200_by_630_even_for_a_very_long_name(self):
        from PIL import Image
        name = "Ürümqi-Hauptstadtbezirk-Nordwestlich-Von-Irgendwo-Mit-Sehr-Langem-Namen-Zeichen"
        self.assertTrue(tc.ensure(self.root, "https://x", "de", "lang", name, "Germany", "de"))
        self.assertEqual(Image.open(tc.card_path(self.root, "de", "lang")).size, (1200, 630))

    def test_budget_per_run_leaves_the_rest_on_the_generic_image(self):
        out = [tc.ensure(self.root, "https://x", "se", f"t{i}", f"Town {i}", "Sweden", "sv") for i in range(4)]
        self.assertEqual([bool(u) for u in out], [True, True, False, False])
        self.assertFalse(tc.card_path(self.root, "se", "t3").exists())

    def test_unknown_language_falls_back_to_english_tagline(self):
        self.assertTrue(tc.ensure(self.root, "https://x", "se", "x", "Town", "Sweden", "xx"))


if __name__ == "__main__":
    unittest.main()
