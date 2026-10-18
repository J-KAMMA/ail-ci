"""Tuples and lambdas as values in the Python syntax, every result compared with CPython.

Every program below is ordinary Python.  CPython runs it as the oracle and the compiled program (the Python
syntax, AIL_NO_GENERAL=1 so the typed path must take it) prints the same bytes, or the spelling is refused by
name -- there is no third outcome where the numbers differ.

Built (python/pkg-v12/tuplib.py lowers them before the surface pass; see AIL_REFERENCE_MORE.md, Tuples):
* Functions returning tuples (`return a, b`, `-> tuple[int, str]`), unpacking at call sites (`q, r = f(x)`,
  nested `(a, b), c = ...`), divmod, str.partition, tuple-typed locals / parameters / fields, `t[k]` with a
  constant k, `for a, b in pairs`, `for i, (a, b) in enumerate(pairs)`, `for a, b in zip(xs, ys)`,
  list[tuple[...]] (append, sort, sorted with key, min, max, index, count, in, pop, insert, slices,
  comprehensions), tuple == != < <= > >= (lexicographic), print / str / f-string with CPython's repr
  (`(1, 'a')`, `(1,)`, quotes and escapes), heapq with tuple items, dict[tuple, V] / set[tuple] (get,
  setdefault, pop, del, update, items, keys, values, set operators; iteration in insertion order), module-level
  lists of number tuples (DIRS = [(0, 1), (1, 0)]).
* Lambdas: `f = lambda ...` then f(x) or passed on, lambdas passed to a Callable parameter (read-only captured
  locals included: the callee is cloned), map / filter / reduce with a lambda, key= lambdas over tuples.
Refused by name: tuple concatenation / repetition / slices / variable index, tuple(x), variable-length
tuple[int, ...], float dict keys, a lambda that escapes or captures a name assigned again after it, a loop that
changes the dict / set of tuples it walks, ...

Generated tests: random operation sequences (>= 5000 operations per program, an LCG inside the program picks
the operation, the key and the value) for dict / set / list / heap of tuples, final state and periodic
checkpoints compared.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
import tuplib  # noqa: E402


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


def oracle(text):
    run = subprocess.run([sys.executable, "-c", text], capture_output=True, text=True, timeout=300)
    return run


class Compared(unittest.TestCase):
    def compare(self, name, text, count_ops=0):
        with tempfile.TemporaryDirectory(prefix="tup_") as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, name + ": " + (built.stdout + built.stderr)[-3000:])
            run = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=300)
            want = oracle(text)
            self.assertEqual(want.returncode, 0, want.stderr)
            self.assertEqual(run.stdout, want.stdout, name)
            self.assertEqual(run.returncode, 0, run.stderr)
            return run.stdout

    def refused(self, text, expected):
        with tempfile.TemporaryDirectory(prefix="tup_") as directory:
            built, source, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled, expected a refusal naming: " + expected)
            self.assertIn(expected, built.stdout + built.stderr)


# ---- programs compared with CPython --------------------------------------------------
RETURNS = r'''def minmax(xs: list[int]) -> tuple[int, int]:
    lo = xs[0]
    hi = xs[0]
    for x in xs:
        if x < lo:
            lo = x
        if x > hi:
            hi = x
    return lo, hi


def parse(line: str) -> tuple[str, int]:
    parts = line.split("|")
    return parts[0], int(parts[1])


def stats(xs: list[float]) -> tuple[float, float, int]:
    s = 0.0
    for x in xs:
        s += x
    return s, s / len(xs), len(xs)


def swap(p: tuple[int, str]) -> tuple[str, int]:
    return p[1], p[0]


def main() -> int:
    lo, hi = minmax([3, 9, -2, 7])
    print(lo, hi)
    name, n = parse("abc|42")
    print(name, n)
    t = minmax([5, 1, 8])
    print(t)
    print(t[0], t[1], t == (1, 8), t < (1, 9), t != (1, 8), t >= (2, 0))
    q, r = divmod(17, 5)
    print(q, r, divmod(-17, 5), divmod(7.5, 2), divmod(-7, -2))
    s, mean, cnt = stats([1.5, 2.5, 3.0])
    print(s, mean, cnt)
    u = swap((7, "x"))
    print(u, str(u))
    print(f"{u} and {t}")
    a, b = 1, 2
    a, b = b, a
    print(a, b)
    one = (5,)
    print(one, len(one))
    (x, y), z = (1, 2), 3
    print(x, y, z)
    p = ("it's", 'say "hi"', 'both \' and "', "tab\there", 2.5, True, -0.0, 1e16)
    print(p)
    k, sep, v = "key=val=x".partition("=")
    print(k, sep, v, "nosep".partition("="), "a.b.c".rpartition("."))
    return 0


main()
'''

LISTS = r'''import heapq


def total(pairs: list[tuple[int, int]]) -> int:
    s = 0
    for a, b in pairs:
        s += a * b
    return s


def main() -> int:
    pairs: list[tuple[int, int]] = []
    for i in range(6):
        pairs.append((i % 3, i))
    print(total(pairs))
    for i, (a, b) in enumerate(pairs):
        print(i, a, b)
    pairs.sort()
    print(pairs[0], pairs[-1], len(pairs))
    ys = sorted(pairs, key=lambda t: (-t[1], t[0]))
    print(ys[0], ys[1][0])
    recs = [("bob", 3, 2.5), ("al", 3, 1.0), ("cy", 1, 9.0)]
    recs.sort(key=lambda r: (r[1], r[0]))
    for name, k, w in recs:
        print(name, k, w)
    names = [name for name, _, _ in recs]
    print(",".join(names))
    best = max(recs)
    print(best, min(recs))
    h: list[tuple[int, str]] = []
    heapq.heappush(h, (5, "e"))
    heapq.heappush(h, (1, "a"))
    heapq.heappush(h, (3, "c"))
    heapq.heappush(h, (1, "A"))
    while h:
        d, s = heapq.heappop(h)
        print(d, s)
    hh = [(3, 1), (2, 2)]
    heapq.heapify(hh)
    print(hh[0])
    pts = [(x, y) for x in range(3) for y in range(2) if x != y]
    print(pts)
    print(len([p for p in pts if p[0] > 0]))
    ssum = sum(a * b for a, b in pts)
    print(ssum)
    print((1, 2) in pts, (5, 5) in pts, (1, 0) not in pts)
    pts.reverse()
    print(pts[0], pts.index((0, 1)), pts.count((2, 0)))
    last = pts.pop()
    print(last)
    xs = [1, 2, 3]
    ys2 = ["a", "b", "c"]
    for x, y in zip(xs, ys2):
        print(x, y)
    for x, p in zip(xs, pts):
        print(x, p)
    for i, x in enumerate(xs):
        print(i, x)
    big = [(1, 2, 3, 4, 5), (1, 2, 3, 4, 0), (0, 9, 9, 9, 9)]
    big.sort()
    print(big)
    print(pts[1:3], pts[::2])
    return 0


main()
'''

GRID = r'''from typing import Dict, List, Set, Tuple

DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]


def bfs(grid: List[str], start: Tuple[int, int], goal: Tuple[int, int]) -> int:
    rows, cols = len(grid), len(grid[0])
    dist: Dict[Tuple[int, int], int] = {start: 0}
    queue: List[Tuple[int, int]] = [start]
    head = 0
    while head < len(queue):
        r, c = queue[head]
        head += 1
        if (r, c) == goal:
            return dist[(r, c)]
        for dr, dc in DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] != "#" and (nr, nc) not in dist:
                dist[(nr, nc)] = dist[(r, c)] + 1
                queue.append((nr, nc))
    return -1


def paths(r: int, c: int, memo: Dict[Tuple[int, int], int]) -> int:
    if r == 0 or c == 0:
        return 1
    if (r, c) in memo:
        return memo[(r, c)]
    v = paths(r - 1, c, memo) + paths(r, c - 1, memo)
    memo[(r, c)] = v
    return v


def islands(grid: List[str]) -> int:
    seen: Set[Tuple[int, int]] = set()
    count = 0
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == "." and (r, c) not in seen:
                count += 1
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    cr, cc = stack.pop()
                    for dr, dc in DIRS:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and grid[nr][nc] == "." \
                                and (nr, nc) not in seen:
                            seen.add((nr, nc))
                            stack.append((nr, nc))
    return count


def main() -> int:
    grid = ["..#....", ".##.##.", "....#..", ".##...#", "......."]
    print(bfs(grid, (0, 0), (4, 6)))
    print(bfs(grid, (0, 0), (0, 3)))
    memo: Dict[Tuple[int, int], int] = {}
    print(paths(8, 8, memo), len(memo))
    print(islands(grid), islands(["..#", "#.#", "..#", "###", "..."]))
    seen = set()
    for r in range(3):
        for c in range(3):
            if (r + c) % 2 == 0:
                seen.add((r, c))
    print(len(seen), (1, 1) in seen, (0, 1) in seen)
    for p in sorted(seen):
        print(p)
    other: Set[Tuple[int, int]] = {(0, 0), (5, 5), (1, 1)}
    print(sorted(seen & other), sorted(seen | other), sorted(seen - other), sorted(seen ^ other))
    print(seen <= (seen | other), other <= seen, (seen & other) == {(0, 0), (1, 1)})
    seen.discard((0, 0))
    seen.discard((9, 9))
    print(len(seen))
    counts = {}
    words = ["a", "b", "a", "c", "b", "a"]
    for i in range(len(words) - 1):
        key = (words[i], words[i + 1])
        counts[key] = counts.get(key, 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(k, v)
    for (a, b), n in counts.items():
        print(a, b, n)
    tot = 0
    for k in counts:
        tot += counts[k]
    print(tot, len(counts), ("a", "b") in counts)
    del counts[("a", "b")]
    print(len(counts), counts.pop(("b", "a"), -1), counts.pop(("zz", "z"), -1))
    best = {}
    best["x"] = (3, 4)
    best["y"] = (1, 2)
    if best["x"] > best["y"]:
        print("x bigger")
    for name in best:
        print(name, best[name])
    return 0


main()
'''

DIJKSTRA = r'''import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Edge:
    src: int
    dst: int
    w: int


class Point:
    def __init__(self, xy: Tuple[int, int], label: str):
        self.xy = xy
        self.label = label

    def moved(self, dx: int, dy: int) -> Tuple[int, int]:
        return self.xy[0] + dx, self.xy[1] + dy


def find(pts: List[Point], label: str) -> Optional[Tuple[int, int]]:
    for p in pts:
        if p.label == label:
            return p.xy
    return None


def split_kv(s: str) -> Tuple[str, str]:
    k, _, v = s.partition("=")
    return k.strip(), v.strip()


def shortest(n: int, edges: List[Edge], src: int) -> List[int]:
    adj: List[List[Tuple[int, int]]] = [[] for _ in range(n)]
    for e in edges:
        adj[e.src].append((e.dst, e.w))
        adj[e.dst].append((e.src, e.w))
    INF = 10 ** 9
    dist = [INF] * n
    dist[src] = 0
    pq: List[Tuple[int, int]] = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def main() -> int:
    pts = [Point((1, 2), "a"), Point((3, 4), "b")]
    print(find(pts, "b"), find(pts, "zz"))
    q = find(pts, "a")
    if q is not None:
        print(q[0] + q[1])
    print(pts[0].moved(5, -5), pts[1].xy)
    print(split_kv("  key = some value  "))
    k, v = split_kv("a=b=c")
    print(k, v)
    edges = [Edge(0, 1, 4), Edge(0, 2, 1), Edge(2, 1, 2), Edge(1, 3, 1), Edge(2, 3, 5)]
    d = shortest(5, edges, 0)
    for i, x in enumerate(d):
        print(i, x if x < 10 ** 9 else -1)
    state = ((1, 2), 3)
    visited: Dict[Tuple[Tuple[int, int], int], str] = {}
    visited[state] = "start"
    visited[((1, 2), 4)] = "other"
    print(len(visited), ((1, 2), 3) in visited, visited[((1, 2), 4)])
    (px, py), dirn = state
    print(px, py, dirn)
    nested = [((1, 2), "x"), ((0, 5), "y")]
    nested.sort()
    print(nested)
    for (a, b), name in nested:
        print(a, b, name)
    best: Dict[str, Tuple[int, str]] = {}
    for word in ["aa", "b", "cc", "aa"]:
        cur = best.get(word)
        if cur is None:
            best[word] = (1, word)
        else:
            best[word] = (cur[0] + 1, word)
    print(sorted(best.items()))
    print(max(best.values()), min(best.values()))
    return 0


main()
'''

LAMBDAS = r'''from functools import reduce
from typing import Callable, List, Tuple


def apply_all(f: Callable[[int], int], xs: List[int]) -> List[int]:
    out: List[int] = []
    for x in xs:
        out.append(f(x))
    return out


def twice(f: Callable[[int], int], x: int) -> int:
    return f(f(x))


def fold(f: Callable[[int, int], int], xs: List[int], init: int) -> int:
    acc = init
    for x in xs:
        acc = f(acc, x)
    return acc


def pass_on(f: Callable[[int], int], xs: List[int]) -> int:
    total = 0
    for y in apply_all(f, xs):
        total += y
    return total


def main() -> int:
    xs = [1, 2, 3, 4]
    k = 10
    double = lambda x: x * 2
    print(double(21))
    print(len(apply_all(lambda x: x + 1, [1, 2])))
    for v in apply_all(lambda x: x * x, xs):
        print(v)
    for v in apply_all(lambda x: x + k, xs):
        print(v)
    print(twice(lambda x: x * 3, 2), twice(lambda x: x - k, 5))
    print(fold(lambda a, b: a * 10 + b, xs, 0))
    add = lambda a, b: a + b + k
    print(add(1, 2), fold(add, xs, 0))
    print(pass_on(lambda x: x + k, xs))
    print(pass_on(double, xs))
    sq = lambda x: x * x
    print(sum(map(sq, xs)), sum(map(lambda x: x * k, xs)))
    evens = [x for x in filter(lambda x: x % 2 == 0, xs)]
    print(evens)
    pairs = [(1, "b"), (3, "a"), (2, "c")]
    key = lambda p: (-p[0], p[1])
    print(sorted(pairs, key=key))
    pairs.sort(key=lambda p: p[1])
    print(pairs)
    lens = sorted(["ccc", "a", "bb"], key=lambda s: len(s))
    print(lens)
    swap = lambda p: (p[1], p[0])
    print(swap((1, "z")))
    print(reduce(lambda a, b: a + b, xs), reduce(lambda a, b: a * b, xs, 1))
    return 0


main()
'''

WORDS = r'''def main() -> int:
    words = "the quick brown fox jumps over the lazy dog the fox".split()
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    items = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    for w, n in items[:3]:
        print(w, n)
    pairs = [(len(w), w) for w in words]
    pairs.sort(reverse=True)
    print(pairs[0], pairs[-1])
    longest = max((len(w), w) for w in words)
    print(longest)
    by_len = {}
    for n, w in pairs:
        by_len[(n, w[0])] = by_len.get((n, w[0]), 0) + 1
    for key in sorted(by_len):
        print(key, by_len[key])
    return 0


main()
'''


class TupleProgramTests(Compared):
    def test_returns_unpack_repr(self):
        self.compare("returns", RETURNS)

    def test_lists_sorting_heap(self):
        self.compare("lists", LISTS)

    def test_grid_sets_dicts(self):
        self.compare("grid", GRID)

    def test_dijkstra_classes_optional(self):
        self.compare("dijkstra", DIJKSTRA)

    def test_lambdas_as_values(self):
        self.compare("lambdas", LAMBDAS)

    def test_word_frequency(self):
        self.compare("words", WORDS)


class UnchangedTests(unittest.TestCase):
    """A program whose tuple uses the compiler already builds is returned byte for byte."""
    def check(self, text):
        notes = []
        self.assertEqual(tuplib.rewrite(text, notes), text)
        self.assertEqual(notes, [])

    def test_swap_and_sort_keys(self):
        self.check("def main() -> int:\n    a = 1\n    b = 2\n    a, b = b, a\n    rows: list[tuple[int, int]] = []\n"
                   "    rows.append((a, b))\n    rows.sort()\n    ys = sorted(rows, key=lambda t: (-t[1], t[0]))\n"
                   "    print(rows[0][0], ys[0][1])\n    return 0\n\n\nmain()\n")

    def test_percent_format_and_enumerate(self):
        self.check("def main() -> int:\n    xs = [5, 6]\n    d = {'a': 1}\n    for i, x in enumerate(xs):\n"
                   "        print('%d:%d' % (i, x))\n    for k, v in d.items():\n        print(k, v)\n    return 0\n\n\nmain()\n")

    def test_no_tuples(self):
        self.check("def main() -> int:\n    print(1)\n    return 0\n\n\nmain()\n")


class RefusalTests(Compared):
    def test_variable_length_tuple(self):
        self.refused("def f(t: tuple[int, ...]) -> int:\n    return len(t)\n\n\ndef main() -> int:\n"
                     "    print(f((1, 2)))\n    return 0\n\n\nmain()\n", "variable-length tuple")

    def test_tuple_concat(self):
        self.refused("def main() -> int:\n    a = (1, 2)\n    b = a + (3,)\n    print(b)\n    return 0\n\n\nmain()\n",
                     "tuple concatenation")

    def test_tuple_variable_index(self):
        self.refused("def main() -> int:\n    a = (1, 2)\n    i = 1\n    print(a[i])\n    return 0\n\n\nmain()\n",
                     "constant")

    def test_float_dict_key(self):
        self.refused("def main() -> int:\n    d = {}\n    d[(1.5, 2)] = 1\n    print(len(d))\n    return 0\n\n\nmain()\n",
                     "float")

    def test_lambda_capture_rebound(self):
        self.refused("from typing import Callable\n\n\ndef ap(f: Callable[[int], int], x: int) -> int:\n    return f(x)\n\n\n"
                     "def main() -> int:\n    k = 1\n    g = lambda x: x + k\n    k = 2\n    print(ap(g, 3))\n"
                     "    return 0\n\n\nmain()\n", "assigned again after the lambda")

    def test_lambda_escapes(self):
        self.refused("def mk(k: int):\n    return lambda x: x + k\n\n\ndef main() -> int:\n    print(mk(1)(2))\n"
                     "    return 0\n\n\nmain()\n", "lambda")

    def test_loop_changes_walked_table(self):
        self.refused("def main() -> int:\n    d = {(0, 0): 1}\n    for k in d:\n        d[(k[0] + 1, 0)] = 2\n"
                     "    print(len(d))\n    return 0\n\n\nmain()\n", "changes the dict / set of tuples it walks")


# ---- generated operation sequences ------------------------------------------------------
DICT_PAIR = '''def main() -> int:
    s = @SEED@
    d: dict[tuple[int, int], int] = {}
    acc = 0
    for it in range(@N@):
        s = (s * 1103515245 + 12345) % 2147483648
        a = (s >> 4) % @KA@
        b = (s >> 11) % @KB@
        op = (s >> 19) % 10
        key = (a, b)
        if op == 0 or op == 1:
            d[key] = it
        elif op == 2:
            d[key] = d.get(key, 0) + 1
        elif op == 3:
            if key in d:
                del d[key]
        elif op == 4:
            acc += d.pop(key, -1)
        elif op == 5:
            acc += d.get(key, -7)
        elif op == 6:
            acc += d.setdefault(key, it)
        elif op == 7:
            if it % 97 == 0:
                cnt = 0
                for k, v in d.items():
                    cnt += k[0] * 31 + k[1] + v
                acc += cnt
        elif op == 8:
            if key in d:
                d[key] += 3
                acc += 1
        else:
            if (b, a) in d:
                acc += d[(b, a)]
        if it % 500 == 0:
            print(it, len(d), acc)
    ks = sorted(d.items())
    print(len(ks), ks[:4], ks[-2:])
    return 0


main()
'''

DICT_STR_TUPLE = '''def main() -> int:
    s = @SEED@
    names = ["al", "bo", "cy", "di", "ed", "fy", "go"]
    d: dict[tuple[str, int], tuple[int, str]] = {}
    last: dict[str, tuple[int, str]] = {}
    acc = 0
    for it in range(@N@):
        s = (s * 1103515245 + 12345) % 2147483648
        nm = names[(s >> 5) % 7]
        n = (s >> 12) % 6
        op = (s >> 20) % 8
        key = (nm, n)
        val = (it % 13, nm)
        if op < 3:
            d[key] = val
            last[nm] = val
        elif op == 3:
            cur = d.get(key)
            if cur is None:
                acc += 1
            else:
                acc += cur[0]
        elif op == 4:
            if key in d:
                del d[key]
        elif op == 5:
            if nm in last:
                acc += last[nm][0]
                if last[nm] > val:
                    acc += 1
        elif op == 6:
            got = d.pop(key, (0, "none"))
            acc += got[0] + len(got[1])
        else:
            if it % 211 == 0:
                for k, v in d.items():
                    acc += k[1] + v[0]
        if it % 500 == 0:
            print(it, len(d), len(last), acc)
    print(sorted(d.items())[:3], sorted(last.items())[:2])
    return 0


main()
'''

SET_TRIPLE = '''def main() -> int:
    s = @SEED@
    a: set[tuple[int, int, int]] = set()
    b: set[tuple[int, int, int]] = set()
    acc = 0
    for it in range(@N@):
        s = (s * 1103515245 + 12345) % 2147483648
        x = (s >> 3) % @K@
        y = (s >> 9) % @K@
        z = (s >> 15) % 3
        op = (s >> 21) % 11
        t = (x, y, z)
        if op < 3:
            a.add(t)
        elif op == 3:
            b.add(t)
        elif op == 4:
            a.discard(t)
        elif op == 5:
            acc += 1 if t in a else 0
            acc += 2 if t in b else 0
        elif op == 6:
            if it % 53 == 0:
                acc += len(a | b) + len(a & b) * 3 + len(a - b) * 5 + len(a ^ b) * 7
        elif op == 7:
            if t in b:
                b.remove(t)
        elif op == 8:
            if it % 101 == 0:
                u = a.union(b)
                acc += len(u)
                a = a & u
        elif op == 9:
            if it % 7 == 0 and len(b) > 0:
                tot = 0
                for e in b:
                    tot += e[0] + e[1] + e[2]
                acc += tot
        else:
            acc += (a <= b) + (b <= a) + (a == b)
        if it % 500 == 0:
            print(it, len(a), len(b), acc)
    print(sorted(a)[:4], sorted(b)[-3:], len(a & b))
    return 0


main()
'''

LIST_TUPLES = '''def main() -> int:
    s = @SEED@
    xs: list[tuple[int, str, float]] = []
    names = ["a", "bb", "c", "dd", "e"]
    acc = 0
    for it in range(@N@):
        s = (s * 1103515245 + 12345) % 2147483648
        op = (s >> 17) % 13
        k = (s >> 3) % 20
        w = names[(s >> 9) % 5]
        f = ((s >> 5) % 16) / 8.0
        t = (k, w, f)
        if op < 4 or len(xs) < 3:
            xs.append(t)
        elif op == 4:
            xs.sort()
        elif op == 5:
            xs.sort(reverse=True)
        elif op == 6:
            acc += len(sorted(xs, key=lambda p: (p[1], -p[0]))) + k
        elif op == 7:
            if t in xs:
                acc += xs.index(t)
            acc += xs.count(t)
        elif op == 8:
            xs.pop()
        elif op == 9:
            m = max(xs)
            mn = min(xs)
            acc += m[0] + mn[0] + (1 if m > mn else 0)
        elif op == 10:
            xs.insert(0, t)
        elif op == 11:
            if len(xs) > 40:
                xs = xs[10:]
        else:
            tot = 0.0
            for a, b, c in xs:
                tot += a + c + len(b)
            acc += int(tot)
        if it % 600 == 0:
            print(it, len(xs), acc, xs[-1])
    print(xs[:3], sorted(xs)[:2])
    return 0


main()
'''

HEAP = '''import heapq


def main() -> int:
    s = @SEED@
    h: list[tuple[int, str]] = []
    g: list[tuple[int, int, int]] = []
    names = ["x", "y", "z", "w"]
    acc = 0
    for it in range(@N@):
        s = (s * 1103515245 + 12345) % 2147483648
        op = (s >> 18) % 9
        k = (s >> 4) % 15
        w = names[(s >> 10) % 4]
        if op < 3:
            heapq.heappush(h, (k, w))
            heapq.heappush(g, (k, it % 5, it))
        elif op == 3 or op == 4:
            if h:
                a, b = heapq.heappop(h)
                acc += a + len(b)
                p, q, r = heapq.heappop(g)
                acc += p * 3 + q + r % 7
        elif op == 5:
            if h:
                a, b = heapq.heappushpop(h, (k, w))
                acc += a
                heapq.heappush(g, (k, 0, it))
        elif op == 6:
            if h:
                old = heapq.heapreplace(h, (k, w))
                acc += old[0] + (1 if old[1] == w else 0)
        elif op == 7:
            if it % 400 == 0:
                heapq.heapify(h)
        else:
            if h:
                acc += h[0][0] + g[0][0]
        if it % 500 == 0:
            print(it, len(h), len(g), acc, h[0] if h else (-1, ""))
    out = []
    while h:
        out.append(heapq.heappop(h))
    print(out[:5], len(out))
    return 0


main()
'''

NESTED_KEYS = '''def main() -> int:
    s = @SEED@
    d: dict[tuple[tuple[int, int], int], int] = {}
    acc = 0
    for it in range(@N@):
        s = (s * 1103515245 + 12345) % 2147483648
        r = (s >> 4) % @K@
        c = (s >> 10) % @K@
        dr = (s >> 16) % 4
        op = (s >> 20) % 6
        key = ((r, c), dr)
        if op < 2:
            d[key] = d.get(key, 0) + it
        elif op == 2:
            if key in d:
                acc += d[key]
        elif op == 3:
            if key in d:
                del d[key]
        elif op == 4:
            acc += len(d) % 7
        else:
            if it % 301 == 0:
                for (p, q), z in sorted(d):
                    acc += p * 5 + q * 3 + z
        if it % 500 == 0:
            print(it, len(d), acc)
    print(sorted(d.items())[:3])
    return 0


main()
'''


def fill(template, **values):
    for key, value in values.items():
        template = template.replace("@" + key + "@", str(value))
    return template


BOOL_TUPLE_FIELDS = r'''def f():
    return False, 3

def main():
    t = (True, 1)
    print(t, t[0])
    print(str(t), f"{t} {t[0]}")
    xs = [(True, 1), (False, 2)]
    print(xs, xs[0][0], xs[1][0])
    for a, b in xs:
        print(a, b)
    d = {1: (True, 5)}
    print(d[1], d[1][0])
    print(t == (True, 1), (True, 1) < (False, 2))
    x = t[0]
    print(x, not x, x and True)
    a, b = f()
    print(a, b, f())
    s = {(True, 1)}
    print(len(s), (True, 1) in s)
    print(sorted(xs), max(xs))

main()
'''

BOOL_TUPLE_SHAPES = r'''def pick(n: int) -> tuple[bool, int]:
    return n % 2 == 0, n


def swap(t: tuple[bool, int]) -> tuple[int, bool]:
    a, b = t
    return b, a


def main() -> int:
    t = (True, 1)
    nest = ((True, 1), False)
    print(t, t[0], nest, nest[0][0], nest[1])
    p, q = nest
    print(p, q, p[0])
    (a, b), c = nest
    print(a, b, c)
    print(f"{nest} {t[0]} {str(t)}")
    d = {}
    d[(True, 3)] = (False, 1)
    d[(False, 3)] = (True, 2)
    for k, v in d.items():
        print(k, v, k[0], v[0])
    for k in d:
        print(k)
    for v in d.values():
        x, y = v
        print(x, y)
    print(d.get((True, 3)), (True, 3) in d)
    s = set()
    s.add((True, 1))
    s.add((False, 1))
    s.add((True, 1))
    print(len(s), sorted(s))
    for e in sorted(s):
        print(e[0], e)
    ys = [pick(i) for i in range(5)]
    print(ys, max(ys), min(ys))
    ys.sort(key=lambda z: (z[0], -z[1]))
    print(ys)
    for i, (ok, n) in enumerate(ys):
        print(i, ok, n)
    for ok, n in zip([True, False, True], [1, 2, 3]):
        print(ok, n)
    print(swap(pick(4)), swap(pick(3))[1])
    r = pick(6)
    print(r == (True, 6), r != pick(6), r < pick(7), r[0] and r[1] > 3)
    if r[0]:
        print("yes")
    w = t[0]
    z = not w
    print(w, z, [w, z])
    m = (1.5, True, "s")
    print(m, m[1])
    h = {(True, 1): 1, (False, 1): 2}
    print(h[(True, 1)] + h[(False, 1)])
    return 0

main()
'''


class BoolInTupleTests(Compared):
    """A bool kept in a tuple is read back as a bool (True / False, not 1 / 0) everywhere: locals, unpacking,
    loop targets, dict values, nested tuples, comparisons.  The tuple field of a bool element is spelled fb<k>:
    the compiler decides whether an unannotated local holds a bool from the field's name, and f<k> is an int in
    other tuple classes."""

    def test_bool_fields_read_back_as_bool(self):
        self.compare("tup_bool_fields", BOOL_TUPLE_FIELDS)

    def test_bool_in_every_tuple_shape(self):
        self.compare("tup_bool_shapes", BOOL_TUPLE_SHAPES)

    def test_bool_field_name_is_distinct(self):
        out = tuplib.rewrite("def main() -> int:\n    a = (True, 1)\n    b = (2, 3)\n    print(a[0], b[0])\n"
                             "    return 0\n\n\nmain()\n", [])
        self.assertIn("fb0: bool", out)
        self.assertIn("f0: int", out)


class GeneratedOperationTests(Compared):
    """Random operation sequences (>= 5000 operations each) over dict / set / list / heap of tuples."""
    def test_dict_pair_int(self):
        rng = random.Random(11)
        self.compare("gdict", fill(DICT_PAIR, SEED=rng.randrange(1, 10 ** 6), N=7000, KA=24, KB=17))

    def test_dict_pair_int_dense(self):
        rng = random.Random(12)
        self.compare("gdict2", fill(DICT_PAIR, SEED=rng.randrange(1, 10 ** 6), N=6000, KA=1000, KB=900))

    def test_dict_str_int_keys_tuple_values(self):
        rng = random.Random(13)
        self.compare("gdictstr", fill(DICT_STR_TUPLE, SEED=rng.randrange(1, 10 ** 6), N=6000))

    def test_set_triples(self):
        rng = random.Random(14)
        self.compare("gset", fill(SET_TRIPLE, SEED=rng.randrange(1, 10 ** 6), N=6000, K=9))

    def test_list_of_tuples(self):
        rng = random.Random(15)
        self.compare("glist", fill(LIST_TUPLES, SEED=rng.randrange(1, 10 ** 6), N=5000))

    def test_heap_of_tuples(self):
        rng = random.Random(16)
        self.compare("gheap", fill(HEAP, SEED=rng.randrange(1, 10 ** 6), N=6000))

    def test_nested_keys(self):
        rng = random.Random(17)
        self.compare("gnested", fill(NESTED_KEYS, SEED=rng.randrange(1, 10 ** 6), N=6000, K=11))


if __name__ == "__main__":
    unittest.main()
