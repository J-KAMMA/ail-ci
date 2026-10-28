"""pre186: an enumerate() counter that would pass INT64_MAX stops by name instead of wrapping.

AIL ints are 64-bit, so the CPython value 9223372036854775808 cannot be represented.  Before, the
general path incremented the counter through INT64_MAX and printed INT64_MIN (and the following
negative values) on both builds.  The counter now stops with ``OverflowError: enumerate() index
integer overflow``, while every value that fits still matches CPython exactly.  The check is in the
shared iterator, so the start may come from a constant, an argument, a list item, an attribute, a
dict value, a for loop or next().
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

IN_RANGE = r'''MAX = 9223372036854775807
MIN = -9223372036854775806


class Box:
    def __init__(self, n):
        self.n = n


def show(label, xs, start):
    print(label, list(enumerate(xs, start)))


def via_arg(xs, n):
    return list(enumerate(xs, n))


def start_arg(n):
    return n


def show_next(label, xs, start):
    it = enumerate(xs, start)
    print(label, next(it), next(it))


def main():
    show("empty_max", [], MAX)
    show("one_max", [7], MAX)
    show("two_max1", [7, 8], MAX - 1)
    show("min", [1, 2], MIN)
    show("arg", [1], start_arg(MAX))
    show("item", [1], [MAX][0])
    show("attr", [1], Box(MAX).n)
    show("dict", [1], {"n": MAX}["n"])
    show_next("next", [1, 2], MAX - 1)
    for i, v in enumerate([10, 20], MAX - 1):
        print("loop", i, v)


main()
'''

OVERFLOW = r'''MAX = 9223372036854775807


class Box:
    def __init__(self, n):
        self.n = n


def out(label, fn):
    try:
        print(label, fn())
    except OverflowError as e:
        print(label, type(e).__name__, e)


def via_arg(n):
    return list(enumerate([1, 2, 3], n))


def via_loop(n):
    kept = []
    for i, v in enumerate([1, 2, 3], n):
        kept.append((i, v))
    return kept


def via_next(n):
    it = enumerate([1, 2, 3], n)
    return [next(it), next(it), next(it)]


def main():
    out("const", lambda: list(enumerate([1, 2, 3], MAX - 1)))
    out("arg", lambda: via_arg(MAX - 1))
    out("item", lambda: list(enumerate([1, 2, 3], [MAX - 1][0])))
    out("attr", lambda: list(enumerate([1, 2, 3], Box(MAX - 1).n)))
    out("dict", lambda: list(enumerate([1, 2, 3], {"n": MAX - 1}["n"])))
    out("loop", lambda: via_loop(MAX - 1))
    out("next", lambda: via_next(MAX - 1))
    out("exact", lambda: list(enumerate([1, 2], MAX)))


main()
'''

UNCAUGHT = r'''print(list(enumerate([1, 2, 3], 9223372036854775806)))
'''


def _run(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    done = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=120)
    return done, ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], cwd=directory,
                          capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))


class Pre186Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre186-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_representable_counters_match_cpython(self):
        want = _cpython(self.dir, 'in_range', IN_RANGE)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            got, err = _run(self.dir, 'in_range_' + ('g' if general else 'd'), IN_RANGE, general)
            self.assertIsNotNone(got, err)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                             'general=%s\n%s' % (general, got.stderr))

    def test_past_int64_stops_by_name(self):
        want = _cpython(self.dir, 'overflow', OVERFLOW)
        self.assertEqual(want.returncode, 0, want.stderr)
        self.assertIn('9223372036854775808', want.stdout)
        for general in (False, True):
            got, err = _run(self.dir, 'overflow_' + ('g' if general else 'd'), OVERFLOW, general)
            self.assertIsNotNone(got, err)
            # exact ints (bigint): the counter passes INT64_MAX exactly, as in CPython
            self.assertEqual((got.stdout, got.returncode), (want.stdout, want.returncode),
                             'general=%s\n%s' % (general, got.stderr))

    def test_uncaught_overflow_is_not_a_wrap(self):
        want = _cpython(self.dir, 'uncaught', UNCAUGHT)
        self.assertEqual(want.returncode, 0, want.stderr)
        self.assertIn('9223372036854775808', want.stdout)
        for general in (False, True):
            got, err = _run(self.dir, 'uncaught_' + ('g' if general else 'd'), UNCAUGHT, general)
            self.assertIsNotNone(got, err)
            # exact ints (bigint): prints the big counter like CPython
            self.assertEqual((got.stdout, got.returncode), (want.stdout, want.returncode),
                             'general=%s\n%s' % (general, got.stderr))


if __name__ == '__main__':
    unittest.main()
