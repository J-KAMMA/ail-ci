"""fuzz50: a write to a field of a frozen dataclass is refused by name, not silently performed.

CPython's @dataclass(frozen=True) installs a __setattr__ that raises FrozenInstanceError for a field
write. The compiler lowered the write to an ordinary field store (both paths), so `a.x = 5` and
`a.x += 1` printed the new value instead of an error. The field name is what a store names, so the
refusal covers a local, a parameter, a list item, a dict value and a nested field; `object.__setattr__`
in __post_init__ still works. A write to `self.f` in a class that is not frozen is that class's own
field and stays allowed.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

FROZEN_WRITE = '''from dataclasses import dataclass

@dataclass(frozen=True)
class A:
    x: int

a = A(1)
try:
    a.x = 5
    print("assigned", a)
except Exception as e:
    print(type(e).__name__, e)
'''

FROZEN_AUG = '''from dataclasses import dataclass

@dataclass(frozen=True)
class A:
    x: int

a = A(3)
try:
    a.x += 1
    print("inplace", a)
except Exception as e:
    print(type(e).__name__, e)
'''

FROZEN_CHANNELS = '''from dataclasses import dataclass

@dataclass(frozen=True)
class A:
    x: int

@dataclass
class Box:
    item: A

def touch(p):
    try:
        p.x = 9
    except Exception as e:
        print(type(e).__name__, e)

def main():
    a = A(1)
    touch(a)
    xs = [A(2)]
    try:
        xs[0].x = 9
    except Exception as e:
        print(type(e).__name__, e)
    d = {"k": A(3)}
    try:
        d["k"].x = 9
    except Exception as e:
        print(type(e).__name__, e)
    b = Box(A(4))
    try:
        b.item.x = 9
    except Exception as e:
        print(type(e).__name__, e)

main()
'''

FROZEN_POST_INIT = '''from dataclasses import dataclass, field

@dataclass(frozen=True)
class Temp:
    value: int
    celsius: int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "celsius", self.value * 2)

t = Temp(21)
print(t, t.celsius, t == Temp(21))
'''

MUTABLE_SAME_FIELD = '''from dataclasses import dataclass

@dataclass(frozen=True)
class A:
    x: int

class M:
    def __init__(self, x: int):
        self.x = x

    def bump(self):
        self.x += 1
        return self.x

m = M(4)
print(m.x, m.bump(), m.x)
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-fuzz50-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source):
        path = self.dir / 'main.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True, timeout=120)

    def build(self, source, general):
        entry = self.dir / ('main_general.py' if general else 'main_default.py')
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('out_general' if general else 'out_default')
        env = dict(os.environ, AIL_NO_CACHE='1')
        env.pop('AIL_NO_GENERAL', None)
        if general:
            env['AIL_UNIFIED_FORCE'] = '1'
        else:
            env.pop('AIL_UNIFIED_FORCE', None)
        return subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(entry), '--syntax', 'python',
                               '-o', str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=900,
                              env=env), exe

    def refused(self, source):
        for general in (False, True):
            built, _ = self.build(source, general)
            self.assertNotEqual(built.returncode, 0, ('general' if general else 'default') + ': ' +
                                built.stdout + built.stderr)
            self.assertIn('frozen dataclass', built.stderr, built.stdout + built.stderr)

    def same(self, source):
        expected = self.cpython(source)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for general in (False, True):
            built, exe = self.build(source, general)
            self.assertEqual(built.returncode, 0, ('general' if general else 'default') + ': ' +
                             built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
            self.assertEqual(ran.stdout, expected.stdout, 'general' if general else 'default')
            self.assertEqual(ran.returncode, 0, ran.stderr)


class FrozenWriteTests(Base):
    def test_direct_assignment_is_refused(self):
        self.refused(FROZEN_WRITE)

    def test_augmented_assignment_is_refused(self):
        self.refused(FROZEN_AUG)

    def test_argument_list_dict_and_nested_field_are_refused(self):
        self.refused(FROZEN_CHANNELS)

    def test_object_setattr_in_post_init_still_works(self):
        self.same(FROZEN_POST_INIT)

    def test_self_field_of_another_class_is_not_refused(self):
        self.same(MUTABLE_SAME_FIELD)


if __name__ == '__main__':
    unittest.main()
