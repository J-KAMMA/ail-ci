"""heapq and bisect built-ins without import: heappush/heappop/heapify/heappushpop/heapreplace,
bisect_left/bisect_right/bisect and insort/insort_left/insort_right.

LLM-written AIL hand-rolled binary heaps and binary searches (about 10 KB of extra source over 20
programs, 2026-10-14). These names are lowered to CPython's own algorithms (heapq._siftdown and
_siftup, bisect's loop) over in-place list reads and writes, so the heap layout after every step
equals CPython's. The oracle below runs the same operation stream with the real heapq and bisect
modules; a heap of structs ordered by `key=` is checked against an object whose __lt__ compares
the same key. Also checked: IndexError on an empty heap, struct-field heaps, refusals (read-only
list parameters, conditional evaluation, a read Python evaluates before the pop), a user function
of the same name, and that the generated C mutates the list in place with no copy per call.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = 'from ail import heappop, heappush\nimport sys\n\nclass Rng:\n\n    def __init__(self, s: int):\n        self.s = s\n\n    def next(self, m: int) -> int:\n        self.s = (self.s * 1103515245 + 12345) % 2147483648\n        return (self.s >> 8) % m\n\nclass Item:\n\n    def __init__(self, t: int, b: str, id: int):\n        self.t = t\n        self.b = b\n        self.id = id\n\nclass Box:\n\n    def __init__(self, h: list[int], items: list[Item], f: list[float]):\n        self.h = h\n        self.items = items\n        self.f = f\n\n    def add(self, x: int) -> None:\n        heappush(self.h, x)\n\n    def take(self) -> int:\n        return heappop(self.h)\n\n    def add_item(self, it: Item) -> None:\n        heappush(self.items, it, key=lambda n: (n.t, n.b))\n\n    def take_item(self) -> Item:\n        return heappop(self.items, key=lambda n: (n.t, n.b))\n\ndef show_i(xs: list[int]) -> str:\n    parts: list[str] = []\n    for x in xs:\n        parts.append(str(x))\n    return \',\'.join(parts)\n\ndef show_f(xs: list[float]) -> str:\n    parts: list[str] = []\n    for x in xs:\n        parts.append(f\'{x:.3f}\')\n    return \',\'.join(parts)\n\ndef show_items(xs: list[Item]) -> str:\n    parts: list[str] = []\n    for it in xs:\n        parts.append(str(it.t) + it.b + str(it.id))\n    return \',\'.join(parts)\n\ndef main() -> int:\n    r = Rng(int(sys.argv[1]))\n    h: list[int] = []\n    fl: list[float] = []\n    sl: list[str] = []\n    bx = Box([], [], [])\n    sorted_i: list[int] = []\n    sorted_s: list[str] = []\n    byt: list[Item] = []\n    for step in range(1500):\n        op = r.next(12)\n        v = r.next(200) - 100\n        if op < 4:\n            heappush(h, v)\n            heappush(fl, float(v) / 8.0)\n            heappush(sl, \'k\' + str(v % 37))\n            bx.add(v)\n            bx.add_item(Item(v % 5, \'s\' + str(v % 3), step))\n            heappush(bx.f, float(v) * 0.25)\n        elif op < 7:\n            if len(h) > 0:\n                a = heappop(h)\n                it = bx.take_item()\n                tk = bx.take()\n                print(\'pop\', a, f\'{heappop(fl):.3f}\', heappop(sl), tk, it.t, it.b, it.id, f\'{heappop(bx.f):.3f}\')\n            else:\n                try:\n                    heappop(h)\n                    print(\'no\')\n                except IndexError as ie:\n                    print(\'empty\', ie.kind)\n        elif op == 7:\n            if len(h) > 0:\n                print(\'pp\', heappushpop(h, v), heapreplace(sl, \'r\' + str(v)), heappushpop(bx.h, v * 2))\n            else:\n                print(\'pp0\', heappushpop(h, v))\n                try:\n                    heapreplace(fl, 1.0)\n                except IndexError:\n                    print(\'replace empty\')\n        elif op == 8:\n            xs: list[int] = []\n            k = r.next(30)\n            for i in range(k):\n                xs.append(r.next(50))\n            heapify(xs)\n            ys: list[str] = []\n            for x in xs:\n                ys.append(str(x * 7 % 11))\n            heapify(ys)\n            zs: list[Item] = []\n            for x in xs:\n                zs.append(Item(x % 4, \'z\' + str(x % 2), x))\n            heapify(zs, key=lambda n: (n.t, n.b))\n            print(\'heapify\', show_i(xs), \',\'.join(ys), show_items(zs))\n        elif op == 9:\n            insort(sorted_i, v % 20)\n            insort_left(sorted_s, \'w\' + str(v % 9))\n            insort_right(sorted_s, \'w\' + str(v % 4))\n            insort(byt, Item(v % 6, \'b\', step), key=lambda n: n.t)\n            lo = r.next(len(sorted_i) + 1)\n            hi = lo + r.next(len(sorted_i) - lo + 1)\n            print(\'bis\', bisect_left(sorted_i, v % 20), bisect_right(sorted_i, v % 20), bisect(sorted_i, 3), bisect_left(sorted_i, v % 20, lo, hi), bisect_right(sorted_i, v % 20, lo=lo, hi=hi), bisect_left(sorted_s, \'w5\'), bisect_right(sorted_s, \'w2\', lo), bisect_left(byt, 3, key=lambda n: n.t), bisect_right(byt, 3, key=lambda n: n.t))\n        elif op == 10:\n            ff = [2.5, 0.5, 1.5]\n            insort(ff, float(v) / 16.0)\n            print(\'fl\', show_f(ff), bisect_left(ff, 0.5), bisect_right(ff, 0.5, 1))\n        else:\n            print(\'state\', show_i(h), show_f(fl), \',\'.join(sl), show_i(bx.h), show_items(bx.items))\n    print(\'final\', show_i(h), \',\'.join(sl), show_i(sorted_i), \',\'.join(sorted_s), show_items(byt))\n    e: list[int] = []\n    try:\n        print(bisect_left(e, 1, -1))\n    except ValueError as err:\n        print(\'lo\', err.message)\n    e2: list[int] = [1, 2, 2, 3]\n    print(\'bneg\', bisect(e2, 2, 0, -1), bisect(e2, 2, 0, -2))\n    try:\n        print(\'bhi\', bisect(e2, 2, 0, 99))\n    except IndexError as err:\n        print(\'bhi\', err.message)\n    try:\n        print(\'bhi\', bisect_left(e2, 2, 0, 99))\n    except IndexError as err:\n        print(\'bhi\', err.message)\n    try:\n        bisect(e2, 2, -1, 3)\n    except ValueError as err:\n        print(\'blo\', err.message)\n    e3: list[int] = [1, 2, 2, 3]\n    try:\n        insort(e3, 2, 0, 99)\n    except IndexError as err:\n        print(\'bins\', err.message)\n    e4: list[int] = [1, 2, 2, 3]\n    insort(e4, 2, 0, -1)\n    print(\'binsneg\', show_i(e4))\n    e5: list[int] = [1, 2, 2, 3]\n    print(\'bnone\', bisect_left(e5, 2, 0, None), bisect_right(e5, 2, hi=None), bisect_left(e5, 2, lo=1, hi=None), bisect(e5, 9, 0, None))\n    insort_left(e5, 3, 0, None)\n    insort_right(e5, 1, hi=None)\n    insort(e5, 2, lo=0, hi=None)\n    print(\'binsnone\', show_i(e5))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

PYTHON = r'''
import sys
from heapq import heappush, heappop, heapify, heappushpop, heapreplace
from bisect import bisect_left, bisect_right, bisect, insort, insort_left, insort_right


class Rng:
    def __init__(self, s): self.s = s
    def next(self, m):
        self.s = (self.s * 1103515245 + 12345) % 2147483648
        return (self.s >> 8) % m


class Item:
    def __init__(self, t, b, id): self.t, self.b, self.id = t, b, id
    def __lt__(self, o): return (self.t, self.b) < (o.t, o.b)


def show_items(xs): return ",".join(str(it.t) + it.b + str(it.id) for it in xs)
def show_i(xs): return ",".join(str(x) for x in xs)
def show_f(xs): return ",".join("%.3f" % x for x in xs)


def main():
    r = Rng(int(sys.argv[1]))
    h, fl, sl = [], [], []
    bh, items, bf = [], [], []
    sorted_i, sorted_s, byt = [], [], []
    for step in range(1500):
        op = r.next(12)
        v = r.next(200) - 100
        if op < 4:
            heappush(h, v); heappush(fl, v / 8.0); heappush(sl, "k" + str(v % 37))
            heappush(bh, v); heappush(items, Item(v % 5, "s" + str(v % 3), step)); heappush(bf, v * 0.25)
        elif op < 7:
            if h:
                a = heappop(h)
                it = heappop(items)
                print("pop", a, "%.3f" % heappop(fl), heappop(sl), heappop(bh), it.t, it.b, it.id, "%.3f" % heappop(bf))
            else:
                try:
                    heappop(h); print("no")
                except IndexError:
                    print("empty", "IndexError")
        elif op == 7:
            if h:
                print("pp", heappushpop(h, v), heapreplace(sl, "r" + str(v)), heappushpop(bh, v * 2))
            else:
                print("pp0", heappushpop(h, v))
                try:
                    heapreplace(fl, 1.0)
                except IndexError:
                    print("replace empty")
        elif op == 8:
            k = r.next(30)
            xs = [r.next(50) for _ in range(k)]
            heapify(xs)
            ys = [str(x * 7 % 11) for x in xs]
            heapify(ys)
            zs = [Item(x % 4, "z" + str(x % 2), x) for x in xs]
            heapify(zs)
            print("heapify", show_i(xs), ",".join(ys), show_items(zs))
        elif op == 9:
            insort(sorted_i, v % 20)
            insort_left(sorted_s, "w" + str(v % 9))
            insort_right(sorted_s, "w" + str(v % 4))
            insort(byt, Item(v % 6, "b", step), key=lambda n: n.t)
            lo = r.next(len(sorted_i) + 1)
            hi = lo + r.next(len(sorted_i) - lo + 1)
            print("bis", bisect_left(sorted_i, v % 20), bisect_right(sorted_i, v % 20), bisect(sorted_i, 3),
                  bisect_left(sorted_i, v % 20, lo, hi), bisect_right(sorted_i, v % 20, lo=lo, hi=hi),
                  bisect_left(sorted_s, "w5"), bisect_right(sorted_s, "w2", lo),
                  bisect_left(byt, 3, key=lambda n: n.t), bisect_right(byt, 3, key=lambda n: n.t))
        elif op == 10:
            ff = [2.5, 0.5, 1.5]
            insort(ff, v / 16.0)
            print("fl", show_f(ff), bisect_left(ff, 0.5), bisect_right(ff, 0.5, 1))
        else:
            print("state", show_i(h), show_f(fl), ",".join(sl), show_i(bh), show_items(items))
    print("final", show_i(h), ",".join(sl), show_i(sorted_i), ",".join(sorted_s), show_items(byt))
    try:
        print(bisect_left([], 1, -1))
    except ValueError as err:
        print("lo", err)
    e2 = [1, 2, 2, 3]
    print("bneg", bisect(e2, 2, 0, -1), bisect(e2, 2, 0, -2))
    try:
        print("bhi", bisect(e2, 2, 0, 99))
    except IndexError as err:
        print("bhi", err)
    try:
        print("bhi", bisect_left(e2, 2, 0, 99))
    except IndexError as err:
        print("bhi", err)
    try:
        bisect(e2, 2, -1, 3)
    except ValueError as err:
        print("blo", err)
    e3 = [1, 2, 2, 3]
    try:
        insort(e3, 2, 0, 99)
    except IndexError as err:
        print("bins", err)
    e4 = [1, 2, 2, 3]
    insort(e4, 2, 0, -1)
    print("binsneg", show_i(e4))
    e5 = [1, 2, 2, 3]
    print("bnone", bisect_left(e5, 2, 0, None), bisect_right(e5, 2, hi=None),
          bisect_left(e5, 2, lo=1, hi=None), bisect(e5, 9, 0, None))
    insort_left(e5, 3, 0, None)
    insort_right(e5, 1, hi=None)
    insort(e5, 2, lo=0, hi=None)
    print("binsnone", show_i(e5))


main()
'''

# The bounds of a Python-syntax program (the general path: `_bisect_call` boxes lo and hi, so the
# conversions CPython's C _bisect does -- lo with the index converter, hi with the one that also
# takes None -- have to be emitted; a bare `(value).i` read a float's payload as a number).
BOUNDS_PYTHON = r'''
import bisect


class Box:
    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi


def note(tag, v):
    print("eval", tag)
    return v


xs = [1, 2, 2, 4]
print(bisect.bisect_left(xs, 2, 0, None), bisect.bisect_right(xs, 2, hi=None))
print(bisect.bisect_left(xs, 2, lo=1, hi=None), bisect.bisect(xs, 2, 1, None))
print(bisect.bisect_left([], 1, 0, None), bisect.bisect_right(xs, 2, True, True))
none_pair = [1, None]
print(bisect.bisect_left(xs, 4, none_pair[0], none_pair[1]))
box = Box(0, None)
print(bisect.bisect_right(xs, 2, box.lo, box.hi), bisect.bisect_left(xs, 2, hi=box.hi))
ys = [1, 3]
bisect.insort_left(ys, 2, 0, None)
bisect.insort_right(ys, 2, hi=None)
bisect.insort(ys, 0, 0, None)
print(ys, bisect.bisect_left(xs, 2, 0, -1), bisect.bisect_left(xs, 2, 0, -2))
for bad in ("1", 1.0, None):
    try:
        print(bisect.bisect_left(xs, 2, bad, None))
    except TypeError as err:
        print("lo", type(err).__name__, err)
for bad in ("2", 1.0, [1]):
    try:
        print(bisect.bisect_left(xs, 2, 0, bad))
    except TypeError as err:
        print("hi", type(err).__name__, err)
try:
    print(bisect.bisect_left(xs, 2, -1, None))
except ValueError as err:
    print("neg", type(err).__name__, err)
try:
    print(bisect.bisect_left(xs, 2, -1, 1.0))
except TypeError as err:
    print("order", type(err).__name__, err)
try:
    print(bisect.bisect_left(xs, 2, None, 1.0))
except TypeError as err:
    print("order", type(err).__name__, err)
print(note("a", bisect.bisect_left(xs, 2, note("lo", 0), note("hi", None))))
try:
    print(bisect.bisect_left(xs, 2, note("lo", 1), note("hi", 1.0)))
except TypeError as err:
    print("order", type(err).__name__, err)
keep = [1, 5]
try:
    bisect.insort_left(keep, 3, 0, 1.5)
except TypeError as err:
    print("insort", type(err).__name__, err)
print(keep)
'''

SHADOW = 'from ail import heappush\nimport sys\n\ndef heappush(xs: list[int], x: int) -> int:\n    return len(xs) + x\n\ndef main() -> int:\n    h: list[int] = [1, 2]\n    print(heappush(h, 10))\n    q: list[int] = []\n    heappop_like(q)\n    return 0\n\ndef heappop_like(q: list[int]) -> None:\n    print(len(q))\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

ORDER = 'from ail import heappop, heappush\nimport sys\n\ndef main() -> int:\n    h: list[int] = []\n    for x in [5, 1, 4]:\n        heappush(h, x)\n    print(heappop(h), heappop(h), len(h))\n    total = heappop(h) * 10 + len(h)\n    print(total)\n    heappush(h, 3)\n    heappush(h, heappop(h) + 1)\n    print(h[0])\n    while len(h) > 0:\n        x = heappop(h)\n        print(x)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

REFUSED = [
    # a list parameter is read-only: the heap has to live in a local or a struct field
    ('from ail import heappush\nimport sys\n\ndef f(h: list[int]) -> None:\n    heappush(h, 1)\n\ndef main() -> int:\n    h: list[int] = []\n    f(h)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'read-only'),
    ('from ail import heappop\nimport sys\n\ndef f(h: list[int]) -> int:\n    return heappop(h)\n\ndef main() -> int:\n    h: list[int] = [1]\n    print(f(h))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'read-only'),
    # Python evaluates h[0] before the pop
    ('from ail import heappop\nimport sys\n\ndef main() -> int:\n    h: list[int] = [1, 2]\n    print(h[0], heappop(h))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'bind the result'),
    ('from ail import heappop\nimport sys\n\nclass B:\n\n    def __init__(self, h: list[float]):\n        self.h = h\n\n    def n(self) -> int:\n        return len(self.h)\n\ndef main() -> int:\n    b = B([1.0])\n    print(b.n(), f\'{heappop(b.h):.1f}\')\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'bind the result'),
    # only evaluated sometimes
    ('from ail import heappop\nimport sys\n\ndef main() -> int:\n    h: list[int] = [1]\n    c = 1\n    x = 0 if c else heappop(h)\n    print(x)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'unconditionally'),
    ('from ail import heappush\nimport sys\n\ndef main() -> int:\n    h: list[int] = [1]\n    x = heappush(h, 2)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'statement'),
    ('from ail import heappush\nimport sys\n\ndef main() -> int:\n    h: list[int] = []\n    heappush(h)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'heappush(h, x)'),
    ('from ail import heappush\nimport sys\n\ndef main() -> int:\n    h: list[int] = []\n    heappush(h, 1, reverse=True)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'key='),
    ('from ail import heappush\nimport sys\n\nclass N:\n\n    def __init__(self, t: int):\n        self.t = t\n\ndef main() -> int:\n    h: list[N] = []\n    heappush(h, N(1), key=3)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'key='),
    ('import sys\n\nclass N:\n\n    def __init__(self, t: int, u: int):\n        self.t = t\n        self.u = u\n\ndef main() -> int:\n    h: list[N] = []\n    print(bisect_left(h, 1, key=lambda n: (n.t, n.u)))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'tuple key'),
    # bisect's bounds are ints (CPython reads them as Py_ssize_t); hi may also be None, lo may not
    ('import sys\n\ndef main() -> int:\n    xs: list[int] = [1]\n    print(bisect_left(xs, 1, None))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'lo must be an int'),
    ('import sys\n\ndef main() -> int:\n    xs: list[int] = [1]\n    h = 1.5\n    print(bisect_left(xs, 1, 0, h))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'declared int'),
    ('import sys\n\ndef main() -> int:\n    xs: list[int] = [1]\n    print(bisect_right(xs, 1, hi=\'2\'))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'declared int'),
    ('import sys\n\ndef main() -> int:\n    xs: list[int] = [1]\n    insort_left(xs, 1, 1.5)\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n', 'declared int'),
]


def build(directory, text, name="p"):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


class HeapqBisectTests(unittest.TestCase):
    def test_random_streams_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, SOURCE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, "oracle.py")
            oracle.write_text(PYTHON)
            seen = []
            for seed in (1, 7, 2026, 99991):
                with self.subTest(seed=seed):
                    ran = subprocess.run([str(exe), str(seed)], capture_output=True, text=True, timeout=60)
                    expected = subprocess.run([sys.executable, str(oracle), str(seed)],
                                              capture_output=True, text=True, timeout=60)
                    self.assertEqual(expected.returncode, 0, expected.stderr)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout, expected.stdout)
                    seen.append(ran.stdout)
            for word in ("pop", "empty IndexError", "pp ", "pp0", "heapify", "bis", "fl ", "state",
                         "replace empty", "lo must be non-negative"):
                self.assertIn(word, "".join(seen))
            # field heaps change the list in place: no copy or snapshot of it per call
            program = c_file.read_text()
            for name in ("Box__add", "Box__take", "Box__add_item", "Box__take_item"):
                body = body_of(program, name)
                for copy in ("ail_list_copy", "_snapshot", "ail_olist_copy", "ail_list_dup"):
                    self.assertNotIn(copy, body, name)
            self.assertIn("ail_numfield_list_set(&(v_self)->f_h", body_of(program, "Box__take"))
            self.assertIn("ail_olist_set(", body_of(program, "Box__take_item"))

    def test_evaluation_order_and_user_function_of_the_same_name(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, ORDER)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "1 4 1\n50\n4\n4\n")
            body = body_of(c_file.read_text(), "py_main")
            self.assertIn("ail_list_push(&v_h", body)
            self.assertNotIn("ail_list_copy", body)
            built, exe, _ = build(directory, SHADOW, name="shadow")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "12\n0\n")

    def test_bounds_on_the_general_path(self):
        """A Python-syntax program: lo/hi boxed values, so CPython's own conversions apply."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "bounds.py")
            exe, debug = Path(directory, "bounds"), Path(directory, "bounds-debug")
            source.write_text(BOUNDS_PYTHON)
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                    "--syntax", "python", "-o", str(exe), "--debug-dir", str(debug)],
                                   capture_output=True, text=True, timeout=300)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            for word in ("argument should be integer or None, not 'float'",
                         "argument should be integer or None, not 'str'",
                         "'NoneType' object cannot be interpreted as an integer",
                         "ValueError lo must be non-negative", "eval hi", "order TypeError"):
                self.assertIn(word, ran.stdout)

    def test_misuse_is_refused_with_a_route(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, (text, hint) in enumerate(REFUSED):
                with self.subTest(text=text):
                    built, exe, _ = build(directory, text, name="n%d" % index)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertFalse(exe.exists())
                    self.assertIn(hint, built.stdout + built.stderr)


# These tests pin the C text of the legacy emitter, the AIL_IR=0 opt-out (the IR is the default since
# 2026-10-19 and has its own text, pinned in test_ail_ir_*): the whole module builds with AIL_IR=0
# unless the caller set AIL_IR.
_SAVED_AIL_IR = []


def setUpModule():
    import os as _os
    _SAVED_AIL_IR.append(_os.environ.get('AIL_IR'))
    if _SAVED_AIL_IR[-1] is None:
        _os.environ['AIL_IR'] = '0'


def tearDownModule():
    import os as _os
    if _SAVED_AIL_IR.pop() is None:
        _os.environ.pop('AIL_IR', None)


if __name__ == "__main__":
    unittest.main()
