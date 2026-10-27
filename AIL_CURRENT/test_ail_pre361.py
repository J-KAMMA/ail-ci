"""pre361: a try/handler alias of a colliding class is refused by name.

The pre352 review recorded as pre-existing its r20 probe: a class alias assigned in a ``try``
body and rebound to another class in the handler compiled on both builds and then stopped with
``AttributeError: 'C' object has no attribute 'g'`` where CPython prints 55.  The field/method
collision screen only resolved a call target written as a class name (``C()``), not one reached
through a variable (``x = C; x()``), so the receiver never reached the by-name refusal.

``_classes_of`` now resolves a call target name through its assignments in scope, including a
plain class name, an alias chain and several assignments (a try body plus its handler).  The
same resolution follows an argument, a list item, an attribute and a dict value.  A receiver
that can only be an unrelated class keeps CPython's result.  A name bound by a walrus or a
``for`` target is not in the assignment table and keeps the pre-existing runtime
``AttributeError``; those routes are unchanged here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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
    'try_handler_class': C + D + '''try:
    x = C
except Exception:
    x = D
print(x().f())
''',
    'try_handler_same': C + '''try:
    x = C
except Exception:
    x = C
print(x().f())
''',
    'try_handler_nonclass': C + '''try:
    x = C
except Exception:
    x = 5
print(x().f())
''',
    'alias_chain': C + '''A = C
x = A
print(x().f())
''',
    'argument': C + '''x = C
def call(k):
    return k().f()
print(call(x))
''',
    'list_item': C + '''x = C
ks = [x]
print(ks[0]().f())
''',
    'attribute': C + '''x = C
class H:
    def __init__(self):
        self.k = x
print(H().k().f())
''',
    'dict_value': C + '''x = C
d = {"k": x}
print(d["k"]().f())
''',
    'reassigned_other_class': C + D + '''x = C
x = D
print(x().f())
''',
    'later_module_assignment': C + '''def call():
    return x().f()
x = C
print(call())
''',
}

MATCH = {
    'noncolliding_alias': C + D + '''x = D
print(x().f())
''',
    'noncolliding_argument': C + D + '''def call(x):
    return x().f()
print(call(D))
''',
    'no_feature': '''xs = [1, 2, 3]
print(sum(xs), len(xs))
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
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            path.name, '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre361(unittest.TestCase):
    def test_alias_call_target_is_refused_by_name(self):
        for general in (False, True):
            for slug, source in REFUSED.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre361-') as directory:
                    built, exe = compile_source(directory, slug, source, general=general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, output)
                    self.assertFalse(exe.exists())
                    self.assertIn(REFUSAL, output)
                    self.assertNotIn('AttributeError', output)
                    self.assertNotIn('Traceback', output)

    def test_unrelated_call_targets_match_cpython(self):
        for general in (False, True):
            for slug, source in MATCH.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre361-') as directory:
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
