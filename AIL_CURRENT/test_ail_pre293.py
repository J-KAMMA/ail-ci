"""Pre-293: an instance field that shadows a method is read before the method.

CPython looks an attribute up on the instance first, so when a class's own method assigns
`self.f = ...` (directly, by tuple unpacking, or through `setattr(self, 'f', ...)`), a later
`obj.f(...)` calls that FIELD's value (a function, a callable instance, or a TypeError), not
the method.  The pre-279 review added that instance-table lookup to both general paths; this
module re-applies the pre293 change on top of it, extending the field set to `setattr` names
so the already-modelled field call also handles `setattr` (the one form that still printed the
method's result).

Every form below matches CPython on both builds; `super().f(...)` and `C.f(obj, ...)` still
resolve through the class, and a typed `Callable` field keeps working.  Verified against
CPython 3.12.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

CALLABLE_INSTANCE = '''class F:
    def __call__(self, x): return x + 10
class C:
    def __init__(self): self.f = F()
    def f(self, x): return x + 100
print(C().f(1))
'''

NONCALLABLE_INSTANCE = '''class F: pass
class C:
    def __init__(self): self.f = F()
    def f(self, x): return x + 100
try: C().f(1)
except TypeError as e: print('TypeError', e)
'''

BYTES_FIELD = '''class C:
    def __init__(self): self.f = b'x'
    def f(self, x): return x + 100
try: C().f(1)
except TypeError as e: print('TypeError', e)
'''

INT_FIELD = '''class C:
    def __init__(self): self.f = 5
    def f(self, x): return x + 100
try: C().f(1)
except TypeError as e: print('TypeError', e)
'''

LAMBDA_FIELD = '''class C:
    def __init__(self): self.f = lambda x: x + 10
    def f(self, x): return x + 100
print(C().f(1))
'''

SETATTR_FIELD = '''class F:
    def __call__(self, x): return x + 10
class C:
    def __init__(self): setattr(self, 'f', F())
    def f(self, x): return x + 100
print(C().f(1))
'''

SETATTR_ROUTES = '''class F:
    def __call__(self, x): return x + 10
class C:
    def __init__(self): self.f = F()
    def f(self, x): return x + 100
def apply(o, v):
    setattr(o, 'f', v)
c = C()
apply(c, F())
print(c.f(1))
print([c][0].f(2))
class H:
    def __init__(self): self.c = c
print(H().c.f(3))
print({'c': c}['c'].f(4))
'''

UNPACKED_FIELD = '''class F:
    def __call__(self, x): return x + 10
class C:
    def __init__(self): self.f, self.g = F(), F()
    def f(self, x): return x + 100
print(C().f(1))
'''

INHERITED_FIELD = '''class F:
    def __call__(self, x): return x + 10
class B:
    def __init__(self): self.f = F()
class C(B):
    def f(self, x): return x + 100
print(C().f(1))
'''

ROUTES = '''class F:
    def __call__(self, x): return x + 10
class C:
    def __init__(self, f): self.f = f
    def f(self, x): return x + 100
class H:
    def __init__(self): self.c = C(F())
def go(c):
    print(c.f(1))
go(C(F()))
print([C(F())][0].f(1))
print(H().c.f(1))
print({'c': C(F())}['c'].f(1))
'''

NEGATIVE_ALIAS = '''class F:
    def __call__(self, x): return -x
class C:
    def __init__(self): self.f = F()
    def f(self, x): return x + 100
a = C()
b = a
print(a.f(-7), b.f(3))
print([a, b][-1].f(0))
'''

SUPER_AND_UNBOUND = '''class F:
    def __call__(self, x): return x + 10
class B:
    def f(self, x): return x + 100
class C(B):
    def __init__(self): self.f = F()
    def f(self, x): return super().f(x) + 1
    def go(self): return super().f(1)
print(C().go())
print(C.f(C(), 1))
'''

ORDINARY = '''class C:
    def __init__(self): self.g = 1
    def f(self, x): return x + 100
print(C().f(1))
'''

TYPED_CALLABLE_FIELD = '''from typing import Callable
def inc(x: int) -> int: return x + 1
class C:
    def __init__(self, g: Callable[[int], int]):
        self.g = g
    def g(self, x: int) -> int:
        return x + 100
print(C(inc).g(1))
'''

UNRELATED_CLASSES = '''class A:
    def __init__(self): self.f = 5
    def f(self, x): return x + 10
class B:
    def f(self, x): return x + 100
def go(x): return x.f(1)
print(go(B()))
'''

UNRELATED_BUILTIN = '''class C:
    def __init__(self): self.append = 5
    def append(self, x): return x
def go(x): x.append(1)
go([])
print('ok')
'''

NESTED_SCOPE = '''class C:
    def f(self, x): return x + 100
    def g(self):
        def h(self):
            self.f = 5
        return 1
print(C().f(1))
'''


class Pre293Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pre293-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, name, text):
        path = self.dir / (name + "_cpython.py")
        path.write_text(text, encoding="utf-8")
        return subprocess.run([sys.executable, "-B", str(path)], cwd=self.dir,
                              capture_output=True, timeout=120,
                              env=dict(os.environ, PYTHONUTF8="1"))

    def build(self, name, text, general):
        path = self.dir / (name + ".py")
        path.write_text(text, encoding="utf-8")
        exe = self.dir / ("exe_" + name + ("_g" if general else "_d"))
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        return subprocess.run([sys.executable, "-B", CLI, "compile", path.name,
                               "--syntax", "python", "-o", exe.name],
                              cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)

    def check_output(self, name, text, builds=(False, True)):
        want = self.cpython(name, text)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in builds:
            with self.subTest(name=name, general=general):
                built = self.build(name, text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(self.dir / ("exe_" + name + ("_g" if general else "_d")))],
                                     cwd=self.dir, capture_output=True, timeout=120)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                                 "%s (general=%s)\n%s" % (name, general,
                                                          got.stderr.decode("utf-8", "replace")))

    def test_callable_instance_field(self):
        self.check_output("callable_instance", CALLABLE_INSTANCE)

    def test_noncallable_fields(self):
        for name, text in (("noncallable", NONCALLABLE_INSTANCE),
                           ("bytes", BYTES_FIELD),
                           ("int", INT_FIELD)):
            with self.subTest(name=name):
                self.check_output(name, text)

    def test_lambda_and_assignment_forms(self):
        for name, text in (("lambda", LAMBDA_FIELD),
                           ("setattr", SETATTR_FIELD),
                           ("setattr_routes", SETATTR_ROUTES),
                           ("unpack", UNPACKED_FIELD),
                           ("inherited", INHERITED_FIELD)):
            with self.subTest(name=name):
                self.check_output(name, text)

    def test_receiver_routes(self):
        # through an argument, a list item, an attribute and a dict value
        self.check_output("routes", ROUTES)

    def test_negative_and_alias(self):
        self.check_output("negative_alias", NEGATIVE_ALIAS)

    def test_super_and_unbound_class_call_are_unchanged(self):
        self.check_output("super_unbound", SUPER_AND_UNBOUND)

    def test_ordinary_method_call_is_unchanged(self):
        self.check_output("ordinary", ORDINARY)

    def test_typed_callable_field_still_matches(self):
        self.check_output("typed_callable", TYPED_CALLABLE_FIELD)

    def test_unknown_receiver_is_not_poisoned_by_another_class(self):
        # a dynamic receiver may be B or a list; a field of A/C must not change that call
        self.check_output("unrelated_classes", UNRELATED_CLASSES)
        self.check_output("unrelated_builtin", UNRELATED_BUILTIN)

    def test_nested_scope_receiver_is_not_the_instance(self):
        # `self` in h is h's own parameter, so C has no field named f
        self.check_output("nested_scope", NESTED_SCOPE)


if __name__ == "__main__":
    unittest.main()
