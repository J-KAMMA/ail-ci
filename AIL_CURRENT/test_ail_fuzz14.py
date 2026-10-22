"""Fuzz round 14: list/sort area, with the silent differences found here fixed.

1. A slice READ converted each bound with `(value).i` on the general path.  CPython treats an
   explicit or run-time None as an omitted bound and raises TypeError for a float/str bound;
   reading `.i` made `a[None:None]` empty and read a float's payload bits as an index.  Every
   slice read now goes through `ail_op_getslice_obj`, which applies CPython's conversions
   (None -> omitted, int/bool -> index, anything else -> the slice-index TypeError).  The same
   conversion is used for a bounds value that arrives through an argument, a list item, a dict
   value, an attribute or a `slice(...)` object.
2. `list.index` / `tuple.index` start and stop, and the index argument of `list.insert` /
   `list.pop`, were also read as `.i`.  None is NOT accepted by list.index (unlike a slice), and
   insert/pop use CPython's integer-conversion message.  The bounds are now validated by
   `ail_op_index_bound` / `ail_op_int_index`; valid negative, huge and out-of-range values keep
   CPython's clamping and IndexError behaviour.

Each program is compared with CPython and built twice (default build, AIL_UNIFIED_FORCE=1 general
path).  The programs also keep the rest of the area (stable key sort, reverse, nested list
multiplication, slice assignment, del) compared, so a regression there fails this module too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=120)
    return r.returncode, r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz14-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out


SLICE_NONE = r'''class Box:
    lo: int
    hi: int
    def __init__(self):
        self.lo = None
        self.hi = None
def cut(a, lo, hi, st):
    return a[lo:hi:st]
def show(xs):
    for v in xs:
        print(v)
def main():
    a = [0, 1, 2, 3, 4]
    none = None
    show(a[None:None])
    show(a[None:3])
    show(a[2:None])
    show(a[None:None:2])
    show(a[None:None:-1])
    show(a[None:None:-2])
    show(cut(a, none, none, none))
    show(cut(a, none, 3, 2))
    show(cut(a, 2, none, -1))
    bounds = [None, 2, None]
    show(a[bounds[0]:bounds[1]:bounds[2]])
    d = {"lo": None, "hi": 4, "st": None}
    show(a[d["lo"]:d["hi"]:d["st"]])
    box = Box()
    show(a[box.lo:box.hi])
    show(a[slice(None, None, None)])
    show(a[slice(None, 3, 2)])
    show(a[slice(3, None, -1)])
main()
'''

SLICE_TYPES = r'''def cut(a, lo, hi, st):
    return a[lo:hi:st]
def main():
    a = [0, 1, 2, 3]
    vals = [1.0, "1", None]
    for lo in vals:
        try:
            print(len(cut(a, lo, 3, 1)))
        except TypeError:
            print("TypeError")
    for hi in vals:
        try:
            print(len(cut(a, 1, hi, 1)))
        except TypeError:
            print("TypeError")
    for st in vals:
        try:
            print(len(cut(a, 0, 4, st)))
        except TypeError:
            print("TypeError")
    d = {"bad": 1.0}
    try:
        print(len(cut(a, d["bad"], 2, 1)))
    except TypeError:
        print("TypeError")
    s = slice(1, 2.0, 1)
    try:
        print(len(a[s]))
    except TypeError:
        print("TypeError")
    for lo in [-9, -1, 0, 2, 5, 100]:
        for hi in [-9, -1, 0, 2, 5, 100]:
            print(len(a[lo:hi]))
main()
'''

INDEX_BOUNDS = r'''def find(a, v, lo, hi):
    return a.index(v, lo, hi)
def main():
    a = [0, 1, 2, 1, 3]
    none = None
    for bad in [1.0, "1", none]:
        try:
            print(a.index(1, bad))
        except TypeError:
            print("TypeError")
        try:
            print(find(a, 1, 0, bad))
        except TypeError:
            print("TypeError")
    try:
        print(a.index(1, none, none))
    except TypeError:
        print("TypeError")
    t = (0, 1, 2, 1)
    try:
        print(t.index(1, 1.0))
    except TypeError:
        print("TypeError")
    vals = [2.0, none, 1]
    for i in range(len(vals)):
        try:
            print(a.index(1, vals[i]))
        except TypeError:
            print("TypeError")
    d = {"lo": 1.0, "hi": none}
    try:
        print(a.index(1, d["lo"], d["hi"]))
    except TypeError:
        print("TypeError")
    print(a.index(1, True))
    for lo in [-9, -1, 0, 2, 5, 100]:
        for hi in [-9, -1, 0, 2, 5, 100]:
            try:
                print(a.index(1, lo, hi))
            except ValueError:
                print("ValueError")
main()
'''

INSERT_POP = r'''class Box:
    i: int
    def __init__(self, i):
        self.i = i
def ins(a, i, v):
    a.insert(i, v)
def pop(a, i):
    return a.pop(i)
def main():
    for bad in [1.0, "1", None]:
        a = [1, 2, 3]
        try:
            ins(a, bad, 9)
            print("insert-ok", len(a))
        except TypeError:
            print("insert-TypeError")
        b = [1, 2, 3]
        try:
            print(pop(b, bad))
        except TypeError:
            print("pop-TypeError")
    vals = [2.0, None]
    c = [1, 2, 3]
    for i in range(len(vals)):
        try:
            c.insert(vals[i], 9)
            print("insert-ok", len(c))
        except TypeError:
            print("insert-TypeError")
    box = Box(1.0)
    d = [1, 2, 3]
    try:
        d.insert(box.i, 9)
    except TypeError:
        print("insert-TypeError")
    big = 9223372036854775807
    neg = -9223372036854775807
    e = [1, 2, 3]
    e.insert(big, 9)
    e.insert(neg, 8)
    for v in e:
        print(v)
    f = [1, 2, 3]
    try:
        f.pop(big)
    except IndexError:
        print("IndexError")
    try:
        f.pop(neg)
    except IndexError:
        print("IndexError")
    print(f.pop(-3), len(f))
    for i in [-9, -3, -1, 0, 3, 9]:
        g = [1, 2]
        g.insert(i, 7)
        for v in g:
            print(v)
        h = [1, 2]
        try:
            print(h.pop(i))
        except IndexError:
            print("IndexError")
main()
'''

AREA = r'''def key(v):
    return v % 3
def main():
    a = [3, 6, 1, 4, 7, 2, 5, 8, 0, 9]
    a.sort(key=key)
    for v in a:
        print(v)
    a.sort(key=key, reverse=True)
    for v in a:
        print(v)
    b = [0, 1, 2, 3, 4, 5]
    b[1:5:2] = [9, 8]
    del b[0]
    b.insert(-1, 7)
    b.pop(0)
    for v in b:
        print(v)
    row = [0]
    nested = [row] * 3
    nested[0][0] = 9
    print(nested[0][0], nested[1][0], nested[2][0])
    row2 = [[1], [2], [3]]
    row2[1:2] = [[7], [8]]
    row2[0][0] = 5
    print(row2[0][0], row2[1][0], len(row2))
    print([[1], [2]] == [[1], [2]], [[1], [2]] < [[1], [3]])
main()
'''


class SliceReadBounds(Base):
    def test_none_literal_dynamic_items_dict_attr_and_slice_object(self):
        self.same(SLICE_NONE)

    def test_wrong_types_raise_typeerror_and_valid_bounds_keep_clamping(self):
        self.same(SLICE_TYPES)


class SequenceIndexBounds(Base):
    def test_list_and_tuple_index_none_and_wrong_types(self):
        self.same(INDEX_BOUNDS)

    def test_insert_and_pop_index_conversion_and_edges(self):
        self.same(INSERT_POP)


class AreaRegression(Base):
    def test_sort_stability_reverse_slice_assignment_del_and_nested_multiplication(self):
        self.same(AREA)


if __name__ == "__main__":
    unittest.main()
