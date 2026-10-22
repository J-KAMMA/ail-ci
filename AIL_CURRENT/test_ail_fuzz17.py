"""fuzz17: dataclasses and enums (both builds, against CPython 3.12).

Three silent differences found by small random programs are fixed:

* A @dataclass with no fields of its own (an empty class, or one extending a fieldless dataclass) used to
  stay an ordinary class: `Empty()` printed `<Empty object>` (CPython: `Empty()`), `Empty() == Empty()` was
  False (CPython: True) and `Empty() != Empty()` was True. It now gets the generated __init__, __eq__ and
  repr, so repr, equality, asdict and replace agree with CPython.
* An Enum member whose value is equal to an earlier member but written differently (`A = 0; B = False`,
  `A = 1; B = 1.0; C = True`) was not treated as an alias on either build. The member table now compares the
  literal values, as CPython does. @unique with such a duplicate is refused by name at compile time (CPython
  raises ValueError while making the class).
* A @dataclass(eq=False) kept object identity, but the runtime treated every dataclass without a __hash__ as
  unhashable, so `hash(p)` and a set of such instances raised TypeError where CPython works. It now gets an
  identity-valid __hash__ (a constant; unequal objects may collide), unless the class defines __eq__ itself.
* Assigning to an enum member's .value or .name (`E.A.value = 9`) silently changed the member; CPython raises
  AttributeError. Such an assignment (including the augmented form) is refused by name at compile time.

Still open (listed in the report): frozen dataclass field assignment is not refused, enum membership by a
plain value (`1 in E`) is False, expressions that evaluate to an equal enum value (`B = 1 + 0`) do not
become aliases, and exception text names a class `instance` rather than the class name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EMPTY_DATACLASS = r'''from dataclasses import dataclass, asdict, replace


@dataclass
class Empty:
    pass


@dataclass
class Child(Empty):
    x: int = 1


@dataclass
class Grand(Empty):
    pass


@dataclass(eq=False)
class Plain:
    pass


def main() -> None:
    e = Empty()
    print(e, repr(e), e == Empty(), e == Child(), e != Empty())
    print(Child(), Grand(), Grand() == Grand(), Child(2) == Child(2))
    print(asdict(e), astuple_ok(e), replace(e) == e)
    p1 = Plain()
    p2 = Plain()
    print(Plain() == Plain(), hash(p1) == hash(p1), len({p1, p2}))


def astuple_ok(x) -> bool:
    return asdict(x) == {}


main()
'''

EQFALSE_HASH = r'''from dataclasses import dataclass


@dataclass(eq=False)
class P:
    x: int


def main() -> None:
    a = P(1)
    b = P(1)
    print(a == b, a == a, a != b, hash(a) == hash(a), len({a, b}), a in [a], b in [a])


main()
'''

ENUM_ALIASES = r'''from enum import Enum, IntEnum


class C(Enum):
    ZERO = 0
    FALSE = False
    EMPTY = ""
    NONE = None
    ONE = 1
    FLOAT = 1.0
    TRUE = True


class L(IntEnum):
    A = 1
    B = True
    C = 2


def main() -> None:
    print(list(C))
    print(C.ZERO is C.FALSE, C.ONE is C.FLOAT, C.ONE is C.TRUE, C.ONE is C.EMPTY)
    print(C(0), C(False), C(1), C(1.0), C(""), C(None))
    print(C.__members__)
    print(list(L), len(L), L.B is L.A, L(1) is L.A, L(2) is L.C)


main()
'''

FLAG_ALIASES = r'''from enum import Flag, IntFlag


class F(Flag):
    A = 1
    B = 2
    AB = 3


class I(IntFlag):
    A = 1
    B = 2
    AB = 3


def main() -> None:
    print(F.A | F.B is F.AB, I.A | I.B is I.AB)
    print(F.AB, I.AB, int(I.AB), list(F), list(I))
    print((F.A | F.B) & F.A, (I.A | I.B) & I.B)


main()
'''

UNIQUE_ENUM = r'''from enum import Enum, unique


@unique
class E(Enum):
    A = 1
    B = 1.0


print(E.A)
'''

UNIQUE_FLAG = r'''from enum import Flag, unique


@unique
class F(Flag):
    A = 1
    B = 1


print(F.A)
'''

MEMBER_VALUE = r'''from enum import Enum


class E(Enum):
    A = 1
    B = 1


print(E.A.value, E.B.name, E.A is E.B)
E.A.value = 9
print(E.A.value)
'''

MEMBER_NAME = r'''from enum import Enum


class E(Enum):
    A = 1


E.A.name = "X"
print(E.A.name)
'''

MEMBER_AUG = r'''from enum import IntEnum


class E(IntEnum):
    A = 1


print(E.A.value, E.A.name, E.A + 1)
E.A.value += 1
print(E.A.value)
'''

EQFALSE_HASH_SEMANTICS = r'''from dataclasses import dataclass


@dataclass(eq=False)
class P:
    x: int


class Base:
    def __hash__(self) -> int:
        return 7
    def __eq__(self, other) -> bool:
        return True


@dataclass(eq=False)
class Q(Base):
    x: int


@dataclass(eq=False)
class H:
    x: int
    __hash__ = lambda self: 11


@dataclass(eq=False)
class N:
    x: int
    __hash__ = None


@dataclass
class E:
    x: int


@dataclass(eq=False)
class C(E):
    y: int


def h(x) -> int:
    return hash(x)


def main() -> None:
    a = P(1)
    b = P(1)
    print(a == b, hash(a) == hash(b), len({a, b}), {a: "a", b: "b"}[b])
    print(hash(Q(1)), Q(1) == Q(2), hash(H(1)))
    for cls in (N, C):
        try:
            hash(cls(1) if cls is N else cls(1, 2))
        except TypeError as exc:
            print(type(exc).__name__, str(exc))
    print(h(a) == hash(a), h([a][0]) == hash(a), h({"k": a}["k"]) == hash(a))


main()
'''

INLINE_TAB_DATACLASS = '''from dataclasses import dataclass


@dataclass
class E: pass


@dataclass
class D: """doc"""


@dataclass
class A: tag = 3


@dataclass(eq=False)
class F: pass


@dataclass
class T:
\tpass


def main() -> None:
    print(E(), repr(E()), E() == E())
    print(D(), D() == D())
    print(A(), A.tag, A() == A())
    f = F()
    print(f == F(), hash(f) == hash(f))
    print(T(), T() == T())


main()
'''

ENUM_TUPLE_TARGET = r'''from enum import Enum


class E(Enum):
    A = 1


def main() -> None:
    E.A.value, x = 9, 2
    print(E.A.value, x)


main()
'''

ENUM_FOR_TARGET = r'''from enum import Enum


class E(Enum):
    A = 1


def main() -> None:
    for E.A.name in ["X"]:
        print(E.A.name)


main()
'''

ENUM_SETATTR_TARGET = r'''from enum import Enum


class E(Enum):
    A = 1


def main() -> None:
    setattr(E.A, "value", 9)
    print(E.A.value)


main()
'''

ENUM_NESTED_TARGET = r'''from enum import Enum


class E(Enum):
    A = 1


def main() -> None:
    [E.A.value for E.A.name in ["X"]]
    E.A.value: int = 9


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general):
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
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz17Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz17-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, err))

    def refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz17-r-') as directory:
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNone(got, '%s (general=%s) built\n%s' % (text[:2000], general, err))
                self.assertIn(needle, err, '%s (general=%s)\n%s' % (text[:2000], general, err))

    def test_empty_dataclass(self):
        self.check('empty_dataclass', EMPTY_DATACLASS)

    def test_eq_false_dataclass_is_hashable(self):
        self.check('eqfalse_hash', EQFALSE_HASH)

    def test_enum_aliases_by_value(self):
        self.check('enum_aliases', ENUM_ALIASES)

    def test_flag_composites_are_not_aliases(self):
        self.check('flag_aliases', FLAG_ALIASES)

    def test_unique_duplicate_enum_is_refused(self):
        self.refused('unique_enum', UNIQUE_ENUM, '@unique with a duplicate value')

    def test_unique_duplicate_flag_is_refused(self):
        self.refused('unique_flag', UNIQUE_FLAG, '@unique with a duplicate value')

    def test_enum_member_value_assignment_is_refused(self):
        self.refused('member_value', MEMBER_VALUE, 'setting .value is not built')

    def test_enum_member_name_assignment_is_refused(self):
        self.refused('member_name', MEMBER_NAME, 'setting .name is not built')

    def test_enum_member_augmented_assignment_is_refused(self):
        self.refused('member_aug', MEMBER_AUG, 'setting .value is not built')

    def test_eq_false_hash_semantics(self):
        self.check('eqfalse_hash_semantics', EQFALSE_HASH_SEMANTICS)

    def test_inline_and_tab_empty_dataclass(self):
        self.check('inline_tab_dataclass', INLINE_TAB_DATACLASS)

    def test_enum_member_write_through_tuple_target_is_refused(self):
        self.refused('enum_tuple_target', ENUM_TUPLE_TARGET, 'setting .value is not built')

    def test_enum_member_write_through_for_target_is_refused(self):
        self.refused('enum_for_target', ENUM_FOR_TARGET, 'setting .name is not built')

    def test_enum_member_write_through_setattr_is_refused(self):
        self.refused('enum_setattr', ENUM_SETATTR_TARGET, 'setting .value is not built')

    def test_enum_member_write_through_nested_targets_is_refused(self):
        self.refused('enum_nested_target', ENUM_NESTED_TARGET, 'setting .')


if __name__ == '__main__':
    unittest.main()
