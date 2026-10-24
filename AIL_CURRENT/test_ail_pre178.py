"""Pre-178: setattr() through a @property has CPython's descriptor behaviour.

A read-only property (a property without a setter) refuses setattr() with
"property 'x' of 'C' object has no setter"; a property with a setter runs that
setter.  The general path used to write straight into the instance attribute
table, so a read-only property silently accepted the value and a setter was
never called.  The same descriptor table now backs direct attribute assignment,
getattr() and inherited properties.  This module keeps the recorded case
(`setattr(c, "x", v)` on a read-only property) and the boundaries the fix
implies: a setter's validation, inherited and overridden properties, names
reaching setattr through an argument, a list item, an attribute and a dict
value, and values of every scalar/container type.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SETATTR_PROPERTY = r'''class ReadOnly:
    def __init__(self, y):
        self.y = y

    @property
    def x(self):
        return self.y * 10


class Writable:
    def __init__(self):
        self.seen = None

    @property
    def x(self):
        return self.seen

    @x.setter
    def x(self, v):
        if v is not None and not isinstance(v, (int, float, str, list, bool)):
            raise ValueError("bad value")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0:
            raise ValueError("negative")
        self.seen = v


class Child(ReadOnly):
    pass


class Grand(Child):
    pass


class Plain:
    def __init__(self):
        self.a = 1


def put(obj, name, v):
    setattr(obj, name, v)


def main():
    ro = ReadOnly(3)
    values = [5, 0, -1, "s", [1, 2], None, True, 2.5]
    for i in range(len(values)):
        v = values[i]
        try:
            put(ro, "x", v)
            print("ro stored", ro.x)
        except AttributeError as e:
            print("ro AttributeError", e, ro.x)
    w = Writable()
    for i in range(len(values)):
        v = values[i]
        try:
            setattr(w, "x", v)
            print("w", type(w.x).__name__, w.x)
        except ValueError as e:
            print("w ValueError", e, w.x)
    pair = ("x", 7)
    put(w, pair[0], pair[1])
    print("tuple-name", w.x)
    holder = Plain()
    holder.name = "x"
    put(w, holder.name, 8)
    print("attr-name", w.x)
    table = {"n": "x", "v": 9}
    put(w, table["n"], table["v"])
    print("dict-name", w.x)
    for obj in (Child(1), Grand(2)):
        try:
            setattr(obj, "x", 4)
            print("inherited stored")
        except AttributeError as e:
            print("inherited AttributeError", e, obj.x)
    p = Plain()
    setattr(p, "a", 2)
    setattr(p, "b", 3)
    print("plain", p.a, p.b, getattr(p, "a"), getattr(p, "b"))


main()
'''


GETATTR_DEFAULT = r'''class A:
    def __init__(self):
        self.data = ["x", 1]
        self.last = "x"
        self.table = {"n": "x"}

    @property
    def x(self):
        raise AttributeError("boom")

    @property
    def y(self):
        raise ValueError("bad")

    @property
    def z(self):
        return 42


def name_from_arg(n):
    return getattr(a, n, "from-arg")


def alias(a, key, d):
    return getattr(a, key, d)


a = A()
nx = "x"
ny = "y"
nz = "z"
for d in (0, -1, 3.5, "s", [1, 2], {"k": "v"}, None, True):
    print("dflt", type(d).__name__, repr(getattr(a, nx, d)))
    print("named", repr(name_from_arg(nx)))
print("list-name", repr(getattr(a, a.data[0], a.data[1])))
print("attr-name", repr(getattr(a, a.last, 7)))
print("dict-name", repr(getattr(a, a.table["n"], 8)))
print("alias", repr(alias(a, nx, 9)))
print("ok", getattr(a, nz, 5))
try:
    print(getattr(a, nx))
except AttributeError as e:
    print("AE", e)
try:
    print(getattr(a, ny, 5))
except ValueError as e:
    print("VE", e)
print("still-ok", getattr(a, nz, 5))
'''

LONG_CLASS_NAME = 'C' * 130
LONG_PROP_NAME = 'p' * 300
LONG_NAMES = ('class %s:\n' % LONG_CLASS_NAME) + (
    '    @property\n'
    '    def short(self):\n'
    '        return 1\n'
    '\n'
    '    @property\n'
    '    def %s(self):\n' % LONG_PROP_NAME) + (
    '        return 2\n'
    '\n'
    'o = %s()\n' % LONG_CLASS_NAME) + (
    'for name in ("short", "%s", "%s"):\n' % (LONG_PROP_NAME, LONG_PROP_NAME[:-1])) + (
    '    try:\n'
    '        setattr(o, name, 3)\n'
    '        print("stored", name)\n'
    '    except AttributeError as e:\n'
    '        print(len(str(e)), str(e))\n'
    'print(o.short)\n'
)


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


class Pre178Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre178-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_setattr_property(self):
        self.check('setattr_property', SETATTR_PROPERTY)

    def test_getattr_property_default(self):
        self.check('getattr_property_default', GETATTR_DEFAULT)

    def test_property_error_long_names(self):
        self.check('property_error_long_names', LONG_NAMES)


if __name__ == '__main__':
    unittest.main()
