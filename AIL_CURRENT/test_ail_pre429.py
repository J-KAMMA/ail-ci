"""pre429: the wide one-argument round() on the int64 default, and the opt-in exact mode.

The fz2 review recorded that the general path's `round()` of a finite float outside int64
stopped through `ail_hit_limit` (AIL_LIMIT), which no `try` could see; `ail_bi_round` now
raises the ordinary `OverflowError("integer overflow")` on the int64 general runtime, so
`except OverflowError`, `except Exception`, a bare `except` and a handler's `finally` all see
it, and an uncaught wide value keeps the output written so far (exit 1).

Integers are int64 by default (ail-ci#198), so the typed path is now the default route: its
checked round stops the program loudly ("integer overflow in round()", exit 1) and no handler
runs, exactly like the other int64 arithmetic stops (test_ail_overflow_uncatchable).  The
forced general path keeps the catchable behaviour above.  In-range floats, int/bool, NaN and
infinity keep CPython's answers on every path.  A constant wide round is refused at build time
in the int64 mode.  With `--exact-int` / `AIL_EXACT_INT=1` the wide value matches CPython
exactly and never overflows; the int64 finite big integer is the declared 64-bit difference
(DIFFERENCES C74/A1).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INT64_MODES = (
    ('int64_default', {}),
    ('int64_default_ir', {'AIL_IR': '1'}),
    ('int64_general', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '0'}),
    ('int64_general_ir', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '1'}),
)

INT64_TYPED = tuple(mode for mode in INT64_MODES if 'AIL_UNIFIED_FORCE' not in mode[1])
INT64_GENERAL = tuple(mode for mode in INT64_MODES if 'AIL_UNIFIED_FORCE' in mode[1])

EXACT_MODES = (
    ('exact_default', {'AIL_EXACT_INT': '1'}),
    ('exact_default_ir', {'AIL_EXACT_INT': '1', 'AIL_IR': '1'}),
    ('exact_general', {'AIL_EXACT_INT': '1', 'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '0'}),
    ('exact_general_ir', {'AIL_EXACT_INT': '1', 'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '1'}),
)

CATCH = '''\
v: float = 1e20
try:
    print(round(v))
except OverflowError as e:
    print("caught", type(e).__name__, repr(str(e)))
print("after")
'''

CATCH_FINALLY = '''\
v: float = 1e20
try:
    print(round(v))
except OverflowError:
    print("caught")
finally:
    print("finally ran")
print("after")
'''

BARE = '''\
v: float = 1e20
try:
    print(round(v))
except:
    print("bare caught")
print("after")
'''

EXCEPTION = '''\
v: float = 1e20
try:
    print(round(v))
except Exception:
    print("exception caught")
print("after")
'''

FINALLY_ONLY = '''\
v: float = 1e20
try:
    print(round(v))
finally:
    print("finally ran")
print("after")
'''

VALUE_ONLY = '''\
v: float = 1e20
try:
    print(round(v))
except ValueError:
    print("value caught")
print("after")
'''

NEGATIVE = '''\
v: float = -1e20
try:
    print(round(v))
except OverflowError as e:
    print("neg caught", repr(str(e)))
print("after")
'''

ROUTES = '''\
def take(v: float) -> int:
    try:
        return round(v)
    except OverflowError:
        return -1


class Holder:
    def __init__(self, v: float) -> None:
        self.v = v


xs: list[float] = [1e20]
h: Holder = Holder(1e20)
d: dict[str, float] = {"v": 1e20}
w: float = xs[0]
ys: list[float] = [w]
print(take(1e20))
for value in (xs[0], h.v, d["v"], w, ys[0]):
    try:
        print(round(value))
    except OverflowError:
        print("caught")
'''

DYNAMIC = '''\
def grow(n: float) -> float:
    v: float = n
    two: float = 2.0
    for _ in range(70):
        v = v * two
    return v


v: float = grow(1.5)
try:
    print(round(v))
except OverflowError:
    print("dynamic caught")
print("after")
'''

UNCAUGHT = '''\
v: float = 1e20
print("before")
print(round(v))
'''

IN_RANGE = '''\
def show(v: float) -> int:
    try:
        return round(v)
    except OverflowError:
        return -1


for v in (2.5, 3.5, -2.5, -0.0, 0.0, 1e15, -1e15,
          9223372036854774784.0, -9223372036854774784.0):
    print(show(v))
print(round(7), round(-7), round(True), round(False))
'''

NON_FINITE = '''\
for v in (float("nan"), float("inf"), float("-inf")):
    try:
        print(round(v))
    except Exception as e:
        print(type(e).__name__, repr(str(e)))
print("after")
'''

CONSTANT = '''\
print(round(1e20))
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


class Pre429Tests(unittest.TestCase):
    def caught(self, name, text, expected, modes=INT64_GENERAL):
        want = expected.encode()
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, 0, (name, mode, got.stderr[-1500:]))
                    self.assertEqual(got.stderr, b'', (name, mode))

    def typed_stop(self, name, text, expected=b''):
        want = expected
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            for mode, extra in INT64_TYPED:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, 1, (name, mode, got.stderr[-1500:]))
                    self.assertIn(b'integer overflow', got.stderr, (name, mode))
                    self.assertNotIn(b'AIL limit', got.stderr, (name, mode))

    def general_stop(self, name, text, expected):
        want = expected
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            for mode, extra in INT64_GENERAL:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, 1, (name, mode, got.stderr[-1500:]))
                    self.assertIn(b'integer overflow', got.stderr, (name, mode))
                    self.assertNotIn(b'AIL limit', got.stderr, (name, mode))

    def refused(self, name, text, modes):
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNone(got, (name, mode))
                    self.assertNotEqual(build_rc, 0, (name, mode))
                    self.assertIn('not in the subset', err, (name, mode))
                    self.assertIn('round()', err, (name, mode))
                    self.assertNotIn('Traceback', err, (name, mode))

    def same(self, name, text, modes):
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            want, want_rc, cpy_err = _cpython(directory, name, text)
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def test_int64_typed_wide_round_is_a_loud_stop(self):
        for name, text in (('catch', CATCH), ('catch_finally', CATCH_FINALLY), ('bare', BARE),
                           ('exception', EXCEPTION), ('finally_only', FINALLY_ONLY),
                           ('value_only', VALUE_ONLY), ('negative', NEGATIVE), ('dynamic', DYNAMIC)):
            self.typed_stop(name, text)
        self.typed_stop('uncaught', UNCAUGHT, b'before\n')

    def test_int64_general_wide_round_is_catchable(self):
        self.caught('catch', CATCH, "caught OverflowError 'integer overflow'\nafter\n")
        self.caught('exception', EXCEPTION, 'exception caught\nafter\n')
        self.caught('bare', BARE, 'bare caught\nafter\n')
        self.caught('catch_finally', CATCH_FINALLY, 'caught\nfinally ran\nafter\n')
        self.caught('negative', NEGATIVE, "neg caught 'integer overflow'\nafter\n")
        self.caught('dynamic', DYNAMIC, 'dynamic caught\nafter\n')
        self.general_stop('finally_only', FINALLY_ONLY, b'finally ran\n')
        self.general_stop('value_only', VALUE_ONLY, b'')
        self.general_stop('uncaught', UNCAUGHT, b'before\n')

    def test_int64_routes_and_containers_keep_the_declared_stop(self):
        self.caught('routes', ROUTES, '-1\n' + 'caught\n' * 5, INT64_MODES)

    def test_in_range_and_non_finite_values_match_cpython(self):
        self.same('in_range', IN_RANGE, INT64_MODES + EXACT_MODES)
        self.same('non_finite', NON_FINITE, INT64_MODES + EXACT_MODES)

    def test_constant_wide_round_is_refused_in_int64(self):
        self.refused('constant', CONSTANT, INT64_MODES)

    def test_exact_ints_keep_cpython_value_and_never_overflow(self):
        self.same('catch_exact', CATCH, EXACT_MODES)
        self.same('routes_exact', ROUTES, EXACT_MODES)
        self.same('uncaught_exact', UNCAUGHT, EXACT_MODES)
        self.same('constant_exact', CONSTANT, EXACT_MODES)


if __name__ == '__main__':
    unittest.main()
