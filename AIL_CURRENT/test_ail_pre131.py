"""pre131: negative r for itertools.permutations / combinations / combinations_with_replacement.

CPython raises `ValueError: r must be non-negative` for every one of the three when the
materialized pool is already a sequence; a non-iterable pool still raises its TypeError
first, because CPython materializes the pool before it looks at r.  The general path's
runtime iterators returned an empty result instead of raising, so a negative r was a
silent difference on both builds (the default build falls back to the general path when
r is computed at run time).

Covered here: negative literals, r=0, r larger than the pool, an empty pool, and negative
values arriving through an argument, a list item, an attribute and a dict value, plus the
positive results that must stay unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


NEGATIVE_R = r'''from itertools import permutations, combinations, combinations_with_replacement

class Box:
    r = -2

def via_arg(xs, r):
    try:
        print("arg", list(permutations(xs, r)))
    except ValueError as e:
        print("arg", str(e))

def via_comb_arg(xs, r):
    try:
        print("argc", list(combinations(xs, r)))
    except ValueError as e:
        print("argc", str(e))

def via_wr_arg(xs, r):
    try:
        print("argw", list(combinations_with_replacement(xs, r)))
    except ValueError as e:
        print("argw", str(e))

o = Box()
L = [1, -1]
D = {"r": -3}

for r in (-1, -2, 0, 1, 3, 4):
    try:
        print("p", r, list(permutations([1, 2, 3], r)))
    except ValueError as e:
        print("p", r, type(e).__name__, str(e))
    try:
        print("c", r, list(combinations([1, 2, 3], r)))
    except ValueError as e:
        print("c", r, type(e).__name__, str(e))
    try:
        print("w", r, list(combinations_with_replacement([1, 2, 3], r)))
    except ValueError as e:
        print("w", r, type(e).__name__, str(e))

for r in (o.r, L[1], D["r"]):
    try:
        print("psrc", r, list(permutations([1, 2, 3], r)))
    except ValueError as e:
        print("psrc", r, type(e).__name__, str(e))
    try:
        print("csrc", r, list(combinations([1, 2, 3], r)))
    except ValueError as e:
        print("csrc", r, type(e).__name__, str(e))
    try:
        print("wsrc", r, list(combinations_with_replacement([1, 2, 3], r)))
    except ValueError as e:
        print("wsrc", r, type(e).__name__, str(e))

for r in (-1, 0):
    try:
        print("pe", r, list(permutations([], r)))
    except ValueError as e:
        print("pe", r, type(e).__name__, str(e))
    try:
        print("ce", r, list(combinations([], r)))
    except ValueError as e:
        print("ce", r, type(e).__name__, str(e))
    try:
        print("we", r, list(combinations_with_replacement([], r)))
    except ValueError as e:
        print("we", r, type(e).__name__, str(e))

via_arg("abc", -1)
via_comb_arg((1, 2), -4)
via_wr_arg([1], -2)
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


class Pre131Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre131-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_negative_r_raises(self):
        self.check('negative_r', NEGATIVE_R)


if __name__ == '__main__':
    unittest.main()
