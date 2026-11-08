"""fz240: float() of an exact integer constant expression past int64 matches CPython.

The daily fuzzer (seed 2076507535) printed `2.5e-3 > float((4611686018427387904 * 53))`
inside a `try`/`finally`.  At the fuzz run AIL stopped with `OverflowError` after the
`finally` line, so the comparison's `False` was missing.  On this tree the direct
`float(<exact int constant expression>)` is folded before the int64 check and converts the
exact value to the nearest double, so the seed matches CPython on both builds; this module
pins that route, its sign/power/bool/float neighbours, and the values that reach `float()`
through an argument, a list item, an attribute and a dict value inside int64.

The same constant expression bound to an `int` local, or a float constant whose nearest
double is infinite, is still refused by name at compile time (the declared int64 contract),
and a wide run-time multiplication keeps the loud int64 overflow.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODES = (
    ('default', {}),
    ('default_ir', {'AIL_IR': '1'}),
)

MINIMAL = '''\
print(((46 ** 0) // (90 - 1)))
print((2.5e-3 > float((4611686018427387904 * 53))))
'''

CONSTANTS = '''\
print(float(4611686018427387904 * 53))
print(float(-(4611686018427387904 * 53)))
print(float(9223372036854775807 + 1))
print(float(2 ** 63))
print(float((1 << 100) + 1))
print(float(-(1 << 100) + 1))
print(float((2 ** 62) * 53))
print(float(True))
print(float(False))
print(float(-0.0))
'''

ROUTES = '''\
def show(x: int) -> None:
    print(float(x))
    print(float(x * 1))


xs: list[int] = [4611686018427387904, 9223372036854775807]


class Holder:
    def __init__(self, v: int) -> None:
        self.v = v


h: Holder = Holder(4611686018427387904)
d: dict[str, int] = {"v": 9223372036854775807}
show(4611686018427387904)
show(xs[0])
show(h.v)
show(d["v"])
'''

REFUSED = (
    ('local_int', 'v: int = 4611686018427387904 * 53\nprint(float(v))\n'),
    ('local_int_in_function', '''\
def main() -> None:
    v: int = 4611686018427387904 * 53
    print(float(v))


main()
'''),
    ('float_constant_infinite', 'print(float(1 << 2000))\n'),
)

WIDE_RUNTIME = '''\
def wide(x: int) -> float:
    return float(x * 53)


print("before")
wide(4611686018427387904)
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR', 'AIL_EXACT_INT'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.returncode, (built.stdout + built.stderr)
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got, built.returncode, ''


class Fz240Tests(unittest.TestCase):
    def same(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz240-') as directory:
            want, want_rc = _cpython(directory, name, text)
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def refused(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz240-') as directory:
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNone(got, (name, mode, err[-3000:]))
                    self.assertNotEqual(build_rc, 0, (name, mode))
                    self.assertIn('int64', err, (name, mode))
                    self.assertTrue('out of range' in err or 'overflows int64' in err,
                                    (name, mode, err[-3000:]))
                    self.assertNotIn('Traceback', err, (name, mode))

    def test_minimized_fuzzer_seed_matches_cpython(self):
        self.same('minimal', MINIMAL)

    def test_other_constant_forms_match_cpython(self):
        self.same('constants', CONSTANTS)

    def test_values_through_routes_match_cpython(self):
        self.same('routes', ROUTES)

    def test_wide_int_local_and_infinite_float_constant_are_refused_by_name(self):
        for name, text in REFUSED:
            self.refused(name, text)

    def test_wide_runtime_multiplication_keeps_the_declared_int64_overflow(self):
        with tempfile.TemporaryDirectory(prefix='ail-fz240-') as directory:
            want, want_rc = _cpython(directory, 'wide_runtime', WIDE_RUNTIME)
            for mode, extra in MODES:
                with self.subTest(mode=mode):
                    got, build_rc, err = _build_and_run(directory, 'wide_runtime_' + mode,
                                                        WIDE_RUNTIME, extra)
                    self.assertIsNotNone(got, err[-3000:])
                    self.assertEqual(build_rc, 0, err[-3000:])
                    out = got.stdout.replace(b'\r\n', b'\n')
                    self.assertEqual(got.returncode, 1, (mode, got.stderr[-1500:]))
                    self.assertIn(b'integer overflow', got.stderr, mode)
                    self.assertTrue(want.startswith(out), (mode, out, want))


if __name__ == '__main__':
    unittest.main()
