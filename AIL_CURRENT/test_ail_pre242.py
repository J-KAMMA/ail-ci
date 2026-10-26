"""Pre-242: a module-level assignment rebinds a module function in direct calls.

A top-level ``def f`` was always called through the compiled function, so a later
``f = lambda: ...`` at module scope was ignored and ``f()`` still printed the old result.
The general path now binds the function value into the module slot at its ``def`` and routes a
call through the slot whenever the name is assigned at module scope, so rebinding works in
order, through another function, a list item, an attribute, a dict value and a conditional
statement, on both builds.  Rebinding a function that itself needs a function value the general
path cannot build (defaults/keywords at the call) is refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

PROGRAM = r'''def zero():
    return "old"


def one(x):
    return x + 1


def two(a, b):
    return a * b


def s(x):
    return "old:" + x


def t(x, y):
    return y + ":" + x


def a():
    return 1


def b(x):
    return x + 10


print(zero(), one(1), two(9, 4), s("a"))
zero = lambda: "new"
one = lambda x: x + 100
two = lambda a, b: a - b
s = t
print(zero(), one(1), two(9, 4), s("b", "a"))
print(a())
a = lambda: 102
print(a())


class Box:
    pass


fs = [lambda: 5]
d = {"k": lambda: 6}
box = Box()
box.fn = b


def pick(fn):
    return fn


a = fs[0]
print(a())
a = d["k"]
print(a())
a = box.fn
print(a(1))
a = pick(lambda: 7)
print(a())


def f():
    return 1


if True:
    f = lambda: 102
print(f())
g = one
one = lambda x: x * 2
print(g(5), one(5))


def nc():
    return 0


nc = 102
try:
    print(nc())
except TypeError as e:
    print("TypeError", e)
nc = None
try:
    nc()
except TypeError as e:
    print("TypeError", e)
'''

REFUSED = {
    'defaults': '''def f(a, b=3):
    return a + b


f = lambda a, b=10: a * b
print(f(2), f(2, 4))
''',
    'keyword_call': '''def f(a, b):
    return a - b


f = lambda a, b: a + b
print(f(b=2, a=5))
''',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    return built, exe


class Pre242Tests(unittest.TestCase):
    def test_module_level_function_rebinding_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre242-') as directory:
            want, rc, err = _cpython(directory, 'program', PROGRAM)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                name = 'program_' + ('g' if general else 'd')
                built, exe = _build(directory, name, PROGRAM, general)
                self.assertEqual(built.returncode, 0, '%s\n%s' % (general, (built.stdout + built.stderr)[-3000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, 'general=%s' % general)

    def test_unsupported_rebinding_forms_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre242-') as directory:
            for slug, text in REFUSED.items():
                want, rc, err = _cpython(directory, slug, text)
                self.assertEqual(rc, 0, err)
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe = _build(directory, name, text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, '%s general=%s\n%s' % (slug, general, output[-3000:]))
                    self.assertFalse(exe.exists(), '%s general=%s' % (slug, general))
                    self.assertIn('not in the subset:', output, '%s\n%s' % (slug, output[-3000:]))


if __name__ == '__main__':
    unittest.main()
