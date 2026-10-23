"""Differential fuzz round 41: numeric builtins on the general (boxed) path.

Found by small programs compared with CPython 3.12 on both builds:

1. `abs()` on the general path returned a bool unchanged for `abs(True)`/`abs(False)`
   (CPython returns the ints 1 and 0), and returned any non-number unchanged instead of
   raising `TypeError` (`abs("x")`, `abs([1])`). The boxed lowering now always calls the
   runtime's `ail_bi_abs`, which boxes int/bool, uses `fabs` for floats and raises the
   CPython message for other types. Negative zero already matched and stays covered.

2. `divmod()` of floats on the general path used a naive `floor(a / b)` and a separate
   `fmod`, so `divmod(1.0, 0.1)` was `(10.0, 0.0999...)` where CPython gives
   `(9.0, 0.0999...)`, and `divmod(-0.0, 3.0)` had `-0.0` for the remainder. Its zero
   divisor and wrong-type messages also said `//` instead of `divmod()`. The boxed
   lowering now calls `ail_bi_divmod`, whose float branch is CPython's own fmod/floor
   algorithm (and keeps the `float divmod()` / `divmod(): 'str' and 'int'` text).
   The typed tuple helper `_ail_divmod_f` now uses the same algorithm, so directly
   typed float `divmod` calls also match (`divmod(inf, 2.0)` is `(nan, nan)`).

3. `divmod()` on instances regressed when the boxed lowering started rejecting every
   non-numeric tag: a Fraction or IntEnum supports `divmod` through its
   `__floordiv__`/`__mod__` methods, which the runtime's operator path dispatches.
   Instance operands now fall through to that path; only non-instance wrong types keep
   the `divmod(): 'str' and 'int'` message.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ABS_CASE = r'''class Box:
    def __init__(self, v: bool):
        self.v = v


def pick(b: bool) -> int:
    return abs(b)


def main() -> None:
    print(abs(-0.0), abs(0.0), abs(-0), abs(0), abs(-5), abs(5), abs(-2.5), abs(2.5))
    print(abs(-0.0) == 0.0, repr(abs(-0.0)), repr(abs(0.0)))
    z = -0.0
    print(repr(abs(z)), repr(abs(z * 1.0)))
    print(abs(True), abs(False), repr(abs(True)), repr(abs(False)))
    print(abs(True) + 1, abs(False) + 1)
    xs = [True, False, -4, -5.5]
    print([abs(v) for v in xs])
    print(abs(xs[0]), abs(xs[2]), abs(xs[3]))
    d = {"a": True, "b": -3, "c": -0.0}
    print(abs(d["a"]), abs(d["b"]), repr(abs(d["c"])))
    obj = Box(True)
    print(abs(obj.v))
    print(pick(False), pick(-7))
    print(list(map(abs, [True, -1, -2.0])))
    print(sorted([True, False, -2, 3], key=abs))
    print(min([True, False, -2, 3], key=abs), max([True, False, -2, 3], key=abs))
    f = abs
    print(f(True), f(False), f(-3), f(-2.5))
    g = {"abs": abs}
    print(g["abs"](False), g["abs"](-4))
    for bad in ("x", [1]):
        try:
            abs(bad)
        except TypeError as e:
            print("TypeError", e)
    print("end")


main()
'''

DIVMOD_CASE = r'''def pair(a: float, b: float):
    return divmod(a, b)


def main() -> None:
    print(divmod(7.5, 2))
    print(divmod(-7.5, 2))
    print(divmod(7.5, -2))
    print(divmod(-7.5, -2))
    print(divmod(0.0, 3.0))
    print(divmod(-0.0, 3.0))
    print(divmod(-0.0, -3.0))
    print(divmod(1e308, 3.0))
    print(divmod(1e300, 1e-300))
    print(divmod(1.0, 0.1))
    print(divmod(-1.0, 0.1))
    print(divmod(7, 2.0))
    print(divmod(7.0, 2))
    vals = [(1e16, 3.0), (-1e16, 3.0), (5.5, 2.5)]
    for a, b in vals:
        print(pair(a, b))
    d = {"a": 1.0, "b": 0.1}
    print(divmod(d["a"], d["b"]))
    xs = [1.0, 0.1]
    print(divmod(xs[0], xs[1]))
    for a, b in ((3.0, -0.0), (1.0, 0.0), (0.0, 0.0)):
        try:
            print(divmod(a, b))
        except ZeroDivisionError as e:
            print("ZeroDivisionError", e)
    try:
        divmod("a", 2)
    except TypeError as e:
        print("TypeError", e)
    print(divmod(float("inf"), 2.0))
    print(divmod(2.0, float("inf")))
    print(divmod(float("nan"), 2.0))
    print("end")


main()
'''


DIRECT_DIVMOD_CASE = r'''def main() -> None:
    print(divmod(1.0, 0.1))
    print(divmod(-1.0, 0.1))
    print(divmod(1.0, -0.1))
    print(divmod(-1.0, -0.1))
    print(divmod(float("inf"), 2.0))
    print(divmod(float("-inf"), 2.0))
    print(divmod(2.0, float("inf")))
    print(divmod(-2.0, float("inf")))
    print(divmod(2.0, float("-inf")))
    print(divmod(float("nan"), 2.0))
    print(divmod(-0.0, 3.0))
    print(divmod(0.0, -3.0))
    print(divmod(1e16, 3.0))
    print(divmod(-1e16, 3.0))
    print(divmod(1e300, 1e-300))
    vals = [(5.5, 2.5), (7, 2.0), (7.0, 2)]
    for a, b in vals:
        print(divmod(a, b))
    for a, b in ((3.0, -0.0), (1.0, 0.0), (0.0, 0.0)):
        try:
            print(divmod(a, b))
        except ZeroDivisionError as e:
            print("ZeroDivisionError", e)
    print("end")


main()
'''

INSTANCE_DIVMOD_CASE = r'''from fractions import Fraction
from enum import IntEnum


class E(IntEnum):
    A = 7


class Box:
    def __init__(self, v: Fraction):
        self.v = v


def frac_pair(a: Fraction, b: int):
    return divmod(a, b)


def main() -> None:
    q, r = divmod(Fraction(7, 2), 2)
    print(q, r, repr(q), repr(r))
    print(divmod(2, Fraction(7, 2)))
    xs = [Fraction(7, 2), Fraction(-7, 2)]
    for x in xs:
        print(frac_pair(x, 2))
        print(divmod(x, 2))
    d = {"x": Fraction(7, 2)}
    print(divmod(d["x"], 2))
    box = Box(Fraction(7, 2))
    print(divmod(box.v, 2))
    print(divmod(E.A, 2))
    print(divmod(E.A, -2))
    print(divmod(-E.A, 2))
    print(repr(divmod(E.A, 2)))
    es = [E.A, -E.A]
    for x in es:
        print(divmod(x, 2))
    ed = {"x": E.A}
    print(divmod(ed["x"], 2))
    print("end")


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


class Fuzz41Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz41-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_abs_bool_and_non_number(self):
        self.check('abs_bool', ABS_CASE)

    def test_divmod_floats(self):
        self.check('divmod_floats', DIVMOD_CASE)

    def test_divmod_direct_floats(self):
        self.check('divmod_direct', DIRECT_DIVMOD_CASE)

    def test_divmod_instances(self):
        self.check('divmod_instances', INSTANCE_DIVMOD_CASE)


if __name__ == '__main__':
    unittest.main()
