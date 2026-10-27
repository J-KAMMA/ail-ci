"""Pre-281: repeating an empty sequence by a huge count finishes at once (job pre281).

The pre271 review noted that ``xs *= n`` grew a runtime guard for a non-empty list.  On
this tree an empty sequence with a huge count still ran the repeat loop ``count`` times:
``xs = []; xs *= 10**18`` (and the plain ``[] * 10**18``, and the empty str/tuple forms)
never returned, while CPython returns the empty sequence immediately.  The repeat paths
now skip the loop when the sequence has no elements, so an empty sequence stays empty for
any count.  The checks cover ``*=`` and ``*``, list/tuple/str/bytes/bytearray, counts
arriving through an argument, a list item, an attribute and a dict value, and the
non-empty/negative/zero/alias cases that must keep working.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EMPTY_REPEATS = r'''BIG = 1000000000000000000

x = []
x *= BIG
print(x)

y = []
print(y * BIG)

t = ()
t *= BIG
print(t)
print(() * BIG)

s = ""
s *= BIG
print(repr(s))
print(repr("" * BIG))

b = b""
b *= BIG
print(b)
print(b"" * BIG)

ba = bytearray()
ba *= BIG
print(bytes(ba))
print(bytes(bytearray() * BIG))
'''

EMPTY_ROUTES = r'''BIG = 1000000000000000000


def mul(a, n):
    a *= n
    return a


print(mul([], BIG))
print(mul("", BIG))
print(mul((), BIG))
print(mul(b"", BIG))

holder = [[]]
holder[0] *= BIG
print(holder)

class C:
    pass

c = C()
c.x = []
c.x *= BIG
print(c.x)

d = {"k": ""}
d["k"] *= BIG
print(repr(d["k"]))

xs = [0, BIG, 2]
for n in xs[1:2]:
    z = []
    z *= n
    print(z)

print([[]][0] * BIG)
print({"x": ()}["x"] * BIG)
'''

NONEMPTY = r'''for n in (-2, -1, 0, 1, 2, 5, True, False):
    x = [1, 2]
    x *= n
    print(n, x)

print([1, 2] * 3, (1, 2) * 3, "ab" * 3, "ab" * 0, "" * 5)
print([] * 5, () * 5, "" * 5, b"" * 5)
print([] * -5, () * -5, "" * -5)
'''

ALIASES = r'''x = [1, 2]
y = x
x *= 3
print(x, y, x is y)

s = "ab"
v = s
s *= 3
print(s, v, s == v)

b = b"ab"
c = b
b *= 3
print(b, c, b == c)

t = (1, 2)
u = t
t *= 3
print(t, u, t == u)
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


class Pre281Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre281-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_empty_sequence_huge_count(self):
        self.check('empty_repeats', EMPTY_REPEATS)

    def test_empty_sequence_huge_count_through_routes(self):
        self.check('empty_routes', EMPTY_ROUTES)

    def test_nonempty_counts_unchanged(self):
        self.check('nonempty', NONEMPTY)

    def test_aliases_unchanged(self):
        self.check('aliases', ALIASES)


if __name__ == '__main__':
    unittest.main()
