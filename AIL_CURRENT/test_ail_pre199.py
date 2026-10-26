"""pre199: range() with a zero step raises ValueError at construction, as CPython does.

The review of job pre186 left this pre-existing difference open: ``range(0, 5, 0)`` was accepted on
both builds and printed ``range(0, 5, 0)``, where CPython raises
``ValueError: range() arg 3 must not be zero`` before the object exists.  The general path now
converts every range() argument as CPython's PyNumber_Index does (int, bool or an instance's
``__index__``) and then builds the range through the checking builtin, so a zero step is refused at
construction and a non-integer argument names its type instead of being read as a pointer.

The cases below cover the zero step as a literal and through an argument, a list item, an attribute,
a dict value, a bool, an ``__index__`` instance, a for loop, a comprehension, sum()/tuple() and an
aliased name, plus CPython's argument-evaluation order.  Non-zero ranges (negative, empty, wide,
bool bounds) keep their previous results on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

STEP_ZERO = r'''def out(label, fn):
    try:
        print(label, fn())
    except ValueError as e:
        print(label, type(e).__name__, e)
    except TypeError as e:
        print(label, type(e).__name__, e)


class Box:
    def __init__(self, n):
        self.n = n


class Index:
    def __init__(self, n):
        self.n = n

    def __index__(self):
        return self.n


class Bad:
    def __index__(self):
        return "x"


class Plain:
    pass


def make(a, b, c):
    return range(a, b, c)


def step_arg(n):
    return range(0, 5, n)


def touch(label, v):
    print("touch", label, v)
    return v


def main():
    out("literal", lambda: range(0, 5, 0))
    out("five_zero", lambda: range(5, 0, 0))
    out("zero_zero", lambda: range(0, 0, 0))
    out("empty", lambda: range(0, 0, 0)[:])
    out("args", lambda: make(0, 5, 0))
    out("arg", lambda: step_arg(0))
    out("item", lambda: range(0, 5, [0][0]))
    out("attr", lambda: range(0, 5, Box(0).n))
    out("dict", lambda: range(0, 5, {"n": 0}["n"]))
    out("neg_stop", lambda: range(-5, -10, 0))
    out("bool_false", lambda: range(0, 5, False))
    out("bool_arg", lambda: step_arg(False))
    out("bool_item", lambda: range(0, 5, [False][0]))
    out("bool_attr", lambda: range(0, 5, Box(False).n))
    out("bool_dict", lambda: range(0, 5, {"n": False}["n"]))
    out("none", lambda: range(0, 5, None))
    out("str", lambda: range(0, 5, "0"))
    out("float", lambda: range(0, 5, 0.0))
    out("index_zero", lambda: range(0, 5, Index(0)))
    out("index_arg", lambda: step_arg(Index(0)))
    out("index_item", lambda: range(0, 5, [Index(0)][0]))
    out("index_attr", lambda: range(0, 5, Box(Index(0)).n))
    out("index_dict", lambda: range(0, 5, {"n": Index(0)}["n"]))
    out("index_bad", lambda: range(0, 5, Bad()))
    out("plain", lambda: range(0, 5, Plain()))
    out("start_bad", lambda: range(Plain(), 5, 0))
    out("stop_bad", lambda: range(0, Plain(), 0))
    out("comprehension", lambda: [i for i in range(0, 5, 0)])
    out("sum", lambda: sum(range(0, 5, 0)))
    out("tuple", lambda: tuple(range(0, 5, 0)))
    out("slice", lambda: range(0, 10, 0)[0:2])
    try:
        r = range(0, 5, 0)
        print("bind", r)
    except ValueError as e:
        print("bind", type(e).__name__, e)
    try:
        for i in range(0, 5, 0):
            print("iter", i)
    except ValueError as e:
        print("loop", type(e).__name__, e)
    try:
        print(range(touch("start", 0), touch("stop", 5), touch("step", 0)))
    except ValueError as e:
        print("order", type(e).__name__, e)
    try:
        print(range(touch("start2", None), touch("stop2", 5), touch("step2", 0)))
    except TypeError as e:
        print("order2", type(e).__name__, e)


main()
'''

UNCAUGHT = r'''print(range(0, 5, 0))
'''

NONZERO = r'''def out(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)


def main():
    out("bool_true", lambda: list(range(0, 5, True)))
    out("index_ok", lambda: list(range(0, 5, Index(2))))
    out("one", lambda: list(range(5)))
    out("two", lambda: list(range(2, 7)))
    out("three", lambda: list(range(2, 12, 3)))
    out("negative", lambda: list(range(5, -5, -2)))
    out("empty", lambda: list(range(5, 0)))
    out("neg_step", lambda: list(range(3, -3, -2)))
    out("big_step", lambda: list(range(0, 10, 100)))
    out("empty_neg", lambda: list(range(0, 10, -1)))
    out("empty_pos", lambda: list(range(10, 0, 1)))
    out("bool_args", lambda: list(range(False, True, True)))
    out("bool_stop", lambda: list(range(False, True)))
    out("len", lambda: len(range(0, 10, 3)))
    out("contains", lambda: 6 in range(0, 10, 3))
    out("min_stop", lambda: list(range(-9223372036854775807, 9223372036854775807, 9223372036854775807)))


class Index:
    def __init__(self, n):
        self.n = n

    def __index__(self):
        return self.n


main()
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


class Pre199Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre199-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_step_zero_matches_cpython(self):
        want = _cpython(self.dir, 'step_zero', STEP_ZERO)
        self.assertEqual(want.returncode, 0, want.stderr)
        self.assertIn('ValueError range() arg 3 must not be zero', want.stdout)
        for general in (False, True):
            got, err = _run(self.dir, 'step_zero_' + ('g' if general else 'd'), STEP_ZERO, general)
            self.assertIsNotNone(got, err)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                             'general=%s\n%s' % (general, got.stderr))

    def test_uncaught_step_zero_is_not_a_range(self):
        want = _cpython(self.dir, 'uncaught', UNCAUGHT)
        self.assertEqual(want.returncode, 1, want.stderr)
        self.assertIn('ValueError: range() arg 3 must not be zero', want.stderr)
        for general in (False, True):
            got, err = _run(self.dir, 'uncaught_' + ('g' if general else 'd'), UNCAUGHT, general)
            self.assertIsNotNone(got, err)
            self.assertNotEqual(got.returncode, 0)
            self.assertEqual(got.stdout, '')
            self.assertIn('ValueError: range() arg 3 must not be zero', got.stderr)

    def test_nonzero_ranges_match_cpython(self):
        want = _cpython(self.dir, 'nonzero', NONZERO)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            got, err = _run(self.dir, 'nonzero_' + ('g' if general else 'd'), NONZERO, general)
            self.assertIsNotNone(got, err)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                             'general=%s\n%s' % (general, got.stderr))


if __name__ == '__main__':
    unittest.main()
