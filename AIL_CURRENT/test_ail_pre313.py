"""pre313: bytearray *= changes the object itself, as CPython's __imul__ does.

The rbpre281 review recorded `ba = bytearray(b"ab"); z = ba; ba *= 2`: AIL rebound `ba` to the
result of `__mul__`, so an alias still showed `b"ab"` where CPython extends the bytearray in
place.  The general path's bytearray prelude now has `__imul__`; both builds are checked,
including empty, zero, negative, bool and larger counts, aliases, non-int operands and values
arriving through an argument, a list item, an attribute and a dict value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _cpython(directory, name, source):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))


def _build(directory, name, source, unified):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory) / name
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          capture_output=True, text=True, timeout=900, env=env), exe


PROGRAMS = {
    'aliases': '''
ba = bytearray(b"ab")
z = ba
ba *= 2
print(ba, z, ba is z)

e = bytearray()
ze = e
e *= 5
print(e, ze, e is ze)

n = bytearray(b"xy")
zn = n
n *= 0
print(n, zn, n is zn)

m = bytearray(b"pq")
zm = m
m *= -3
print(m, zm, m is zm)

o = bytearray(b"rs")
zo = o
o *= True
print(o, zo, o is zo)

t = bytearray(b"uv")
zt = t
t *= 3
print(t, zt, t is zt)

b = b"ab"
zb = b
b *= 2
print(b, zb, b is zb)
''',
    'routes': '''
def scale(ba, n):
    z = ba
    ba *= n
    return z

x = bytearray(b"ab")
print(scale(x, 2), x)

xs = [bytearray(b"cd")]
zs = xs[0]
xs[0] *= 3
print(xs[0], zs, xs[0] is zs)

class Box:
    def __init__(self, ba):
        self.ba = ba

box = Box(bytearray(b"ef"))
zb = box.ba
box.ba *= 2
print(box.ba, zb, box.ba is zb)

d = {"k": bytearray(b"gh")}
zd = d["k"]
d["k"] *= 4
print(d["k"], zd, d["k"] is zd)

item = [bytearray(b"ij")]
zi = item[0]
item[0] *= 2
print(item[0], zi, item[0] is zi)
''',
    'types': '''
ba = bytearray(b"ab")
try:
    ba *= 2.0
except TypeError as e:
    print(type(e).__name__, str(e))
try:
    ba *= "2"
except TypeError as e:
    print(type(e).__name__, str(e))
try:
    ba *= [2]
except TypeError as e:
    print(type(e).__name__, str(e))
try:
    ba *= None
except TypeError as e:
    print(type(e).__name__, str(e))
print(ba)

c = bytearray(b"ab")
c *= False
print(c)
d = bytearray(3)
d *= 2
print(d)
e = bytearray([1, 2])
e *= 2
print(e)
''',
}


class Pre313BytearrayInplaceTests(unittest.TestCase):
    def test_bytearray_inplace_repeat_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre313-') as directory:
            for slug, source in PROGRAMS.items():
                want = _cpython(directory, slug, source)
                self.assertEqual(want.returncode, 0, want.stderr)
                for unified in (False, True):
                    built, exe = _build(directory, '%s_%d' % (slug, unified), source, unified)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(got.returncode, want.returncode, got.stderr)
                    self.assertEqual(got.stdout, want.stdout, '%s unified=%s\n%s'
                                     % (slug, unified, got.stderr))
                    self.assertEqual(got.stderr, '')


if __name__ == '__main__':
    unittest.main()
