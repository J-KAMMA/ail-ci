"""Differential fuzz round 24: math.fsum's non-finite bookkeeping.

Found with small programs compared against CPython on both builds:

1. The pure-Python `math.fsum` helper built for the Python syntax (ail_syntax.py) summed any list
   with a non-finite member with a plain running `+=` and returned it. CPython instead keeps
   CPython's own math_fsum_impl bookkeeping: an infinity is remembered separately, `+inf` with
   `-inf` raises ValueError("-inf + inf in fsum"), a finite sum whose intermediate overflows raises
   OverflowError("intermediate overflow in fsum"), and NaN passes through. So fsum([inf, -inf])
   printed nan where CPython raises, and fsum([1e308, 1e308]) printed nan instead of raising
   OverflowError. The helper now carries CPython's special_sum/inf_sum values and raises the two
   errors with CPython's messages.

The finite path (empty, zeros, subnormals, cancellation, rounding) was already right and stays in
these programs compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FSUM_SPECIAL = r'''import math


def show(xs: list[float]) -> None:
    try:
        print(xs, math.fsum(xs))
    except ValueError as e:
        print(xs, "ValueError", e)
    except OverflowError as e:
        print(xs, "OverflowError", e)


def main() -> None:
    inf = float("inf")
    nan = float("nan")
    show([])
    show([0.0])
    show([-0.0])
    show([1.0, 2.0])
    show([inf])
    show([-inf])
    show([inf, -inf])
    show([-inf, inf])
    show([inf, nan])
    show([nan, inf])
    show([inf, -inf, nan])
    show([-inf, inf, 1.0])
    show([1e308, 1e308, -inf])
    show([1.0, nan, -inf])
    show([1e308, 1e308])
    show([-1e308, -1e308])
    show([1e308, 1e308, -1e308])
    show([1e-300, -1e-300, 5e-324])
    show([0.1] * 10)
    show([1e16, 1.0, 1.0, -1e16])


main()
'''

FSUM_ROUTES = r'''import math


class Box:
    def __init__(self, xs: list[float]) -> None:
        self.xs = xs


def total(xs: list[float]) -> float:
    return math.fsum(xs)


def attr_total(b: Box) -> float:
    return math.fsum(b.xs)


def caught(xs: list[float]) -> None:
    try:
        print(math.fsum(xs))
    except ValueError as e:
        print("ValueError", e)
    except OverflowError as e:
        print("OverflowError", e)


def main() -> None:
    base = [0.1, 0.2, 0.3]
    alias = base
    print(total(base))
    print(math.fsum([base[0], base[1], base[2]]))
    print(math.fsum(alias), base)
    d: dict[str, list[float]] = {"xs": base}
    print(math.fsum(d["xs"]))
    b = Box(base)
    print(attr_total(b), b.xs)
    inf = float("inf")
    nan = float("nan")
    caught([base[0], inf, -inf])
    caught([base[0], inf, nan])
    nested = [math.fsum([0.1, 0.2]), -math.fsum([0.1, 0.2]), inf]
    caught(nested)
    caught([inf, -inf])
    b.xs = [inf, -inf]
    caught(b.xs)
    d["xs"] = [1e308, 1e308]
    caught(d["xs"])
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
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
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz24Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz24-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_fsum_non_finite_and_overflow(self):
        self.check('fsum_special', FSUM_SPECIAL)

    def test_fsum_values_through_arguments_lists_dicts_and_attributes(self):
        self.check('fsum_routes', FSUM_ROUTES)


if __name__ == '__main__':
    unittest.main()
