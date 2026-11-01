"""The int64-constant census: which big constants the default build refuses, and the safe subset it folds.

The compiler census stops on constants such as the FNV multiplier, an all-ones 64-bit mask and the
int64 sentinel.  This module locks the rule from docs/design/I64_CONSTANTS.md:

  * a constant whose *result* fits int64 is folded and builds, even with an out-of-int64
    intermediate, and a mask applied to an int64 constant is the same folded shape;
  * a mask that itself fits int64 can be applied to a variable;
  * every other shape is refused by name with the --exact-int hint, never wrapped;
  * exact mode builds the refused program and prints CPython's answer.

It checks the default and forced-general builds and compares stdout and exit code with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
HINT = "--exact-int"


REFUSED = {
    "hash_module": '''H = 0xcbf29ce484222325
print(H)
''',
    "mask_variable": '''def f(x: int) -> int:
    return x & ((1 << 64) - 1)
print(f(5))
''',
    "mask_negative_argument": '''def f(x: int) -> int:
    return x & ((1 << 64) - 1)
print(f(-1))
''',
    "sentinel_module": '''B = 1 << 63
print(B)
''',
    "sentinel_class": '''class C:
    B = 1 << 64
print(C.B)
''',
    "default_argument": '''def f(x=1 << 64):
    return x
print(f())
''',
    "list_item": '''xs = [2 ** 63]
print(xs[0])
''',
    "dict_value": '''d = {"k": 2 ** 64}
print(d["k"])
''',
    "attribute_value": '''class C:
    pass
C.v = 10 ** 30
print(C.v)
''',
    "threshold_comparison": '''print(5 if 10 ** 30 > 0 else 0)
''',
    "range_bound": '''def f(x: int) -> bool:
    return -(1 << 63) <= x < (1 << 63)
print(f(0))
''',
}


SAFE = {
    "folded_intermediates": '''print((1 << 64) - (1 << 64) + 5)
print((1 << 64) >> 64, 1 << 64 >> 64)
print(-(1 << 63), (1 << 63) - 1)
''',
    "mask_on_int64_constant": '''print(5 & ((1 << 64) - 1))
print(((1 << 64) - 1) & 0xFF)
print(0 & (1 << 64) - 1)
''',
    "mask_that_fits": '''def f(x: int) -> int:
    return x & 0x7FFFFFFFFFFFFFFF

def g(x: int) -> int:
    return x & 0xFFFFFFFF

print(f(0), f(-1), f(9223372036854775807), f(-9223372036854775807 - 1))
print(g(-1), g(0), g(4294967296), g(-4294967297))
''',
    "boundary_spellings": '''print(-9223372036854775807 - 1)
print(-(1 << 63))
print(9223372036854775807)
print(((1 << 63) - 1) * -1 - 1)
''',
}


EXACT = '''H = 0xcbf29ce484222325
M = (1 << 64) - 1

def mask(x: int) -> int:
    return x & M

print(H, M, mask(5), mask(-1), 5 & M)
'''


def _env(general, exact=False):
    env = dict(os.environ)
    for key in ("AIL_UNIFIED_FORCE", "AIL_EXACT_INT", "AIL_BIGINT", "AIL_NO_GENERAL",
                "AIL_UNIFIED", "AIL_QUIET_FALLBACK"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    if exact:
        env["AIL_EXACT_INT"] = "1"
    return env


def _build(directory, name, text, general=False, exact=False):
    source = Path(directory) / (name + ".py")
    executable = Path(directory) / (name + ("_g" if general else "_d") + ("_x" if exact else ""))
    source.write_text(text, encoding="utf-8")
    made = subprocess.run([sys.executable, "-B", CLI, "compile", str(source), "--syntax", "python",
                           "-o", str(executable)], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=_env(general, exact))
    return made, executable


def _run(executable, directory):
    done = subprocess.run([str(executable)], cwd=directory, capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout.replace("\r\n", "\n")


def _cpython(directory, name, text):
    source = Path(directory) / (name + "_cpython.py")
    source.write_text(text, encoding="utf-8")
    done = subprocess.run([sys.executable, "-B", str(source)], cwd=directory, capture_output=True,
                          text=True, timeout=120, env=dict(os.environ, PYTHONUTF8="1"))
    return done.returncode, done.stdout.replace("\r\n", "\n")


class I64ConstantsTests(unittest.TestCase):
    def test_big_constants_are_refused_with_the_exact_hint(self):
        with tempfile.TemporaryDirectory(prefix="ail-i64-constants-") as directory:
            for name, text in REFUSED.items():
                for general in (False, True):
                    with self.subTest(name=name, general=general):
                        made, executable = _build(directory, name, text, general)
                        output = made.stdout + made.stderr
                        self.assertNotEqual(made.returncode, 0, output[-2000:])
                        self.assertFalse(executable.exists())
                        self.assertIn(HINT, output)
                        self.assertTrue(any(phrase in output for phrase in
                                            ("out of range", "overflows int64", "does not fit")), output[-2000:])

    def test_safe_shapes_match_cpython_on_both_builds(self):
        with tempfile.TemporaryDirectory(prefix="ail-i64-safe-") as directory:
            for name, text in SAFE.items():
                want = _cpython(directory, name, text)
                for general in (False, True):
                    with self.subTest(name=name, general=general):
                        made, executable = _build(directory, name, text, general)
                        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
                        self.assertEqual(_run(executable, directory), want)

    def test_exact_mode_builds_the_refused_program(self):
        with tempfile.TemporaryDirectory(prefix="ail-i64-exact-") as directory:
            want = _cpython(directory, "exact", EXACT)
            made, executable = _build(directory, "exact", EXACT, exact=True)
            self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
            self.assertEqual(_run(executable, directory), want)

    def test_default_mode_refuses_the_same_program(self):
        with tempfile.TemporaryDirectory(prefix="ail-i64-refuse-") as directory:
            for general in (False, True):
                made, executable = _build(directory, "exact", EXACT, general)
                output = made.stdout + made.stderr
                self.assertNotEqual(made.returncode, 0, output[-2000:])
                self.assertFalse(executable.exists())
                self.assertIn(HINT, output)
                self.assertIn("out of range", output)


if __name__ == "__main__":
    unittest.main()
