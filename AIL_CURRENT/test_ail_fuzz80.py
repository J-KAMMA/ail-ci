"""Differential fuzz round 80: enum details.

Found with ten small programs compared against CPython on both builds: an empty `Flag` (`IntFlag`)
accepted `F(0)` and made a pseudo-member `<F: 0>` where CPython raises TypeError.  Calling an
empty `Enum`, `IntEnum`, `StrEnum`, `Flag` or `IntFlag` is now refused by name at compile time on
both builds; an empty enum that is only iterated or used as a base class for a non-empty enum still
builds and matches CPython.  Members as dict keys, iteration order (aliases, Flags), value lookup
errors, IntEnum arithmetic, `auto()` and enum values in `match` patterns were compared and agreed.

Other differences seen in the same ten programs (not fixed here): `+IntEnum` (unary plus) is a
TypeError on both builds, and a `StrEnum` member as a dict key does not find its plain `str` key
(`d[S.A]` works, `d["a"]` raises KeyError). Both are reported in the job report.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EMPTY_USE = {
    kind: 'from enum import %s\n\nclass E(%s):\n    pass\n\nprint(list(E), len(E), E.__members__)\n' % (kind, kind)
    for kind in ('Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag')
}

EMPTY_CALL = {
    kind: 'from enum import %s\n\nclass E(%s):\n    pass\n\nprint(E(0))\n' % (kind, kind)
    for kind in ('Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag')
}

EMPTY_BASE = r'''from enum import Enum


class Base(Enum):
    def describe(self) -> str:
        return "value=" + str(self.value)

    @property
    def doubled(self) -> int:
        return self.value * 2


class A(Base):
    X = 1
    Y = 2


print(A.X.describe(), A.X.doubled, list(A), len(A))
print([(m.name, m.value) for m in A])
'''

NONEMPTY = r'''from enum import Enum, IntEnum, Flag, IntFlag, auto


class E(Enum):
    Z = 3
    A = 1
    M = 2
    A2 = 1


class I(IntEnum):
    C = 3
    A = 1
    B = 2


class F(Flag):
    B = 2
    A = 1
    C = 4


class G(IntFlag):
    HIGH = 4
    LOW = 1
    MID = 2


def main() -> None:
    print([e.name for e in E])
    print([i.name for i in I], len(E), len(I))
    print([f.name for f in F])
    print([g.name for g in G])
    print({E.A: 1, E.A2: 2}[E.A], {I.A: 1, 1: 2}[1])
    print([(m.name, m.value) for m in F])
    for v in (E.M, E.A):
        match v:
            case E.Z:
                print("z")
            case E.M:
                print("m")
            case _:
                print("other")


main()
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


class Fuzz80Tests(unittest.TestCase):
    def check_matches_cpython(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz80-') as directory:
            want, code, err = _cpython(directory, name, text)
            self.assertEqual(code, 0, err)
            for general in (True, False):
                built, exe = _build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, code),
                                 got.stderr.decode('utf-8', 'replace')[-1500:])

    def test_empty_enums_iterate_as_cpython(self):
        for kind, text in EMPTY_USE.items():
            with self.subTest(kind=kind):
                self.check_matches_cpython(kind + '_use', text)

    def test_empty_enum_calls_are_refused_by_name(self):
        for kind, text in EMPTY_CALL.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='ail-fuzz80-') as directory:
                want, code, err = _cpython(directory, kind, text)
                self.assertNotEqual(code, 0, want)
                for general in (True, False):
                    built, exe = _build(directory, '%s_%s' % (kind, 'g' if general else 'd'), text, general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertIn('has no members this compiler builds; calling an empty %s is not built' % kind,
                                  built.stdout + built.stderr)
                    self.assertFalse(exe.exists())

    def test_empty_enum_base_can_be_extended(self):
        self.check_matches_cpython('empty_base', EMPTY_BASE)

    def test_nonempty_enums_still_match_cpython(self):
        self.check_matches_cpython('nonempty', NONEMPTY)


if __name__ == '__main__':
    unittest.main()
