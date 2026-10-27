"""pre327: a slice of an instance reached through an unknown value.

The pre323 reviewer recorded that user-class slicing through a ``for`` / ``with`` /
tuple-binding route already failed on the base with a runtime
``NotImplementedError`` for in-range bounds, while CPython passes a slice object to
``__getitem__``.  The general path only asked for its slice prelude when the
receiver's class was static, so a value of unknown kind (a parameter, a loop
target, a with target or an unpacked item) took the old ``ail_op_getslice`` route.
It now requests the prelude and checks the instance tag at run time.

The direct out-of-int64 literal (including a slice bound) stays a named compile-time
refusal, as it already was on the base.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES = {
    'routes': '''
class C:
    def __init__(self, n):
        self.items = list(range(n))
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def __getitem__(self, i):
        if isinstance(i, slice):
            return (i.start, i.stop, i.step)
        return self.items[i]


class H:
    pass


def cut(x):
    return x[1:3]


def cutvar(x, lo, hi, st):
    return x[lo:hi:st]


c = C(6)
alias = c
holder = H()
holder.c = c
d = {"c": c}
xs = [c]
print(cut(c), cut(alias), cut(holder.c), cut(d["c"]), cut(xs[0]))
print(cutvar(c, None, None, None), cutvar(c, -4, -1, 2), cutvar(c, 4, 1, -1))
for item in [c]:
    print(cut(item))
with C(2) as w:
    print(cut(w))
t, = [c]
print(cut(t))
''',
    'bounds': '''
class C:
    def __init__(self, n):
        self.items = list(range(n))
    def __getitem__(self, i):
        return (i.start, i.stop, i.step, self.items[i])


def cut(x, a, b, s):
    return x[a:b:s]


for n in (0, 1, 5):
    c = C(n)
    print(n, cut(c, None, None, None), cut(c, None, None, -1))
    print(n, cut(c, -100, 100, 1), cut(c, 100, -100, -2), cut(c, 2, 2, 1))
r = list(range(7))
c = C(7)
print(cut(c, r[0], r[-1], r[2]), cut(c, -r[-1], 0, -1))
print(cut(c, True, False, True))
''',
    'builtins': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


def cut(x, a, b, s):
    return x[a:b:s]


for v in ([0, 1, 2, 3, 4], (0, 1, 2, 3, 4), "abcde", b"abcde", bytearray(b"abcde"), range(5)):
    print(cut(v, None, None, None), cut(v, 1, 4, 2), cut(v, -2, None, 1), cut(v, None, None, -1))
''',
    'types': '''
class A:
    pass


class B:
    def __getitem__(self, i):
        return "B"


class D(B):
    pass


def cut(x):
    return x[1:2]


for v in (B(), D(), A(), 5, 2.5, None):
    try:
        print(cut(v))
    except Exception as e:
        print(type(e).__name__)
''',
    'assign_delete': '''
class C:
    def __init__(self):
        self.items = list(range(6))
    def __getitem__(self, i):
        return self.items[i]
    def __setitem__(self, i, v):
        self.items[i] = v
    def __delitem__(self, i):
        del self.items[i]


def setcut(x):
    x[1:4] = [9]


def delcut(x):
    del x[::2]


c = C()
alias = c
items = [c]
d = {"c": c}
for target in (c, alias, items[0], d["c"]):
    setcut(target)
    print(target.items)
delcut(c)
print(c.items, alias.items)
''',
    'slice_fields': '''
class C:
    def __getitem__(self, i):
        return i


def f(x):
    return x[1:2]


s = f(C())
print(s.start, s.stop, s.step, repr(f(C())))
print(f(C()).start is None, f(C()).step is None)
''',
    'direct_literal': '''
print(9223372036854775808)
a = [1, 2, 3]
print(a[9223372036854775808:])
''',
    'huge_computed_bound': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


def cut(x):
    return x[2 ** 63:]


print(cut(C()))
''',
}

REFUSALS = ('int64 literal out of range', 'int64 constant out of range')


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre327(unittest.TestCase):
    def test_instance_slice_through_unknown_value(self):
        for slug, source in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre327-') as directory:
                expected, status = run_cpython(directory, 'pre327_' + slug, source)
            modes = set()
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre327-') as directory:
                    built, exe = compile_source(directory, 'pre327_' + slug, source, general)
                    output = built.stdout + built.stderr
                    if built.returncode != 0:
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertTrue(any(marker in output for marker in REFUSALS),
                                        output[-4000:])
                        modes.add('refused')
                    else:
                        self.assertTrue(exe.exists(), '%s did not build' % slug)
                        ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected,
                                         ran.stdout + ran.stderr)
                        modes.add('ran')
            self.assertEqual(len(modes), 1, '%s builds disagree: %s' % (slug, sorted(modes)))


if __name__ == '__main__':
    unittest.main()
