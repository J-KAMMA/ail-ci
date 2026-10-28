"""pre399: a class name is not bound inside its own class body.

CPython binds a class name only after the body has run, so any read of it while the body is
executing (directly, through a list item / dict value / argument, a comprehension, an
immediately called lambda, a lambda default, or a ``map``/``sorted`` callback) raises
``NameError``.  Before this fix the general path returned the pre-created class object and the
program ran.

The general path now gives each such class a module-lifetime flag that is 0 while its body runs
and turns 1 afterwards; a read of the busy class compiles to a NameError unless the flag is set,
so a lambda stored in the class body and called later still returns the class, as CPython does.
A generator expression stored in the class body is likewise read only when the generator is
consumed (its body is lowered lazily, only the outermost iterable runs during the class body), so
a saved generator expression sees the class and a generator whose outermost iterable -- or that
``any``/``next`` consume in place -- reads the class raises ``NameError``.

Every program is built with the general path forced and with the default build; stdout and the
exit status must match CPython.  A name re-bound earlier in the class body wins over the busy
class, and a class named after a builtin (`class id: x = id`) resolves to the builtin inside its
own body.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# CPython runs these: the class name is read only after the body has finished.
MATCH = {
    'deferred_list_item': '''
class C:
    fs = [lambda: C]
print(C().fs[0]() is C)
''',
    'deferred_dict_value': '''
class C:
    d = {"f": lambda: C}
print(C().d["f"]() is C)
''',
    'deferred_method': '''
class C:
    def m(self):
        return C
print(C().m() is C)
''',
    'control_immediate': '''
class C:
    y = (lambda: 1)()
    z = [2, 3][1]
print(C.y, C.z)
''',
    'unrelated_class': '''
class B:
    v = 7
class C:
    x = B
print(C.x is B)
''',
    'class_body_name_shadows_class_attribute': '''
class D:
    v = 7
class C:
    C = D
    x = C.v
print(C.x)
''',
    'class_body_name_shadows_class_method': '''
class D:
    def m(self):
        return 42
class C:
    C = D()
    x = C.m()
print(C.x)
''',
    'class_body_name_shadows_from_container': '''
class D:
    v = 7
    def m(self):
        return 42
class C:
    C = [D][0]
    x = C.v
print(C.x)
class E:
    E = {"d": D()}["d"]
    y = E.m()
print(E.y)
''',
    'class_body_name_shadows_through_argument': '''
class D:
    v = 7
class C:
    C = D
    x = (lambda c: c.v)(C)
print(C.x)
''',
    'class_body_name_builtin_fallback': '''
class id:
    x = id
    y = id(7)
print(id.x is id)
print(type(id.y) is int)
''',
    'earlier_attribute': '''
x = 99
class C:
    x = 3
    y = x + 1
print(C().y)
''',
    'earlier_module_binding': '''
C = 5
class C:
    x = C
print(C.x)
''',
    'after_definition_lambda': '''
class C:
    pass
f = lambda: C
print(f() is C)
''',
    'deferred_generator': '''
class C:
    v = 1
    g = (C for i in range(1))
out = list(C().g)
print(out[0] is C)
''',
    'deferred_generator_attribute': '''
class C:
    v = 1
    g = (C.v for i in range(1))
print(list(C().g))
''',
    'deferred_generator_lambda': '''
class C:
    v = 1
    g = (lambda: C for i in range(1))
f = list(C().g)[0]
print(f() is C)
''',
    'deferred_generator_second_loop': '''
class C:
    v = 1
    g = ((i, x) for i in range(1) for x in [C])
print(list(C().g))
''',
    'deferred_generator_condition': '''
class C:
    v = 1
    g = (i for i in range(3) if C.v)
print(list(C().g))
''',
}

# CPython raises NameError (exit 1) and prints nothing new; the busy class name must do the same.
NAMEERROR = {
    'immediate_lambda': '''
class C:
    y = (lambda: C)()
print(C.y)
''',
    'immediate_lambda_construct': '''
class D:
    v = 1
    fs = [(lambda: [D][0]().v)()]
print(D.fs)
''',
    'direct': '''
class C:
    x = C
print(C.x)
''',
    'list_item': '''
class C:
    x = [C][0]
print(C.x)
''',
    'dict_value': '''
class C:
    x = {"k": C}["k"]
print(C.x)
''',
    'argument': '''
class C:
    x = (lambda c: c)(C)
print(C.x)
''',
    'comprehension_element': '''
class C:
    xs = [C for i in range(1)]
print(C.xs)
''',
    'nested_lambda': '''
class C:
    x = (lambda: (lambda: C)())()
print(C.x)
''',
    'lambda_default': '''
class C:
    x = (lambda a=C: a)()
print(C.x)
''',
    'map_callback': '''
class C:
    xs = list(map(lambda i: C, [1]))
print(C.xs)
''',
    'sorted_key': '''
class C:
    xs = sorted([1, 2], key=lambda i: C)
print(C.xs)
''',
    'after_earlier_output': '''
print("before")
class C:
    x = C
print("after")
''',
    'class_attribute': '''
class C:
    v = 1
    x = C.v
print(C.x)
''',
    'alias': '''
class C:
    v = 1
    A = C
print(C.A)
''',
    'tuple_item': '''
class C:
    x = (C, C)[0]
print(C.x)
''',
    'generator_outermost_iterable': '''
class C:
    g = (i for i in (C,))
print(list(C().g))
''',
    'generator_outermost_attribute': '''
class C:
    v = 1
    g = (i for i in C.v)
print(list(C().g))
''',
    'generator_consumed_by_any': '''
class C:
    x = any(C for i in range(1))
print(C.x)
''',
    'generator_consumed_by_next': '''
class C:
    x = next(C for i in range(1))
print(C.x)
''',
}


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            path.name, '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr.decode('utf-8', 'replace')


class Pre399Tests(unittest.TestCase):
    def test_self_reference_matches_cpython(self):
        for general in (False, True):
            for slug, source in MATCH.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre399-') as directory:
                    want_out, want_rc, want_err = run_cpython(directory, slug, source)
                    self.assertEqual(want_rc, 0, want_err)
                    built, exe = compile_source(directory, slug, source, general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, want_rc, ran.stderr)
                    self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), want_out)

    def test_busy_class_name_raises_name_error(self):
        for general in (False, True):
            for slug, source in NAMEERROR.items():
                with self.subTest(case=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre399-') as directory:
                    want_out, want_rc, want_err = run_cpython(directory, slug, source)
                    self.assertEqual(want_rc, 1, want_err)
                    self.assertIn('NameError', want_err)
                    built, exe = compile_source(directory, slug, source, general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                    self.assertEqual(ran.returncode, want_rc, ran.stderr)
                    self.assertEqual(ran.stdout.replace(b'\r\n', b'\n'), want_out)
                    self.assertIn(b'NameError', ran.stderr)
                    self.assertIn(b"is not defined", ran.stderr)


if __name__ == '__main__':
    unittest.main()
