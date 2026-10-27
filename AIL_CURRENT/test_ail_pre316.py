"""pre316: an attribute-assigned partial called on an instance is the field, not a method.

The rbrbpre61 review recorded that `c.f = partial(add, 3); c.f(4)` was refused by name.  The
general path dispatched `.f()` as a class method and never looked at the instance table when no
class defined `f`; CPython finds the plain callable field first (it is called without the
receiver, exactly like a field that shadows a method).  The lookup is now also used when the
class has no method of that name, for a statically known receiver and for one that arrives
through an argument or another field.  Unsupported keyword/starred calls stay refused by name.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre316-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general, built.stdout))
            test.assertIn('not in the subset', built.stdout + built.stderr, (name, general))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre316-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout.replace(b'\r\n', b'\n'),
                             (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))


MATCH = {
    'field_partial': '''from functools import partial


def add(a, b):
    return a + b


def three(a, b, c):
    return a * 100 + b * 10 + c


class C:
    pass


c = C()
c.f = partial(add, 3)
c.g = partial(lambda x: x * 2, 21)
c.h = partial(three, 1, 2)
c.k = partial(add, b=10)
c.z = partial(add)
print(c.f(4), c.g(), c.h(7), c.k(5), c.z(2, 8))
print(c.f(-7), c.k(-10), c.z(-1, 1))
print(c.f(2 ** 62), c.f(-2 ** 62))
''',
    'routes_alias': '''from functools import partial


def add(a, b):
    return a + b


def make(v):
    return partial(add, v)


class Box:
    pass


box = Box()
box.v = 100
vals = [7]
d = {"v": 11}
c = Box()
c.f = make(5)
c.g = partial(add, vals[0])
c.h = partial(add, box.v)
c.i = partial(add, d["v"])
print(c.f(1), c.g(2), c.h(3), c.i(4))
alias = c
print(alias.f(2))
c.f = make(-3)
print(c.f(5), alias.f(5))
e = Box()
e.f = make(2 ** 61)
print(e.f(2 ** 61))
try:
    Box().f(1)
except AttributeError as exc:
    print("AttributeError", exc)
''',
    'errors': '''from functools import partial


def add(a, b):
    return a + b


class C:
    pass


c = C()
c.f = 5
try:
    c.f(1)
except TypeError as exc:
    print("TypeError", exc)
try:
    C().f(1)
except AttributeError as exc:
    print("AttributeError", exc)
''',
    'shadow_method': '''from functools import partial


def add(a, b):
    return a + b


class C:
    def f(self, x):
        return x + 1

    def g(self, x):
        return x + 2


c = C()
print(c.f(4), c.g(4))
c.f = partial(add, 10)
print(c.f(4), c.g(4))
c.f = lambda x: x * 3
print(c.f(4), c.g(4))
print(C().f(5), C().g(5))
''',
    'receiver_routes': '''from functools import partial


def add(a, b):
    return a + b


class C:
    pass


def call(c, v):
    return c.f(v)


def wrap(c):
    return c


c = C()
c.f = partial(add, 10)
print(call(c, 5), wrap(c).f(6))
box = C()
box.c = c
print(wrap(box.c).f(7))
''',
}

REFUSED = {
    'keyword': 'from functools import partial\n\n\ndef add(a, b):\n    return a + b\n\n\n'
               'class C:\n    pass\n\n\nc = C()\nc.f = partial(add, 10)\nprint(c.f(b=5))\n',
    'starred': 'from functools import partial\n\n\ndef add(a, b):\n    return a + b\n\n\n'
               'class C:\n    pass\n\n\nc = C()\nc.f = partial(add, 10)\nprint(c.f(*[5]))\n',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class AttributeAssignedPartialCall(unittest.TestCase):
    def test_matching_programs(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)

    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)


if __name__ == '__main__':
    unittest.main()
