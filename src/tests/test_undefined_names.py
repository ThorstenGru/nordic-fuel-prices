"""A name that no longer exists (a helper removed in a cleanup) only fails when that code path runs, in production. pyflakes finds it statically."""
import os
import unittest

try:
    from pyflakes import api, reporter
except ImportError:  # CI installs pyflakes; a machine without it skips
    api = None

SRC = os.path.join(os.path.dirname(__file__), "..")


class Collect:
    def __init__(self): self.msgs = []
    def unexpectedError(self, filename, msg): self.msgs.append(f"{filename}: {msg}")
    def syntaxError(self, filename, msg, lineno, offset, text): self.msgs.append(f"{filename}:{lineno}: syntax error {msg}")
    def flake(self, message): self.msgs.append(str(message))


class UndefinedNames(unittest.TestCase):
    @unittest.skipIf(api is None, "pyflakes not installed")
    def test_no_undefined_names_in_src(self):
        bad = []
        for root, _, files in os.walk(SRC):
            if "__pycache__" in root:
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                c = Collect()
                path = os.path.join(root, f)
                with open(path, encoding="utf-8") as fh:
                    api.check(fh.read(), path, c)
                bad += [m for m in c.msgs if "undefined name" in m]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
