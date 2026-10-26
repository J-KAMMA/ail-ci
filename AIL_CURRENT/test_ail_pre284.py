"""pre284: a constant read through a class attribute is folded, or refused by name.

`class K: N = 2**62` followed by `class C: X = K.N * 4` evaluated checked int64 arithmetic
in the class body, so both builds stopped with ``integer overflow`` where CPython keeps the
bignum; the same read inside a module-level comprehension did too.  The folder now records a
top-level class whose attributes are single constant assignments (and a single-assignment
`Alias = Class`), and the compile-time int64 checks resolve `Class.attr` as well, so an
in-range value is emitted as a literal and an out-of-range one is refused by name at compile
time.  A class whose name or attribute is rebound, a derived or decorated class, a float/bool
attribute and a comprehension target that shadows the class stay as written.  A function body
keeps its own scope: a parameter or local that shadows a module name is never folded, and a
module name a function declares `global` leaves the class attribute unresolved; only a
function's default arguments and decorators run in module scope.

The refusal wording depends on which check sees the folded value: the literal check says
``int64 literal out of range``, the expression checks say ``int64 constant expression out of
range``.  Either named refusal is accepted here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = ('int64 literal out of range', 'int64 constant expression out of range')

OUT_OF_RANGE = {
    'class_body': '''class K:
    N = 2 ** 62
class C:
    X = K.N * 4
print(C.X)
''',
    'comprehension': '''class K:
    N = 2 ** 62
xs = [K.N * 4 for _ in range(1)]
print(xs)
''',
    'comprehension_in_call': '''class K:
    N = 2 ** 62
print([K.N * 4 for _ in range(1)])
''',
    'alias': '''class K:
    N = 2 ** 62
K2 = K
class C:
    X = K2.N * 4
print(C.X)
''',
    'argument': '''class K:
    N = 2 ** 62
def show(v):
    print(v)
show(K.N * 4)
''',
    'list_item': '''class K:
    N = 2 ** 62
print([K.N * 4])
''',
    'attribute': '''class K:
    N = 2 ** 62
class Box:
    x = 0
b = Box()
b.x = K.N * 4
print(b.x)
''',
    'dict_value': '''class K:
    N = 2 ** 62
print({"x": K.N * 4})
''',
    'default': '''class K:
    N = 2 ** 62
def show(v=K.N * 4):
    print(v)
show()
''',
    'negative': '''class K:
    N = -(2 ** 62)
class C:
    X = K.N * 4
print(C.X)
''',
    'module_assignment': '''class K:
    N = 2 ** 62
X = K.N * 2
print(X)
''',
    'class_with_method': '''class K:
    N = 2 ** 62
    def get(self):
        return self.N
class C:
    X = K.N * 4
print(C.X)
''',
    'class_local': '''class K:
    N = 2 ** 62
    M = N * 2
print(K.M)
''',
    'default_comprehension': '''class K:
    N = 2 ** 62
def show(v=[K.N * 4 for _ in range(1)]):
    print(v)
show()
''',
}

SHADOWED = {
    'parameter_shadows_module_constant': '''N = 2
def f(N):
    return [N * 4 for _ in range(1)]
print(f(3), [N * 4 for _ in range(1)])
''',
    'parameter_shadows_class': '''class K:
    N = 2 ** 61
class Other:
    N = 3
def f(K):
    return [K.N // 4 for _ in range(1)]
print(f(Other))
''',
    'local_shadows_class': '''class K:
    N = 2 ** 61
class Other:
    N = 3
def f():
    K = Other
    return [K.N // 4 for _ in range(1)]
print(f())
''',
    'parameter_shadows_class_abs': '''class K:
    N = 2 ** 61
class Other:
    N = 1
def f(K):
    return abs(K.N * 4)
print(f(Other))
''',
    'global_rebinding': '''class K:
    N = 2 ** 61
class Other:
    N = 1
def f():
    global K
    K = Other
f()
class C:
    X = K.N * 4
print(C.X)
''',
    'closure_shadow': '''class K:
    N = 2 ** 62
class Other:
    N = 1
def outer(K):
    def inner(x=K.N * 4):
        return abs(K.N * 4) + -x + [K.N // 4 for _ in range(1)][0]
    return inner()
print(outer(Other))
''',
}

IN_RANGE = '''class K:
    N = 2 ** 62
class W:
    N = 2 ** 61
    M = N * 2
    Q = M
class C:
    A = K.N // 2
    B = W.N * 4 - 1
    D = -K.N
    E = W.M * 2 - 1
    F = W.Q // 2
X = K.N // 4
xs = [W.N * 4 - 1 for _ in range(2)]
ys = [K.N * 4 for K in []]


class Types:
    F = 2.5
    B = True
    M = (1 << 63) - 1


print(C.A, C.B, C.D, C.E, C.F, X, xs, ys)
print(Types.F * 4, Types.B * 4, Types.M - 1)
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre284Tests(unittest.TestCase):
    def test_attribute_constant_out_of_int64_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre284-') as directory:
            for label, text in OUT_OF_RANGE.items():
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        built, _ = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                        self.assertNotEqual(built.returncode, 0, label)
                        message = built.stdout + built.stderr
                        self.assertTrue(any(refusal in message for refusal in REFUSALS), message)
                        self.assertNotIn('integer overflow', message, label)
                        self.assertNotIn('Traceback', message, label)

    def test_attribute_constant_in_range_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre284-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('in_range_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'in_range_' + ('g' if general else 'd'),
                                          IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_shadowed_names_keep_their_runtime_value(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre284-') as directory:
            for label, text in SHADOWED.items():
                want, want_rc, err = _cpython(directory, label, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        got, build_err = _run(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                              text, general)
                        self.assertIsNotNone(got, build_err)
                        self.assertEqual(got, (want, want_rc), build_err)


if __name__ == '__main__':
    unittest.main()
