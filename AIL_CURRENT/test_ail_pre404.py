"""pre404: a lambda in a comprehension follows a renamed comprehension target.

The pre380 review recorded that a lambda nested in a comprehension never followed a
renamed comprehension target.  ``x = 99; ys = [(lambda: x)() for x in range(3)]``
kept the lambda reading the outer ``x`` and printed ``[99, 99, 99]`` where CPython
prints ``[0, 1, 2]``.  The body's free loads are now resolved against the enclosing
comprehensions, so a function-scope program captures the renamed target and matches
CPython.  At module scope a closure over a comprehension variable is not built, so
the construct is refused by name at compile time instead of silently reading the
wrong variable.

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
    'function_scope': '''
def f():
    x = 99
    ys = [(lambda: x)() for x in range(3)]
    return x, ys
print(f())
''',
    'range_argument': '''
def f(n):
    x = 99
    ys = [(lambda: x)() for x in range(n)]
    return x, ys
print(f(3))
''',
    'list_item': '''
def f():
    x = 99
    rows = [[10, 20], [30]]
    ys = [(lambda: x)() for x in rows[1]]
    return x, ys
print(f())
''',
    'attribute': '''
class P:
    items = [4, 5]
def f():
    x = 99
    p = P()
    ys = [(lambda: x)() for x in p.items]
    return x, ys
print(f())
''',
    'dict_value': '''
def f():
    x = 99
    d = {'k': [6, 7]}
    ys = [(lambda: x)() for x in d['k']]
    return x, ys
print(f())
''',
    'set_comp': '''
def f():
    x = 99
    s = {(lambda: x)() for x in range(3)}
    return x, sorted(s)
print(f())
''',
    'dict_comp': '''
def f():
    x = 99
    d = {x: (lambda: x)() for x in range(2)}
    return x, d
print(f())
''',
    'generator_consumed': '''
def f():
    x = 99
    ys = list((lambda: x)() for x in range(3))
    return x, ys
print(f())
''',
    'condition_reads_target': '''
def f():
    x = 99
    ys = [x for x in range(4) if (lambda: x)() > 1]
    return x, ys
print(f())
''',
    'nested_same_name': '''
def f():
    x = 99
    ys = [[(lambda: x)() for x in range(2)] for x in range(2)]
    return x, ys
print(f())
''',
    'two_targets': '''
def f():
    x = 99
    y = -1
    zs = [(lambda: (x, y))() for x in range(2) for y in range(2)]
    return x, y, zs
print(f())
''',
    'empty_negative_string': '''
def f():
    x = 99
    a = [(lambda: x)() for x in range(0)]
    b = [(lambda: x)() for x in range(-2)]
    s = 'outer'
    c = [(lambda: s)() for s in 'ab']
    return x, a, b, s, c
print(f())
''',
    'walrus_body': '''
def f():
    x = 99
    ys = [(lambda: (y := x))() for x in range(3)]
    return x, ys
print(f())
''',
    'nested_lambda': '''
def f():
    x = 99
    ys = [(lambda: (lambda: x)())() for x in range(3)]
    return x, ys
print(f())
''',
    'module_default_control': '''
x = 99
ys = [(lambda v=x: v)() for x in range(3)]
print(x, ys)
''',
    'module_outer_read_control': '''
x = 99
ys = [(lambda: x)() for i in range(3)]
print(x, ys)
''',
    'module_argument_control': '''
x = 99
ys = [(lambda v: v * x)(i) for i in range(3)]
print(x, ys)
''',
    'class_default_control': '''
x = 99
class C:
    ys = [(lambda v=x: v)() for x in range(3)]
print(x, C.ys)
''',
}

# At module scope the compiler does not build a closure over a comprehension variable.
REFUSALS = {
    'module_scope': '''
x = 99
ys = [(lambda: x)() for x in range(3)]
print(x, ys)
''',
    'module_list_item': '''
x = 99
rows = [[10, 20], [30]]
ys = [(lambda: x)() for x in rows[1]]
print(x, ys)
''',
    'module_attribute': '''
class P:
    items = [4, 5]
x = 99
ys = [(lambda: x)() for x in P.items]
print(x, ys)
''',
    'module_dict_comp': '''
x = 99
d = {x: (lambda: x)() for x in range(2)}
print(x, d)
''',
    'module_nested': '''
x = 99
ys = [[(lambda: x)() for x in range(2)] for x in range(2)]
print(x, ys)
''',
    'module_condition': '''
x = 99
ys = [x for x in range(4) if (lambda: x)() > 1]
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


class Pre404Tests(unittest.TestCase):
    def test_lambda_body_follows_renamed_target(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre404-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_module_scope_closure_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre404-') as directory:
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
