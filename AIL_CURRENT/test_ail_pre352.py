"""pre352: a class alias used as a receiver of a bound-method field is refused by name.

The pre339 review recorded as pre-existing that an alias assignment inside a ``try`` still
stopped at run time with ``AttributeError: 'C' object has no attribute 'g'`` where CPython calls
the stored bound method and prints 55.  The field/method collision screen only resolved a
receiver written as a class name, not one reached through a class alias.

Alias resolution here follows a name bound by plain assignments in its own scope, including a
chain and an assignment inside a ``try`` with a non-class handler value.  A name with several
class bindings (a rebinding, a conditional or a loop target) or a parameter/local shadow is not
resolved, so those programs keep CPython's result.  The alias can reach the receiver directly,
through a chain or tuple unpack, a function argument, a list item, an attribute or a dict value.
The second pre-existing item from the same review (a function called before a later rebinding of
an ancestor name) is unchanged and is not covered here.
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

C = '''class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
'''
D = '''class D:
    def f(self):
        return 7
'''

REFUSED = {
    'try_except_pass': C + '''try:
    Alias = C
except Exception:
    pass
print(Alias().f())
''',
    'try_finally': C + '''try:
    Alias = C
finally:
    pass
print(Alias().f())
''',
    'try_handler_value': C + '''try:
    Alias = C
except Exception:
    Alias = None
print(Alias().f())
''',
    'direct_alias': C + '''Alias = C
print(Alias().f())
''',
    'alias_chain': C + '''A = C
B = A
print(B().f())
''',
    'tuple_unpack': C + '''Alias, n = C, 1
print(Alias().f(), n)
''',
    'local_alias': C + '''def main():
    Alias = C
    return Alias().f()
print(main())
''',
    'argument': C + '''Alias = C
def call(k):
    return k().f()
print(call(Alias))
''',
    'list_item': C + '''Alias = C
ks = [Alias]
print(ks[0]().f())
''',
    'attribute': C + '''Alias = C
class H:
    def __init__(self):
        self.k = Alias
print(H().k().f())
''',
    'dict_value': C + '''Alias = C
d = {"k": Alias}
print(d["k"]().f())
''',
}

MATCH = {
    'no_feature': '''class C:
    def __init__(self, v):
        self.v = v
    def twice(self):
        return self.v * 2
Alias = C
print(Alias(21).twice())
''',
    'other_class': C + D + '''Alias = D
print(Alias().f())
''',
    'reassign_other': C + D + '''Alias = C
Alias = D
print(Alias().f())
''',
    'dead_branch': C + D + '''Alias = D
if False:
    Alias = C
print(Alias().f())
''',
    'for_target': C + D + '''Alias = C
for Alias in [D]:
    print(Alias().f())
''',
    'local_shadow_rhs': C + D + '''def f():
    C = D
    Alias = C
    return Alias().f()
print(f())
''',
    'parameter_shadow': C + D + '''def f(C):
    Alias = C
    return Alias().f()
print(f(D))
''',
    'module_rebind': C + D + '''C = D
Alias = C
print(Alias().f())
''',
    'kwonly_shadow': C + D + '''Alias = C
def call(*, Alias=D):
    return Alias().f()
print(call())
''',
    'conditional_reassign': C + D + '''Alias = D
flag = len([]) == 1
if flag:
    Alias = C
print(Alias().f())
''',
    'other_argument': C + D + '''def call(k):
    return k().f()
print(call(D))
''',
    'other_list_item': C + D + '''ks = [D]
print(ks[0]().f())
''',
    'other_dict_value': C + D + '''d = {"k": D}
print(d["k"]().f())
''',
}


def compile_source(directory, name, source, general=False):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre352(unittest.TestCase):
    def test_aliased_collision_is_refused_by_name(self):
        for general in (False, True):
            for slug, source in REFUSED.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre352-') as directory:
                    built, exe = compile_source(directory, slug, source, general=general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, output)
                    self.assertFalse(exe.exists())
                    self.assertIn(REFUSAL, output)
                    self.assertNotIn('AttributeError', output)
                    self.assertNotIn('Traceback', output)

    def test_unambiguous_aliases_still_match_cpython(self):
        for general in (False, True):
            for slug, source in MATCH.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre352-') as directory:
                    wanted = subprocess.run([sys.executable, '-B', '-c', source],
                                            capture_output=True, timeout=120,
                                            env=dict(os.environ, PYTHONUTF8='1'))
                    self.assertEqual(wanted.returncode, 0, wanted.stderr)
                    built, exe = compile_source(directory, slug, source, general=general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, wanted.returncode, ran.stderr)
                    self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'),
                                     wanted.stdout.replace(b'\r\n', b'\n'))


if __name__ == '__main__':
    unittest.main()
