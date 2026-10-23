"""Pre-existing CPython differences fixed before job pre6 (fuzz67 p18).

`__slots__` was ignored on the general path: an instance accepted any new attribute
(`c.b = 3`) instead of raising AttributeError.  The general runtime now carries the
class's slot names and checks every attribute store; the class-body names keep
CPython's different "object attribute ... is read-only" message.  A __slots__ value
that is not a literal string/tuple/list is refused by name at compile time.  Builtin
exception instances keep a __dict__ (n_slots = -1 in ail_ctx_init), and a slots
instance's methods are read-only just like its class-body attributes.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None

SLOTS = r"""class Base:
    __slots__ = ("a",)
    def __init__(self):
        self.a = -7

class Child(Base):
    __slots__ = ("b",)
    PASS = 50
    def __init__(self):
        Base.__init__(self)
        self.b = 2**62

def poke(obj):
    try:
        obj.z = 1
        return "assigned"
    except AttributeError as err:
        return "AttributeError " + str(err)

def main():
    c = Child()
    print(c.a, c.b, c.PASS)
    print(poke(c), poke([c][0]))
    holder = {"c": c}
    print(poke(holder["c"]))
    setattr(c, "b", 1.5)
    print(c.b)
    try:
        setattr(c, "PASS", 60)
    except AttributeError as err:
        print("AttributeError", str(err))

main()
"""

DYNAMIC = r"""names = ("a",)

class C:
    __slots__ = names

c = C()
c.a = 1
print(c.a)
"""

BUILTIN_EXCEPTION = r"""try:
    raise ValueError("boom")
except ValueError as err:
    err.custom = 5
    print(err.custom, err.args[0])
"""

READONLY_METHOD = r"""class C:
    __slots__ = ("a",)
    x = 7
    def __init__(self):
        self.a = 1
    def f(self):
        return self.a

c = C()
print(c.a, c.x, c.f())
for name in ("b", "x", "f", "__slots__"):
    try:
        setattr(c, name, 3)
        print(name, "set")
    except AttributeError as err:
        print(name, "AttributeError", str(err))
print(c.a, c.x)
"""


class Slots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre6-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cpython(self, source):
        path = self.dir / 'cpython.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], cwd=self.dir,
                              capture_output=True, timeout=120)

    def build_default(self, source):
        src = self.dir / 'default.py'
        src.write_text(source, encoding='utf-8')
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
        env.pop('AIL_NO_GENERAL', None)
        env.pop('AIL_UNIFIED_FORCE', None)
        return subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name,
                               '--syntax', 'python', '-o', 'default.out'], cwd=self.dir,
                              capture_output=True, text=True, timeout=900, env=env), self.dir / 'default.out'

    def build_general(self, source):
        src = self.dir / 'general.py'
        src.write_text(source, encoding='utf-8')
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
        env.pop('AIL_NO_GENERAL', None)
        return subprocess.run([sys.executable, '-B', str(PYC), 'general.out', '--file', src.name,
                               '--general-only'], cwd=self.dir, capture_output=True, text=True,
                              timeout=900, env=env), self.dir / 'general.out'

    def test_slots_are_enforced_on_both_paths(self):
        want = self.run_cpython(SLOTS)
        self.assertEqual(want.returncode, 0, want.stderr)
        for name, build in (('default', self.build_default), ('general', self.build_general)):
            with self.subTest(name):
                built, exe = build(SLOTS)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
                self.assertEqual(got.returncode, want.returncode, got.stderr)
                self.assertEqual(got.stdout, want.stdout)

    def test_builtin_exception_instances_still_accept_attributes(self):
        want = self.run_cpython(BUILTIN_EXCEPTION)
        self.assertEqual(want.returncode, 0, want.stderr)
        for name, build in (('default', self.build_default), ('general', self.build_general)):
            with self.subTest(name):
                built, exe = build(BUILTIN_EXCEPTION)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
                self.assertEqual(got.returncode, want.returncode, got.stderr)
                self.assertEqual(got.stdout, want.stdout)

    def test_methods_are_read_only_on_a_slots_instance(self):
        want = self.run_cpython(READONLY_METHOD)
        self.assertEqual(want.returncode, 0, want.stderr)
        for name, build in (('default', self.build_default), ('general', self.build_general)):
            with self.subTest(name):
                built, exe = build(READONLY_METHOD)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
                self.assertEqual(got.returncode, want.returncode, got.stderr)
                self.assertEqual(got.stdout, want.stdout)

    def test_dynamic_slots_are_refused_by_name(self):
        src = self.dir / 'dynamic.py'
        src.write_text(DYNAMIC, encoding='utf-8')
        built = subprocess.run([sys.executable, '-B', str(PYC), 'dynamic.out', '--file', src.name,
                                '--general-only'], cwd=self.dir, capture_output=True, text=True,
                               timeout=900, env=dict(os.environ, AIL_NO_CACHE='1'))
        self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
        self.assertIn('__slots__', built.stderr)
        self.assertNotIn('Traceback', built.stderr)


if __name__ == '__main__':
    unittest.main()
