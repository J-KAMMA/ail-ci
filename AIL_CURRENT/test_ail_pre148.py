"""pre148: itertools combinators reject a negative r (DIFFERENCES C?-job-fuzz8-10220554-1).

The general path's ail_it_permutations / ail_it_combinations / ail_it_combinations_wr
returned an empty iterator for a negative r.  CPython constructs the iterator after
materializing the pool and then raises `ValueError: r must be non-negative` (verified:
the pool's __iter__ runs before the check).  All three now return
ail_raise_c(cx, AIL_B_VALUEERROR, "r must be non-negative"); r > n still gives an empty
iterator, as CPython does.  The typed path already raised in PoolStream.setup.

The programs cover a literal, a function argument, a list item, a dict value, an
attribute, a bool, the keyword form, empty pools, r=0, r>n, values that already worked,
and an uncaught ValueError (exit status 1).  Each is built on both builds and compared
with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NEGATIVE_LITERALS = r'''import itertools

try:
    itertools.permutations([1, 2], -1)
    print("perm no error")
except ValueError as e:
    print("perm VE:", e)
try:
    itertools.combinations([1, 2, 3], -2)
    print("comb no error")
except ValueError as e:
    print("comb VE:", e)
try:
    itertools.combinations_with_replacement([1, 2], -3)
    print("cwr no error")
except ValueError as e:
    print("cwr VE:", e)
try:
    itertools.permutations([], -1)
except ValueError as e:
    print("perm empty VE:", e)
try:
    itertools.combinations("", -4)
except ValueError as e:
    print("comb strempty VE:", e)

n = 0
for t in itertools.permutations([1, 2], 5):
    n += 1
print("perm r>n", n)
n = 0
for t in itertools.combinations([1, 2], 0):
    n += 1
print("comb r=0", n)
n = 0
for t in itertools.combinations_with_replacement([], 1):
    n += 1
print("cwr empty r=1", n)
'''

VIA_ARGUMENT = r'''import itertools


def perm_count(xs, r):
    n = 0
    try:
        for t in itertools.permutations(xs, r):
            n += 1
        return "n=%d" % n
    except ValueError as e:
        return "VE: " + str(e)


def comb_count(xs, r):
    n = 0
    try:
        for t in itertools.combinations(xs, r):
            n += 1
        return "n=%d" % n
    except ValueError as e:
        return "VE: " + str(e)


print(perm_count([1, 2, 3], -1))
print(perm_count([1, 2, 3], 2))
print(perm_count([], -5))
print(perm_count([1, 2], 10))
print(comb_count([1, 2, 3], -7))
print(comb_count([1, 2, 3], 3))
'''

VIA_LIST_DICT = r'''import itertools

rs = [-1, 2, 0]
n = 0
try:
    for t in itertools.combinations([1, 2, 3], rs[0]):
        n += 1
    print("comb list n", n)
except ValueError as e:
    print("comb list VE:", e)

d = {"r": -2}
try:
    for t in itertools.permutations([1, 2], d["r"]):
        pass
    print("perm dict no error")
except ValueError as e:
    print("perm dict VE:", e)

k = 3
try:
    for t in itertools.combinations_with_replacement([1, 2], -k):
        pass
    print("cwr expr no error")
except ValueError as e:
    print("cwr expr VE:", e)

n = 0
for t in itertools.combinations_with_replacement([1], 3):
    n += 1
print("cwr ok", n)
'''

VIA_ATTRIBUTE = r'''import itertools


class Box:
    def __init__(self, r):
        self.r = r


b = Box(-2)
n = 0
try:
    for t in itertools.permutations([1, 2, 3], b.r):
        n += 1
    print("perm attr n", n)
except ValueError as e:
    print("perm attr VE:", e)

c = Box(2)
n = 0
for t in itertools.combinations([1, 2, 3], c.r):
    n += 1
print("comb attr n", n)
'''

BOOL_WIDTH = r'''import itertools

n = 0
for t in itertools.combinations([1, 2, 3], False):
    n += 1
print("comb False", n)
n = 0
try:
    for t in itertools.permutations([1, 2], True):
        n += 1
    print("perm True", n)
except ValueError as e:
    print("perm True VE:", e)

xs = [1, 2, 3]
n = 0
for t in itertools.combinations(xs, len(xs)):
    n += 1
print("comb len", n)
n = 0
for t in itertools.permutations(xs):
    n += 1
print("perm default", n)
'''

KEYWORD = r'''import itertools

try:
    itertools.permutations([1, 2], r=-2)
except ValueError as e:
    print("perm kw VE:", e)
try:
    itertools.combinations([1, 2], r=-2)
except ValueError as e:
    print("comb kw VE:", e)
try:
    itertools.combinations_with_replacement([1, 2], r=-2)
except ValueError as e:
    print("cwr kw VE:", e)
'''

TYPED = r'''import itertools


def pc(xs: list[int], r: int) -> int:
    n = 0
    try:
        for t in itertools.permutations(xs, r):
            n += 1
    except ValueError:
        return -1
    return n


print(pc([1, 2, 3], -1))
print(pc([1, 2, 3], 2))
print(pc([1, 2, 3], 9))
'''

UNCAUGHT = r'''import itertools

print("before")
for t in itertools.permutations([1, 2], -1):
    print(t)
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


class Pre148Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre148-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_negative_literals(self):
        self.check('negative_literals', NEGATIVE_LITERALS)

    def test_via_argument(self):
        self.check('via_argument', VIA_ARGUMENT)

    def test_via_list_dict(self):
        self.check('via_list_dict', VIA_LIST_DICT)

    def test_via_attribute(self):
        self.check('via_attribute', VIA_ATTRIBUTE)

    def test_bool_width(self):
        self.check('bool_width', BOOL_WIDTH)

    def test_keyword(self):
        self.check('keyword', KEYWORD)

    def test_typed(self):
        self.check('typed', TYPED)

    def test_uncaught(self):
        self.check('uncaught', UNCAUGHT, rc=1)


if __name__ == '__main__':
    unittest.main()
