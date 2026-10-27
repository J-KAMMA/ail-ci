"""pre59: itertools permutations/combinations reject a negative r.

The general-path runtime returned an empty result for a negative r where CPython
raises ``ValueError: r must be non-negative`` (DIFFERENCES row
C?-job-fuzz8-10220554-1).  ``ail_it_permutations``, ``ail_it_combinations`` and
``ail_it_combinations_wr`` now check the sign before the "r larger than the
pool" early exit, so empty pools and r == 0 keep their CPython results.

The programs cover negative, zero, larger-than-pool and empty-pool values; r
reaching the call through an argument, a list item, an attribute and a dict
value; keyword r; and the typed for-loop/unpacking path.  Each is built on both
builds and compared with CPython.

A negative ``r`` literal is refused at compile time (pre75), so the direct and
keyword cases pass a computed ``neg`` value instead to exercise the runtime
ValueError.  The literal refusal itself is covered by ``test_ail_pre75``.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''import itertools
neg = 0 - 1
def show(tag, fn):
    try:
        print(tag, list(fn()))
    except Exception as e:
        print(tag, type(e).__name__, e)
for n in (0, 1, 3):
    for r in (-1, -2, -100):
        show("p%d %d" % (n, r), lambda n=n, r=r: itertools.permutations(range(n), r))
        show("c%d %d" % (n, r), lambda n=n, r=r: itertools.combinations(range(n), r))
        show("w%d %d" % (n, r), lambda n=n, r=r: itertools.combinations_with_replacement(range(n), r))
show("p kw", lambda: itertools.permutations(range(3), r=neg))
show("c kw", lambda: itertools.combinations(range(3), r=neg))
show("w kw", lambda: itertools.combinations_with_replacement(range(3), r=neg))
show("p expr", lambda: itertools.permutations(range(3), 1 - 2))
show("c expr", lambda: itertools.combinations(range(3), 1 - 2))
show("w expr", lambda: itertools.combinations_with_replacement(range(3), 1 - 2))
show("p bool", lambda: itertools.permutations(range(3), False))
show("c bool", lambda: itertools.combinations(range(3), False))
'''

SOURCES = r'''import itertools
class Box:
    def __init__(self, r):
        self.r = r
def getp(xs, r):
    return list(itertools.permutations(xs, r))
def getc(xs, r):
    return list(itertools.combinations(xs, r))
def getw(xs, r):
    return list(itertools.combinations_with_replacement(xs, r))
def show(tag, fn):
    try:
        print(tag, fn())
    except Exception as e:
        print(tag, type(e).__name__, e)
b = Box(-2)
rs = [-1, 0, 2]
d = {"r": -3}
show("arg p", lambda: getp([1, 2, 3], -1))
show("arg c", lambda: getc([1, 2, 3], -4))
show("arg w", lambda: getw([1, 2, 3], -5))
show("list p", lambda: list(itertools.permutations([1, 2], rs[0])))
show("list c", lambda: list(itertools.combinations([1, 2], rs[0])))
show("list w", lambda: list(itertools.combinations_with_replacement([1, 2], rs[0])))
show("attr p", lambda: list(itertools.permutations([1, 2], b.r)))
show("attr c", lambda: list(itertools.combinations([1, 2], b.r)))
show("attr w", lambda: list(itertools.combinations_with_replacement([1, 2], b.r)))
show("dict p", lambda: list(itertools.permutations([1, 2], d["r"])))
show("dict c", lambda: list(itertools.combinations([1, 2], d["r"])))
show("dict w", lambda: list(itertools.combinations_with_replacement([1, 2], d["r"])))
show("arg ok p", lambda: getp([1, 2, 3], 2))
show("arg ok c", lambda: getc([1, 2, 3], 2))
show("arg ok w", lambda: getw([1, 2, 3], 2))
'''

BOUNDS = r'''from itertools import permutations, combinations, combinations_with_replacement
neg = 0 - 1
def show(tag, fn):
    try:
        print(tag, list(fn()))
    except Exception as e:
        print(tag, type(e).__name__, e)
show("p r=n", lambda: permutations(range(3), 3))
show("p r>n", lambda: permutations(range(3), 4))
show("p r=0", lambda: permutations(range(3), 0))
show("c r=n", lambda: combinations(range(3), 3))
show("c r>n", lambda: combinations(range(3), 4))
show("c r=0", lambda: combinations(range(3), 0))
show("w r>n", lambda: combinations_with_replacement(range(3), 4))
show("w r=0", lambda: combinations_with_replacement(range(3), 0))
show("p empty r=-1", lambda: permutations([], neg))
show("c empty r=-1", lambda: combinations([], neg))
show("w empty r=-1", lambda: combinations_with_replacement([], neg))
show("p neg big", lambda: permutations(range(3), -(10 ** 6)))
show("c neg big", lambda: combinations(range(3), -(10 ** 6)))
show("w neg big", lambda: combinations_with_replacement(range(3), -(10 ** 6)))
'''

LOOP = r'''from itertools import permutations, combinations, combinations_with_replacement
def show(tag, fn):
    try:
        print(tag, fn())
    except Exception as e:
        print(tag, type(e).__name__, e)
def p_loop(xs, r):
    out = []
    for a, b in permutations(xs, r):
        out.append(a * 10 + b)
    return out
def c_loop(xs, r):
    out = []
    for a, b in combinations(xs, r):
        out.append(a * 10 + b)
    return out
def w_loop(xs, r):
    out = []
    for a, b in combinations_with_replacement(xs, r):
        out.append(a * 10 + b)
    return out
def p_any(xs, r):
    out = []
    for p in permutations(xs, r):
        out.append(len(p))
    return out
show("p loop neg", lambda: p_loop([1, 2, 3], -1))
show("c loop neg", lambda: c_loop([1, 2, 3], -2))
show("w loop neg", lambda: w_loop([1, 2, 3], -3))
show("p loop ok", lambda: p_loop([1, 2, 3], 2))
show("c loop ok", lambda: c_loop([1, 2, 3], 2))
show("w loop ok", lambda: w_loop([1, 2], 2))
show("p any neg", lambda: p_any([1, 2, 3], -1))
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


class Pre59Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre59-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_negative_r_basic(self):
        self.check('negative_r_basic', BASIC)

    def test_negative_r_sources(self):
        self.check('negative_r_sources', SOURCES)

    def test_negative_r_bounds(self):
        self.check('negative_r_bounds', BOUNDS)

    def test_negative_r_loop(self):
        self.check('negative_r_loop', LOOP)


if __name__ == '__main__':
    unittest.main()
