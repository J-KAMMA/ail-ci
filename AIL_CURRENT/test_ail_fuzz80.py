"""Differential fuzz round 80: enum details.

Found with ten small programs compared against CPython on both builds: an empty `Enum` (or
`IntEnum`, `StrEnum`, `Flag`, `IntFlag`) class was accepted, and iterating it printed what CPython
prints, but `E(0)` printed `E(0)` (a pseudo-member) where CPython raises TypeError and `F(0)`
became a member where CPython raises TypeError too. An empty enum class is now refused by name at
compile time on both builds. Members as dict keys, iteration order (aliases, Flags), value lookup
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

EMPTY = {
    'Enum': 'from enum import Enum\n\nclass E(Enum):\n    pass\n\nprint(list(E))\n',
    'IntEnum': 'from enum import IntEnum\n\nclass E(IntEnum):\n    pass\n\nprint(list(E))\n',
    'StrEnum': 'from enum import StrEnum\n\nclass E(StrEnum):\n    pass\n\nprint(list(E))\n',
    'Flag': 'from enum import Flag\n\nclass E(Flag):\n    pass\n\nprint(list(E))\n',
    'IntFlag': 'from enum import IntFlag\n\nclass E(IntFlag):\n    pass\n\nprint(list(E))\n',
}

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
    def test_empty_enums_are_refused_by_name(self):
        for kind, text in EMPTY.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='ail-fuzz80-') as directory:
                want, code, err = _cpython(directory, kind, text)
                self.assertEqual((want, code), (b'[]\n', 0), err)
                for general in (True, False):
                    built, exe = _build(directory, '%s_%s' % (kind, 'g' if general else 'd'), text, general)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertIn('has no members this compiler builds; an empty %s is not built' % kind, built.stdout + built.stderr)
                    self.assertFalse(exe.exists())

    def test_nonempty_enums_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz80-') as directory:
            want, code, err = _cpython(directory, 'nonempty', NONEMPTY)
            self.assertEqual(code, 0, err)
            for general in (True, False):
                built, exe = _build(directory, 'nonempty_%s' % ('g' if general else 'd'), NONEMPTY, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, code),
                                 got.stderr.decode('utf-8', 'replace')[-1500:])


if __name__ == '__main__':
    unittest.main()
