"""pre227: a class constant built through a known module name is folded exactly.

A class body evaluates `X = N * 4` at run time, so `N = 2**62` stopped with ``integer
overflow`` where CPython keeps an unbounded int, and `N = 2**61; X = N * 2 - 1` trapped
although the final value fits.  `fold_constants` now resolves a module name bound once
before the class into the class-level constant expression (wide intermediate steps
allowed), so an in-range value is emitted as a literal and a value that cannot fit int64
is refused by name at compile time on both builds.  Values that only reach the class body
at run time keep the fixed-width trap, and a nested class definition is refused by name.

The refusal wording depends on which check sees the folded literal: the literal check says
``int64 literal out of range``, while the later module/class constant check says
``int64 constant expression out of range``.  Either named refusal is accepted here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = ('int64 literal out of range', 'int64 constant expression out of range')

OUT_OF_RANGE = {
    'mult': '''N = 2**62
class C:
    X = N * 4
print(C.X)
''',
    'shift': '''N = 2**62
class C:
    X = N << 2
print(C.X)
''',
    'power': '''N = 2**40
class C:
    X = N ** 2
print(C.X)
''',
    'negative': '''N = 2**62
class C:
    X = -N * 2 - 1
print(C.X)
''',
    'alias': '''N = 2**62
M = N
class C:
    X = M * 4
print(C.X)
''',
    'annotated': '''N = 2**62
class C:
    X: int = N * 4
print(C.X)
''',
}

IN_RANGE = r'''N = 2**62
M = N
N61 = 2**61
N60 = 2**60
R = 2**62
R = 2
TS = "ab"
TF = 2.5
TB = True


class C:
    A = N * 2 - 1
    B = (N * 4) // 4
    D = N // 2
    E = -N * 2
    G = N + 1
    H = N % 3
    I = N >> 1
    J = N61 * 4 - 1
    K = (N61 * 4) // 2
    L = M
    U = R * 4
    X = TS * 2
    Y = TF * 2
    Z = TB * 3


class Shadow:
    W = N60 * 4
    N60 = 1


print(C.A, C.B, C.D, C.E, C.G, C.H, C.I, C.J, C.K, C.L, C.U)
print(C.X, C.Y, C.Z)
print(Shadow.W)
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


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre227Tests(unittest.TestCase):
    def test_class_constant_out_of_int64_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre227-') as directory:
            for label, text in OUT_OF_RANGE.items():
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        built, _ = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                        self.assertNotEqual(built.returncode, 0, label)
                        message = built.stdout + built.stderr
                        self.assertTrue(any(text in message for text in REFUSALS), message)
                        self.assertNotIn('integer overflow', message, label)
                        self.assertNotIn('Traceback', message, label)

    def test_class_constant_in_range_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre227-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('in_range_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'in_range_' + ('g' if general else 'd'),
                                          IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)


if __name__ == '__main__':
    unittest.main()
