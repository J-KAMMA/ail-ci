"""list.index / tuple.index bounds against CPython 3.12 (DIFFERENCES C169).

`xs.index(x, None)` and `xs.index(x, 0, None)` read the None as index 0: the bounds were taken from
the boxed value's `.i` field without looking at its tag.  CPython converts each bound with
_PyEval_SliceIndex: an int, a bool or an object with __index__ is an index; None, a float, a str and
anything else raise TypeError("slice indices must be integers or have an __index__ method").  The
general path now evaluates both bounds, converts __index__ and tests the tags at run time (the value
may reach the call through a variable, a list item, an attribute or a dict value).  A bad __index__
return is CPython's "__index__ returned non-int (type ...)".  list, tuple and deque are covered; str
bounds keep their own None default.

Each program is built with the general path forced and with the default build; stdout, the exit status
and the last stderr line must equal CPython's.
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


BOUNDS = r'''def attempt(label: str, xs, needle, lo, hi) -> None:
    try:
        print(label, xs.index(needle, lo, hi))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def two(label: str, xs, needle, lo) -> None:
    try:
        print(label, xs.index(needle, lo))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    xs = [10, 20, 30]
    t = (10, 20, 30)
    for name, seq in (("list", xs), ("tuple", t)):
        two(name + "-start-none", seq, 20, None)
        attempt(name + "-both-none", seq, 20, None, None)
        attempt(name + "-stop-none", seq, 20, 0, None)
        attempt(name + "-start-none-stop", seq, 20, None, 3)
        two(name + "-start-float", seq, 20, 1.0)
        attempt(name + "-stop-float", seq, 20, 0, 2.0)
        two(name + "-start-str", seq, 20, "1")
        attempt(name + "-stop-str", seq, 20, 0, "2")
        attempt(name + "-start-bool", seq, 20, True, True)
        attempt(name + "-negative", seq, 20, -2, 3)
        attempt(name + "-empty", [], 20, 0, 0) if name == "list" else attempt(name + "-empty", (), 20, 0, 0)


main()
'''

SOURCES = r'''class Box:
    def __init__(self, lo, hi) -> None:
        self.lo = lo
        self.hi = hi


def attempt(label: str, xs, needle, lo, hi) -> None:
    try:
        print(label, xs.index(needle, lo, hi))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def two(label: str, xs, needle, lo) -> None:
    try:
        print(label, xs.index(needle, lo))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    xs = [10, 20, 30, 20]
    box = Box(None, 3)
    d = {"lo": None, "hi": 3}
    bounds = [None, 0, 1, -1, 1.0, "1", True]
    for i in range(len(bounds)):
        b = bounds[i]
        two("item-%d" % i, xs, 20, b)
        attempt("item-both-%d" % i, xs, 20, b, 3)
    attempt("attr-lo", xs, 20, box.lo, box.hi)
    attempt("attr-hi", xs, 20, 0, box.hi)
    attempt("dict-lo", xs, 20, d["lo"], d["hi"])
    attempt("arg-none", xs, 20, None, None)
    attempt("arg-float", xs, 20, 1.0, 3)
    attempt("arg-str", xs, 20, 1, "3")
    attempt("arg-bool", xs, 20, True, True)
    attempt("arg-neg", xs, 20, -2, -1)
    attempt("arg-big", xs, 20, 0, 10 ** 9)
    attempt("arg-negbig", xs, 20, -10 ** 9, 10 ** 9)
    t = (10, 20, 30, 20)
    attempt("tuple-attr", t, 20, box.lo, box.hi)
    attempt("tuple-dict", t, 20, d["lo"], d["hi"])


main()
'''

ORDER = r'''def note(tag: str, value):
    print("eval", tag, value)
    return value


def main() -> None:
    xs = [note("x0", 10), note("x1", 20), note("x2", 30)]
    try:
        print(xs.index(note("needle", 20), note("lo", None), note("hi", 3)))
    except Exception as e:
        print(type(e).__name__, str(e))
    try:
        print(xs.index(note("needle2", 30), note("lo2", 1), note("hi2", None)))
    except Exception as e:
        print(type(e).__name__, str(e))
    t = (note("t0", 10), note("t1", 20))
    try:
        print(t.index(note("tneedle", 20), note("tlo", None)))
    except Exception as e:
        print(type(e).__name__, str(e))


main()
'''

INDEX_OBJECT = r'''from collections import deque


class Ix:
    def __init__(self, v) -> None:
        self.v = v

    def __index__(self) -> int:
        return self.v


class BadIx:
    def __index__(self):
        return "x"


class NoIx:
    pass


def attempt(label: str, xs, needle, lo, hi) -> None:
    try:
        print(label, xs.index(needle, lo, hi))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    xs = [10, 20, 30, 20]
    attempt("ix-lo", xs, 20, Ix(0), Ix(4))
    attempt("ix-neg", xs, 20, Ix(-1), Ix(4))
    attempt("ix-both", xs, 20, Ix(1), Ix(4))
    attempt("bad", xs, 20, BadIx(), 4)
    attempt("noix", xs, 20, NoIx(), 4)
    t = (10, 20, 30, 20)
    attempt("tuple-ix", t, 20, Ix(1), Ix(4))
    attempt("tuple-bad", t, 20, Ix(1), BadIx())
    q = deque([10, 20, 30])
    attempt("deque-none", q, 20, None, 3)
    attempt("deque-float", q, 20, 1.0, 3)
    attempt("deque-ok", q, 20, 1, 3)
    s = "abcabc"
    attempt("str-none", s, "b", None, None)
    attempt("str-float", s, "b", 1.0, 5)
    attempt("str-str", s, "b", 1, "5")


main()
'''

UNCAUGHT = r'''def main() -> None:
    print("before")
    print([10, 20, 30].index(20, None))


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IndexBounds(unittest.TestCase):
    def check(self, name, text, modes=('general', 'default')):
        with tempfile.TemporaryDirectory(prefix='ail-c169-') as directory:
            want = _cpython(directory, name, text)
            for mode in modes:
                got, error = _build_run(directory, name, text, mode)
                self.assertIsNone(error, '%s %s: %s' % (name, mode, error))
                self.assertEqual(got, want, '%s %s' % (name, mode))

    def test_none_float_str_bounds(self):
        self.check('bounds', BOUNDS)

    def test_values_from_items_attributes_dicts_arguments(self):
        self.check('sources', SOURCES)

    def test_both_bounds_evaluated_before_the_error(self):
        self.check('order', ORDER)

    def test_index_protocol_and_deque_str_regressions(self):
        self.check('index_object', INDEX_OBJECT)

    def test_uncaught_typeerror(self):
        self.check('uncaught', UNCAUGHT)


if __name__ == '__main__':
    unittest.main()
