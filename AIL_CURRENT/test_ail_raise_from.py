"""`raise X from Y`, `raise X from None` and a bare `except:` (python/pkg-v12/raisefrom.py, pyfunc.py), against CPython 3.12.

R1  a fixed program: chained raises caught by class and by a bare except, re-raised, and one left uncaught
    (exit status 1, `Type: message` on stderr, DIFFERENCES A4): the typed path alone (IR 0 and 1) and the
    general path print what CPython prints and exit with its status.
R2  refused by name: a program that reads `__cause__` (the cause is not kept), a bare except in a program
    that calls sys.exit() (CPython's bare except takes the SystemExit) -- on the typed path and the general.
R3  random programs: nested try/except with raise-from, bare excepts and the runtime's own exceptions
    (int("x"), a zero division, an index out of range): CPython == typed path (IR 0 and 1) == general path.
"""
import os
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from test_ail_nested_functions import build, build_general, run_cpython, run_exe   # noqa: E402

HAVE_CC = shutil.which('gcc') is not None
SEEDS = int(os.environ.get('AIL_RAISE_FROM_SEEDS', '10'))

FIXED = '''def parse(s: str) -> int:
    try:
        return int(s)
    except ValueError as exc:
        raise RuntimeError("bad number: " + s) from exc


def checked(n: int) -> int:
    if n < 0:
        raise ValueError("negative") from None
    return n * 2


def safe(s: str) -> int:
    try:
        return parse(s)
    except:
        return -1


def main() -> None:
    print(parse("12"))
    try:
        parse("zz")
    except RuntimeError as e:
        print("caught", e)
    print(checked(4))
    try:
        checked(-1)
    except ValueError as e:
        print("caught", e)
    print(safe("7"), safe("x"))
    try:
        try:
            checked(-3)
        except ValueError:
            raise
    except:
        print("bare")
    parse("q")


main()
'''

REFUSED = {
    'cause': ('def main() -> None:\n    try:\n        try:\n            int("x")\n        except ValueError as e:\n'
              '            raise RuntimeError("r") from e\n    except RuntimeError as r:\n'
              '        print(repr(r.__cause__))\n\n\nmain()\n', '__cause__'),
    'exit': ('import sys\n\n\ndef main() -> None:\n    try:\n        sys.exit(3)\n    except:\n'
             '        print("caught")\n\n\nmain()\n', 'SystemExit'),
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Fixed(unittest.TestCase):
    def test_typed_and_general_paths(self):
        with tempfile.TemporaryDirectory(prefix='ail-raise-') as tmp:
            want = run_cpython(tmp, FIXED, 'fixed')
            self.assertEqual(want.returncode, 1)
            for ir in ('0', '1'):
                res, exe = build(tmp, FIXED, 'fixed', ir=ir)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (1, want.stdout))
                self.assertEqual(got.stderr.strip().splitlines()[-1], 'RuntimeError: bad number: q')
            res, exe = build_general(tmp, FIXED, 'fixed')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (1, want.stdout))

    def test_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-raise-') as tmp:
            for name, (text, word) in REFUSED.items():
                with self.subTest(name=name):
                    for typed_only in (True, False):
                        res, _ = build(tmp, text, name + str(typed_only), typed_only=typed_only)
                        self.assertEqual(res.returncode, 3, res.stderr)
                        self.assertIn(word, res.stderr)


def gen_program(seed):
    rng = random.Random(seed)
    ops = ['int(s)', 'n // (n - %d)' % rng.randint(0, 3), 'xs[n]', 'len(s) + n']
    lines = ['def step(s: str, n: int) -> int:', '    xs = [1, 2, 3]']
    for k in range(rng.randint(2, 4)):
        lines.append('    try:')
        lines.append('        v%d = %s' % (k, rng.choice(ops)))
        kind = rng.choice(['ValueError', 'ZeroDivisionError', 'IndexError', None])
        if kind:
            lines.append('    except %s as e%d:' % (kind, k))
        else:
            lines.append('    except:')
        r = rng.random()
        if r < 0.3:
            lines.append('        raise RuntimeError("step %d " + s)%s' % (k, ' from e%d' % k if kind else ' from None'))
        elif r < 0.5:
            lines.append('        raise ValueError("again %d") from None' % k)
        elif r < 0.7 and kind:
            lines.append('        print("caught %d", e%d)' % (k, k))
            lines.append('        v%d = -1' % k)
        else:
            lines.append('        v%d = %d' % (k, k * 10))
        lines.append('    n = n + v%d %% 5' % k)
    lines.append('    return n')
    lines += ['', '', 'def main() -> None:']
    for s, n in [('7', 1), ('x', 0), ('12', 3), ('', 2), ('3', 5)]:
        lines.append('    try:')
        lines.append('        print(step(%r, %d))' % (s, n))
        lines.append('    except RuntimeError as e:')
        lines.append('        print("runtime", e)')
        lines.append('    except:')
        lines.append('        print("other")')
    lines += ['', '', 'main()', '']
    return '\n'.join(lines)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Random(unittest.TestCase):
    def test_random_programs(self):
        with tempfile.TemporaryDirectory(prefix='ail-raise-rand-') as tmp:
            for seed in range(SEEDS):
                text = gen_program(seed)
                name = 'r%d' % seed
                with self.subTest(seed=seed):
                    want = run_cpython(tmp, text, name)
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, 'seed %d: %s\n%s' % (seed, res.stderr[-1500:], text))
                        got = run_exe(exe)
                        self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout),
                                         'seed %d IR=%s\n%s' % (seed, ir, text))
                    res, exe = build_general(tmp, text, name)
                    self.assertEqual(res.returncode, 0, res.stderr[-1500:])
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout),
                                     'seed %d general\n%s' % (seed, text))


if __name__ == '__main__':
    unittest.main()
