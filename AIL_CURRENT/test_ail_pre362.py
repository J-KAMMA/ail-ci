"""pre362: a lambda in a comprehension keeps the comprehension's variable.

The reviewer of job pre347 recorded ``x = 99; class C: ys = [(lambda: x)() for x in
range(3)]; print(x, C.ys)``: the base tree refused it by name, while the new class-body
rename pass removed the shared name and the class-attribute path then recursed (an
uncaught ``RecursionError``).  Two causes are fixed here:

* a name a lambda body reads from an enclosing comprehension is now resolved like any
  other comprehension name, so renaming the target renames the lambda's read too (a
  function-local target no longer makes the lambda read the global: the function form
  used to print ``(99, [99, 99, 99])`` where CPython prints ``(99, [0, 1, 2])``);
* compiling a class attribute no longer re-enters its own value: a call through a value
  in a class body skipped the class whose attribute is being compiled, instead of
  ``call_value`` -> ``_call_class`` -> the same attribute -> ... (``RecursionError``).

A class-body comprehension whose target a lambda genuinely reads still cannot share the
cell, so it is refused by name (``not in the subset: closures nested too deeply to settle
their shared names``), as before, with no ``RecursionError``.

Programs are built with the general path forced and with the default build; stdout and
the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'function_target': '''
def f():
    x = 99
    ys = [(lambda: x)() for x in range(3)]
    return x, ys
print(f())
''',
    'function_no_clash': '''
def f():
    ys = [(lambda: x)() for x in range(3)]
    return ys
print(f())
''',
    'function_nested_lambda': '''
def f():
    x = 99
    ys = [(lambda: (lambda: x)())() for x in range(3)]
    return x, ys
print(f())
''',
    'function_default': '''
def f():
    x = 99
    ys = [(lambda y=x: y)() for x in range(3)]
    return x, ys
print(f())
''',
    'module_default': '''
x = 99
ys = [(lambda y=x: y)() for x in range(3)]
print(x, ys)
''',
    'class_parameter_shadows_target': '''
x = 99
class C:
    z = x
    ys = [(lambda x: x)(7) for x in range(3)]
print(x, C.z, C.ys)
''',
    'class_lambda_ignores_target': '''
x = 99
class C:
    ys = [(lambda: 7)() for x in range(3)]
print(x, C.ys)
''',
    'class_lambda_parameter_only': '''
class C:
    ys = [(lambda i: i * 2)(7) for i in range(3)]
print(C.ys)
''',
    'class_call_through_lambda': '''
class A:
    k = 3
    def __init__(self):
        self.v = 4
class B:
    ys = [(lambda: A().v)() for i in range(2)]
print(B.ys, A.k)
''',
    'argument_route': '''
def f(n):
    x = n
    zs = [(lambda: x)() for x in range(2)]
    return x, zs
print(f(7))
''',
    'list_item_route': '''
def f(xs):
    x = xs[0]
    zs = [(lambda: x)() for x in range(2)]
    return x, zs
print(f([42]))
''',
    'attribute_route': '''
class Box:
    v = 8
def f(b):
    x = b.v
    zs = [(lambda: x)() for x in range(2)]
    return x, zs
print(f(Box()))
''',
    'dict_value_route': '''
def f(d):
    x = d['k']
    zs = [(lambda: x)() for x in range(2)]
    return x, zs
print(f({'k': 3}))
''',
    'strings_route': '''
s = 1
def f():
    s = 5
    return s, [(lambda: s)() for s in ['a', 'b']]
print(s, f())
''',
    'empty_and_negative': '''
def f():
    x = 5
    a = [(lambda: x)() for x in range(0)]
    b = [(lambda: x)() for x in range(-2)]
    return x, a, b
print(f())
''',
    'two_targets': '''
def f():
    x = 1
    y = 2
    return [(lambda: (x, y))() for x in range(2) for y in range(2)]
print(f())
''',
    'late_binding': '''
def f():
    x = 99
    fs = [lambda: x for x in range(3)]
    return x, [g() for g in fs]
print(f())
''',
    'nested_function': '''
x = 99
def outer():
    x = 3
    def inner():
        return [(lambda: x)() for x in range(2)]
    return x, inner()
print(x, outer())
''',
}

# A class-body comprehension whose target a lambda really reads cannot share the cell on
# this path: the target stays unrenamed and the construct keeps the named refusal.
REFUSALS = {
    'class_review_case': '''
x = 99
class C:
    ys = [(lambda: x)() for x in range(3)]
print(x, C.ys)
''',
    'class_nested_lambda': '''
x = 99
class C:
    ys = [(lambda: (lambda: x)())() for x in range(3)]
print(x, C.ys)
''',
    'class_set_condition': '''
x = 99
class C:
    ys = {x for x in range(3) if (lambda: x)() >= 1}
print(x, sorted(C.ys))
''',
    'class_dict_comp': '''
x = 99
class C:
    ys = {x: (lambda: x)() for x in range(3)}
print(x, sorted(C.ys.items()))
''',
    'class_genexp': '''
x = 99
class C:
    ys = list((lambda: x)() for x in range(3))
print(x, C.ys)
''',
    'class_dict_value': '''
x = 99
class C:
    ys = [(lambda: x)() for x in range(3)]
    d = {'x': x}
print(x, C.ys, C.d)
''',
    'class_second_lambda': '''
x = 99
class C:
    ys = [(lambda: x)() for x in range(3)]
    f = lambda: x
print(x, C.ys, C.f())
''',
    'module_target': '''
x = 99
ys = [(lambda: x)() for x in range(3)]
print(x, ys)
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


class Pre362Tests(unittest.TestCase):
    def test_function_and_class_lambda_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre362-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_class_body_lambda_target_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre362-') as directory:
            for slug, text in REFUSALS.items():
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


if __name__ == '__main__':
    unittest.main()
