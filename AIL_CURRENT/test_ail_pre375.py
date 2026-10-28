"""pre375: a walrus or `for` target receiver of a colliding class is refused by name.

The pre361 review recorded as pre-existing its p15/p16 probes: a class alias bound by a walrus
(``if (y := C): print(y().f())``) or by a ``for`` target (``for y in [C]: print(y().f())``)
compiled on both builds and then stopped with ``AttributeError: 'C' object has no attribute
'g'`` where CPython prints 55.  ``refuse_field_method_call`` already resolved a plain
assignment (and a ``try``/handler pair), but the walrus and ``for`` target bindings were not in
its assignment table, so the receiver never reached the by-name refusal.

The table now takes a walrus target and each element a ``for`` iterable is seen to hold (a
literal, a name bound to one, an instance field, a subscript of one and an argument list,
including a method argument).  A walrus/``for`` binding is an additional possible value, not a
replacement: when its value cannot be resolved, a module-level alias of the colliding class is
still consulted (and a plain local assignment still shadows, as before).  A target in a
comprehension is deliberately left alone, and a plain assignment is not merged into a
parameter's call-site resolution.

The pre375 task's p6 (``y = C; y().g()``) is refused too: constructing a class whose colliding
field holds a bound method fails inside ``__init__`` at run time (``self.f = self.g`` reads the
method as a value), so the construction itself is refused by name.  A field holding a plain
lambda is representable and keeps CPython.  A receiver that can only be an unrelated class, an
empty iterable and a name that only another function rebinds keep CPython's result.
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
    'walrus_module': C + '''if (y := C):
    print(y().f())
''',
    'walrus_function': C + '''def go():
    if (y := C):
        print(y().f())
go()
''',
    'walrus_while': C + '''while (y := C):
    print(y().f())
    break
''',
    'walrus_argument': C + '''def go(k):
    if (y := k):
        print(y().f())
go(C)
''',
    'walrus_comprehension': C + '''if (y := C):
    print([y().f() for _ in range(1)])
''',
    'for_list': C + '''for y in [C]:
    print(y().f())
''',
    'for_bound_list': C + '''ys = [C]
for y in ys:
    print(y().f())
''',
    'for_set': C + '''for y in {C}:
    print(y().f())
''',
    'for_unpack': C + D + '''for a, b in [(C, D)]:
    print(a().f())
''',
    'for_attribute': C + '''class H:
    def __init__(self):
        self.ks = [C]
for y in H().ks:
    print(y().f())
''',
    'for_dict_value': C + '''d = {"k": [C]}
for y in d["k"]:
    print(y().f())
''',
    'for_list_item': C + '''ks = [[C]]
for y in ks[0]:
    print(y().f())
''',
    'for_argument': C + '''def go(ks):
    for y in ks:
        print(y().f())
go([C])
''',
    'for_method_argument': C + '''class H:
    def run(self, ks):
        for y in ks:
            print(y().f())
H().run([C])
''',
    'for_rebinds_parameter': C + D + '''def go(y):
    for y in [C]:
        pass
    return y().f()
print(go(D))
''',
    # Constructing a class whose colliding field holds a bound method fails inside __init__
    # at run time (`self.f = self.g` reads the method as a value); the construction is now
    # refused by name instead.
    'p6_alias_construction': C + '''y = C
y().g()
''',
    'p6_direct_construction': C + '''C().g()
''',
    # A walrus/`for` binding is one more possible value, not a replacement: the module-level
    # alias of the colliding class is still a possible receiver.
    'walrus_shadows_module_alias': C + '''X = C
def pick():
    return C
def go():
    (X := pick())
    print(X().f())
go()
''',
    'for_shadows_module_alias': C + D + '''ys = [D]
ys.append(C)
X = C
def go():
    for X in ys:
        pass
    print(X().f())
go()
''',
}

MATCH = {
    'walrus_unrelated': D + '''if (y := D):
    print(y().f())
''',
    'for_unrelated': D + '''for y in [D]:
    print(y().f())
''',
    'for_empty': C + '''for y in []:
    print(y().f())
print('done')
''',
    'for_argument_empty': C + '''def go(ks):
    for y in ks:
        print(y().f())
    print('done')
go([])
''',
    'param_plain_reassignment': C + D + '''def go(y):
    print(y().f())
    y = C
go(D)
''',
    'for_other_function': C + D + '''def other():
    for y in [C]:
        pass
y = D
print(y().f())
''',
    # A plain local binding still shadows the enclosing scope: only the walrus/`for` routes
    # are additional possibilities, so an unrelated class built this way keeps CPython.
    'plain_local_shadow': C + D + '''X = C
def go():
    X = D
    print(X().f())
go()
''',
    'walrus_local_unrelated': C + D + '''def go():
    if (y := D):
        print(y().f())
go()
''',
    # A colliding field holding a plain lambda is representable; construction stays supported.
    'lambda_field_construction': '''class C:
    def __init__(self):
        self.f = lambda: 101
    def f(self):
        return 102
y = C
print(y().f())
''',
    'no_feature': '''for y in range(3):
    print(y)
print(sum([x * 2 for x in range(3)]))
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


class Pre375(unittest.TestCase):
    def test_walrus_and_loop_targets_are_refused_by_name(self):
        for general in (False, True):
            for slug, source in REFUSED.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre375-') as directory:
                    built, exe = compile_source(directory, slug, source, general=general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, output)
                    self.assertFalse(exe.exists())
                    self.assertIn(REFUSAL, output)
                    self.assertNotIn('AttributeError', output)
                    self.assertNotIn('Traceback', output)

    def test_unrelated_and_empty_targets_match_cpython(self):
        for general in (False, True):
            for slug, source in MATCH.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre375-') as directory:
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
