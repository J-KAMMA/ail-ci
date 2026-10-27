"""pre324: a class method default that reads an earlier class-body name.

CPython evaluates a default argument when the ``def`` statement runs, inside the
class body, so ``class C: x = 3; def m(self, a=x): ...`` keeps the class attribute
(3).  The general path hoists a non-literal default to module scope, before the
class exists, so it read the module global instead (100) or raised for a missing
one.  This path cannot evaluate a method default in the class namespace, so it now
refuses that construct by name on both builds.  Defaults that do not read an
earlier class-body name (a later class attribute, a module global, a lambda or
comprehension body) still match CPython, as does a module function's default.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'reads the class-body name'


def compile_source(directory, name, source, general=False):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre324(unittest.TestCase):
    REFUSED = {
        'direct': '''x = 100
class C:
    x = 3
    def m(self, a=x):
        return a
print(C().m())
''',
        'expression': '''x = 100
class C:
    x = 3
    y = 4
    def m(self, a=x + y):
        return a
print(C().m())
''',
        'with_init': '''x = 100
class C:
    x = 3
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'init_before_attr': '''x = 100
class C:
    def __init__(self):
        pass
    x = 3
    def m(self, a=x):
        return a
print(C().m())
''',
        'kwonly': '''x = 100
class C:
    x = 3
    def __init__(self):
        pass
    def m(self, *, a=x):
        return a
print(C().m())
''',
        'method_earlier': '''x = 100
class C:
    def x(self):
        return 7
    def m(self, a=x):
        return a(C())
print(C().m())
''',
        'alias_attr': '''x = 100
class C:
    x = 3
    y = x
    def __init__(self):
        pass
    def m(self, a=y):
        return a
print(C().m())
''',
        'list_item': '''x = 100
class C:
    x = [3][0]
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'dict_value': '''data = {"v": 3}
class C:
    x = data["v"]
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'attribute': '''class H:
    v = 3
h = H()
x = 100
class C:
    x = h.v
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'negative': '''x = 100
class C:
    x = -3
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'empty_list': '''x = [1]
class C:
    x = []
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'builtin_shadow': '''len = 100
class C:
    len = 5
    def __init__(self):
        pass
    def m(self, a=len):
        return a
print(C().m())
''',
        'comp_outer': '''x = 100
class C:
    x = 3
    def __init__(self):
        pass
    def m(self, a=[i for i in range(x)]):
        return a
print(C().m())
''',
        'lambda_default': '''x = 100
class C:
    x = 3
    def __init__(self):
        pass
    def m(self, f=lambda a=x: a):
        return f()
print(C().m())
''',
    }

    MATCH = {
        'later_attr': '''x = 100
class C:
    def __init__(self):
        pass
    def m(self, a=x):
        return a
    x = 3
print(C().m())
''',
        'unrelated_attr': '''x = 100
class C:
    y = 3
    def __init__(self):
        pass
    def m(self, a=x):
        return a
print(C().m())
''',
        'lambda_body': '''x = 100
class C:
    x = 3
    def __init__(self):
        pass
    def m(self, f=lambda: x):
        return f()
print(C().m())
''',
        'comp_body': '''x = 100
class C:
    x = 3
    def __init__(self):
        pass
    def m(self, a=[x for _ in range(2)]):
        return a
print(C().m())
''',
        'module_function': '''x = 100
class C:
    x = 3
def f(a=x):
    return a
print(f())
''',
        'literal_default': '''class C:
    x = 3
    def __init__(self):
        pass
    def m(self, a=7):
        return a + C.x
print(C().m())
''',
    }

    def test_class_default_reading_earlier_name_is_refused(self):
        for general in (False, True):
            for name, source in self.REFUSED.items():
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre324_' + name, source, general=general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())
                    self.assertIn(REFUSAL, built.stdout + built.stderr)
                    self.assertIn('method C.m', built.stdout + built.stderr)

    def test_unaffected_class_defaults_match_cpython(self):
        for name, source in self.MATCH.items():
            with tempfile.TemporaryDirectory() as directory:
                expected, status = run_cpython(directory, 'pre324_' + name, source)
            for general in (False, True):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built, exe = compile_source(directory, 'pre324_' + name, source, general=general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(ran.returncode, status, ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)


if __name__ == '__main__':
    unittest.main()
