"""Pre-existing CPython differences fixed after job fuzz64, against CPython 3.12.

P1_identity: a Counter with a NaN count compared to itself. CPython compares every count with
== (Counter.__eq__), so the NaN never equals even the same object: c == c is False. The general
path used dict equality, whose `x is y` shortcut answered True; both builds now follow
Counter.__eq__ (missing counts are zero, as in Counter({'a': 0}) == Counter()).

Programs are built with the general path forced and with the default build; stdout and the exit
status must match CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre17-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], 0, text)
        for general in (True, False):
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text, general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text, general, err))


_NAN_PROGRAM = '''import math
from collections import Counter


def same(x, y):
    return (x == y, x != y)


def through(x):
    return x


class Box:
    def __init__(self, v):
        self.v = v


def main():
    nan = float("nan")
    c = Counter()
    c["a"] = nan
    print("self", c == c, c != c)
    print("copy", Counter(c) == c, c == Counter(c))
    print("fresh", Counter({"a": float("nan")}) == c, c == Counter({"a": float("nan")}))
    print("arg", same(c, c), same(through(c), c))
    print("list", [c][0] == c, [c] == [c], same([c][0], c))
    print("dict", {"k": c}["k"] == c, same({"k": c}["k"], c))
    print("attr", Box(c).v == c, same(Box(c).v, c))
    d = Counter({"a": nan})
    print("samecount", c == d, d == c, d != c)
    plain = {"a": nan}
    print("dict-self", plain == plain, same(plain, plain))
    print("counter-dict", c == plain, plain == c, c != plain, plain != c)
    print("math", Counter({"a": math.nan}) == Counter({"a": math.nan}))


main()
'''

_MISSING_PROGRAM = '''from collections import Counter, defaultdict


def main():
    print("zeros", Counter({"a": 0}) == Counter(), Counter() == Counter({"b": 0}),
          Counter({"a": 0}) == Counter({"b": 0}))
    print("zeros-ne", Counter({"a": 0}) != Counter())
    print("one-side", Counter({"a": 1, "b": 0}) == Counter({"a": 1}),
          Counter({"a": 1}) == Counter({"a": 1, "b": 0}))
    print("negative", Counter({"a": -1}) == Counter({"a": -1}),
          Counter({"a": -1}) == Counter({"a": 1}))
    print("float", Counter({"a": 1.5}) == Counter({"a": 1.5}),
          Counter({"a": 1.5}) == Counter({"a": 1}))
    print("bool-int", Counter({"a": True}) == Counter({"a": 1}),
          Counter({"a": False}) == Counter())
    c = Counter("aab")
    print("self", c == c, c != c, c.copy() == c, Counter(c) == c)
    print("different", Counter("aab") == Counter("abb"), Counter("abc") == Counter("cba"))
    dd = defaultdict(int, {"a": 1})
    print("defaultdict", dd == dd, dd != dd, dd == Counter({"a": 1}))
    print("counter-dict", Counter({"a": 0}) == {}, {} == Counter({"a": 0}),
          Counter({"a": 0}) != {}, Counter({"a": 1}) == {"a": 1})


main()
'''


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class Pre17Differential(unittest.TestCase):
    def test_counter_nan_self_equality(self):
        check_program(self, 'p1_identity', _NAN_PROGRAM)

    def test_counter_missing_counts_are_zero(self):
        check_program(self, 'p1_missing_zero', _MISSING_PROGRAM)
