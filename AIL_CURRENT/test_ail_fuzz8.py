"""fuzz8: silent differences in the iteration tools, compared with CPython 3.12.

1. `itertools.accumulate(..., initial=None)`: CPython's signature spells the default as
   `initial=None`, and its implementation treats an actual None as "not given"
   (`accumulate([], initial=None)` is `[]`, `accumulate([1, 2], initial=None)` is `[1, 3]`).
   The general path used to yield the None as the first accumulated value and then fail adding
   to it.  The value may arrive as a constant, an argument, a list item, an attribute or a dict
   value; all of those are covered below.
2. `sorted(xs, key=k, reverse=True)` / `xs.sort(key=k, reverse=True)`: CPython calls `k` on the
   input in its ORIGINAL order (once per element, including a one-element list), then reverses
   the decorations and the elements.  The C sort reversed the elements first, so a key with a
   side effect saw the input backwards.  The result order was already right, which is what made
   this a silent difference.
3. `itertools.groupby(xs, key=k)` on the typed path called `k` twice on the first element of
   every group after the first (once as the look-ahead that ended the previous group, again as
   the start of the next).  CPython calls it exactly once per element; the typed lowering now
   keeps the look-ahead key.

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and its stdout and
exit status must equal CPython's.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


ACC_NONE = r'''import itertools

def summarize(xs, init, use_func):
    if use_func:
        return list(itertools.accumulate(xs, lambda a, b: a + b, initial=init))
    return list(itertools.accumulate(xs, initial=init))

def via_arg(init):
    return summarize([1, 2, 3], init, False)

class C:
    pass
o = C()
o.init = None
D = {"init": None}
L = [None, 0, -1]

print(summarize([], None, False))
print(summarize([5], None, False))
print(summarize([], None, True))
print(summarize([1, 2], None, True))
print(summarize([], 0, False), summarize([], False, False), summarize([], -1, False))
print(summarize([1, 2], 0, False), summarize([1, 2], False, True))
print(via_arg(None), via_arg(0), via_arg(10))
print(summarize([], L[0], False), summarize([1, 2], L[0], False))
print(summarize([], L[1], False), summarize([1, 2], L[2], False))
print(summarize([], o.init, False), summarize([1, 2], o.init, False))
print(summarize([], D["init"], False), summarize([1, 2], D["init"], False))
a = [1, 2]
init = []
print(list(itertools.accumulate(a, lambda x, y: x + [y], initial=init)), a, init)
'''

SORT_REV_KEY = r'''calls = []

def key(x):
    calls.append(x)
    return x % 3

calls = []
print(sorted([5, 1, 8, 2, 4], key=key, reverse=False))
print(calls)
calls = []
print(sorted([5, 1, 8, 2, 4], key=key, reverse=True))
print(calls)
calls = []
print(sorted([], key=key, reverse=True), calls)
calls = []
print(sorted([7], key=key, reverse=True), calls)
calls = []
print(sorted([-5, 1, -8, 2], key=key, reverse=True))
print(calls)
calls = []
print(sorted([3, 1, 2], key=key, reverse=True))
print(calls)
calls = []
a = [5, 1, 8, 2, 4]
a.sort(key=key, reverse=True)
print(a, calls)
calls = []
a = [5, 1, 8, 2, 4]
a.sort(key=key, reverse=False)
print(a, calls)
calls = []
print(sorted([2, 2, 2], key=key, reverse=True), calls)

def k2(x):
    calls.append(x)
    return -x

def desc(xs, k):
    return sorted(xs, key=k, reverse=True)

class C:
    pass
o = C()
o.k = k2
L = [k2]
D = {"k": k2}
calls = []
print(desc([1, 3, 2], k2), calls)
calls = []
print(desc([1, 3, 2], L[0]), calls)
calls = []
print(desc([1, 3, 2], o.k), calls)
calls = []
print(desc([1, 3, 2], D["k"]), calls)
'''

GROUPBY_CALLS = r'''import itertools
calls = []

def key(x):
    calls.append(x)
    return x // 2

print("empty")
calls = []
for g, vals in itertools.groupby([], key=key):
    print(g, list(vals))
print(calls)
print("single")
calls = []
for g, vals in itertools.groupby([0], key=key):
    print(g, list(vals))
print(calls)
print("range")
calls = []
for g, vals in itertools.groupby([0, 1, 2, 3, 4, 5], key=key):
    print(g, list(vals))
print(calls)
print("same")
calls = []
for g, vals in itertools.groupby([1, 1, 1], key=key):
    print(g, list(vals))
print(calls)
print("alternate")
calls = []
for g, vals in itertools.groupby([1, 2, 1, 2], key=key):
    print(g, list(vals))
print(calls)
print("negative")
calls = []
for g, vals in itertools.groupby([-3, -2, -1, 0, 1], key=key):
    print(g, list(vals))
print(calls)

def k2(x):
    calls.append(x)
    return -x

class C:
    pass
o = C()
o.k = k2
L = [k2]
D = {"k": k2}
kk = k2
calls = []
for g, vals in itertools.groupby([1, 2, 2, 3], key=kk):
    print(g, list(vals))
print(calls)
kk = L[0]
calls = []
for g, vals in itertools.groupby([1, 2, 2, 3], key=kk):
    print(g, list(vals))
print(calls)
kk = o.k
calls = []
for g, vals in itertools.groupby([1, 2, 2, 3], key=kk):
    print(g, list(vals))
print(calls)
kk = D["k"]
calls = []
for g, vals in itertools.groupby([1, 2, 2, 3], key=kk):
    print(g, list(vals))
print(calls)
calls = []
g = itertools.groupby([1, 1, 2, 2, 3], key=key)
for k, grp in g:
    print(k, next(grp), next(grp))
print(calls)
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz8-")
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
        ref = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=120)
        out = ref.stdout.replace(b"\r\n", b"\n")
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.replace(b"\r\n", b"\n"), out,
                             "general" if general else "default")
            self.assertEqual(ran.returncode, ref.returncode,
                             "general" if general else "default")
        return out


class AccumulateInitialNone(Base):
    def test_none_is_not_an_initial_value(self):
        out = self.same(ACC_NONE)
        self.assertIn(b"[]\n[5]\n[]\n[1, 3]\n", out)
        self.assertIn(b"[]\n[1, 3]\n", out)


class SortedReverseKey(Base):
    def test_key_calls_in_original_order(self):
        out = self.same(SORT_REV_KEY)
        self.assertIn(b"[5, 8, 2, 1, 4]\n[5, 1, 8, 2, 4]\n", out)   # reverse=True, key trace

    def test_one_element_still_calls_key(self):
        out = self.same(SORT_REV_KEY)
        self.assertIn(b"[7] [7]\n", out)


class GroupbyKeyCalls(Base):
    def test_key_called_once_per_element(self):
        out = self.same(GROUPBY_CALLS)
        self.assertIn(b"[0, 1, 2, 3, 4, 5]\n", out)
        self.assertNotIn(b"[0, 1, 2, 2, 3, 4, 4, 5]\n", out)


if __name__ == "__main__":
    unittest.main()
