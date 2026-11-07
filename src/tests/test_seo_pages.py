import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import seo_pages as sp  # noqa: E402


class JsonLd(unittest.TestCase):
    def test_script_end_in_a_name_cannot_close_the_block(self):
        cfg = sp.COUNTRIES["se"]
        html = sp.page(cfg, "T", "d", "https://x/", "H", "<p>b</p>", [{"name": "</script><b>x"}], "", "2026-11-07", "f")
        self.assertNotIn("</script><b>", html)
        self.assertIn("<\\/script>", html)


if __name__ == "__main__":
    unittest.main()
