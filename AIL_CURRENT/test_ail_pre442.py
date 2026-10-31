"""pre442: an IntEnum member value that CPython's int() rejects is refused by name.

The pre411 review recorded as pre-existing that ``class E(IntEnum): A = "0x10"`` was accepted
on both builds, where CPython raises ``ValueError: invalid literal for int() with base 10:
'0x10'`` while the class statement runs (enum.py ``__set_name__`` creates each member with
``int(value)``).  The class was then only rejected when the member was used as an index, with a
different message and a different point in the program.

The enum lowering now applies CPython's conversion to every literal member value of an
``IntEnum`` and refuses a value that ``int()`` rejects (a tuple value is unpacked as CPython
does: ``A = ("5", 10)`` is ``int("5", 10)``).  Non-literal values are left to the run time, and
the pre-existing ``.value`` normalisation difference (a float or a str stays raw here) is
unchanged.

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython, or the compile is refused with the message below.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'which int() rejects at class creation in CPython'

MATCHING = {
    'decimal_strings': '''
from enum import IntEnum

class E(IntEnum):
    S = "5"
    NEG = "-1"
    UNDER = "1_0"
    PAD = " 5 "

a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
print(E.S.__index__(), E.NEG.__index__(), E.UNDER.__index__(), E.PAD.__index__())
print(a[E.S], a[E.NEG], a[E.UNDER], a[E.PAD])
''',
    'float_bool_bytes': '''
from enum import IntEnum

class E(IntEnum):
    ONE = 1.5
    NEG = -1.5
    ZERO = 0.0
    TWO = 2.0
    T = True
    F = False
    B = b"2"

print(E.ONE.__index__(), E.NEG.__index__(), E.ZERO.__index__(), E.TWO.__index__())
print(E.T.__index__(), E.F.__index__(), E.B.__index__())
print([10, 20, 30][E.TWO], [10, 20, 30][E.B])
''',
    'auto_values': '''
from enum import IntEnum, auto

class E(IntEnum):
    A = auto()
    B = auto()

print(E.A.__index__(), E.B.__index__())
''',
    'value_routes': '''
from enum import IntEnum

class E(IntEnum):
    FIVE = "5"


def at(i):
    return i


a = [10, 20, 30, 40, 50, 60]
n = E.FIVE
print(a[n], a[at(E.FIVE)])
items = [E.FIVE]
print(a[items[0]])
class Box:
    pass
box = Box()
box.i = E.FIVE
print(a[box.i])
d = {"k": E.FIVE}
print(a[d["k"]])
print(a[E.FIVE])
''',
}

REFUSED = {
    'hex_string': 'A = "0x10"',
    'hex_string_indexed': 'A = "0x10"\nprint([10, 20, 30][E.A])',
    'binary_string': 'A = "0b11"',
    'empty_string': 'A = ""',
    'blank_string': 'A = "  "',
    'decimal_point_string': 'A = "1.5"',
    'signed_hex_string': 'A = "-0x10"',
    'none_value': 'A = None',
    'complex_value': 'A = 1j',
    'tuple_pair': 'A = (1, 2)',
    'tuple_three': 'A = (1, 2, 3)',
    'alias_repeat': 'A = "0x10"\n    B = "0x10"',
    'second_member': 'OK = 1\n    BAD = "no"',
}


def refused_program(body):
    return 'from enum import IntEnum\n\nclass E(IntEnum):\n    %s\n' % body


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
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class Pre442(unittest.TestCase):
    def test_valid_member_values_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre442-') as directory:
            for name, text in MATCHING.items():
                want, status = run_cpython(directory, name, text)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        built, exe = build(directory, name, text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                                             cwd=directory)
                        self.assertEqual(ran.returncode, status, ran.stderr[-1200:])
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), want, ran.stderr[-1200:])

    def test_rejected_member_values_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre442-') as directory:
            for name, body in REFUSED.items():
                text = refused_program(body)
                _, status = run_cpython(directory, name, text)
                self.assertNotEqual(status, 0, (name, 'CPython accepts this value'))
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        built, _ = build(directory, name, text, general)
                        output = built.stdout + built.stderr
                        self.assertNotEqual(built.returncode, 0, (name, output))
                        self.assertIn('IntEnum member', output, (name, output))
                        self.assertIn(MESSAGE, output, (name, output))


if __name__ == '__main__':
    unittest.main()
