"""pre126: itertools permutations/combinations validate r like CPython.

The job-pre101 review listed the general path's handling of a negative r as a
pre-existing difference: permutations, combinations and combinations_with_replacement
returned [] instead of raising ValueError "r must be non-negative".  The same path read
r as a raw int64 field, so a float, str, None, list, tuple or bytes r was accepted or
misread instead of raising the index TypeError.  permutations also has to keep treating
a None r as "not given" (that is the default), while the two combinations() reject None.

Both general emitters now pass the r object to one runtime converter; it checks the type
and the sign before the pool is used.  Bounds, empty pools, bools, wide values, and r
reaching the call through an argument, a list item, an attribute and a dict value are
compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


BOUNDS = r'''import itertools


def show(tag, fn):
    try:
        print(tag, list(fn()))
    except Exception as e:
        print(tag, type(e).__name__, str(e))


xs = [1, 2, 3]
neg = 0 - 1
for r in (-3, -1, 0, 1, 3, 4):
    show("perm " + repr(r), lambda r=r: itertools.permutations(xs, r))
    show("comb " + repr(r), lambda r=r: itertools.combinations(xs, r))
    show("cwr " + repr(r), lambda r=r: itertools.combinations_with_replacement(xs, r))
show("perm no-r", lambda: itertools.permutations(xs))
show("perm None", lambda: itertools.permutations(xs, None))
show("perm kw None", lambda: itertools.permutations(xs, r=None))
show("comb None", lambda: itertools.combinations(xs, None))
show("cwr None", lambda: itertools.combinations_with_replacement(xs, None))
show("perm empty -1", lambda: itertools.permutations([], neg))
show("comb empty -1", lambda: itertools.combinations([], neg))
show("cwr empty -1", lambda: itertools.combinations_with_replacement([], neg))
show("perm empty 0", lambda: itertools.permutations([], 0))
show("comb empty 0", lambda: itertools.combinations([], 0))
show("cwr empty 0", lambda: itertools.combinations_with_replacement([], 0))
show("perm empty None", lambda: itertools.permutations([], None))
'''


TYPES_AND_SOURCES = r'''import itertools


class Box:
    pass


def show(tag, fn):
    try:
        print(tag, list(fn()))
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def perm(xs, r):
    return itertools.permutations(xs, r)


def comb(xs, r):
    return itertools.combinations(xs, r)


def cwr(xs, r):
    return itertools.combinations_with_replacement(xs, r)


xs = [1, 2]
vals = [True, False, 2.0, "2", None, [2], (2,), {"x": 1}, b"2"]
for i, r in enumerate(vals):
    show("perm v%d %s" % (i, type(r).__name__), lambda r=r: itertools.permutations(xs, r))
    show("comb v%d %s" % (i, type(r).__name__), lambda r=r: itertools.combinations(xs, r))
    show("cwr v%d %s" % (i, type(r).__name__), lambda r=r: itertools.combinations_with_replacement(xs, r))
box = Box()
show("perm attr", lambda: itertools.permutations(xs, box))
show("comb attr", lambda: itertools.combinations(xs, box))
show("cwr attr", lambda: itertools.combinations_with_replacement(xs, box))

xs = [1, 2, 3]
box.r = -1
box.n = None
d = {"r": -2, "n": None}
items = [-4, None, 2]
for name, fn in (("perm", perm), ("comb", comb), ("cwr", cwr)):
    show(name + " arg -1", lambda fn=fn: fn(xs, -1))
    show(name + " list -4", lambda fn=fn: fn(xs, items[0]))
    show(name + " attr -1", lambda fn=fn: fn(xs, box.r))
    show(name + " dict -2", lambda fn=fn: fn(xs, d["r"]))
show("perm arg None", lambda: perm(xs, None))
show("perm list None", lambda: itertools.permutations(xs, items[1]))
show("perm attr None", lambda: itertools.permutations(xs, box.n))
show("perm dict None", lambda: itertools.permutations(xs, d["n"]))
show("perm arg 2", lambda: perm(xs, items[2]))
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


class Pre126Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre126-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_bounds_and_none(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre126-ref-') as directory:
            out, _, _ = _cpython(directory, 'bounds', BOUNDS)
        self.assertIn(b'perm -1 ValueError r must be non-negative\n', out)
        self.assertIn(b'perm -3 ValueError r must be non-negative\n', out)
        self.assertIn(b'cwr empty -1 ValueError r must be non-negative\n', out)
        self.check('bounds', BOUNDS)

    def test_types_and_sources(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre126-ref-') as directory:
            out, _, _ = _cpython(directory, 'types_sources', TYPES_AND_SOURCES)
        self.assertIn(b'perm v2 float TypeError Expected int as r\n', out)
        self.assertIn(b'comb v2 float TypeError \'float\' object cannot be interpreted as an integer\n', out)
        self.assertIn(b'cwr v8 bytes TypeError \'bytes\' object cannot be interpreted as an integer\n', out)
        self.check('types_sources', TYPES_AND_SOURCES)


if __name__ == '__main__':
    unittest.main()
