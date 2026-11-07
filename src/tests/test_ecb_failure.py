import asyncio
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers import _anwb  # noqa: E402


class Sess:
    def __init__(self): self.calls = 0
    def get(self, *a, **k):
        self.calls += 1
        raise OSError("down")


class EcbFailure(unittest.TestCase):
    def test_second_caller_does_not_repeat_the_timeouts(self):
        s = Sess()
        with mock.patch.object(_anwb, "_ecb_cache", {}), mock.patch.object(_anwb, "_ecb_failed", False), mock.patch.object(_anwb, "_ecb_lock", None):
            first = asyncio.run(_anwb._ecb_rates(s))
            calls_after_first = s.calls
            second = asyncio.run(_anwb._ecb_rates(s))
        self.assertEqual(calls_after_first, 2)               # ECB and Frankfurter, once
        self.assertEqual(s.calls, 2)                         # the next country asks nobody
        self.assertEqual(first, second); self.assertNotIn("SEK", second)


if __name__ == "__main__":
    unittest.main()
