"""A class value's `__name__` (fuzz67, found before job pre6).

`C.__name__` raised `AttributeError: 'type' object has no attribute '__name__'` on both builds.
The general path already keeps a class value as a real CLASS object with its class-statement
name; attribute reads now return it, including when the value arrives through an argument, a
list item, an instance attribute or a dict value. A class-body `__name__ = ...` assignment is
ignored for the attribute, as CPython does (it only lands in the class dict).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CLASS_NAMES = r'''class Base:
    pass


class Child(Base):
    pass


class Renamed:
    __name__ = "not-the-name"
    value = 3


class Failure(Exception):
    pass


class Holder:
    pass


def name_of(k):
    return k.__name__


def main():
    h = Holder()
    h.k = Child
    d = {"base": Base, "child": Child, "renamed": Renamed, "failure": Failure}
    xs = [Base, Child, Renamed, Failure]
    print(Base.__name__, Child.__name__, Renamed.__name__, Failure.__name__)
    print(name_of(Base), name_of(Child), name_of(Renamed), name_of(Failure))
    print([k.__name__ for k in xs])
    print(h.k.__name__)
    print(d["base"].__name__, d["child"].__name__, d["renamed"].__name__, d["failure"].__name__)
    print(name_of(xs[0]), name_of(xs[1]), name_of(xs[2]), name_of(xs[3]))
    k = Child
    print(k.__name__, k is Child)
    k = Base
    print(k.__name__, k is Base)
    print(type(Base).__name__)


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


class Pre24Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre24-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_class_value_name(self):
        self.check('class_value_name', CLASS_NAMES)

    def test_class_body_own_name_is_nameerror(self):
        self.check('class_body_own_name', r'''class C:
    x = C.__name__


print(C.x)
''', rc=1)

    def test_rebound_class_name(self):
        self.check('rebound_class_name', r'''class C:
    pass


print(C.__name__)
C = 5
try:
    print(C.__name__)
except AttributeError as e:
    print("AE", type(e).__name__)
''')

    def test_conditional_rebinding(self):
        self.check('conditional_rebinding', r'''class C:
    pass


if len("x") == 2:
    C = 5
print(C.__name__)
if len("xy") == 2:
    C = 5
try:
    print(C.__name__)
except AttributeError:
    print("AE")
''')

    def test_global_rebinding_in_function(self):
        self.check('global_rebinding', r'''class C:
    pass


def rebind():
    global C
    C = 5


rebind()
try:
    print(C.__name__)
except AttributeError:
    print("AE")
''')

    def test_parameter_shadowing_class_name(self):
        self.check('parameter_shadowing', r'''class C:
    pass


class D(C):
    pass


def f(C):
    return C.__name__


print(f(D), f(C))
''')


if __name__ == '__main__':
    unittest.main()
