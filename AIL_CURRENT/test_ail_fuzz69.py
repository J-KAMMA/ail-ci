"""fuzz69: round(x, n) with a negative n rounds to the nearest power of ten, as CPython does.

Found with small programs in the floating-point area compared against CPython on both builds:

`round(1e300, -300)` printed 1.0000000000000002e+300 where CPython prints 1e+300. The negative
branch scaled by a computed 10**k (`v / 10**k`, then `nearbyint`, then `* 10**k`, or the
`pow(10, n)` product form); 10**300 is not a double and neither operation is exact, so the
answer moved by an ulp. CPython rounds the exact decimal value to the nearest multiple of the
power of ten, ties to even (15.0 -> 20.0, 25.0 -> 20.0), and raises OverflowError with
"rounded value too large to represent" when the rounded decimal is beyond DBL_MAX
(round(1.7976931348623157e308, -308)). A negative n below -308 is CPython's NDIGITS_MIN and
gives signed zero. The runtime now prints the double's exact decimal expansion and rounds it as
decimal text, like CPython's _Py_dg_dtoa path. A positive n above 323 now returns x unchanged,
CPython's NDIGITS_MAX (round(5e-324, 324) was 0.0).

The programs below keep the shape compared with CPython on both builds: values reach round()
as literals, through an argument, a list item, an attribute and a dict value, with negative,
zero, huge, subnormal and non-finite inputs.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ROUND_NEG_VALS = [0.0, -0.0, 0.5, -0.5, 1.0, -1.0, 1.5, 2.5, 3.5, 5.0, 15.0, 25.0, 35.0, -15.0, -25.0, 1234.5, 1235.5, -1234.5, -1235.5, 1e300, -1e300, 1.2345678901234567e300, 9.99e307, 1.7976931348623157e308, 5e-324, 1e-300, float("inf"), float("-inf"), float("nan")]
ROUND_NEG_NS = [-1, -2, -3, -10, -22, -23, -291, -292, -293, -294, -295, -300, -307, -308, -309, -323, -324, 0, 1, 2, 323, 324]


def _lit(v):
    if v != v:
        return 'float("nan")'
    if v == float("inf"):
        return 'float("inf")'
    if v == float("-inf"):
        return 'float("-inf")'
    return repr(v)


def _round_source(values, ns):
    lines = ["vals = [%s]" % ", ".join(_lit(v) for v in values), "for v in vals:"]
    for n in ns:
        lines += ["    try:",
                  "        print(repr(v), %d, repr(round(v, %d)))" % (n, n),
                  "    except OverflowError as e:",
                  "        print(repr(v), %d, type(e).__name__)" % n]
    return "\n".join(lines) + "\n"


# Every ndigits below is a literal, so both the typed path and the general path see the
# constant calls as well as the loop over the float values.
ROUND_NEG = _round_source(ROUND_NEG_VALS, ROUND_NEG_NS)

# No negative literals here: n > 323 is CPython's NDIGITS_MAX and returns x
# (round(5e-324, 324) is 5e-324, not 0.0).
ROUND_POS = _round_source([0.0, 0.5, -0.5, 1.5, 2.5, 5e-324, 1e-300, 9.99e307, float("inf"), float("-inf"), float("nan")],
                          [0, 1, 2, 308, 323, 324, 400])


ROUND_NEG_SOURCES = r'''def through(v):
    return round(v, -1)


def through2(v):
    return round(v, -2)


class C:
    def __init__(self, v):
        self.v = v


o = C(1234.5)
xs = [15.0, 25.0, -15.0, 0.0]
d = {"v": 15.0}
print(through(1234.5), through(xs[0]), through(o.v))
print(round(xs[1], -1), round(d["v"], -1), round(xs[3], -1))
print(through2(xs[2]), through2(o.v), round(d["v"], -2))
print(round(float("nan"), -1), round(float("inf"), -1), round(float("-inf"), -1))
print(round(1e300, -300), round(-1e300, -300), round(1.2345678901234567e300, -300))
'''


ROUND_TYPES = r'''class C:
    def __init__(self, v):
        self.v = v


def tryit(v, n):
    try:
        return repr(round(v, n))
    except TypeError:
        return "TypeError"


o = C(1.0)
xs = [1.0, 1]
d = {"n": 2.0, "none": None, "s": "2"}
print(tryit(1.0, 2.0), tryit(1, 2.0), tryit(1.0, d["s"]))
print(tryit(xs[0], d["n"]), tryit(xs[1], d["n"]), tryit(o.v, d["n"]))
print(tryit(1.0, None), tryit(1, None), tryit(o.v, d["none"]))
print(tryit(1.0, 2), tryit(1, -1), tryit(-2.5, -1))
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


class Fuzz69Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz69-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_round_negative_ndigits(self):
        self.check('round_neg', ROUND_NEG)

    def test_round_negative_from_sources(self):
        self.check('round_neg_sources', ROUND_NEG_SOURCES)

    def test_round_positive_ndigits_above_max(self):
        self.check('round_pos', ROUND_POS)

    def test_round_ndigits_type(self):
        self.check('round_types', ROUND_TYPES)


if __name__ == '__main__':
    unittest.main()
