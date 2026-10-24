"""pre153: class attributes through a class value that is not a direct class-name expression.

A reviewer of job pre127 found that `U.m` raised `AttributeError: 'type' object has no
attribute 'm'` on both builds whenever the class value reached the attribute read through
anything but the literal class name: `global U`, a parameter, a list/tuple item, a dict
value, an attribute, or a returned alias.  The class object carried only its name and base;
the attributes lived in a module slot used to fill instances, and the general runtime's
attribute helper accepted only instances/exception values.

The class object now carries a class-attribute table (filled at the class-definition
statement, walked through the base chain on read), and `ail_inst_getattr` consults it for
`AIL_T_CLASS`.  Each program below is built on both builds and compared with CPython, which
also keeps the cases that already matched (p4 comprehension/loop shadowing, p25 a class
constructor called through a shadowed parameter) locked in.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INDIRECT = r'''class U:
    m = 5

    def value(self):
        return 7


def through_param(c):
    return c.m


def through_global():
    global U
    return U.m, U().value()


class Holder:
    def __init__(self, c):
        self.c = c


def alias():
    return U


print(through_param(U))
print(through_global())
print([U][0].m, (U, 1)[0].m)
print({"k": U}["k"].m, {"a": {"b": U}}["a"]["b"].m)
print(Holder(U).c.m)
print(alias().m, U.m, U().m)


class B:
    m = "s"


class D(B):
    pass


print(through_param(D), D.m, D().m, through_param(B))
'''

VALUES = r'''class U:
    e = []
    f = 1.5
    n = None
    b = False
    neg = -3
    xs = ["a"]


def through_param(c):
    return c.e, c.f, c.n, c.b, c.neg, len(c.xs)


def grow(c):
    c.xs.append("b")
    return c.xs


print(through_param(U))
print(grow(U), U.xs, U().xs, len(U.xs))
print(through_param(U))
'''

UNCHANGED = r'''class U:
    m = 5


def f():
    for x in [1]:
        pass
    return [x.m for x in [U()]]


print(f())


class A:
    def __init__(self):
        self.m = 5


def g(A):
    return A().m


print(g(A))
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


class Pre153Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre153-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_indirect_class_attribute(self):
        self.check('indirect', INDIRECT)

    def test_class_attribute_values(self):
        self.check('values', VALUES)

    def test_unchanged_cases(self):
        self.check('unchanged', UNCHANGED)


if __name__ == '__main__':
    unittest.main()
