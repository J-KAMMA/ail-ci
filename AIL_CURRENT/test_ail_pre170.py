"""pre170: duplicate class-body assignments read through a class value.

The general path used to register every class-body assignment but return the first match when the
class was reached through an alias, an argument, a list/dict item or getattr(), while CPython keeps
the last definition (`class C: x = 1; x = 2`).  The class object now carries its class-body entries
in source order and the runtime lookup scans each class backwards, so the last definition wins.

Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DUP = r'''class C:
    x = 1
    x = 2


A = C
print(C.x, A.x, getattr(C, "x"), getattr(A, "x"))


class Base:
    k = 1
    y = 9


class D(Base):
    k = 4
    y = 2
    k = 6


B = D
print(D.k, B.k, B.y, getattr(B, "y"))
print(hasattr(B, "k"), hasattr(B, "missing"))


class Empty:
    pass


E = Empty
print(hasattr(E, "x"), getattr(E, "missing", "dflt"))
'''

SOURCES = r'''class B:
    k = 1
    items = [1, 2]
    table = {"a": 1}


class C(B):
    k = 2
    items = [3]


class Holder:
    def __init__(self, cls):
        self.cls = cls


def read(cls):
    return cls.k


A = C
xs = [C, B]
d = {"c": C}
h = Holder(C)
print(A.k, read(C), read(A), xs[0].k, xs[1].k, d["c"].k, h.cls.k)
print(A.items, d["c"].items, h.cls.items, A.table)
C.items.append(4)
print(B.items, A.items, d["c"].items)
print(A.__name__, getattr(A, "__name__"))
try:
    print(A.nope)
except AttributeError as e:
    print("AttributeError", e)
'''

SHADOW = r'''class A:
    x = 1


class B:
    x = 2


def local_alias():
    A = B
    return A.x


def param_alias(A):
    return A.x


def branch_alias(flag):
    if flag:
        C = A
    else:
        C = B
    return C.x


print(local_alias(), param_alias(B), param_alias(A), branch_alias(0), branch_alias(1))
A = B
print(A.x)


class P:
    x = 10


class Q:
    x = 20


def global_rebind():
    global P
    P = Q
    return P.x


print(global_rebind(), P.x)
'''

ARRAY = r'''class B:
    x = 1
    y = 2


class C(B):
    x = 5
    x = 6


def entry(xs):
    A = C
    b = B
    print(A.x, b.y, getattr(A, "y"), C.x)
'''


def _cpython(directory, name, text, args=()):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)] + list(args), capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general, run_args=()):
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
    got = subprocess.run([str(exe)] + list(run_args), capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre170Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre170-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_duplicate_class_attributes(self):
        self.check('dup', DUP)

    def test_class_value_sources(self):
        self.check('sources', SOURCES)

    def test_shadowed_or_rebound_class_name(self):
        self.check('shadow', SHADOW)

    def test_array_entry_initialises_class_attributes(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre170-') as directory:
            empty = Path(directory) / 'empty'
            empty.write_bytes(b'')
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'array_' + ('g' if general else 'd'),
                                                ARRAY, general, (str(empty),))
                self.assertIsNotNone(got, build_err)
                self.assertEqual(got, (b'6 2 2 6\n', 0), build_err)


if __name__ == '__main__':
    unittest.main()
