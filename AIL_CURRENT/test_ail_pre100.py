"""`%d` of a float on the general path (job pre100).

CPython's `%d` truncates a float toward zero and prints the whole integer, even when it is
larger than an int64 (`"%d" % 1e20` prints `100000000000000000000`). The general runtime
converted the float to int64 first, so a finite value past the boundary stopped with
`integer overflow` (dynamic format) or `TypeError` (literal format). Both builds now format
the truncated value as decimal digits directly, so every route matches CPython: a literal, a
name bound to a float, a function argument, a list item, an attribute, a dict value and a
run-time format string. NaN and infinity keep CPython's ValueError / OverflowError.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None
sys.path.insert(0, str(ROOT))


def surface(text):
    import ail_syntax
    return ail_syntax.fold_constants(ail_syntax.python_surface(text))


def build_general(directory, text, name):
    source, exe = Path(directory, name + '_g.ail'), Path(directory, name + '_g')
    source.write_text(surface(text), encoding='utf-8')
    env = dict(os.environ, AIL_IR='0', AIL_NO_CACHE='1', AIL_SURFACE='python')
    env.pop('AIL_NO_GENERAL', None)
    return subprocess.run([sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only'],
                          cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def build_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_d')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
    env.pop('AIL_NO_GENERAL', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                           'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def run(cmd, directory):
    return subprocess.run(cmd, cwd=directory, capture_output=True, timeout=300)


FLOAT_PERCENT_D = r"""def via_arg(x):
    return "%d" % x


class Box:
    pass


def main():
    vals = [0.0, -0.0, 1.9, -1.9, 0.5, -0.5, 7.0, -7.0, 1e15, -1e15,
            9.3e18, 1e19, -1e19, 1e20, -1e20, 1.7976931348623157e308]
    for v in vals:
        print("%d" % v)
    print("%5d|%-5d|%+d|% d|%05d|%.3d|%8.3d" % (1.9, 1.9, 1.9, 1.9, -1.9, 3.7, 3.7))
    print("%d|%d|%d" % (7, -7, 5))
    print(via_arg(1e20), via_arg(-1.9))
    xs = [1.9, 1e20]
    print("%d" % xs[0], "%d" % xs[1])
    b = Box()
    b.x = 9.3e18
    print("%d" % b.x)
    d = {"k": -1e20}
    print("%d" % d["k"])
    alias = 1.9
    other = alias
    print("%d" % other)
    fmt = "%d"
    print(fmt % 1e20, fmt % 1.9, fmt % -1e20)
    for v in (float("nan"), float("inf"), float("-inf")):
        try:
            print("%d" % v)
        except (ValueError, OverflowError) as e:
            print(type(e).__name__, e)


main()
"""

CASES = [('float_percent_d', FLOAT_PERCENT_D)]


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class FloatPercentD(unittest.TestCase):
    def check(self, name, text, general):
        with tempfile.TemporaryDirectory() as directory:
            builder = build_general if general else build_default
            built, exe = builder(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            source = Path(directory, name + '_cpython.py')
            source.write_text(text, encoding='utf-8')
            want = run([sys.executable, str(source)], directory)
            got = run([str(exe)], directory)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])
            self.assertEqual(got.stdout, want.stdout, name)

    def test_general(self):
        for name, text in CASES:
            with self.subTest(name):
                self.check(name, text, True)

    def test_default(self):
        for name, text in CASES:
            with self.subTest(name):
                self.check(name, text, False)


if __name__ == '__main__':
    unittest.main()
