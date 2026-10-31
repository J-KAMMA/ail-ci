"""pre429: the int64 path's wide one-argument round() is catchable, like the typed path.

The fz2 review recorded, as pre-existing then, that the general path's `round()` of a finite
float outside int64 stopped through `ail_hit_limit` (AIL_LIMIT), which no `try` could see,
while the typed path's `integer overflow` stop is catchable as OverflowError once the program
has an active handler.  On today's tree the exact-int (BIGINT) arm returns CPython's full
integer, so the accepted change is kept on the other side of the big-int gate: with
`AIL_BIGINT=off`, `ail_bi_round` raises the same `OverflowError("integer overflow")` through
the ordinary exception path.

Both int64 builds therefore catch the wide value in `except OverflowError`, `except Exception`
and a bare `except`, run an `except` clause's `finally`, and report the same uncaught class
when a handler was active but did not match.  In-range floats, int/bool, NaN and infinity keep
CPython's answers.  With exact ints the wide value matches CPython exactly; the int64 finite
big integer is the declared 64-bit difference (DIFFERENCES C74/A1), so an uncaught wide round
there is checked as exit 1 + "integer overflow" + a stdout prefix rather than against CPython's
exact value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODES = (
    ('int64_default', {'AIL_BIGINT': 'off'}),
    ('int64_default_ir', {'AIL_BIGINT': 'off', 'AIL_IR': '1'}),
    ('int64_general', {'AIL_BIGINT': 'off', 'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '0'}),
    ('int64_general_ir', {'AIL_BIGINT': 'off', 'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '1'}),
)

EXACT_MODES = (
    ('default', {}),
    ('default_ir', {'AIL_IR': '1'}),
    ('general', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '0'}),
    ('general_ir', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '1'}),
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


class Pre429Tests(unittest.TestCase):
    def caught(self, name, text, expected):
        want = expected.encode()
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, 0, (name, mode, got.stderr[-1500:]))
                    self.assertEqual(got.stderr, b'', (name, mode))

    def stopped(self, name, text, expected, prefix=True):
        want = expected.encode()
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            cpy, cpy_rc, cpy_err = _cpython(directory, name, text)
            self.assertEqual(cpy_rc, 0, cpy_err)
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    out = got.stdout.replace(b'\r\n', b'\n')
                    self.assertEqual(out, want, (name, mode))
                    if prefix:
                        self.assertTrue(cpy.startswith(out), (name, mode))
                    self.assertEqual(got.returncode, 1, (name, mode, got.stderr[-1500:]))
                    self.assertIn(b'integer overflow', got.stderr, (name, mode))
                    self.assertNotIn(b'AIL limit', got.stderr, (name, mode))

    def same(self, name, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-pre429-') as directory:
            want, want_rc, cpy_err = _cpython(directory, name, text)
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def test_overflow_error_is_catchable_on_both_builds(self):
        self.caught('catch', CATCH, "caught OverflowError 'integer overflow'\nafter\n")

    def test_except_exception_and_bare_except_catch_it(self):
        self.caught('exception', EXCEPTION, 'exception caught\nafter\n')
        self.caught('bare', BARE, 'bare caught\nafter\n')

    def test_handler_finally_runs_and_wide_value_through_routes_is_caught(self):
        self.caught('catch_finally', CATCH_FINALLY, 'caught\nfinally ran\nafter\n')
        self.caught('routes', ROUTES, '-1\n' + 'caught\n' * 5)

    def test_negative_and_computed_wide_values_are_caught(self):
        self.caught('negative', NEGATIVE, "neg caught 'integer overflow'\nafter\n")
        self.caught('dynamic', DYNAMIC, 'dynamic caught\nafter\n')

    def test_unmatched_and_uncaught_stop_is_the_declared_int64_one(self):
        self.stopped('value_only', VALUE_ONLY, '')
        # A handler that only has `finally` runs it and then lets the OverflowError go: CPython
        # printed its (unrepresentable) big integer first, so this stdout is not a prefix.
        self.stopped('finally_only', FINALLY_ONLY, 'finally ran\n', prefix=False)
        self.stopped('uncaught', UNCAUGHT, 'before\n')

    def test_in_range_and_non_finite_values_match_cpython(self):
        self.same('in_range', IN_RANGE)
        self.same('non_finite', NON_FINITE)

    def test_constant_wide_round_stops_on_int64_and_matches_with_exact_ints(self):
        self.stopped('constant', CONSTANT, '')
        self.same('constant_exact', CONSTANT, EXACT_MODES)

    def test_exact_ints_keep_cpython_value_and_never_overflow(self):
        self.same('catch_exact', CATCH, EXACT_MODES)


if __name__ == '__main__':
    unittest.main()
