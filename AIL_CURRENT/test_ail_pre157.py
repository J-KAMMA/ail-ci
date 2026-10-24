"""pre157: attributes read through a class value (an alias, argument, list item, ...).

The general path knew a class only as (name, base): `C.x` where `C` was the class name
itself was resolved at compile time, but any other way a class reaches the read (`A = C;
A.x`, a parameter, a list/dict element, an instance attribute, a cell or a nonlocal) fell
through to the instance attribute table and raised AttributeError.  Class attributes are
now registered on the class object by name and their shared module slot, so the read walks
the base chain exactly as CPython does.  `__name__`, getattr()/hasattr() and the missing
attribute error text are covered too.

Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CLASS_ATTRIBUTES = r'''class B:
    k = 1
    text = "base"
    items = [1, 2]
    table = {"a": 1}
    pair = (3, 4)
    flag = True
    nothing = None


class C(B):
    k = 2
    items = [3]


def read(cls):
    return cls.k


def read_name(cls):
    return cls.__name__


def read_via_getattr(cls, name):
    return getattr(cls, name)


def make_class():
    return C


def outer_local():
    c = C
    return c.k


def outer_cell():
    c = C

    def inner():
        return c.k

    return inner()


def outer_nonlocal():
    c = B

    def inner():
        nonlocal c
        c = C
        return c.k

    return inner()


class Holder:
    def __init__(self, cls):
        self.cls = cls


def main():
    A = C
    print(A.k, read(C), read(A))
    print(C.text, A.text, C.items, A.items)
    print(A.__name__, getattr(A, "__name__"))
    print(getattr(A, "k"), getattr(A, "missing", "dflt"), hasattr(A, "k"), hasattr(A, "missing"))
    xs = [C]
    d = {"c": C}
    print(xs[0].k, d["c"].text)
    h = Holder(C)
    print(h.cls.k, h.cls.text)
    print(outer_local(), outer_cell(), outer_nonlocal())
    print(read_via_getattr(A, "text"))
    M = make_class()
    print(M.k, M.table, M.pair, M.flag, M.nothing)
    first, second = C, B
    print(first.k, second.k)
    for k in (C, B):
        print(k.text, k.k)
    try:
        print(A.missing)
    except AttributeError as e:
        print("AttributeError", e)
    print(B.k, B.items)
    B.items.append(4)
    print(C.items, A.items)
    print(read_name(C))


main()
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


class Pre157Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre157-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_class_attributes(self):
        self.check('class_attributes', CLASS_ATTRIBUTES)


if __name__ == '__main__':
    unittest.main()
