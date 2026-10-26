"""pre271: an oversized in-place list repeat is CPython's MemoryError, not an int64 stop.

The rbpre55 review recorded that `xs *= 2**62` stopped with an uncatchable `integer overflow`
instead of raising MemoryError.  `ail_op_imul` now stops with `MemoryError` before the element
product leaves int64, and an empty list no longer loops over a huge count.  Both builds are
checked, including a count that reaches the statement through an argument, a list item, an
attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(directory, name, source, unified):
    path, exe = Path(directory, name + ".ail"), Path(directory, name)
    path.write_text(source)
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    if unified:
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        env.pop("AIL_UNIFIED_FORCE", None)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path),
                            "--syntax", "python", "-o", str(exe)],
                           capture_output=True, text=True, timeout=300, env=env)
    return built, exe


def cpython(directory, name, source):
    path = Path(directory, name + ".py")
    path.write_text(source)
    return subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=60)


def run(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)


class Pre271AugmentedRepeatTests(unittest.TestCase):
    def _assert_memoryerror(self, directory, name, source, expected):
        self.assertEqual(expected.returncode, 1, expected.stderr)
        self.assertEqual(expected.stdout, "")
        self.assertEqual(expected.stderr.splitlines()[-1], "MemoryError")
        for unified in (False, True):
            built, exe = build(directory, "%s_%d" % (name, unified), source, unified)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = run(exe)
            self.assertEqual(got.returncode, 1, got.stderr)
            self.assertEqual(got.stdout, "")
            self.assertEqual(got.stderr, "MemoryError\n")

    def test_constant_oversized_repeats_are_memoryerror(self):
        sources = (
            "xs = [1, 2]\nxs *= 2 ** 62\nprint(len(xs))\n",
            "xs = [1, 2]\nxs *= 4611686018427387904\nprint(len(xs))\n",
            "xs = [1]\nxs *= 2 ** 62\nprint(len(xs))\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, source in enumerate(sources):
                self._assert_memoryerror(directory, "constant_%d" % index, source,
                                         cpython(directory, "constant_%d" % index, source))

    def test_oversized_count_through_routes_is_memoryerror(self):
        sources = (
            "def f(n):\n    xs = [1, 2]\n    xs *= n\n    return len(xs)\n"
            "print(f(2 ** 62))\n",
            "ns = [2 ** 62]\nxs = [1, 2]\nxs *= ns[0]\nprint(len(xs))\n",
            "class C:\n    def __init__(self, n):\n        self.xs = [1, 2]\n"
            "        self.xs *= n\nc = C(2 ** 62)\nprint(len(c.xs))\n",
            "d = {'n': 2 ** 62}\nxs = [1, 2]\nxs *= d['n']\nprint(len(xs))\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, source in enumerate(sources):
                self._assert_memoryerror(directory, "route_%d" % index, source,
                                         cpython(directory, "route_%d" % index, source))

    def test_empty_boundaries_and_types_match_cpython(self):
        source = (
            "xs = []\nxs *= 2 ** 62\nprint(xs)\n"
            "ys = []\nys *= -5\nprint(ys)\n"
            "zs = [1, 2]\nzs *= 1\nprint(zs)\n"
            "zs *= 0\nprint(zs)\n"
            "zs = [1, 2]\nzs *= -3\nprint(zs)\n"
            "bs = [1, 2]\nbs *= True\nprint(bs)\n"
            "bs *= False\nprint(bs)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, "boundaries", source)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for unified in (False, True):
                built, exe = build(directory, "boundaries_%d" % unified, source, unified)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = run(exe)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected.stdout)
                self.assertEqual(got.stderr, "")

    def test_aliasing_and_small_repeats_match_cpython(self):
        source = (
            "a = [1, 2]\nb = a\na *= 2\nprint(a, b)\n"
            "c = [3]\nd = c\nc *= 0\nprint(c, d)\n"
            "e = [4]\nf = e\ne *= 1\nprint(e, f)\n"
            "g = [5]\nh = g\ng *= -1\nprint(g, h)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, "aliasing", source)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for unified in (False, True):
                built, exe = build(directory, "aliasing_%d" % unified, source, unified)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = run(exe)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected.stdout)
                self.assertEqual(got.stderr, "")


if __name__ == "__main__":
    unittest.main()
