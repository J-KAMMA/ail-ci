"""pre127: a parameter, local, cell or closure binding shadows a module-level class.

`expr_Name` treated every name that matched a class definition as the class value,
even when the current activation had its own local slot for that name.  `U.m` inside
`def via_param(U): ...` therefore read the module-level class U instead of the
argument, and both builds raised `AttributeError: 'type' object has no attribute 'm'`
where CPython returns the instance's class attribute or method result.

The programs read the value through an argument, a list item, an attribute and a dict
value, cover a local, a cell and a nonlocal closure binding, and keep an unshadowed
class value (a factory returning `U()`) working.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SHADOWED_CLASS_NAME = r'''class U:
    m = 42

    def value(self):
        return self.m + 1


class Box:
    def __init__(self, u):
        self.u = u

    def read(self, U):
        return U.m


def via_param(U):
    return U.m


def via_method(U):
    return U.value()


def via_arg(U, factor):
    return U.value() * factor


def outer(U):
    def inner(U):
        return U.m + U.value()

    return inner(U)


def make():
    return U()


def main():
    u = U()
    print(via_param(u), via_method(u))
    print(via_arg(u, 3))
    print(outer(u))
    print(Box(u).read(u))
    print([U()][0].value(), make().value())
    print(via_param([u][0]), via_method(Box(u).u), via_param({"u": u}["u"]))
    print(Box(u).read([u][0]))


main()
'''

SIMPLE_PARAMETER = r'''class U:
    def m(self):
        return 42


def f(U: object):
    return U.m()


print(f(U()))
'''

LOCAL_CELL_CLOSURE = r'''class U:
    tag = "class"


class V:
    def tag(self):
        return "instance"


def local():
    U = V()
    return U.tag()


def cell():
    U = V()

    def inner():
        return U.tag()

    return inner()


def nonlocal_cell():
    U = V()

    def inner():
        nonlocal U
        U = V()
        return U.tag()

    return inner()


print(local(), cell(), nonlocal_cell())
'''


SELF_REFERENTIAL_LOCAL = r'''class U:
    m = 3

    def value(self):
        return 4


def plain():
    U = U()
    return U.m, U.value()


def annotated():
    U: object = U()
    return U.m, U.value()


def tuple_target():
    U, x = U(), 5
    return U.m, U.value(), x


for f in (plain, annotated, tuple_target):
    try:
        f()
    except UnboundLocalError:
        print("UnboundLocalError")
'''

LOOP_TARGET_SHADOWS_CLASS = r'''class U:
    m = 8

    def value(self):
        return 9


def f(items):
    total = 0
    for U in items:
        total = total + U.m
    return total, U().value()


try:
    print(f([U(), U()]))
except TypeError:
    print("TypeError")
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


class Pre127Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre127-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_shadowed_class_name(self):
        self.check('shadowed_class_name', SHADOWED_CLASS_NAME)

    def test_simple_parameter(self):
        self.check('simple_parameter', SIMPLE_PARAMETER)

    def test_local_cell_closure(self):
        self.check('local_cell_closure', LOCAL_CELL_CLOSURE)

    def test_self_referential_local(self):
        self.check('self_referential_local', SELF_REFERENTIAL_LOCAL)

    def test_loop_target_shadows_class(self):
        self.check('loop_target_shadows_class', LOOP_TARGET_SHADOWS_CLASS)


if __name__ == '__main__':
    unittest.main()
