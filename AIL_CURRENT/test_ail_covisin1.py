"""isinstance() with a type argument that is not a plain name.

Covers the forms the module census found: a nested tuple of type names, a module-level tuple
constant (`TYPES = (int, str)`), an alias of a class (`K = B`) and a class reached through a
module (`shapes.Shape`).  The static forms are compiled on the typed path alone and on the
general path; a type set that is only known at run time (a parameter or a field holding a class
or a tuple of classes) is compared on the general path.  Every program's stdout and exit code
are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AIL = ROOT / 'ail_chatgpt.py'


def _build(directory, name, mode):
    env = dict(os.environ)
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    elif mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = 'exe_' + mode
    built = subprocess.run([sys.executable, '-B', str(AIL), 'compile', name, '--syntax', 'python',
                            '-o', exe], cwd=directory, capture_output=True, text=True, timeout=1800, env=env)
    return built, Path(directory, exe)


def _run(directory, name):
    return subprocess.run([sys.executable, name], cwd=directory, capture_output=True, text=True, timeout=300)


class IsinstanceTypeForms(unittest.TestCase):
    def compare(self, files, modes, main='p.py', failure=False):
        with tempfile.TemporaryDirectory(prefix='covisin1_') as directory:
            for name, text in files.items():
                Path(directory, name).write_text(text, encoding='utf-8')
            want = _run(directory, main)
            if failure:
                self.assertNotEqual(want.returncode, 0)
            else:
                self.assertEqual(want.returncode, 0, want.stderr)
            for mode in modes:
                built, exe = _build(directory, main, mode)
                self.assertEqual(built.returncode, 0,
                                 mode + ': ' + (built.stdout + built.stderr)[-3000:])
                run = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=300)
                self.assertEqual(run.stdout, want.stdout, mode)
                self.assertEqual(run.returncode, want.returncode, mode + ': ' + run.stderr[-2000:])

    def test_static_forms(self):
        self.compare({'p.py': STATIC}, ('typed', 'general'))

    def test_runtime_type_values(self):
        self.compare({'p.py': RUNTIME}, ('general',))

    def test_module_class_attribute_typed(self):
        self.compare({'p.py': MODULE_ATTR_TYPED, 'shapes.py': SHAPES}, ('typed',))

    def test_module_class_attribute_general(self):
        self.compare({'p.py': MODULE_ATTR, 'shapes.py': SHAPES}, ('general',))

    def test_type_constants_keep_side_effects(self):
        self.compare({'p.py': SIDE_EFFECTS}, ('general',))

    def test_module_alias_shadowed_by_parameter_and_local(self):
        self.compare({'p.py': SCOPE_SHADOW}, ('general',))

    def test_module_alias_in_nested_scopes(self):
        self.compare({'p.py': NESTED_SCOPES}, ('general',))

    def test_use_before_assignment_is_name_error(self):
        self.compare({'p.py': ORDER_BEFORE}, ('general',), failure=True)

    def test_function_defined_before_assignment_called_after(self):
        self.compare({'p.py': ORDER_AFTER}, ('general',))

    def test_builtin_tuple_shadowed_by_parameter(self):
        self.compare({'p.py': BUILTIN_SHADOW}, ('general',))

    def test_constant_value_is_snapshotted_at_assignment(self):
        self.compare({'p.py': SNAPSHOTS}, ('general',))

    def test_forward_alias_constant_is_name_error(self):
        self.compare({'p.py': FORWARD_ALIAS}, ('general',), failure=True)

    def test_forward_tuple_constant_is_name_error(self):
        self.compare({'p.py': FORWARD_TUPLE}, ('general',), failure=True)

    def test_exception_type_constant(self):
        self.compare({'p.py': EXCEPTION_CONST}, ('general',))

    def test_unexecuted_class_binding_keeps_constructor(self):
        self.compare({'p.py': CONDITIONAL_REBIND}, ('default', 'general'))

    def test_module_bound_constructor_keyword_arguments(self):
        self.compare({'p.py': KW_CTORS}, ('default', 'general'))

    def test_decorated_class_binding_keeps_keyword_refusal(self):
        with tempfile.TemporaryDirectory(prefix='covisin1_') as directory:
            Path(directory, 'p.py').write_text(DECORATED_KW, encoding='utf-8')
            for mode in ('default', 'general'):
                built, _ = _build(directory, 'p.py', mode)
                self.assertNotEqual(built.returncode, 0, mode)
                self.assertIn('not in the subset', built.stdout + built.stderr, mode)


STATIC = r'''class A: pass
class B(A): pass

TYPES = (int, str)
SHAPES = (A, B)
NESTED = ((float, bool), TYPES)
K = B


def ai(x: A):
    print(isinstance(x, SHAPES), isinstance(x, K), isinstance(x, (A, B)), isinstance(x, ((A,), (B,))))


def ii(x: int):
    print(isinstance(x, TYPES), isinstance(x, NESTED), isinstance(x, (int, (str, float))),
          isinstance(x, (int, str)))


def bi(x: bool):
    print(isinstance(x, TYPES), isinstance(x, NESTED), isinstance(x, (bool,)), isinstance(x, (int,)))


def si(x: str):
    print(isinstance(x, TYPES), isinstance(x, NESTED), isinstance(x, (str, float)), isinstance(x, (int, str)))


ai(A())
ai(B())
ii(1)
bi(True)
si("s")
print(isinstance(True, (int,)), isinstance(1, (bool,)))
'''

RUNTIME = r'''class A: pass
class B(A): pass
class C: pass


def check(x, spec):
    print(isinstance(x, spec))


class Holder:
    def __init__(self):
        self.spec = (A,)


h = Holder()
for v in (A(), B(), C()):
    check(v, B)
    check(v, (A, C))
    check(v, ((B,), ()))
    check(v, h.spec)
print(isinstance(A(), (A,)), isinstance(B(), B))
'''

SHAPES = r'''class Shape: pass
class Square(Shape): pass
'''

SIDE_EFFECTS = r'''class A: pass
class B(A): pass

TYPES = (int, str)
SIDE = print("side effect ran")
UNUSED = 41


def f(x):
    print(isinstance(x, TYPES), isinstance(x, (A, B)))


f(1)
f(True)
f("s")
f(A())
'''

MODULE_ATTR_TYPED = r'''import shapes


def fs(x: shapes.Shape):
    print(isinstance(x, shapes.Shape), isinstance(x, shapes.Square),
          isinstance(x, (shapes.Shape, shapes.Square)), isinstance(x, ((shapes.Square,), (shapes.Shape,))))


fs(shapes.Shape())
fs(shapes.Square())
'''

MODULE_ATTR = r'''import shapes


def fs(x: shapes.Shape):
    print(isinstance(x, shapes.Shape), isinstance(x, shapes.Square),
          isinstance(x, (shapes.Shape, shapes.Square)), isinstance(x, ((shapes.Square,), (shapes.Shape,))))


def fi(x: int):
    print(isinstance(x, shapes.Shape), isinstance(x, (shapes.Shape, shapes.Square)),
          isinstance(x, ((shapes.Square,), (shapes.Shape,))))


def fb(x: bool):
    print(isinstance(x, shapes.Shape), isinstance(x, (shapes.Shape, shapes.Square)), isinstance(x, (int,)))


fs(shapes.Shape())
fs(shapes.Square())
fi(1)
fb(True)
print(isinstance(shapes.Square(), shapes.Shape), isinstance(True, int), isinstance(1, bool))
'''

SCOPE_SHADOW = r'''class A: pass
class B: pass
K = A


def f(K):
    print(isinstance(A(), K), isinstance(B(), K))


def g():
    K = B
    print(isinstance(A(), K), isinstance(B(), K))


f(B)
f(A)
g()
print(isinstance(A(), K), isinstance(B(), K))
'''

NESTED_SCOPES = r'''class A: pass
class B: pass
class C: pass
K = A


def outer(K):
    def inner():
        print("inner", isinstance(A(), K), isinstance(B(), K))
    inner()


def comp():
    return [isinstance(A(), K) for K in (B, A)]


class Body:
    K = B
    r = (isinstance(A(), K), isinstance(B(), K))


outer(B)
print("comp", comp())
print("body", Body.r)
print("module", isinstance(A(), K), isinstance(B(), K))
'''

ORDER_BEFORE = r'''class A: pass
class B: pass


def f(x):
    print("f", isinstance(x, K))


f(A())
K = B
f(A())
'''

ORDER_AFTER = r'''class A: pass
class B: pass


def f(x):
    print(isinstance(x, K))


K = B
f(A())
f(B())
'''

BUILTIN_SHADOW = r'''class A: pass
class B: pass
TYPES = (int, str)


def f(TYPES):
    print("f", isinstance(A(), TYPES), isinstance(B(), TYPES))


f((A,))
f((B,))
print("module", isinstance(1, TYPES), isinstance("s", TYPES), isinstance(1.0, TYPES))
'''

SNAPSHOTS = r'''class A: pass
class B: pass
class Box: pass

box = Box()
box.t = A
T = box.t
box.t = B
print(isinstance(A(), T), isinstance(B(), T))

U = (A,)
A = B
print(isinstance(A(), U), isinstance(B(), U), isinstance(A(), A), isinstance(B(), A))

TYPES = (A,)


def shadow(A):
    print(isinstance(A, TYPES), isinstance(B(), TYPES))


shadow(B)
'''

FORWARD_ALIAS = r'''K = C
class C: pass
print(isinstance(C(), K))
'''

FORWARD_TUPLE = r'''T = (K,)
print(isinstance(1, T))
K = str
'''

CONDITIONAL_REBIND = r'''class A: pass
class B: pass
if False:
    A = B
for A in []:
    pass
try:
    raise KeyError
except KeyError:
    pass
else:
    A = B
if False:
    A, = (B,)
A: int
if False:
    A: int
print(type(A()).__name__)


def make():
    return A()


print(type(make()).__name__)
if True:
    A = B
print(type(A()).__name__)
'''

KW_CTORS = r'''class A:
    def __init__(self, x, y=2):
        self.x = x; self.y = y
class B:
    def __init__(self, x, y=3):
        self.x = x; self.y = y
if False:
    A = B
a = A(x=3)
print(a.x + a.y)
if True:
    A = B
b = A(x=4, y=5)
print(b.x + b.y)
class E(Exception):
    def __init__(self, x, y):
        super().__init__()
        self.x = x; self.y = y
class F(Exception):
    def __init__(self, x, y):
        super().__init__()
        self.x = x; self.y = y
E = F
e = E(x=7, y="f")
print(e.x, e.y)
class C:
    def __init__(self, x, y=2, *, z=3):
        self.x = x; self.y = y; self.z = z
class D:
    def __init__(self, x, y=4, *, z=5):
        self.x = x; self.y = y; self.z = z
if False:
    C = D
c = C(z=10, x=1)
print(c.x, c.y, c.z)
'''

DECORATED_KW = r'''def deco(cls):
    def f(x):
        return x + 5
    return f
@deco
class A:
    def __init__(self, x=0):
        self.x = x
class B:
    pass
if False:
    A = B
print(A(x=3))
'''

EXCEPTION_CONST = r'''T = (ValueError, KeyError)


def f(k):
    try:
        if k == 0:
            raise ValueError("v")
        raise KeyError("k")
    except Exception as e:
        print(isinstance(e, T), isinstance(e, TypeError))


f(0)
f(1)
'''

if __name__ == '__main__':
    unittest.main()
