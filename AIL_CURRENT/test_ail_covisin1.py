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
    def compare(self, files, modes, main='p.py'):
        with tempfile.TemporaryDirectory(prefix='covisin1_') as directory:
            for name, text in files.items():
                Path(directory, name).write_text(text, encoding='utf-8')
            want = _run(directory, main)
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

if __name__ == '__main__':
    unittest.main()
