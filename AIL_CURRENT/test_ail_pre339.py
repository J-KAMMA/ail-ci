"""pre339: a class alias used as a receiver of a bound-method field is refused by name.

The pre314 review recorded as pre-existing that a class alias did not reach the field/method
collision screen: ``Alias = C; Alias().f()`` compiled, then stopped with
``AttributeError: 'C' object has no attribute 'g'`` (CPython calls the stored bound method and
prints 55).  The alias reaches the same collision directly, through an assigned receiver, an
alias chain, tuple unpacking, a function-local alias, an argument, a list item, an attribute or a
dict value.  Each such call is now refused by name on both builds.  An alias of a class without
the collision, a lambda field, and a name shadowed by a parameter or local assignment keep
CPython's result.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
REFUSAL = 'also stores an instance field named f'

REFUSED = {
    'module_alias': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias = C
print(Alias().f())
''',
    'assigned_receiver': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias = C
c = Alias()
print(c.f())
''',
    'alias_chain': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return -5
    def f(self):
        return 102
A = C
B = A
print(B().f())
''',
    'tuple_unpack': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias, n = C, 1
print(Alias().f())
''',
    'function_local': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 0
    def f(self):
        return 102
def main():
    Alias = C
    print(Alias().f())
main()
''',
    'argument': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias = C
def call(k):
    return k().f()
print(call(Alias))
''',
    'list_item': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias = C
ks = [Alias]
print(ks[0]().f())
''',
    'attribute': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias = C
class H:
    def __init__(self):
        self.k = Alias
print(H().k().f())
''',
    'dict_value': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
Alias = C
d = {"k": Alias}
print(d["k"]().f())
''',
}

MATCH = {
    'lambda_field': '''class C:
    def __init__(self):
        self.f = lambda: 11
    def f(self):
        return 102
Alias = C
print(Alias().f())
''',
    'unrelated_alias': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
class D:
    def f(self):
        return 7
Alias = D
print(Alias().f())
''',
    'parameter_shadow': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
class D:
    def f(self):
        return 7
Alias = C
def call(Alias):
    return Alias().f()
print(call(D))
''',
    'local_shadow': '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
class D:
    def f(self):
        return 7
Alias = C
def call():
    Alias = D
    return Alias().f()
print(call())
''',
    'no_feature': '''class C:
    def __init__(self, v):
        self.v = v
    def twice(self):
        return self.v * 2
Alias = C
print(Alias(21).twice())
''',
}


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return (ran.stdout.replace(b'\r\n', b'\n'), ran.returncode), ran.stderr.decode('utf-8', 'replace')


class Pre339(unittest.TestCase):
    def test_class_alias_bound_method_field_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre339-') as directory:
            for slug, text in REFUSED.items():
                for general in (False, True):
                    with self.subTest(case=slug, general=general):
                        got, output = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                             text, general)
                        self.assertIsNone(got, output)
                        self.assertIn(REFUSAL, output)
                        self.assertNotIn('Traceback', output)
                        self.assertNotIn('AttributeError', output)

    def test_supported_aliases_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre339-') as directory:
            for slug, text in MATCH.items():
                want = subprocess.run([sys.executable, '-B', '-c', text], capture_output=True,
                                      timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
                self.assertEqual(want.returncode, 0, want.stderr)
                expected = want.stdout.replace(b'\r\n', b'\n')
                for general in (False, True):
                    with self.subTest(case=slug, general=general):
                        got, output = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                             text, general)
                        self.assertIsNotNone(got, output)
                        self.assertEqual(got, (expected, 0), output)


if __name__ == '__main__':
    unittest.main()
