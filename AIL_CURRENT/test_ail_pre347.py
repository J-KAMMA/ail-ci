"""pre347: a class-body comprehension target does not overwrite an enclosing name.

The reviewer of job rbpre304 recorded ``x = 99; class C: ys = [x for x in range(3)];
print(x, C.ys)``: both builds printed ``2 [0, 1, 2]`` where CPython prints
``99 [0, 1, 2]`` because a comprehension target is local to the comprehension.  The
comprehension-scope pass did not look inside a class body, so the target kept the
enclosing module's name slot.  Class bodies are now analysed in their enclosing
scope, which renames the target only when that name can clash.

Programs are built with the general path forced and with the default build; stdout
and the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'target_global': '''
x = 99
class C:
    ys = [x for x in range(3)]
print(x, C.ys)
''',
    'class_attribute_and_global': '''
x = 99
class C:
    x = 3
    ys = [x for x in range(x)]
    z = x
print(x, C.x, C.ys, C.z)
''',
    'class_attribute_target': '''
class C:
    x = 3
    ys = [x for x in range(4)]
    z = x
print(C.x, C.ys, C.z)
''',
    'later_class_attribute': '''
class C:
    ys = [x for x in range(3)]
    x = 9
print(C.ys, C.x)
''',
    'all_comprehensions': '''
x = 99
class C:
    a = [x for x in range(3)]
    b = {x for x in range(3)}
    c = {x: x * x for x in range(3)}
    d = list(x for x in range(3))
print(x, C.a, sorted(C.b), C.c, C.d)
''',
    'empty_and_negative': '''
x = 99
class C:
    a = [x for x in range(0)]
    b = [x for x in range(-3)]
    c = {x for x in range(0)}
    d = {x: x for x in range(0)}
print(x, C.a, C.b, sorted(C.c), C.d)
''',
    'multiple_generators': '''
x = 99
y = 50
class C:
    a = [(x, y) for x in range(2) for y in range(2)]
    b = [x + y for x in range(2) for y in range(2)]
print(x, y, C.a, C.b)
''',
    'conditions': '''
x = 99
class C:
    ys = [x for x in range(5) if x < 2]
    zs = [x for x in range(5) if x > 1]
print(x, C.ys, C.zs)
''',
    'nested_comprehensions': '''
x = 50
class C:
    ys = [[x for x in range(2)] for x in range(2)]
print(x, C.ys)
''',
    'class_name_target': '''
class C:
    ys = [C for C in range(3)]
print(C.ys, C.__name__)
''',
    'builtin_name_target': '''
len = 5
class C:
    ys = [len for len in range(3)]
print(len, C.ys)
''',
    'multiple_classes': '''
x = 1
class A:
    xs = [x for x in range(2)]
class B:
    xs = [x for x in range(3)]
print(x, A.xs, B.xs)
''',
    'module_iterable': '''
vals = [1, 2, 3]
class C:
    xs = [v for v in vals]
print(C.xs)
''',
    'routes': '''
x = 99
def show(v):
    return v
class Box:
    v = x
class C:
    ys = [x for x in range(3)]
payload = [x]
mapping = {"x": x}
class D:
    v = x
print(x, show(x), payload[0], Box.v, D.v, mapping["x"], C.ys)
''',
    'module_and_function_control': '''
x = 99
ys = [x for x in range(3)]
def f():
    x = 5
    zs = [x for x in range(2)]
    return x, zs
print(x, ys, f())
''',
}


# A lambda nested in a class-body comprehension reads the comprehension target, not the global of
# the same name.  Renaming the target would remove the shared name the closure pass uses to see
# the clash, and the class-attribute path would then recurse while compiling itself, so the target
# is left unrenamed and the construct keeps the base tree's named closure refusal.
LAMBDA_REFUSALS = {
    'lambda_target': '''
x = 99
class C:
    ys = [(lambda: x)() for x in range(3)]
print(x, C.ys)
''',
    'nested_lambda_target': '''
x = 99
class C:
    ys = [(lambda: (lambda: x)())() for x in range(3)]
print(x, C.ys)
''',
    'lambda_in_condition': '''
x = 99
class C:
    ys = [x for x in range(3) if (lambda: x)()]
print(x, C.ys)
''',
    'lambda_as_list_item': '''
x = 99
class C:
    ys = [lambda: x for x in range(3)]
print(x, [f() for f in C.ys])
''',
}


def _run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=1200, env=env)


def _build_and_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre347Tests(unittest.TestCase):
    def test_lambda_reading_a_class_target_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre347-') as directory:
            for slug, text in LAMBDA_REFUSALS.items():
                self.assertEqual(_run_cpython(directory, slug, text)[1], 0, slug)
                for general in (True, False):
                    _, built = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' %
                                        (slug, general, output))
                    self.assertIn('not in the subset', output, '%s (general=%s)\n%s' %
                                  (slug, general, output))
                    self.assertNotIn('RecursionError', output, '%s (general=%s)\n%s' %
                                     (slug, general, output))

    def test_class_body_comprehension_target_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre347-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()
