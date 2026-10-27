"""pre326: the pre324 review's pre-existing class-scope differences.

The pre324 reviewer recorded these as already present before that job: a nested
class inside a function is refused; an async method in a class body is refused;
and a class-body ``for`` / ``with`` / ``try`` / ``global`` is refused.  CPython
runs all of them.  Reproducing the first on this tree shows that both builds
already refuse it at compile time with a named ``not in the subset`` message,
which the task allows, so no compiler change is needed.  The test pins the named
refusals of every recorded case and keeps a top-level class control matching
CPython, so a wrong output or an un-named failure is never accepted.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = ('a nested class definition',
            'a class body statement other than def/assignment/pass/docstring')

CASES = {
    'nested_class_method': ('''
def make():
    class C:
        def value(self):
            return 7
    return C().value()
print(make())
''', 'refused'),
    'nested_class_attr': ('''
def make():
    class C:
        x = 3
    return C.x
print(make())
''', 'refused'),
    'nested_class_init': ('''
def make(n):
    class C:
        def __init__(self, v):
            self.v = v
        def get(self):
            return self.v
    return C(n).get()
print(make(5))
''', 'refused'),
    'nested_class_never_called': ('''
def make():
    class C:
        pass
    return 0
print(make())
''', 'refused'),
    'nested_class_conditional': ('''
def make(flag):
    if flag:
        class C:
            x = 1
        return C.x
    return 2
print(make(True))
''', 'refused'),
    'nested_class_nested_function': ('''
def outer():
    def inner():
        class C:
            x = 4
        return C.x
    return inner()
print(outer())
''', 'refused'),
    'nested_class_in_method': ('''
class Holder:
    def make(self):
        class C:
            x = 5
        return C.x
print(Holder().make())
''', 'refused'),
    'async_method': ('''
class C:
    async def m(self):
        return 1
print("ok")
''', 'refused'),
    'class_for': ('''
class C:
    for i in range(3):
        pass
print("ok")
''', 'refused'),
    'class_with': ('''
class C:
    with open(__file__) as f:
        pass
print("ok")
''', 'refused'),
    'class_try': ('''
class C:
    try:
        x = 1
    except Exception:
        pass
print("ok")
''', 'refused'),
    'class_global': ('''
x = 0
class C:
    global x
    x = 3
print(x)
''', 'refused'),
    'top_level_class_control': ('''
class C:
    x = 3
    def value(self):
        return self.x
print(C().value())
''', 'ran'),
}


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre326(unittest.TestCase):
    def test_class_scope_pre_existing_refusals(self):
        for slug, (source, expected_mode) in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre326-') as directory:
                expected, status = run_cpython(directory, 'pre326_' + slug, source)
            modes = set()
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre326-') as directory:
                    built, exe = compile_source(directory, 'pre326_' + slug, source, general)
                    output = built.stdout + built.stderr
                    if expected_mode == 'refused':
                        self.assertNotEqual(built.returncode, 0, '%s built' % slug)
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertTrue(any(marker in output for marker in REFUSALS),
                                        output[-4000:])
                        modes.add('refused')
                    else:
                        self.assertEqual(built.returncode, 0, output[-4000:])
                        self.assertTrue(exe.exists(), '%s did not build' % slug)
                        ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected,
                                         ran.stdout + ran.stderr)
                        modes.add('ran')
            self.assertEqual(len(modes), 1, '%s builds disagree: %s' % (slug, sorted(modes)))


if __name__ == '__main__':
    unittest.main()
