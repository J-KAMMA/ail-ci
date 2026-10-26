"""Pre-293: a call of an instance field that shadows a method is refused by name.

CPython looks an attribute up on the instance first, so when a class's own method assigns
`self.f = ...`, a later `obj.f(...)` calls that FIELD's value (a function, a callable instance,
or a TypeError), not the method.  The general path dispatched statically to the method and
printed the method's result (`101` where CPython calls the callable instance and prints `11`).
It cannot model a call through the field's value, so the call is now refused by name at compile
time, naming the field and its class, instead of silently running the method.

The forms that CPython still resolves through the class (super().f(...), C.f(obj, ...)) and a
typed-path `Callable` field keep their behaviour.  Verified against CPython 3.12.
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

    def assert_refused(self, name, text, field, klass):
        want = self.cpython(name, text)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            with self.subTest(name=name, general=general):
                built = self.build(name, text, general)
                shown = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0,
                                    "built a program whose output would differ:\n" + shown)
                self.assertIn("calling the instance field '%s'" % field, shown)
                self.assertIn(klass, shown)

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

    def test_callable_instance_field_is_refused(self):
        self.assert_refused("callable_instance", CALLABLE_INSTANCE, "f", "C")

    def test_noncallable_fields_are_refused(self):
        for name, text in (("noncallable", NONCALLABLE_INSTANCE),
                           ("bytes", BYTES_FIELD),
                           ("int", INT_FIELD)):
            with self.subTest(name=name):
                self.assert_refused(name, text, "f", "C")

    def test_lambda_and_assignment_forms_are_refused(self):
        for name, text in (("lambda", LAMBDA_FIELD),
                           ("setattr", SETATTR_FIELD),
                           ("unpack", UNPACKED_FIELD),
                           ("inherited", INHERITED_FIELD)):
            with self.subTest(name=name):
                self.assert_refused(name, text, "f", "B" if name == "inherited" else "C")

    def test_receiver_routes_are_refused(self):
        # through an argument, a list item, an attribute and a dict value
        self.assert_refused("routes", ROUTES, "f", "C")

    def test_super_and_unbound_class_call_are_unchanged(self):
        self.check_output("super_unbound", SUPER_AND_UNBOUND)

    def test_ordinary_method_call_is_unchanged(self):
        self.check_output("ordinary", ORDINARY)

    def test_typed_callable_field_still_matches(self):
        # the typed path models a Callable field and matches CPython; the general build still
        # cannot model the call through the field and refuses it by name
        self.check_output("typed_callable", TYPED_CALLABLE_FIELD, builds=(False,))
        built = self.build("typed_callable", TYPED_CALLABLE_FIELD, True)
        self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("calling the instance field 'g'", built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()
