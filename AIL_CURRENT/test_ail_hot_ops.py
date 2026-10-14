"""Hot operations of round-4 programs, checked against CPython:

* A heap of structs ordered by `key=` reading int or float fields (heappush/heappop/heapify) sifts
  in C over the list's pointer array (`ail_oheap_*`): no element is retained or released and no
  list slot is stored through the reference-counting setter on any comparison or move. Ties keep
  CPython's order (only `<` of the key tuples decides, as with an object whose __lt__ compares
  them), -0.0 equals 0.0, an empty heappop raises IndexError, and a heap in a struct field works.
* `if k in d { x = d[k]; }` on a dict[int, int] and an int local is one probe (`x = d.get(k, x)`);
  deletions, re-insertions, absent keys and KeyError are unchanged.
"""
import tempfile
import unittest

from test_ail_element_views import run_pair
from test_ail_text_views import body_of

HEAP_SOURCE = r"""
struct It { d: int; w: float; n: int; }
struct Q { h: list[It]; }

fn drain(q: Q) -> int {
    let t = 0;
    while len(q.h) > 0 {
        let z = heappop(q.h, key=lambda z: z.d);
        t = (t * 13 + z.n + 1) % 1000000007;
    }
    return t;
}

fn main() {
    let n = int(sys.argv[1]);
    let h: list[It] = [];
    let q = Q([]);
    let seed = 12345;
    let out = 0;
    let empties = 0;
    for step in range(n) {
        seed = (seed * 1103515245 + 12345) % 2147483648;
        let r = seed % 10;
        if r < 6 {
            heappush(h, It(seed % 7 - 3, float(seed % 5) * 0.5 - 1.0, step), key=lambda it: (it.d, it.w));
            heappush(q.h, It(seed % 4, 0.0, step), key=lambda z: z.d);
        } else {
            if len(h) > 0 {
                let it = heappop(h, key=lambda it: (it.d, it.w));
                out = (out * 31 + it.n + 7) % 1000000007;
                if step % 97 == 0 { print("pop", it.d, it.n); }
            }
            try {
                let z = heappop(q.h, key=lambda z: z.d);
                out = (out * 17 + z.n) % 1000000007;
            } except IndexError as ie {
                empties += 1;
            }
        }
    }
    let zs: list[It] = [];
    for i in range(60) {
        let w = 0.0;
        if i % 3 == 0 { w = -0.0; }
        if i % 5 == 0 { w = 1.5; }
        zs.append(It((i * 37) % 11 - 5, w, i % 4));
    }
    heapify(zs, key=lambda e: (e.d, e.w, e.n));
    let order: list[str] = [];
    while len(zs) > 0 {
        let e = heappop(zs, key=lambda e: (e.d, e.w, e.n));
        order.append(str(e.d * 10 + e.n));
    }
    print(" ".join(order));
    print(out, empties, len(h), drain(q));
}
"""

HEAP_PYTHON = r"""
import sys
from heapq import heappush, heappop, heapify

class It:
    def __init__(self, d, w, n):
        self.d, self.w, self.n = d, w, n

def keyed(key):
    class W:
        __slots__ = ("v",)
        def __init__(self, v): self.v = v
        def __lt__(a, b): return key(a.v) < key(b.v)
    return W

A = keyed(lambda it: (it.d, it.w))
B = keyed(lambda z: z.d)
C = keyed(lambda e: (e.d, e.w, e.n))

def main():
    n = int(sys.argv[1])
    h, qh = [], []
    seed, out, empties = 12345, 0, 0
    for step in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        r = seed % 10
        if r < 6:
            heappush(h, A(It(seed % 7 - 3, float(seed % 5) * 0.5 - 1.0, step)))
            heappush(qh, B(It(seed % 4, 0.0, step)))
        else:
            if len(h) > 0:
                it = heappop(h).v
                out = (out * 31 + it.n + 7) % 1000000007
                if step % 97 == 0: print("pop", it.d, it.n)
            try:
                z = heappop(qh).v
                out = (out * 17 + z.n) % 1000000007
            except IndexError:
                empties += 1
    zs = []
    for i in range(60):
        w = 0.0
        if i % 3 == 0: w = -0.0
        if i % 5 == 0: w = 1.5
        zs.append(C(It((i * 37) % 11 - 5, w, i % 4)))
    heapify(zs)
    order = []
    while zs:
        e = heappop(zs).v
        order.append(str(e.d * 10 + e.n))
    print(" ".join(order))
    t = 0
    while qh:
        z = heappop(qh).v
        t = (t * 13 + z.n + 1) % 1000000007
    print(out, empties, len(h), t)

main()
"""

DICT_SOURCE = r"""
fn look(d: dict[int, int], k: int) -> int {
    let p = -1;
    if k in d { p = d[k]; }
    return p;
}

fn main() {
    let n = int(sys.argv[1]);
    let d: dict[int, int] = {};
    let acc = 0;
    let misses = 0;
    let p = -1;
    for i in range(n) {
        let k = (i * 7919) % 5003 * 1000003;
        if k in d { p = d[k]; }
        acc = (acc * 3 + p) % 1000000007;
        d[k] = i;
        let j = k + 1000003;
        if i % 7 == 0 and j in d { d.pop(j); }
        if i % 11 == 0 {
            try { acc = (acc + d[k * 3 + 1]) % 1000000007; }
            except KeyError { misses += 1; }
        }
        if i % 13 == 0 { d[k] = d[k] + 5; }
        acc = (acc + look(d, j) + look(d, k)) % 1000000007;
    }
    let small: dict[int, int] = {};
    for i in range(50) { small[i % 9] = i; }
    let q = 7;
    if 3 in small { q = small[3]; }
    if 30 in small { q = small[30]; }
    let s = 0;
    for k, v in d.items() { s = (s * 7 + k % 1000 + v) % 1000000007; }
    print(acc, misses, len(d), s, p, q);
}
"""

DICT_PYTHON = r"""
import sys
def look(d, k):
    p = -1
    if k in d: p = d[k]
    return p
def main():
    n = int(sys.argv[1])
    d = {}
    acc = misses = 0
    p = -1
    for i in range(n):
        k = (i * 7919) % 5003 * 1000003
        if k in d: p = d[k]
        acc = (acc * 3 + p) % 1000000007
        d[k] = i
        j = k + 1000003
        if i % 7 == 0 and j in d: d.pop(j)
        if i % 11 == 0:
            try: acc = (acc + d[k * 3 + 1]) % 1000000007
            except KeyError: misses += 1
        if i % 13 == 0: d[k] = d[k] + 5
        acc = (acc + look(d, j) + look(d, k)) % 1000000007
    small = {}
    for i in range(50): small[i % 9] = i
    q = 7
    if 3 in small: q = small[3]
    if 30 in small: q = small[30]
    s = 0
    for k, v in d.items(): s = (s * 7 + k % 1000 + v) % 1000000007
    print(acc, misses, len(d), s, p, q)
main()
"""

class HotOpsTests(unittest.TestCase):
    def test_struct_heap_matches_cpython_without_refcounts(self):
        with tempfile.TemporaryDirectory() as directory:
            for n in ("0", "1", "40", "3000"):
                _, program = run_pair(self, directory, HEAP_SOURCE, HEAP_PYTHON, argv=(n,))
            main = body_of(program, "py_main")
            for op in ("ail_oheap_up_It_0_1(", "ail_oheap_pop_It_0_1(", "ail_oheap_up_It_0(",
                       "ail_oheap_heapify_It_0_1_2(", "ail_oheap_pop_It_0_1_2("):
                self.assertIn(op, main)
            self.assertIn("ail_oheap_pop_It_0(", body_of(program, "drain"))
            # no element read, store or retain is left of the sift loops
            self.assertNotIn("ail_olist_get", main)
            self.assertNotIn("ail_olist_set", main)
            sift = program[program.index("static void ail_oheap_down_It_0_1("):]
            sift = sift[:sift.index("\n}\n")]
            self.assertNotIn("retain", sift)
            self.assertNotIn("release", sift)

    def test_int_dict_get_fusion_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            for n in ("0", "5", "20000"):
                _, program = run_pair(self, directory, DICT_SOURCE, DICT_PYTHON, argv=(n,))
            look = body_of(program, "look")
            self.assertIn("ail_idict_get(", look)
            self.assertNotIn("ail_idict_has(", look)
            self.assertNotIn("ail_idict_need(", look)
            # a read that is not the whole assigned value keeps its own probe
            self.assertIn("ail_idict_need(", body_of(program, "py_main"))


if __name__ == "__main__":
    unittest.main()
