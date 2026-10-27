"""List and tuple repeats too large for int64 are named at compile time or stopped as CPython's MemoryError.

Before, `[1, 2] * (2**63 - 1)` and its literal spelling segfaulted (exit 139) instead of raising
MemoryError, and an empty list repeated by a huge count spun over the count. Both builds are checked.
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
    env = dict(os.environ, AIL_NO_CACHE="1")
    if unified:
        env["AIL_UNIFIED_FORCE"] = "1"
    else:
        env.pop("AIL_UNIFIED_FORCE", None)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path),
                            "--syntax", "python", "-o", str(exe)],
                           capture_output=True, text=True, timeout=300, env=env)
    return built, exe


class Pre55RepeatTests(unittest.TestCase):
    def test_constant_oversized_repeat_is_refused_by_name(self):
        sources = (
            "xs = [1, 2] * (2**63 - 1)\nprint(len(xs))\n",
            "xs = [1, 2] * 9223372036854775807\nprint(len(xs))\n",
            "xs = (1, 2) * (2**62)\nprint(len(xs))\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            for unified in (False, True):
                for index, source in enumerate(sources):
                    built, _ = build(directory, "refuse_%d_%d" % (index, unified), source, unified)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    message = built.stdout + built.stderr
                    self.assertIn("not in the subset", message)
                    self.assertIn("repeat", message)
                    self.assertIn("too large", message)

    def test_runtime_oversized_repeat_is_memoryerror(self):
        sources = (
            "def f(n):\n    return [1, 2] * n\nprint(len(f(2**62)))\n",
            "def f(n):\n    return (1, 2) * n\nprint(len(f(2**62)))\n",
            "def f(n):\n    return ['a', 'b'] * n\nprint(len(f(2**62)))\n",
            "ns = [2**62]\nprint(len([1, 2] * ns[0]))\n",
            "class C:\n    def __init__(self, n):\n        self.n = n\nc = C(2**62)\nprint(len([1, 2] * c.n))\n",
            "d = {'n': 2**62}\nprint(len([1, 2] * d['n']))\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            for unified in (False, True):
                for index, source in enumerate(sources):
                    built, exe = build(directory, "memory_%d_%d" % (index, unified), source, unified)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                    self.assertEqual(ran.returncode, 1, ran.stderr)
                    self.assertEqual(ran.stdout, "")
                    self.assertEqual(ran.stderr, "MemoryError\n")

    def test_small_empty_negative_and_aliasing_repeats_match_cpython(self):
        source = (
            "print([1, 2] * 0, [1, 2] * -3, [1, 2] * 3, [1, 2] * True)\n"
            "print([1, 2] * (-(2**62)), [-1] * 5)\n"
            "a = [1, 2]\nb = a * 2\na[0] = 9\nprint(a, b)\n"
            "print((1, 2) * 3, ['a', 'b'] * 2, [1.5] * 3)\n"
            "def f(xs, n):\n    return xs * n\n"
            "print(len(f([], 2**62)), len(f((), 2**62)), len(f([], -(2**62))))\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "edge.py")
            path.write_text(source)
            expected = subprocess.run([sys.executable, str(path)], capture_output=True, text=True,
                                      timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for unified in (False, True):
                built, exe = build(directory, "edge_%d" % unified, source, unified)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout, expected.stdout)
                self.assertEqual(ran.stderr, "")


if __name__ == "__main__":
    unittest.main()
