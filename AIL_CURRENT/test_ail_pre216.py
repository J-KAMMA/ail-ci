"""pre216: range.index() and range.count().

Both methods were absent: `range(2, 20, 3).index(8)` raised
`AttributeError: 'range' object has no attribute 'index'` (and the same for `count`) on both
builds, where CPython returns 2 and 1.  The general-path method dispatch now has a range
branch: an int or bool is located arithmetically (a range may be far too long to walk), an
integral float is treated like the equal int, any other value is located by walking the range
and comparing with == (CPython's generic sequence search), and a value that is not found
raises range's own `ValueError` text for an int or CPython's generic sequence text for
anything else.  The value reaches the method as a literal, an argument, a list item, an
attribute, a dict value and an alias; empty, negative-step, bool, float, __eq__ objects and
int64-boundary ranges are covered, and a call with more than one argument gets range's own
arity TypeError.  An index or count above int64 is this runtime's int limit, reported as a
named, catchable OverflowError rather than the uncatchable integer-overflow stop.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

RANGE_METHODS = r"""def show_index(r, v):
    try:
        print(r.index(v))
    except Exception as e:
        print(type(e).__name__, str(e))


def show_count(r, v):
    try:
        print(r.count(v))
    except Exception as e:
        print(type(e).__name__, str(e))


def lookup(q, v):
    return q.index(v)


def how_many(q, v):
    return q.count(v)


class Box:
    def __init__(self, r, v=None):
        self.r = r
        self.v = v


class Eq:
    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return other == self.n


class Boom:
    def __eq__(self, other):
        raise RuntimeError("boom")


def main():
    r = range(2, 20, 3)
    for v in (2, 5, 8, 11, 14, 17, 19, 20, -1, 0, True, False, 8.0, 8.5, 0.0, "8"):
        show_index(r, v)
        show_count(r, v)
    for rr, vals in (
        (range(0), (0, 1, -1, True, 0.0)),
        (range(5), (0, 4, 5, -1, True, 4.0, 4.5)),
        (range(10, 0, -2), (10, 8, 2, 0, 1, 10.0)),
        (range(0, 10, 3), (0, 3, 9, 10, True, 3.0)),
        (range(9223372036854775800, 9223372036854775807),
         (9223372036854775800, 9223372036854775806, 9223372036854775807)),
        (range(9223372036854775806, 9223372036854775790, -3),
         (9223372036854775806, 9223372036854775800, 9223372036854775790)),
        (range(-9223372036854775807 - 1, -9223372036854775800),
         (-9223372036854775807 - 1, -9223372036854775801)),
    ):
        for v in vals:
            show_index(rr, v)
            show_count(rr, v)
    a = r
    xs = [r]
    d = {"r": r}
    b = Box(r)
    print(a.index(8), a.count(8))
    print(xs[0].index(8), xs[0].count(8))
    print(d["r"].index(8), d["r"].count(8))
    print(b.r.index(8), b.r.count(8))
    print(lookup(r, 8), how_many(r, 8))
    e = Eq(8)
    print(r.index(e), r.count(e))
    show_index(r, Eq(9))
    show_count(r, Eq(9))
    print(range(10, 0, -2).index(Eq(8)), range(10, 0, -2).count(Eq(8)))
    eqs = [Eq(8)]
    dq = {"v": Eq(8)}
    bq = Box(r, Eq(8))
    print(r.index(eqs[0]), r.count(eqs[0]))
    print(r.index(dq["v"]), r.count(dq["v"]))
    print(bq.r.index(bq.v), bq.r.count(bq.v))
    show_index(r, Boom())
    show_count(r, Boom())
    try:
        print(lookup(r, 9))
    except Exception as e:
        print(type(e).__name__, str(e))
    print(how_many(r, 9))
    show_index(r, 2)
    for call in (
        lambda: r.index(2, 1),
        lambda: r.count(2, 1),
        lambda: r.index(2, 1, 4),
        lambda: r.count(2, 1, 4),
    ):
        try:
            print(call())
        except Exception as e:
            print(type(e).__name__, str(e))


main()
"""


INDEX_OVERFLOW = r"""def main():
    lo = -9223372036854775807 - 1
    hi = 9223372036854775807
    r = range(lo, hi, 1)
    print(r.count(hi - 1))
    try:
        print(r.index(hi - 1))
    except Exception as e:
        print(type(e).__name__, str(e))


main()
"""


def build_and_run(directory, source, general):
    src = directory / ("p_g.py" if general else "p_d.py")
    src.write_text(source, encoding="utf-8")
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    env.pop("AIL_UNIFIED_FORCE", None)
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    exe = directory / ("exe_g" if general else "exe_d")
    built = subprocess.run([sys.executable, "-B", CLI, "compile", src.name,
                            "--syntax", "python", "-o", exe.name],
                           cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    if built.returncode != 0:
        return None, None, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
    return ran.stdout.replace(b"\r\n", b"\n"), ran.returncode, None


class Pre216Tests(unittest.TestCase):
    def test_range_methods_match_cpython_on_both_builds(self):
        with tempfile.TemporaryDirectory(prefix="ail-pre216-") as directory:
            directory = Path(directory)
            ref = directory / "ref.py"
            ref.write_text(RANGE_METHODS, encoding="utf-8")
            py = subprocess.run([sys.executable, "-B", str(ref)], capture_output=True, timeout=60)
            self.assertEqual(py.returncode, 0, py.stderr)
            expected = py.stdout.replace(b"\r\n", b"\n")
            for general in (False, True):
                out, code, err = build_and_run(directory, RANGE_METHODS, general)
                self.assertIsNone(err, err)
                self.assertEqual(out, expected, "general" if general else "default")
                self.assertEqual(code, py.returncode)

    def test_index_beyond_int64_is_named_not_hard_exit(self):
        with tempfile.TemporaryDirectory(prefix="ail-pre216-") as directory:
            directory = Path(directory)
            expected = (b"1\n"
                        b"OverflowError range.index() index exceeds int64\n")
            for general in (False, True):
                out, code, err = build_and_run(directory, INDEX_OVERFLOW, general)
                self.assertIsNone(err, err)
                self.assertEqual(code, 0, "general" if general else "default")
                self.assertEqual(out, expected, "general" if general else "default")


if __name__ == "__main__":
    unittest.main()
