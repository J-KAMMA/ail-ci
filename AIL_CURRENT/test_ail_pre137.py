"""pre137: a negative r is a ValueError for the itertools choosers.

The general path built an empty iterator for
`permutations(iterable, r)`, `combinations(iterable, r)` and
`combinations_with_replacement(iterable, r)` when `r < 0`.  CPython raises
`ValueError: r must be non-negative`.  Both builds now raise the same
catchable error; the pool is still materialized first, so a non-iterable
argument raises TypeError first, as CPython does.

The programs cover `r` reaching the call as a literal, a local, a function
argument, a list item, an attribute and a dict value, plus r = 0, r > n,
an empty pool, booleans, and the uncaught exit status.  Each program is built
on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


NEGATIVE_R = r'''import itertools


class Box:
    def __init__(self, r):
        self.r = r


def from_arg(v):
    return v


def call(label, which, xs, r):
    try:
        if which == 0:
            out = list(itertools.permutations(xs, r))
        elif which == 1:
            out = list(itertools.combinations(xs, r))
        else:
            out = list(itertools.combinations_with_replacement(xs, r))
        print(label, out)
    except Exception as e:
        print(label, type(e).__name__, str(e), e.args)


def run():
    neg = -1
    xs = [-2, -3, -4, -5]
    d = {"r": -3}
    b = Box(-4)
    for which in (0, 1, 2):
        call("lit", which, [1, 2, 3], -1)
        call("local", which, [1, 2, 3], neg)
        call("arg", which, [1, 2, 3], from_arg(-5))
        call("list", which, [1, 2, 3], xs[0])
        call("attr", which, [1, 2, 3], b.r)
        call("dict", which, [1, 2, 3], d["r"])
        call("empty-neg", which, [], -1)
        call("empty-arg", which, [], from_arg(-2))


run()
'''

BOUNDARIES = r'''import itertools


def show(label, which, xs, r):
    try:
        if which == 0:
            out = list(itertools.permutations(xs, r))
        elif which == 1:
            out = list(itertools.combinations(xs, r))
        else:
            out = list(itertools.combinations_with_replacement(xs, r))
        print(label, out)
    except Exception as e:
        print(label, type(e).__name__, str(e))


def run():
    for r in (0, 1, 2, 3, 4):
        show("p-%d" % r, 0, [1, 2, 3], r)
        show("c-%d" % r, 1, [1, 2, 3], r)
        show("w-%d" % r, 2, [1, 2, 3], r)
    show("p-zero-empty", 0, [], 0)
    show("c-zero-empty", 1, [], 0)
    show("w-zero-empty", 2, [], 0)
    show("p-one-empty", 0, [], 1)
    show("c-one-empty", 1, [], 1)
    show("w-one-empty", 2, [], 1)
    show("p-true", 0, [1, 2, 3], True)
    show("p-false", 0, [1, 2, 3], False)
    show("c-false", 1, [1, 2, 3], False)
    show("w-true", 2, [1, 2], True)
    show("p-range", 0, range(3), 2)
    show("c-tuple", 1, (1, 2, 3), 2)
    show("w-zero", 2, [1, 2], 0)


run()
'''

CATCH_AND_ORDER = r'''import itertools


def gen(log):
    log.append("iter")
    yield 1
    yield 2


def inner():
    q = [5][0]
    r = 0 - q
    return list(itertools.permutations([1, 2], r))


def run():
    log = []
    neg = 0 - 1
    try:
        list(itertools.permutations(gen(log), neg))
    except ValueError as e:
        print("gen", type(e).__name__, str(e), e.args, log)
    try:
        inner()
    except ValueError as e:
        print("nested", type(e).__name__, str(e))
    r = -2
    try:
        itertools.combinations([1, 2, 3], r)
    except ValueError as e:
        print("no-iterate", type(e).__name__, str(e))
    print("alive")


run()
'''

UNCAUGHT = r'''import itertools


def gen():
    yield 1


def inner():
    q = [5][0]
    r = 0 - q
    return list(itertools.permutations([1, 2], r))


print("before")
inner()
print("after")
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre137Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, stderr=None):
        with tempfile.TemporaryDirectory(prefix='ail-pre137-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got[0], want, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got[1], rc, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                if stderr is not None:
                    self.assertIn(stderr, build_err)

    def test_negative_r(self):
        self.check('negative_r', NEGATIVE_R)

    def test_boundaries(self):
        self.check('boundaries', BOUNDARIES)

    def test_catch_and_order(self):
        self.check('catch_and_order', CATCH_AND_ORDER)

    def test_uncaught(self):
        self.check('uncaught', UNCAUGHT, rc=1, stderr='ValueError: r must be non-negative')


if __name__ == '__main__':
    unittest.main()
