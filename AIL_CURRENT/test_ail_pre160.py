"""round()'s ndigits conversion against CPython 3.12 (job pre160).

CPython checks the number's `__round__`/type before it converts ndigits.  An instance with
`__round__` receives the ndigits object untouched (so its `__index__` is not called), an int or
float converts ndigits with `__index__` only after that check, and None means "no ndigits".  The
general path used to read the ndigits value's raw int field: `__index__` was never called, a str or
list ndigits was silently accepted, an instance without `__round__` was named `instance`, and a
`__round__` method received a garbage integer instead of the object.  These programs compare with
CPython on both builds.  The negative-ndigits boundary is included: an ndigits at or below -309
rounds every finite float to a signed zero, and a rounded magnitude above DBL_MAX raises
OverflowError.  An out-of-int64 intermediate inside `__index__` (for example `10**30`) cannot be
evaluated at all (AIL integers are int64), so that program stops by name ("integer overflow") while
running `__index__`; CPython uses its arbitrary-precision result.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip() and 'raised near' not in x]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, text, mode):
    src = Path(directory) / (name + '_' + mode + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), None


ROUND = r'''class Idx:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        print("index called")
        return self.v

    def __repr__(self):
        return "Idx(%d)" % self.v


class NoRound:
    pass


class R:
    def __round__(self, n=None):
        print("round got", repr(n))
        return 99


class Bad:
    def __index__(self):
        return "x"


class Boom:
    def __index__(self):
        raise ValueError("boom")


class Box:
    def __init__(self, n):
        self.n = n


def show(label, x, n):
    try:
        print(label, round(x, n))
    except Exception as e:
        print(label, type(e).__name__, e)


def use(n):
    return round(2.5, n)


def main():
    for v in ("x", None, [1]):
        try:
            print(round(v, Idx(2)))
        except Exception as e:
            print(type(e).__name__, e)
    try:
        print(round(NoRound(), Idx(2)))
    except Exception as e:
        print(type(e).__name__, e)
    print(round(R(), Idx(2)))
    print(round(R(), None))
    show("f-none", 2.5, None)
    show("i-none", 7, None)
    show("f-str", 2.5, "2")
    show("i-str", 7, "2")
    show("f-float", 2.5, 1.0)
    show("i-float", 7, 1.0)
    show("f-list", 2.5, [1])
    show("i-list", 7, [1])
    show("f-true", 2.5, True)
    show("i-true", 7, True)
    show("f-false", 2.5, False)
    show("i-false", 7, False)
    show("f-idx", 2.5, Idx(1))
    show("i-idx", 7, Idx(-2))
    show("f-bad", 2.5, Bad())
    show("i-bad", 7, Bad())
    show("f-boom", 2.5, Boom())
    i = Idx(2)
    xs = [Idx(1)]
    b = Box(Idx(3))
    d = {"n": Idx(4)}
    print(use(i), use(xs[0]), use(b.n), use(d["n"]))
    print(round(2.5, i), round(-2.5, Idx(0)), round(2.5, Idx(-1)))
    print(round(7, Idx(-2)), round(7, Idx(2)))


main()
'''

SATURATE = r'''class A:
    def __index__(self):
        a = 10**30
        b = 10**30 + 5
        return a - b


class B:
    def __index__(self):
        a = 10**30
        b = 10**30 + 5
        return a + b - b - a


print(round(2.5, A()))
print(round(2.5, B()))
'''

NEGATIVE = r'''class Idx:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Box:
    def __init__(self, n):
        self.n = n


class MinIdx:
    def __index__(self):
        return -9223372036854775807 - 1


class Min1Idx:
    def __index__(self):
        return -9223372036854775807


def use(n):
    return round(2.5, n)


def show(label, v, n):
    try:
        print(label, repr(round(v, n)))
    except Exception as e:
        print(label, type(e).__name__, e)


i = Idx(-309)
xs = [Idx(-400)]
b = Box(Idx(-309))
d = {"n": Idx(-400)}
print(use(i), round(2.5, xs[0]), round(2.5, b.n), round(2.5, d["n"]))
for n in (-2, -308, -309, -310, -323, -324, -400, -1000):
    show("lit", 2.5, n)
    show("idx", 2.5, Idx(n))
    show("neg", -2.5, Idx(n))
    show("zero", -0.0, Idx(n))
show("min", 2.5, MinIdx())
show("min1", 2.5, Min1Idx())
for n in (-306, -307, -308):
    show("ovf", 1.7976931348623157e308, Idx(n))
    show("ovfl", -1.7976931348623157e308, n)
for n in (-18, -19, -20, -100, -400):
    show("int", 7, Idx(n))
    show("intl", -7, n)
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class RoundNDigits(unittest.TestCase):
    def test_round_ndigits_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre160-') as tmp:
            want = _cpython(tmp, 'round', ROUND)
            for mode in ('general', 'default'):
                got, error = _build_run(tmp, 'round', ROUND, mode)
                self.assertIsNone(error, mode + ': ' + str(error))
                self.assertEqual(got, want, mode)

    def test_negative_ndigits_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre160-') as tmp:
            want = _cpython(tmp, 'negative', NEGATIVE)
            for mode in ('general', 'default'):
                got, error = _build_run(tmp, 'negative', NEGATIVE, mode)
                self.assertIsNone(error, mode + ': ' + str(error))
                self.assertEqual(got, want, mode)

    def test_out_of_int64_index_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre160-') as tmp:
            for mode in ('general', 'default'):
                got, error = _build_run(tmp, 'saturate', SATURATE, mode)
                self.assertIsNone(error, mode + ': ' + str(error))
                stdout, code, stderr = got
                self.assertNotEqual(code, 0, mode + ': ' + stdout.decode('utf-8', 'replace'))
                self.assertIn('integer overflow', stderr, mode)
