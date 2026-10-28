"""pre47: constant integer expressions are folded before code generation.

`-(-2)**63` is exactly 2**63, so CPython prints 9223372036854775808. The compiler used to
emit the inner `(-2)**63` (which fits int64) and then negate it, stopping at run time with
`integer overflow`. Constant integer expressions whose value fits int64 are now emitted as
one literal; one whose value does not fit int64 is a big integer (bigint, BIGINT.md) that
builds on both the default and the general path and prints CPython's value. `2**63 - 1` and `-2**63` are in range and must still be right.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None


def build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_SURFACE='python', AIL_IR='0')
    env.pop('AIL_NO_GENERAL', None)
    cmd = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name]
    if general:
        cmd.append('--general-only')
    result = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return result, exe


def cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', source.name], cwd=directory, capture_output=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Pre47(unittest.TestCase):
    def check_program(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre47-') as directory:
            want = cpython(directory, name, text)
            for general in (False, True):
                mode = 'general' if general else 'default'
                with self.subTest(program=name, mode=mode, step='build'):
                    built, exe = build(directory, name + '_' + mode, text, general)
                    self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
                with self.subTest(program=name, mode=mode, step='run'):
                    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout.replace(b'\r\n', b'\n'))
                    self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])

    def check_refused(self, name, text):
        # exact ints (bigint): builds and matches CPython (stdout, exit code)
        self.check_program(name, text)

    def test_in_range_constants_match_cpython(self):
        self.check_program('in_range', '''def show(x):
    print(x)


print(-2**63)
print(2**63-1)
print((-2)**62)
print((2**70)//(2**10))
print(1**1000000)
print(0**0)
print((-1)**1001)
print(1<<62)
print(-1>>100)
show((2**63-1)//3)
show([(-2)**63][0])

class Box:
    def __init__(self):
        self.v = 2**63-1


print(Box().v)
print({'a': (-2)**63}['a'])
''')

    def test_int64_min_in_pipeline_element(self):
        # A folded INT64_MIN reaches the pipeline emitter as Python spells it, a unary minus over
        # the positive literal 9223372036854775808. Emitting ck_neg(9223372036854775808) trapped on
        # the value the constant denotes; this is the pipeline counterpart of the script cases above.
        cases = {
            'pipe_neg_pow': 'sum((-2**63) for x in xs)',
            'pipe_add': 'sum(x + (-2**63) for x in xs)',
            'pipe_shift': 'sum(-1 << 63 for x in xs)',
            'pipe_max': 'max((-2**63) for x in xs)',
            'pipe_min_guard': 'min((-2**63) for x in xs if x == 0)',
        }
        with tempfile.TemporaryDirectory(prefix='ail-pre47-') as directory:
            (Path(directory) / 'data.bin').write_bytes(struct.pack('<q', 0))
            for name, text in cases.items():
                with self.subTest(program=name, step='build'):
                    built, exe = build(directory, name, text + '\n', False)
                    self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
                with self.subTest(program=name, step='run'):
                    got = subprocess.run([str(exe), 'data.bin'], cwd=directory,
                                         capture_output=True, timeout=120)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'),
                                     b'-9223372036854775808\n')
                    self.assertEqual(got.returncode, 0, got.stderr[-500:])

    def test_negated_even_power_is_refused(self):
        self.check_refused('negated', 'print(-(-2)**63)\n')

    def test_out_of_range_constants_are_refused(self):
        cases = {
            'pow': 'print(2**63)\n',
            'decimal': 'print(10**40)\n',
            'shift': 'print(1<<63)\n',
            'cancel': 'print((2**70)//(2**5))\n',
            'huge': 'print(2**10000)\n',
            'argument': 'def show(x):\n    print(x)\n\nshow(2**63)\n',
            'list': 'print([2**63])\n',
            'attribute': 'class Box:\n    def __init__(self):\n        self.v = 2**63\n\n\nprint(Box().v)\n',
            'dict': "print({'a': 2**63})\n",
        }
        for name, text in cases.items():
            self.check_refused(name, text)


if __name__ == '__main__':
    unittest.main()
