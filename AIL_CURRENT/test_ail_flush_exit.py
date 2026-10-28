"""stdout written before an uncaught exception reaches the output, as CPython does (flush, traceback, exit 1).

A mixed program (the general path with typed clones of its numeric functions, pymix.py) lost every `print`
made before a clone trapped: the clone is its own translation unit and flushed only its stdio buffer, while the
boxed program's text sat in its own buffer (cx->out_buf). Both trap paths of a clone (`ail_die` and the uncaught
exception) now drain that buffer first (pyboxed2._mix_drain_before_exit).

Each program is compiled by pyc.py (AIL_IR=1 and 0) and by the typed path alone where it builds, run with stdout
a pipe, and must print what CPython prints, with CPython's exit status. The mixed programs are checked to be
mixed (a `_mix0.c` clone exists), so the test cannot pass by the program quietly staying boxed.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')

MIXED_DIV = r'''
def risky(a: int, b: int) -> int:
    return a // b

def main():
    d = {"k": [1, 2, 3]}
    for k in d:
        print("key", k, d[k])
    print("before")
    print(risky(5, 0))
    print("never")
main()
'''

MIXED_RAISE = r'''
def chk(n):
    if n > 2:
        raise ValueError("too big")
    return n
objs = {"a": 1, "b": [1, 2]}
print(objs)
for i in range(5):
    print(chk(i))
'''

MIXED_INT = r'''
def conv(s: str) -> int:
    return int(s)

box = {"a": 1}
print("start", box)
print(conv("12"))
print(conv("x1"))
print("never")
'''

MIXED_BIG = r'''
def risky(a: int, b: int) -> int:
    return a // b

def main():
    d = {"k": [1, 2, 3]}
    for i in range(30000):
        print("row", i, d["k"][i % 3])
    print(risky(7, 0))
main()
'''

MIXED_CAUGHT = r'''
def risky(a: int, b: int) -> int:
    return a // b

table = {"n": 1}
print("one", table)
try:
    print(risky(1, 0))
except ZeroDivisionError:
    print("caught")
print(risky(4, 2))
print(risky(1, 0))
'''

GENERAL_USER_EXC = r'''
class Boom(Exception):
    pass

def go(d):
    print("go", d)
    raise Boom("x")

print("start")
go({"a": 1})
'''

GENERAL_KEY = r'''
d = {"a": [1, 2]}
for i in range(3):
    print("i", i, d)
print(d["zz"])
'''

TYPED_DIV = r'''
def f(n: int) -> int:
    return 10 // n

print("before")
print(f(0))
'''

TYPED_INDEX = r'''
xs = [1, 2, 3]
print("before")
print("x", end="")
print(xs[5])
'''

TYPED_INT = r'''
print("a")
print(int("abc"))
'''


class FlushExit(unittest.TestCase):
    def run_one(self, name, text, mixed=False, modes=('1', '0'), typed=True):
        with tempfile.TemporaryDirectory(prefix='ail-flushexit-') as tmp:
            src = Path(tmp) / (name + '.py')
            src.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                                  env=dict(os.environ, PYTHONUTF8='1'))
            self.assertEqual(want.returncode, 1, want.stderr.decode()[-500:])
            self.assertTrue(want.stdout)
            runs = [('ir' + m, {'AIL_IR': m}) for m in modes]
            if typed:
                runs.append(('typed', {'AIL_NO_GENERAL': '1'}))
            for label, extra in runs:
                env = dict(os.environ, AIL_SURFACE='python', **extra)
                env.pop('AIL_NO_MIX', None)
                exe = Path(tmp) / ('exe_' + label)
                built = subprocess.run([sys.executable, '-B', PYC, str(exe), '--file', str(src)], cwd=tmp,
                                       capture_output=True, text=True, timeout=900, env=env)
                if label == 'typed' and built.returncode:
                    continue                                  # this program needs the general path
                self.assertEqual(built.returncode, 0, label + ': ' + built.stderr[-1500:])
                if mixed and label != 'typed':
                    self.assertTrue(list(Path(tmp).glob('exe_%s_mix*.c' % label)), label + ': no typed clone')
                got = subprocess.run([str(exe)], cwd=tmp, capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
                self.assertEqual(got.stdout.decode(), want.stdout.decode(), label)
                self.assertEqual(got.returncode, 1, label + ': ' + got.stderr.decode()[-500:])

    def test_mixed_zero_division_in_clone(self):
        self.run_one('mixed_div', MIXED_DIV, mixed=True)

    def test_mixed_raise_in_clone(self):
        self.run_one('mixed_raise', MIXED_RAISE, mixed=True)

    def test_mixed_int_value_error_in_clone(self):
        # (int(text) returns an exact tagged int now, so `conv` is no longer given a typed int64 clone: the program
        # still has to flush what it printed before the uncaught ValueError)
        self.run_one('mixed_int', MIXED_INT)

    def test_mixed_output_beyond_one_buffer(self):
        self.run_one('mixed_big', MIXED_BIG, mixed=True)

    def test_mixed_caught_then_uncaught(self):
        self.run_one('mixed_caught', MIXED_CAUGHT)

    def test_general_user_exception(self):
        self.run_one('general_exc', GENERAL_USER_EXC)

    def test_general_key_error(self):
        self.run_one('general_key', GENERAL_KEY)

    def test_typed_division(self):
        self.run_one('typed_div', TYPED_DIV)

    def test_typed_index(self):
        self.run_one('typed_index', TYPED_INDEX)

    def test_typed_int(self):
        self.run_one('typed_int', TYPED_INT)


if __name__ == '__main__':
    unittest.main()
