import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import fb_music  # noqa: E402


class Music(unittest.TestCase):
    def test_render_is_deterministic_quiet_enough_and_fades(self):
        a = fb_music.render(3.0)
        self.assertEqual(len(a), 3 * fb_music.RATE)
        self.assertEqual(a, fb_music.render(3.0))                         # same input, same music
        peak = max(abs(x) for x in a)
        self.assertTrue(0.3 < peak <= 0.5 + 1e-9, peak)                   # audible, but at most about -6 dBFS
        self.assertLess(abs(a[0]), 0.02)                                  # fades in
        self.assertLess(abs(a[-1]), 0.02)                                 # and out, no click at the end
        self.assertGreater(sum(abs(x) for x in a[fb_music.RATE:2 * fb_music.RATE]), 100)   # not silence

    def test_wav_file_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.wav"
            fb_music.write_wav(p, fb_music.render(1.0))
            with wave.open(str(p)) as w:
                self.assertEqual((w.getnchannels(), w.getframerate(), w.getnframes()), (1, fb_music.RATE, fb_music.RATE))

    def test_missing_ffmpeg_keeps_the_silent_video(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v.mp4"
            v.write_bytes(b"silent")
            from unittest import mock
            with mock.patch.object(fb_music.subprocess, "run", side_effect=FileNotFoundError("ffmpeg")):
                self.assertFalse(fb_music.add_music(v, 1.0))
            self.assertEqual(v.read_bytes(), b"silent")                   # untouched
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["v.mp4"])   # no leftovers


if __name__ == "__main__":
    unittest.main()
