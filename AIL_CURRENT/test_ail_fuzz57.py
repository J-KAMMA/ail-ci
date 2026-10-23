"""Differential round 57: assigning to a read-only property raises CPython's AttributeError.

`obj.x = v` where `x` is a `@property` without a setter silently stored an ordinary
instance attribute: the assignment printed a later `obj.x` unchanged, and the error
CPython raises (`property 'x' of 'C' object has no setter`) never appeared. The general
runtime now dispatches every CLASS-level property owner in most-derived-first order: a
setter is called when that class has one, otherwise `ail2_prop_no_setter` raises with the
instance's own class name. The typed path refuses the assignment by name (it has no
property setters); the default build falls back to the general path. Programs with a
setter and ordinary attributes keep their previous behaviour.

Found with small programs compared against CPython on both builds: the error reached the
code through a variable, a list item, an attribute and a dict value, and through an
inherited property (the message names the subclass). Properties with setters still work
through the same sources, for zero, negative, huge and wrong-typed values.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

READONLY_SOURCES = r'''class Base:
    def __init__(self, v):
        self._x = v

    @property
    def x(self):
        return self._x


class Child(Base):
    pass


class Box:
    pass


def attempt(o):
    try:
        o.x = 99
        print("stored", o.x)
    except AttributeError as e:
        print("AttributeError", e)


def set_value(o, v):
    try:
        o.x = v
        print("stored", type(v).__name__)
    except AttributeError as e:
        print("AttributeError", type(v).__name__, e)


def main() -> None:
    c = Base(1)
    xs = [Child(2), c]
    b = Box()
    b.holder = c
    d = {"c": c}
    attempt(c)
    attempt(xs[0])
    attempt(xs[1])
    attempt(b.holder)
    attempt(d["c"])
    for v in [0, -1, 10 ** 18, True, 1.5, "s", [1], {"a": 1}, None]:
        set_value(c, v)
    print(c.x, xs[0].x, b.holder.x, d["c"].x)
    print("done")


main()
'''

READONLY_UNCAUGHT = r'''class C:
    def __init__(self):
        self._x = 3

    @property
    def x(self):
        return self._x


def main() -> None:
    c = C()
    print(c.x)
    alias = c
    alias.x = 10
    print("after", alias.x)


main()
'''

SETTER_SOURCES = r'''class Temp:
    def __init__(self, c):
        self._c = c

    @property
    def c(self):
        return self._c

    @c.setter
    def c(self, v):
        if v < 0:
            raise ValueError("negative")
        self._c = v


class Box:
    pass


def set_via(t, v):
    t.c = v


def main() -> None:
    t = Temp(0)
    print(t.c)
    for v in [5, 0, 10 ** 18, 2]:
        set_via(t, v)
        print(t.c)
    xs = [t]
    xs[0].c = 7
    b = Box()
    b.t = t
    b.t.c = 8
    d = {"t": t}
    d["t"].c = 9
    print(xs[0].c, b.t.c, d["t"].c)
    try:
        t.c = -3
    except ValueError as e:
        print("ValueError", e)
    print(t.c)
    print("done")


main()
'''

NESTED_GETTERS = r'''class Inner:
    def __init__(self, n):
        self._n = n

    @property
    def value(self):
        return self._n


class Outer:
    def __init__(self):
        self.items = [Inner(0), Inner(-2)]
        self.table = {"a": Inner(3)}

    @property
    def first(self):
        return self.items[0].value

    @property
    def empty(self):
        return ""


def main() -> None:
    o = Outer()
    print(o.first, o.items[1].value, o.table["a"].value, o.empty)
    o.items[1]._n = 7
    print(o.items[1].value)
    print("done")


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


class Fuzz57Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz57-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_readonly_property_sources(self):
        self.check('readonly_sources', READONLY_SOURCES)

    def test_readonly_property_uncaught(self):
        self.check('readonly_uncaught', READONLY_UNCAUGHT, rc=1)

    def test_property_setters(self):
        self.check('setter_sources', SETTER_SOURCES)

    def test_nested_property_getters(self):
        self.check('nested_getters', NESTED_GETTERS)


if __name__ == '__main__':
    unittest.main()
