"""pre363: a lambda called inside a class-body comprehension no longer crashes the compiler.

The pre347 review recorded, as pre-existing, an uncaught ``RecursionError`` for a
class-body comprehension whose lambda uses a default (``[(lambda v=x: v)() for x in
range(3)]``) or a shadowing parameter (``[(lambda x: x)(i) for i in range(3)]``), where
CPython runs the program.  ``call_value`` expanded the construct-a-class branch for every
call through a value; compiling that branch re-evaluates the class attribute whose value
is still being compiled and recursed.  A lambda literal can never be a class, so its call
now goes straight to the value call, and a re-entrant class-attribute read is refused by
name instead of recursing.  The comprehension-scope guard also ignores lambda defaults
(evaluated in the comprehension scope, so they follow the target's rename) and names the
lambda binds itself, so the examples above now match CPython instead of clobbering the
enclosing name.

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
    'lambda_default': '''
x = 99
class C:
    ys = [(lambda v=x: v)() for x in range(3)]
print(x, C.ys)
''',
    'lambda_param_shadow': '''
x = 99
class C:
    ys = [(lambda x: x)(i) for i in range(3)]
print(x, C.ys)
''',
    'lambda_arg_target': '''
x = 99
class C:
    ys = [(lambda x: x)(x) for x in range(3)]
print(x, C.ys)
''',
    'lambda_no_target': '''
x = 99
class C:
    ys = [(lambda: 7)() for x in range(3)]
print(x, C.ys)
''',
    'all_comprehension_kinds': '''
x = 99
class C:
    a = [(lambda v=x: v)() for x in range(2)]
    b = {(lambda v=x: v)() for x in range(2)}
    c = {(lambda v=x: v)(): x for x in range(2)}
    d = list((lambda v=x: v)() for x in range(2))
print(x, C.a, sorted(C.b), sorted(C.c.items()), C.d)
''',
    'nested_lambda_default': '''
x = 99
class C:
    ys = [(lambda w=(lambda v=x: v): w())() for x in range(3)]
print(x, C.ys)
''',
    'empty_and_negative': '''
x = 99
class C:
    a = [(lambda v=x: v)() for x in range(0)]
    b = [(lambda v=x: v)() for x in range(-2)]
print(x, C.a, C.b)
''',
    'default_then_attribute': '''
x = 99
class C:
    ys = [(lambda v=x: v)() for x in range(2)]
    z = x
print(x, C.ys, C.z)
''',
    'module_lambda_call_control': '''
class P:
    v = 7
f = (lambda: 42)()
p = P()
print(f, p.v)
''',
}

# A lambda that reads the comprehension target in its body is still left unrenamed, so the
# closure pass refuses it by name (pre347's guard), never with a RecursionError.
REFUSALS = {
    'lambda_body_target': '''
x = 99
class C:
    ys = [(lambda: x)() for x in range(3)]
print(x, C.ys)
''',
    'lambda_in_condition': '''
x = 99
class C:
    ys = [x for x in range(3) if (lambda: x)()]
print(x, C.ys)
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


class Pre363Tests(unittest.TestCase):
    def test_class_body_lambda_calls_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre363-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertNotIn('RecursionError', build_err or '')
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_lambda_reading_target_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre363-') as directory:
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
