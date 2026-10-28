"""fz2: one-argument `round()` of a finite float outside int64 is the declared 64-bit stop.

The daily fuzzer (seed 2075200891) multiplied a float until it was about -2e20 and then used
`round(v)` in a comparison.  CPython's int is unbounded and returns the exact integer; AIL's int
is int64.  The typed runtime used to stop with its own trap text
`round() result does not fit in this language's int64`, which the fuzz runner could not class as
the declared int64 difference, so the seed was reported as a silent DIFF.  `ail_round0` now uses
the ordinary `integer overflow` stop (stderr "integer overflow", exit 1, stdout flushed up to the
call), exactly like `+`, `-`, `*` and the other int64 limits; the general path and the two-argument
`round(x, n)` already reported it that way.  A *constant* float at or outside the boundary is
builds and prints the exact integer under exact ints (it was refused by name at compile time
for the int64 era, pre54).

Each wide program must either match CPython exactly or stay inside the fuzz runner's `overflow`
contract: exit 1, "integer overflow" on stderr, and AIL's stdout a prefix of CPython's.  In-range
values, integral arguments, and NaN/Infinity keep CPython's own answers (and exceptions).
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

MINIMAL = '''\
print("before")
v: float = 1e20
print(round(v))
'''

COMPARISON = '''\
v: float = 1e20
for i in range(3):
    if i < round(v):
        print("yes")
print("done")
'''

NEGATIVE = '''\
v: float = -1e20
print("before", v)
print(round(v))
'''

ROUTES = (
    ('argument', '''\
def take(v: float) -> int:
    return round(v)


print("before")
print(take(1e20))
'''),
    ('list_item', '''\
xs: list[float] = [1e20]
print("before")
print(round(xs[0]))
'''),
    ('attribute', '''\
class Holder:
    def __init__(self, v: float) -> None:
        self.v = v


h: Holder = Holder(1e20)
print("before")
print(round(h.v))
'''),
    ('dict_value', '''\
d: dict[str, float] = {"v": 1e20}
print("before")
print(round(d["v"]))
'''),
    ('alias', '''\
v: float = 1e20
w: float = v
xs: list[float] = [v]
ys: list[float] = xs
print("before")
print(round(w))
print(round(ys[0]))
'''),
)

IN_RANGE = '''\
def show(v: float) -> None:
    print(round(v))


for v in (2.5, 3.5, -2.5, -0.0, 0.0, 1e15, -1e15,
          9223372036854774784.0, -9223372036854774784.0):
    show(v)
print(round(7), round(-7), round(True), round(False))
print(type(round(2.5)).__name__)
'''

NON_FINITE = '''\
for v in (float("nan"), float("inf"), float("-inf")):
    try:
        print(round(v))
    except Exception as e:
        print(type(e).__name__, repr(str(e)))
print("after")
'''

CONSTANT_WIDE = '''\
print(round(1e20))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, mode, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.returncode, (built.stdout + built.stderr)
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got, built.returncode, ''


class Fz2Tests(unittest.TestCase):
    def _want(self, directory, name, text):
        want, want_rc, err = _cpython(directory, name, text)
        self.assertEqual(want_rc, 0, err)
        return want, want_rc

    def same(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz2-') as directory:
            want, want_rc = self._want(directory, name, text)
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, mode, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def wide(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz2-') as directory:
            want, want_rc = self._want(directory, name, text)
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, mode, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    out = got.stdout.replace(b'\r\n', b'\n')
                    err_text = got.stderr.decode('utf-8', 'replace')
                    if (out, got.returncode) == (want, want_rc):
                        continue
                    self.assertEqual(got.returncode, 1, (name, mode, err_text[-1500:]))
                    self.assertIn('integer overflow', err_text, (name, mode))
                    self.assertNotIn('does not fit in this language', err_text, (name, mode))
                    self.assertTrue(want.startswith(out), (name, mode, out[-500:], want[-500:]))

    def test_minimized_reproducer_is_declared_overflow(self):
        self.wide('minimal', MINIMAL)

    def test_round_in_a_comparison_is_declared_overflow(self):
        self.wide('comparison', COMPARISON)

    def test_negative_wide_value_is_declared_overflow(self):
        self.wide('negative', NEGATIVE)

    def test_wide_value_through_argument_list_attribute_and_dict(self):
        for name, text in ROUTES:
            self.wide(name, text)

    def test_in_range_and_integral_arguments_match_cpython(self):
        self.same('in_range', IN_RANGE)

    def test_nan_and_infinity_keep_cpython_exceptions(self):
        self.same('non_finite', NON_FINITE)

    def test_constant_wide_round_matches_cpython(self):
        self.same('constant', CONSTANT_WIDE)


if __name__ == '__main__':
    unittest.main()
