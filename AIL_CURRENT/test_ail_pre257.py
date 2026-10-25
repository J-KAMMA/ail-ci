"""pre257: a nested function calls an outer local callable that shadows a module-level name.

The pre244 review recorded that a closure over an outer local callable printed the module-level
function's result instead of the local value (`1` where CPython prints `101`).  Two causes were
involved on this tree: the tuple pass's lambda-alias lowering removed the lambda assignment even
though calls inside a nested scope were not rewritten, and the general path's call dispatch chose
a module-level function of the same spelling before a captured (by-value or nonlocal) name.  The
tuple pass now leaves such an assignment as written, and the call path calls the captured value.

The cases below cover the local assigned after and before the nested def, a parameter, a builtin
and a module function shadowed by the local, two lambdas closing over each other, calls with
arguments, and the local callable reaching the closure through an argument, a list item, an
attribute and a dict value, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

PROGRAMS = {
    'module_def_shadow': '''def f():
    return 1

def outer():
    def inner():
        return f()
    f = lambda: 101
    return inner()

print(outer())
''',
    'parameter_shadow': '''def f():
    return 1

def outer(f):
    def inner():
        return f()
    return inner()

print(outer(lambda: 101))
''',
    'local_before_inner': '''def f():
    return 1

def outer():
    f = lambda: 101
    def inner():
        return f()
    return inner()

print(outer())
''',
    'nested_def_then_lambda': '''def outer():
    def f():
        return 1
    def inner():
        return f()
    f = lambda: 101
    return inner()

print(outer())
''',
    'builtin_shadow': '''def outer():
    def inner():
        return len([1, 2, 3])
    len = lambda x: 101
    return inner()

print(outer())
''',
    'lambda_closure_before': '''def f():
    return 1

def outer():
    g = lambda: f()
    f = lambda: 101
    return g()

print(outer())
''',
    'lambda_closure_after': '''def f():
    return 1

def outer():
    f = lambda: 101
    g = lambda: f()
    return g()

print(outer())
''',
    'arguments': '''def f():
    return 1

def outer():
    def inner(x):
        return f(x) + 1
    f = lambda x: x * 10
    return inner(4)

print(outer())
''',
    'flow_argument': '''def f():
    return 1

def outer(source):
    f = source
    def inner():
        return f()
    return inner()

print(outer(lambda: 101))
''',
    'flow_list': '''def f():
    return 1

def outer(source):
    f = source[0]
    def inner():
        return f()
    return inner()

print(outer([lambda: 101]))
''',
    'flow_attribute': '''def f():
    return 1

class Box:
    def __init__(self, v):
        self.v = v

def outer(source):
    f = source.v
    def inner():
        return f()
    return inner()

print(outer(Box(lambda: 101)))
''',
    'flow_dict': '''def f():
    return 1

def outer(source):
    f = source["cb"]
    def inner():
        return f()
    return inner()

print(outer({"cb": lambda: 101}))
''',
    'module_control': '''def f():
    return 7

def outer():
    def inner():
        return f()
    return inner()

print(outer())
''',
    'alias_control': '''def outer():
    f = lambda x: x + 1
    return f(41)

print(outer())
''',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre257Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre257-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                 % (slug, general, build_err))

    def test_outer_local_callable_closure(self):
        for slug in ('module_def_shadow', 'parameter_shadow', 'local_before_inner',
                     'nested_def_then_lambda', 'builtin_shadow', 'lambda_closure_before',
                     'lambda_closure_after', 'arguments'):
            self.check(slug, PROGRAMS[slug])

    def test_outer_local_callable_value_flows(self):
        for slug in ('flow_argument', 'flow_list', 'flow_attribute', 'flow_dict'):
            self.check(slug, PROGRAMS[slug])

    def test_controls(self):
        for slug in ('module_control', 'alias_control'):
            self.check(slug, PROGRAMS[slug])


if __name__ == '__main__':
    unittest.main()
