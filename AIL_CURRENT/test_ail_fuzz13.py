"""Differential fuzz round 13: builtins and conversions, compared with CPython on both builds.

1. Float remainder (`%` and divmod) of an exact multiple took +0.0 where CPython takes the
   divisor's sign: `5.0 % -5.0` and `divmod(5.0, -5.0)[1]` are -0.0, `-5.0 % 5.0` is 0.0. The
   boxed runtime and the unboxed float lowering both now use copysign(0.0, divisor) for a zero
   remainder, so divmod, `%` and `//` agree with CPython for every sign combination.

2. `sum(xs, start)` with a str start concatenated it (`sum(["a", "b"], "")` printed "ab");
   CPython raises TypeError with the "use ''.join(seq)" advice. The call now raises that
   TypeError (catchable) on both builds. A tuple start made the typed pass type the result as
   the start's fixed-shape tuple, so `print(sum([(1,), (2,)], ()))` printed "()" (and a (9,)
   start printed only "(9,)"). The result type is left open now, and the ordinary tuple value
   is printed by the generic runtime: "(1, 2)".

3. Two-argument min()/max() of an int and a float on the default build compared after C's
   usual conversion to double, so 9007199254740993 and 9007199254740992.0 compared equal and
   min()/max() returned the wrong operand (and a float where CPython returns the int). That
   shape is left to the general path, which compares the two boxed values exactly and keeps
   the selected operand's type.

Still open (not silent: they are build errors or uncatchable runtime errors, listed in the
report): round() of inf/nan on the default build; round() of values outside int64 on both
builds; isinstance(x, ()) hits an empty tuple-class build error; chr/ord of non-BMP values;
int() with keyword start/base spellings and except TypeError in one probe are outside the
subset.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DIVMOD_SIGNED_ZERO = '''class Box:
    def __init__(self, v: float) -> None:
        self.v = v


def run(a: float, b: float) -> None:
    q, r = divmod(a, b)
    print(a, b, q, r, a % b, a // b)


def main() -> None:
    vals: list[float] = [5.0, -5.0, 0.0, -0.0, 1.5, -1.5, 10.0, -10.0]
    for i in range(len(vals)):
        for j in range(len(vals)):
            if vals[i] != 0.0 and vals[j] != 0.0:
                run(vals[i], vals[j])
    d: dict[str, float] = {"a": 5.0, "b": -5.0}
    run(d["a"], d["b"])
    run(d["b"], d["a"])
    run(Box(d["a"]).v, Box(d["b"]).v)
    print("done")


main()
'''

SUM_START = '''class Box:
    def __init__(self, v: object) -> None:
        self.v = v


def sumit(xs: list[tuple[int, ...]], st: tuple[int, ...]) -> None:
    print(sum(xs, st))


def sumstr(xs: list[str], st: str) -> None:
    try:
        print(sum(xs, st))
    except TypeError:
        print("TE")


def main() -> None:
    xs: list[tuple[int, ...]] = [(1,), (2,), (3,)]
    starts: list[tuple[int, ...]] = [(), (9,), (9, 8)]
    for i in range(len(starts)):
        sumit(xs, starts[i])
        print(sum(xs, starts[i]))
    sd: dict[str, tuple[int, ...]] = {"e": (), "n": (7,)}
    sumit(xs, sd["e"])
    print(sum(xs, Box(sd["n"]).v))
    print(sum([(4,), (5,)], (0,)), sum([], ()), sum([], (1, 2)))
    lists: list[list[int]] = [[1], [2]]
    print(sum(lists, []), sum(lists, [9]), sum([[1], [2]], [0]))
    ss: list[str] = ["a", "b"]
    sts: list[str] = ["", "-"]
    for i in range(len(sts)):
        sumstr(ss, sts[i])
    sd2: dict[str, str] = {"s": ""}
    sumstr(ss, sd2["s"])
    sumstr(ss, Box(sd2["s"]).v)
    print("done")


main()
'''

SUM_STR_UNCATCHED = '''def main() -> None:
    print(sum(["a", "b"], ""))
    print("unreachable")


main()
'''

MINMAX_MIXED = '''class Box:
    def __init__(self, v: object) -> None:
        self.v = v


def mm(a: int, b: float) -> None:
    print(min(a, b), max(a, b), min(b, a), max(b, a))


def main() -> None:
    big: int = 9007199254740993
    fl: float = 9007199254740992.0
    mm(big, fl)
    mm(-big, -fl)
    print(min(big, fl), max(big, fl), min(fl, big), max(fl, big))
    print(min(Box(big).v, Box(fl).v), max(Box(big).v, Box(fl).v))
    md: dict[str, object] = {"i": big, "f": fl}
    print(min(md["i"], md["f"]), max(md["i"], md["f"]))
    xs: list[float] = [-0.0, 0.0]
    print(min(xs[0], xs[1]), max(xs[0], xs[1]))
    print(min(1, 2.0), max(1, 2.0), min(2.0, 1), max(2.0, 1))
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


class Fuzz13Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz13-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_float_divmod_and_modulo_signed_zero(self):
        self.check('divmod_signed_zero', DIVMOD_SIGNED_ZERO)

    def test_sum_start_tuple_list_and_str(self):
        self.check('sum_start', SUM_START)

    def test_sum_str_start_is_type_error(self):
        self.check('sum_str_uncatched', SUM_STR_UNCATCHED, rc=1)

    def test_minmax_of_mixed_int_and_float(self):
        self.check('minmax_mixed', MINMAX_MIXED)


if __name__ == '__main__':
    unittest.main()
