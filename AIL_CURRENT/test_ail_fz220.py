"""fz220: `round()` of a constant float expression outside int64 is refused by name.

The daily fuzzer (seed 2076011178) built `round((1e10 * 1e10))` and printed the result.  CPython's
int is unbounded and prints 100000000000000000000; AIL's int is int64, so the run stopped with the
ordinary `integer overflow in round()` after a prefix of the output.  The runtime stop is the
declared 64-bit difference, but this value is known at compile time: pre54 already refused a
*constant float literal* at the boundary, and the fuzzer's arithmetic expression slipped through.
The refusal now folds constant float expressions (`+ - * / // % **`, unary signs), so the program is
a named compile-time refusal in the int64 modes, while exact ints (`--exact-int`) still match
CPython.

Runtime values (an argument, a list item, an attribute, a dict value) cannot be folded, so they keep
the declared overflow contract: exit 1, `integer overflow` on stderr, stdout a prefix of CPython's.
In-range constant expressions and NaN/Infinity keep CPython's answers and exceptions.
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
    ('general', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '0'}),
    ('general_ir', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '1'}),
)
EXACT_MODES = tuple((name, dict(extra, AIL_EXACT_INT='1')) for name, extra in MODES)

MINIMAL = '''\
print(round(1e10 * 1e10))
'''

WIDE_CONSTANTS = (
    ('negative', 'print(round(-(1e10 * 1e10)))\n'),
    ('division', 'print(round(1e10 / 1e-10))\n'),
    ('power_boundary', 'print(round((2.0 ** 62) * 2.0))\n'),
    ('int_and_float', 'print(round(2 * 1e20))\n'),
    ('floor_division', 'print(round((1e10 // 1e-10) // 1.0))\n'),
    ('modulo', 'print(round(1e20 % 3e20))\n'),
)

IN_RANGE = '''\
print(round(1e5 * 1e10))
print(round((1e10 * 1e10) / 1e10))
print(round((2.0 ** 62) - 2.0 ** 62))
print(round(-2.5 * 1e15))
print(round(1e-320 * 1e-10))
print(round(2.5), round(-2.5), round(0.5))
'''

NON_FINITE = '''\
for v in (1e308 * 10, -(1e308 * 10)):
    try:
        print(round(v))
    except Exception as e:
        print(type(e).__name__, str(e))
'''

ZERO_DIVISION = '''\
try:
    print(round(1.0 / 0.0))
except Exception as e:
    print(type(e).__name__, str(e))
'''

ROUTES = '''\
class Holder:
    def __init__(self, v: float) -> None:
        self.v = v


def take(v: float) -> int:
    return round(v)


def main() -> int:
    xs: list[float] = [1e20]
    d: dict[str, float] = {"v": 1e20}
    h: Holder = Holder(1e20)
    print("before")
    print(take(1e20))
    print(round(xs[0]))
    print(round(h.v))
    print(round(d["v"]))
    return 0


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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


class Fz220Tests(unittest.TestCase):
    def refused(self, name, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-fz220-') as directory:
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNone(got, (name, mode, err[-3000:]))
                    self.assertNotEqual(build_rc, 0, (name, mode))
                    self.assertIn('not in the subset', err, (name, mode))
                    self.assertIn('round()', err, (name, mode))
                    self.assertNotIn('Traceback', err, (name, mode))

    def same(self, name, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-fz220-') as directory:
            want, want_rc, cpy_err = _cpython(directory, name, text)
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def wide(self, name, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-fz220-') as directory:
            want, want_rc, cpy_err = _cpython(directory, name, text)
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    out = got.stdout.replace(b'\r\n', b'\n')
                    err_text = got.stderr.decode('utf-8', 'replace')
                    if (out, got.returncode) == (want, want_rc):
                        continue
                    self.assertEqual(got.returncode, 1, (name, mode, err_text[-1500:]))
                    self.assertIn('integer overflow', err_text, (name, mode))
                    self.assertNotIn('does not fit in this language', err_text, (name, mode))
                    self.assertTrue(want.startswith(out), (name, mode, out[-500:], want[-500:]))

    def test_minimized_fuzzer_seed_is_refused_in_int64(self):
        self.refused('minimal', MINIMAL)

    def test_other_wide_constant_expressions_are_refused_in_int64(self):
        for name, text in WIDE_CONSTANTS:
            self.refused(name, text)

    def test_in_range_constant_expressions_match_cpython(self):
        self.same('in_range', IN_RANGE)

    def test_nan_and_infinity_and_zero_division_keep_cpython_exceptions(self):
        self.same('non_finite', NON_FINITE)
        self.same('zero_division', ZERO_DIVISION)

    def test_wide_runtime_values_stay_in_the_declared_overflow(self):
        self.wide('routes', ROUTES)

    def test_wide_constant_expressions_match_cpython_with_exact_ints(self):
        self.same('minimal_exact', MINIMAL, EXACT_MODES)
        for name, text in WIDE_CONSTANTS:
            self.same(name + '_exact', text, EXACT_MODES)

    def test_wide_runtime_values_match_cpython_with_exact_ints(self):
        self.same('routes_exact', ROUTES, EXACT_MODES)


if __name__ == '__main__':
    unittest.main()
