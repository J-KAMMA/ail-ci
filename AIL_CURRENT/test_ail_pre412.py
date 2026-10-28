"""pre412: an IntEnum whose declared value is a float or a str indexes by its int value.

An IntEnum member keeps the value written in the class body, so ``class E(IntEnum): A = 1.5``
has ``E.A.value == 1.5`` here where CPython normalises it to ``1``.  ``__index__`` returned
that raw value too, so every subscription by such a member raised
``TypeError: list indices must be integers or slices, not float``.  It now converts the value
through ``int()``, which is CPython's normalisation for the index protocol: a float truncates,
a decimal string is parsed, and a member of another IntEnum uses its own int value.  The
pre-existing ``.value`` difference is unchanged and not checked here.

Only the int64 range is covered: a declared float/str that normalises outside the signed
64-bit range keeps the ordinary fixed-width run-time trap.  Bytes, bytearray and deque
subscription, slice bounds, sequence repeat and ``pop(i)`` are separate pre-existing causes and
are not part of this module.

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'float_value': '''
from enum import IntEnum

class E(IntEnum):
    ONE = 1.5
    NEG = -1.5
    ZERO = 0.0
    TWO = 2.0
    ONE_ALIAS = 1


def at(i):
    return i


a = [10, 20, 30, 40]
print(E.ONE.__index__())
print([10, 20, 30].index(20, E.ONE))
print("abcabc".find("b", E.ONE))
n = E.ONE
print(a[n])
print(a[at(E.ONE)])
items = [E.ONE]
print(a[items[0]])
class Box:
    pass
box = Box()
box.i = E.ONE
print(a[box.i])
d = {"k": E.ONE}
print(a[d["k"]])
print(a[E.ONE_ALIAS])
print(a[E.NEG])
print(a[E.ZERO])
print(a[E.TWO])
print((1, 2, 3)[E.TWO])
print("abcd"[E.ONE])
print(a[at(E.NEG)])
try:
    print([][E.ZERO])
except IndexError as exc:
    print(type(exc).__name__)
''',
    'string_value': '''
from enum import IntEnum

class E(IntEnum):
    FIVE = "5"
    ONE = "1"
    NEG = "-1"
    ZERO = "0"
    TWO = "2"
    FIVE_ALIAS = 5


def at(i):
    return i


a = [10, 20, 30, 40, 50, 60]
print(E.FIVE.__index__())
print([10, 20, 30].index(20, E.ONE))
print("abcabc".find("b", E.ONE))
n = E.FIVE
print(a[n])
print(a[at(E.FIVE)])
items = [E.FIVE]
print(a[items[0]])
class Box:
    pass
box = Box()
box.i = E.FIVE
print(a[box.i])
d = {"k": E.FIVE}
print(a[d["k"]])
print(a[E.FIVE_ALIAS])
print(a[E.NEG])
print(a[E.ZERO])
print(a[E.TWO])
print((1, 2, 3)[E.TWO])
print("abcd"[E.TWO])
print(a[at(E.NEG)])
try:
    print([][E.ZERO])
except IndexError as exc:
    print(type(exc).__name__)
''',
    'int64_bounds': '''
from enum import IntEnum

class E(IntEnum):
    MAX = "9223372036854775807"
    MIN = "-9223372036854775808"
    NEGONE = "-1"

for m in (E.MAX, E.MIN, E.NEGONE):
    try:
        print([][m])
    except IndexError as exc:
        print(type(exc).__name__)
print([7, 8, 9][E.NEGONE])
''',
}


def run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace('\r\n', '\n'), done.returncode


def build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre412(unittest.TestCase):
    def test_normalised_intenum_index_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre412-') as directory:
            for name, text in PROGRAMS.items():
                want, status = run_cpython(directory, name, text)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        built, exe = build(directory, name, text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                                             cwd=directory)
                        self.assertEqual(ran.returncode, status, ran.stderr[-1200:])
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), want, ran.stderr[-1200:])


if __name__ == '__main__':
    unittest.main()
