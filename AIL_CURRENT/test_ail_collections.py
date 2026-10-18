"""`from collections import ...`: Counter, defaultdict, OrderedDict and deque, every result compared with CPython.

Every program below is ordinary Python.  CPython runs it as the oracle and the compiled program (the Python
syntax, AIL_NO_GENERAL=1 so the typed path must take it) prints the same bytes, or the spelling is refused by
name -- there is no third outcome where the numbers differ.

Built (python/pkg-v12/collib.py lowers them before the surface pass; see AIL_REFERENCE_MORE.md, Collections):
* Counter[str|int]: Counter(iterable | mapping), c[k] (0 for a missing key, no insert), c[k] += n, del c[k]
  (silent when missing), update(iterable | mapping), most_common([n]) in `for key, count in ...`, comprehensions,
  [i][0|1], len, dict() and print, elements, total, + - & |, print(c) (CPython's repr), key=c.get, plain dict methods.
* defaultdict(int | float | str | lambda: <constant>): d[k] reads insert the default (as CPython), d[k] op= v,
  .get does not insert, iteration in insertion order, dict(d).  defaultdict(list): d[k].append / extend / += /
  index / len / sort / pop, d.get(k, []) read-only, items / values / keys loops.  defaultdict(set): add, discard,
  remove, update, in, len, sorted / sum / min / max / any / all of a row (direct iteration of a set is refused:
  its order is unspecified in CPython).
* OrderedDict: insertion order, move_to_end(k), popitem(last=True | False).
* deque: append, appendleft, pop, popleft, extend, extendleft, rotate, clear, count, index, remove, insert,
  reverse, copy, len, indexing (negative too), item assignment, del, in, iteration, truthiness, maxlen=,
  IndexError / ValueError as CPython; print(q).
* Tuples of int / float / bool / str (not nested) as Counter / defaultdict / OrderedDict keys, deque elements
  and defaultdict(list | set) rows: `deque([(r, c)])` + popleft, `r, c = q.popleft()`, `adj[u].append((v, w))` +
  `for v, w in adj[u]`, Counter of coordinate tuples, `defaultdict(int)` with tuple keys; printing as CPython
  (`deque([(1, 2)])`, `Counter({(0, 1): 2})`, `defaultdict(<class 'int'>, {...})`, `OrderedDict({...})`).
  The pass runs before the tuple lowering (tuplib.py): the helpers are written with `tuple[...]` annotations,
  which the tuple pass then turns into classes and tables.
Refused by name: namedtuple, defaultdict(bool | dict | Counter | lambda: <expression>), float keys, nested
tuples, == on collections, q.maxlen, d.default_factory, deque slices, OrderedDict(items), a collection in a
class field or at module level, most_common as a list of pairs, d[k] = <existing list>, a loop that changes the
collection it walks, Counter.subtract, del d[k] on defaultdict(list) / (set), print of a defaultdict(set) or of
a defaultdict(lambda: ...), ...

Generated tests: random operation sequences (>= 5000 operations per program, an LCG inside the program picks
the operation, the key and the value) for every type, the final state and periodic checkpoints compared.
"""
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


# ---- programs compared with CPython --------------------------------------------------
COUNTER_PROGRAM = r'''from collections import Counter


def tokens(text: str) -> list[str]:
    out = []
    for w in text.lower().split():
        out.append(w.strip(".,;"))
    return out


def main() -> int:
    text = "The quick brown fox. The lazy dog; the end, a fox and a dog and a cat"
    words = tokens(text)
    counts = Counter(words)
    print(len(counts), sum(counts.values()))
    for word, n in counts.most_common(4):
        print(word, n)
    for word, n in counts.most_common():
        print(word + ":" + str(n))
    c2 = Counter("mississippi")
    for ch, n in c2.most_common(3):
        print(ch, n)
    c2["m"] -= 1
    c2["z"] += 5
    del c2["i"]
    del c2["nope"]
    print(c2["m"], c2["i"], c2["q"], len(c2))
    c3 = Counter(["a", "b", "a"])
    c4 = Counter(["a", "c", "c"])
    s = c3 + c4
    d = c3 - c4
    u = c3 | c4
    i = c3 & c4
    for k in s:
        print("s", k, s[k])
    for k in d:
        print("d", k, d[k])
    for k in u:
        print("u", k, u[k])
    for k in i:
        print("i", k, i[k])
    print(c3.total(), len(list(c3.elements())))
    e = []
    for x in c4.elements():
        e.append(x)
    print(",".join(e))
    ints = Counter([3, 1, 3, 2, 1, 3])
    for k, v in ints.most_common(2):
        print(k, v)
    print(ints)
    print(counts.most_common(2))
    return 0


main()
'''
DEFAULTDICT_PROGRAM = r'''from collections import defaultdict, OrderedDict
import sys


def main() -> int:
    groups = defaultdict(list)
    names = ["apple", "avocado", "banana", "blueberry", "cherry", "apricot", "cranberry", "date"]
    for name in names:
        groups[name[0]].append(name)
    for letter in sorted(groups):
        print(letter, len(groups[letter]), ",".join(groups[letter]))
    print(len(groups), "z" in groups, "a" in groups)
    lens = defaultdict(list)
    for i, name in enumerate(names):
        lens[len(name)].append(i)
    for k, v in lens.items():
        print(k, sum(v), v[0])
    for k in lens:
        print(k, len(lens[k]))
    total = defaultdict(float)
    for i in range(10):
        total["even" if i % 2 == 0 else "odd"] += i * 0.5
    print(total["even"], total["odd"], total["none"], len(total))
    z = defaultdict(lambda: -1)
    z["a"] += 1
    print(z["a"], z["b"], len(z))
    s = defaultdict(str)
    s[1] += "x"
    s[1] += "y"
    s[2] += "z"
    print(s[1], s[2], s[3] == "", len(s))
    cnt = defaultdict(int)
    for ch in "hello world":
        cnt[ch] += 1
    mx = 0
    for ch in cnt:
        if cnt[ch] > mx:
            mx = cnt[ch]
    print(mx, len(cnt), cnt["l"], cnt["q"], len(cnt))
    di = dict(cnt)
    print(len(di), di["h"])
    od = OrderedDict()
    for w in ["b", "a", "c"]:
        od[w] = len(w) * 10
    od.move_to_end("b")
    for k in od:
        print(k, od[k])
    od.popitem(last=False)
    k2, v2 = od.popitem()
    print(k2, v2, len(od))
    return 0


main()
'''
DEQUE_PROGRAM = r'''from collections import deque


def bfs(grid: list[str], h: int, w: int) -> int:
    dist = [-1] * (h * w)
    dist[0] = 0
    q = deque()
    q.append(0)
    best = 0
    while q:
        cur = q.popleft()
        r = cur // w
        c = cur % w
        for d in range(4):
            nr = r + (1 if d == 0 else -1 if d == 1 else 0)
            nc = c + (1 if d == 2 else -1 if d == 3 else 0)
            if nr < 0 or nr >= h or nc < 0 or nc >= w:
                continue
            if grid[nr][nc] == "#":
                continue
            nxt = nr * w + nc
            if dist[nxt] >= 0:
                continue
            dist[nxt] = dist[cur] + 1
            if dist[nxt] > best:
                best = dist[nxt]
            q.append(nxt)
    return best


def window_max(a: list[int], k: int) -> int:
    dq = deque()
    total = 0
    for i in range(len(a)):
        while dq and a[dq[-1]] <= a[i]:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:
            dq.popleft()
        if i >= k - 1:
            total += a[dq[0]]
    return total


def main() -> int:
    grid = []
    for r in range(12):
        row = ""
        for c in range(15):
            row += "#" if (r * 7 + c * 3) % 11 == 0 and r + c > 0 else "."
        grid.append(row)
    print(bfs(grid, 12, 15))
    a = [(i * 37 + 11) % 101 for i in range(60)]
    print(window_max(a, 5))
    last = deque(maxlen=4)
    for i in range(10):
        last.append(i * i)
        if len(last) == 4:
            print(sum(last), max(last), min(last))
    dq = deque([1, 2, 3, 4, 5])
    dq.rotate(2)
    print(dq[0], dq[4], dq[-2])
    dq.rotate(-1)
    print(dq[0], len(dq))
    dq.extend([9, 8])
    dq.extendleft([7, 6])
    print(sum(dq), dq.count(9), dq.index(3))
    dq.remove(9)
    dq.insert(1, 100)
    dq.reverse()
    dq.clear()
    print(len(dq), bool(dq))
    try:
        dq.pop()
    except IndexError:
        print("empty pop")
    try:
        dq.popleft()
    except IndexError:
        print("empty popleft")
    d2 = deque(range(5), maxlen=3)
    print(len(d2), d2[0])
    d3 = d2.copy()
    d3.append(50)
    print(d3[2], d2[2])
    return 0


main()
'''
DEFAULTDICT_SET_PROGRAM = r'''from collections import defaultdict


def main() -> int:
    g = defaultdict(set)
    edges = [[1, 2], [2, 3], [1, 3], [3, 4], [1, 2], [4, 1]]
    for e in edges:
        g[e[0]].add(e[1])
        g[e[1]].add(e[0])
    for k in sorted(g):
        print(k, len(g[k]), ",".join([str(x) for x in sorted(g[k])]))
    print(2 in g[1], 9 in g[1], len(g))
    g[1].discard(2)
    g[1].discard(77)
    g[3].remove(4)
    g[3].update([7, 8, 8, 2])
    for k in g:
        print(k, ",".join([str(x) for x in sorted(g[k])]), sum(g[k]), max(g[k]))
    try:
        g[5].remove(1)
    except KeyError:
        print("KeyError")
    names = defaultdict(set)
    for w in "a b a c b d".split():
        names[len(w)].add(w)
    ss = sorted(names[1])
    print(",".join(ss), len(names))
    return 0


main()
'''
SNIPPETS = {}
SNIPPETS['func_params'] = r'''from collections import Counter, defaultdict
from typing import Dict, List


def top(c: Counter[str], n: int) -> int:
    t = 0
    for w, k in c.most_common(n):
        t += k
    return t


def build(words: List[str]) -> Dict[str, List[int]]:
    g = defaultdict(list)
    for i, w in enumerate(words):
        g[w].append(i)
    return g


def total(g: Dict[str, List[int]]) -> int:
    t = 0
    for k in g:
        t += len(g[k])
    return t


def main() -> int:
    words = "a b c a b a".split()
    c = Counter(words)
    print(top(c, 2))
    g = build(words)
    print(total(g), len(g))
    return 0

main()
'''
SNIPPETS['annotated'] = r'''from collections import Counter, defaultdict, deque, OrderedDict
from typing import DefaultDict, Deque, Dict, List


def main() -> int:
    a: Counter[str] = Counter()
    b: DefaultDict[str, int] = defaultdict(int)
    c: Dict[int, List[str]] = defaultdict(list)
    d: Deque[int] = deque()
    e: "OrderedDict[str, float]" = OrderedDict()
    a["x"] += 1
    b["y"] += 2
    c[1].append("p")
    d.append(3)
    e["z"] = 1.5
    print(a["x"], b["y"], len(c[1]), d[0], e["z"])
    return 0

main()
'''
SNIPPETS['stdin_wc'] = r'''import sys
from collections import Counter

def main() -> int:
    c = Counter()
    for line in sys.stdin:
        for w in line.split():
            c[w.lower()] += 1
    for w, n in c.most_common(3):
        print(w, n)
    print(len(c))
    return 0

main()
'''
SNIPPETS['graph_bfs'] = r'''from collections import defaultdict, deque

def main() -> int:
    edges = [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4], [5, 6]]
    graph = defaultdict(list)
    for e in edges:
        graph[e[0]].append(e[1])
        graph[e[1]].append(e[0])
    seen = {0}
    q = deque([0])
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in graph[u]:
            if v not in seen:
                seen.add(v)
                q.append(v)
    print(len(order), order[0], order[-1])
    print(len(graph), 7 in graph, len(graph[9]), len(graph))
    return 0

main()
'''
SNIPPETS['indeg'] = r'''from collections import defaultdict, deque

def main() -> int:
    n = 6
    deps = [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4]]
    adj = defaultdict(list)
    indeg = defaultdict(int)
    for a in range(n):
        indeg[a] += 0
    for d in deps:
        adj[d[0]].append(d[1])
        indeg[d[1]] += 1
    q = deque()
    for k in indeg:
        if indeg[k] == 0:
            q.append(k)
    out = []
    while q:
        u = q.popleft()
        out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    print(len(out), out[0], out[-1])
    return 0

main()
'''
SNIPPETS['anagrams'] = r'''from collections import defaultdict

def main() -> int:
    words = ["eat", "tea", "tan", "ate", "nat", "bat"]
    groups = defaultdict(list)
    for w in words:
        key = w[0:1] + str(len(w))
        groups[key].append(w)
    for k in groups:
        print(k, len(groups[k]), " ".join(groups[k]))
    res = [groups[k] for k in groups]
    print(len(res))
    return 0

main()
'''
SNIPPETS['lru'] = r'''from collections import OrderedDict

def main() -> int:
    cache = OrderedDict()
    cap = 3
    hits = 0
    for i in range(30):
        key = (i * 7) % 5
        if key in cache:
            hits += 1
            cache.move_to_end(key)
        else:
            cache[key] = i
            if len(cache) > cap:
                cache.popitem(last=False)
    print(hits, len(cache))
    for k in cache:
        print(k, cache[k])
    return 0

main()
'''
SNIPPETS['lru_str'] = r'''from collections import OrderedDict

def main() -> int:
    cache = OrderedDict()
    for i in range(20):
        key = "k" + str((i * 3) % 4)
        if key in cache:
            cache.move_to_end(key)
        cache[key] = i
        if len(cache) > 2:
            cache.popitem(last=False)
    for k, v in cache.items():
        print(k, v)
    return 0

main()
'''
SNIPPETS['window'] = r'''from collections import deque

def main() -> int:
    data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    win = deque(maxlen=3)
    out = []
    for x in data:
        win.append(x)
        out.append(sum(win) / len(win))
    for v in out:
        print(round(v, 3))
    q = deque()
    for i in range(5):
        q.appendleft(i)
    while len(q) > 1:
        a = q.pop()
        b = q.pop()
        q.appendleft(a + b)
    print(q[0])
    return 0

main()
'''
SNIPPETS['rotate_str'] = r'''from collections import deque

def main() -> int:
    d = deque("abcdef")
    d.rotate(2)
    print("".join(d))
    d.rotate(-3)
    print("".join(d))
    print(d.count("a"), "c" in d, len(d))
    return 0

main()
'''
SNIPPETS['counter_cmp'] = r'''from collections import Counter

def is_anagram(a: str, b: str) -> bool:
    ca = Counter(a)
    cb = Counter(b)
    for k in ca:
        if cb[k] != ca[k]:
            return False
    return len(ca) == len(cb)


def main() -> int:
    print(is_anagram("listen", "silent"), is_anagram("abc", "abd"))
    return 0

main()
'''
SNIPPETS['sliding_counter'] = r'''from collections import Counter

def main() -> int:
    s = "abcabcbb"
    seen = Counter()
    left = 0
    best = 0
    for right in range(len(s)):
        seen[s[right]] += 1
        while seen[s[right]] > 1:
            seen[s[left]] -= 1
            left += 1
        if right - left + 1 > best:
            best = right - left + 1
    print(best)
    return 0

main()
'''
SNIPPETS['mc_list'] = r'''from collections import Counter

def main() -> int:
    c = Counter("hello world")
    words = [w for w, n in c.most_common(3)]
    print(",".join(words))
    freq = {w: n for w, n in c.most_common(2)}
    print(len(freq), freq["l"])
    return 0

main()
'''
SNIPPETS['counter_sum_bad'] = r'''from collections import Counter

def main() -> int:
    c = Counter([1, 2, 2])
    d = c.copy()
    d[5] += 1
    print(len(c), len(d), sum(c.values()), sum(d.values()))
    c.clear()
    print(len(c))
    return 0

main()
'''
SNIPPETS['items_sorted'] = r'''from collections import Counter

def main() -> int:
    c = Counter("abracadabra")
    for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        print(k, v)
    return 0

main()
'''
SNIPPETS['ddl_ops'] = r'''from collections import defaultdict

def main() -> int:
    g = defaultdict(list)
    for i in range(12):
        g["k" + str(i % 4)].append(i)
    ks = sorted(g)
    print(ks[0], len(ks))
    big = sorted(g, key=lambda k: -len(g[k]))
    print(big[0])
    names = [k for k in g]
    print(",".join(names))
    sizes = [len(v) for v in g.values()]
    print(sum(sizes))
    lst = list(g)
    print(len(lst))
    tot = sum(len(g[k]) for k in g)
    print(tot)
    mx = max(len(g[k]) for k in g)
    print(mx)
    cnt = len([k for k in g if len(g[k]) > 2])
    print(cnt)
    h = defaultdict(list)
    h[5] = [1, 2, 3]
    h[6] += [4]
    print(len(h[5]), h[6][0])
    return 0

main()
'''
SNIPPETS['counter_equal'] = r'''from collections import Counter


def same(a: str, b: str) -> bool:
    return Counter(a) == Counter(b)


def main() -> int:
    print(same("listen", "silent"), same("ab", "abb"), Counter("aab") != Counter("aba"))
    c = Counter("abc")
    d = Counter("cab")
    if c == d:
        print("eq")
    d["z"] += 0
    print(c == d, c != d)
    return 0


main()
'''
SNIPPETS['nums_counter'] = r'''import sys
from collections import Counter


def main() -> int:
    nums = [int(x) for x in sys.stdin.read().split()]
    c = Counter(nums)
    for n, k in c.most_common(2):
        print(n, k)
    dup = [n for n in c if c[n] > 1]
    print(len(dup), max(c.values()), sum(c.values()))
    return 0

main()
'''
SNIPPETS['window_counter'] = r'''from collections import Counter


def longest(s: str, k: int) -> int:
    cnt = Counter()
    left = 0
    best = 0
    for right in range(len(s)):
        cnt[s[right]] += 1
        while len(cnt) > k:
            cnt[s[left]] -= 1
            if cnt[s[left]] == 0:
                del cnt[s[left]]
            left += 1
        best = max(best, right - left + 1)
    return best


def main() -> int:
    print(longest("eceba", 2), longest("aabbcc", 1), longest("abcabcabc", 3))
    return 0

main()
'''
SNIPPETS['kth'] = r'''from collections import Counter


def top_k(nums: list[int], k: int) -> list[int]:
    return [n for n, _ in Counter(nums).most_common(k)]


def main() -> int:
    res = top_k([1, 1, 1, 2, 2, 3, 3, 3, 3], 2)
    print(res[0], res[1], len(res))
    return 0

main()
'''
SNIPPETS['queue_sim'] = r'''from collections import deque


def josephus(n: int, k: int) -> int:
    q = deque(range(1, n + 1))
    while len(q) > 1:
        q.rotate(-(k - 1))
        q.popleft()
    return q[0]


def main() -> int:
    print(josephus(7, 3), josephus(10, 2), josephus(41, 3))
    buf = deque(maxlen=5)
    total = 0
    for i in range(20):
        buf.append(i * i)
        total += buf[0]
    print(total, len(buf), buf[-1])
    stack = deque()
    for ch in "(()[]{})":
        if ch in "([{":
            stack.append(ch)
        else:
            stack.pop()
    print(len(stack) == 0)
    return 0

main()
'''
SNIPPETS['graph_funcs'] = r'''from collections import defaultdict, deque


def build(n: int) -> defaultdict[int, list[int]]:
    g = defaultdict(list)
    for i in range(n):
        g[i].append((i + 1) % n)
        g[i].append((i * 2) % n)
    return g


def bfs(g: defaultdict[int, list[int]], s: int, n: int) -> int:
    seen = [False] * n
    seen[s] = True
    q = deque([s])
    cnt = 0
    while q:
        u = q.popleft()
        cnt += 1
        for v in g[u]:
            if not seen[v]:
                seen[v] = True
                q.append(v)
    return cnt


def main() -> int:
    g = build(12)
    print(bfs(g, 0, 12), len(g))
    h = build(5)
    h[9].append(1)
    print(len(h), len(h[9]))
    return 0

main()
'''
SNIPPETS['od_cache'] = r'''from collections import OrderedDict


def run(cap: int) -> int:
    cache = OrderedDict()
    miss = 0
    for i in range(60):
        k = (i * i + 3) % 11
        if k in cache:
            cache.move_to_end(k)
        else:
            miss += 1
            cache[k] = i
            if len(cache) > cap:
                cache.popitem(last=False)
    return miss


def main() -> int:
    print(run(3), run(5), run(11))
    return 0

main()
'''
SNIPPETS['ctor_inline'] = r'''from collections import Counter


def main() -> int:
    s = "abracadabra"
    print(max(Counter(s).values()), len(Counter(s)), sum(Counter(s).values()))
    k = sorted(Counter(s))
    print(len(k), k[0])
    ok = all(v == 1 for v in Counter("abc").values())
    print(ok, Counter(s)["a"], "z" in Counter(s))
    d = dict(Counter(s))
    print(len(d), d["a"])
    return 0

main()
'''

STDIN = b"the cat The dog\nthe end a cat\n"
STDINS = {"nums_counter": b"5 3 5 1 3 5 9 1\n"}

# ---- refused spellings ------------------------------------------------------------
REFUSALS = {}
REFUSALS['namedtuple'] = (r'''from collections import namedtuple


P = namedtuple("P", "x y")

def main() -> int:
    p = P(1, 2)
    print(p.x)
    return 0

main()
''', 'namedtuple')
REFUSALS['dd_set_iteration'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(set)
    d["a"].add(1)
    for x in d["a"]:
        print(x)
    return 0

main()
''', 'order of a set is unspecified')
REFUSALS['dd_set_items'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(set)
    d["a"].add(1)
    for k, v in d.items():
        print(k, len(v))
    return 0

main()
''', 'defaultdict(set)')
REFUSALS['dd_bool'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(bool)
    print(d["a"])
    return 0

main()
''', 'defaultdict(bool)')
REFUSALS['dd_counter'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(Counter)
    return 0

main()
''', 'defaultdict(Counter)')
REFUSALS['dd_lambda_list'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    n = 3
    d = defaultdict(lambda: [0] * n)
    return 0

main()
''', 'lambda')
REFUSALS['ctr_eq'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    a = Counter("ab")
    b = Counter("ba")
    print(a <= b)
    return 0

main()
''', 'comparing collections')
REFUSALS['deque_maxlen_attr'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    q = deque(maxlen=3)
    q.append(1)
    print(q.maxlen)
    return 0

main()
''', 'maxlen')
REFUSALS['deque_slice'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    q = deque([1, 2, 3])
    print(q[1:2])
    return 0

main()
''', 'slicing')
REFUSALS['od_items_ctor'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    o = OrderedDict([("a", 1)])
    return 0

main()
''', 'OrderedDict(...)')
REFUSALS['class_field'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


class Box:
    def __init__(self):
        self.q = deque()

def main() -> int:
    b = Box()
    return 0

main()
''', 'attribute')
REFUSALS['module_level'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


Q = deque()

def main() -> int:
    return 0

main()
''', 'module level')
REFUSALS['mc_pairs'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    c = Counter("abc")
    top = c.most_common(2)
    return 0

main()
''', 'list of pairs')
REFUSALS['ddl_alias_store'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(list)
    xs = [1, 2]
    d["a"] = xs
    xs.append(3)
    print(len(d["a"]))
    return 0

main()
''', 'same list object')
REFUSALS['loop_mutation'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(int)
    d[1] += 1
    for k in d:
        d[k + 1] += 1
    return 0

main()
''', 'RuntimeError')
REFUSALS['ctr_subtract'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    c = Counter("abc")
    c.subtract("a")
    return 0

main()
''', 'subtract')
REFUSALS['chainmap'] = (r'''from collections import ChainMap


def main() -> int:
    return 0

main()
''', 'ChainMap')
REFUSALS['ddl_del'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(list)
    d[1].append(2)
    del d[1]
    return 0

main()
''', 'del d[k]')
REFUSALS['ddl_get_mutate'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(list)
    d[2].append(1)
    d.get(1, []).append(3)
    return 0

main()
''', 'returns a copy')
REFUSALS['deque_iter_mutation'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    q = deque([1, 2])
    for x in q:
        q.append(x)
    return 0

main()
''', 'RuntimeError')
REFUSALS['dd_param_read'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def peek(d: defaultdict[str, int], k: str) -> int:
    return d[k]

def main() -> int:
    d = defaultdict(int)
    print(peek(d, "a"))
    return 0

main()
''', 'parameter')
REFUSALS['ctr_float_keys'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    c = Counter([1.5, 2.5, 1.5])
    return 0

main()
''', 'keys must be')
REFUSALS['default_factory'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    d = defaultdict(int)
    d["a"] += 1
    print(d.default_factory)
    return 0

main()
''', 'default_factory')
REFUSALS['ctr_in_fstring'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    c = Counter("ab")
    print(f"{c}")
    return 0

main()
''', 'plain value')
REFUSALS['dq_in_class_param'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def f(q: deque) -> int:
    return 0

def main() -> int:
    return f(deque([1]))

main()
''', 'cannot be told')
REFUSALS['ctr_alias'] = (r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    c = Counter("ab")
    d = c
    d["z"] += 1
    print(c["z"])
    return 0

main()
''', 'shares')

# ---- tuples in collections: typical programs ------------------------------------------
TUPLE_SNIPPETS = {}
TUPLE_SNIPPETS['grid_bfs'] = r'''from collections import deque

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def make(h: int, w: int, seed: int) -> list[str]:
    grid = []
    s = seed
    for i in range(h):
        row = ""
        for j in range(w):
            s = (s * 1103515245 + 12345) % 2147483648
            if (s // 7) % 4 == 0 and (i, j) != (0, 0):
                row += "#"
            else:
                row += "."
        grid.append(row)
    return grid


def bfs(grid: list[str], h: int, w: int) -> int:
    start = (0, 0)
    q = deque([start])
    visited = {start}
    dist = [[-1] * w for _ in range(h)]
    dist[0][0] = 0
    far = 0
    reached = 0
    while q:
        r, c = q.popleft()
        reached += 1
        for dr, dc in DIRS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and grid[nr][nc] != "#" and (nr, nc) not in visited:
                visited.add((nr, nc))
                dist[nr][nc] = dist[r][c] + 1
                if dist[nr][nc] > far:
                    far = dist[nr][nc]
                q.append((nr, nc))
    print(reached, len(visited), far)
    return far


def main() -> int:
    for seed in range(1, 6):
        g = make(30, 40, seed)
        print(seed, bfs(g, 30, 40))
    q = deque([(1, 2), (3, 4)])
    q.appendleft((0, 0))
    print(q, len(q), q[1], (3, 4) in q)
    return 0


main()
'''
TUPLE_SNIPPETS['dijkstra'] = r'''import heapq
from collections import defaultdict


def dijkstra(adj: defaultdict[int, list[tuple[int, int]]], n: int, src: int) -> list[int]:
    INF = 10 ** 9
    dist = [INF] * n
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u in adj:
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
    return dist


def main() -> int:
    n = 400
    adj = defaultdict(list)
    s = 99
    for i in range(3000):
        s = (s * 1103515245 + 12345) % 2147483648
        u = s % n
        s = (s * 1103515245 + 12345) % 2147483648
        v = s % n
        s = (s * 1103515245 + 12345) % 2147483648
        w = 1 + s % 50
        adj[u].append((v, w))
        adj[v].append((u, w))
    dist = dijkstra(adj, n, 0)
    reach = 0
    total = 0
    for x in dist:
        if x < 10 ** 9:
            reach += 1
            total += x
    print(reach, total, dist[1], dist[n - 1])
    print(len(adj), len(adj[5]), adj[5][0])
    return 0


main()
'''
TUPLE_SNIPPETS['coord_counter'] = r'''from collections import Counter


def cells(n: int) -> Counter[tuple[int, int]]:
    c: Counter[tuple[int, int]] = Counter()
    s = 7
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        x = s % 100
        s = (s * 1103515245 + 12345) % 2147483648
        y = s % 100
        c[(x // 25, y // 25)] += 1
    return c


def main() -> int:
    c = cells(500)
    print(len(c), c.total())
    for pos, n in c.most_common(3):
        print(pos, n)
    print(c.most_common(2))
    print(c[(0, 0)], c[(9, 9)], (1, 1) in c)
    d = Counter([(0, 0), (1, 1), (1, 1)])
    print(d)
    e = c + d
    print(e.most_common(1))
    c.update([(0, 0), (0, 0)])
    print(c[(0, 0)])
    words = Counter(zip([1, 2, 1, 2, 3], "ababc"))
    print(words)
    return 0


main()
'''
TUPLE_SNIPPETS['tuple_keys_int'] = r'''from collections import defaultdict


def main() -> int:
    hits = defaultdict(int)
    s = 5
    for i in range(800):
        s = (s * 1103515245 + 12345) % 2147483648
        hits[(s % 7, (s // 7) % 5)] += 1
    print(len(hits), hits[(0, 0)], hits[(8, 8)], len(hits))
    best = (0, 0)
    top = 0
    for k in hits:
        if hits[k] > top:
            best = k
            top = hits[k]
    print(best, top)
    n = 0
    for k, v in sorted(hits.items()):
        if n < 5:
            print(k, v)
        n += 1
    seen = defaultdict(float)
    seen[("a", 1)] += 0.5
    seen[("b", 2)] += 1.5
    seen[("a", 1)] += 2.0
    for k2 in seen:
        print(k2, seen[k2])
    return 0


main()
'''
TUPLE_SNIPPETS['bfs_node_dist'] = r'''from collections import defaultdict, deque


def main() -> int:
    n = 300
    g = defaultdict(list)
    s = 3
    for i in range(700):
        s = (s * 1103515245 + 12345) % 2147483648
        u = s % n
        s = (s * 1103515245 + 12345) % 2147483648
        v = s % n
        g[u].append(v)
        g[v].append(u)
    q = deque([(0, 0)])
    seen = {0}
    far = (0, 0)
    order = []
    while q:
        node, d = q.popleft()
        order.append(node)
        if d >= far[1]:
            far = (node, d)
        for nxt in g[node]:
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, d + 1))
    print(len(order), far, order[0], order[7])
    levels = defaultdict(list)
    kids = defaultdict(list)
    links = [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (4, 5)]
    for p, ch in links:
        kids[p].append(ch)
    q2 = deque([(0, 0)])
    done = {0}
    while q2:
        name, depth = q2.popleft()
        levels[depth].append((name, len(kids[name])))
        for child in kids[name]:
            if child not in done:
                done.add(child)
                q2.append((child, depth + 1))
    for depth in levels:
        print(depth, levels[depth])
    return 0


main()
'''
TUPLE_SNIPPETS['reprs'] = r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    q = deque([(1, 2), (3, 4)], maxlen=3)
    print(q)
    q.append((5, 6))
    q.append((7, 8))
    print(q)
    q3 = deque([("a", 1)])
    q4 = deque([(1.5, 2)])
    print(q3, q4)
    c = Counter([(0, 1), (0, 1), (2, 3)])
    print(c)
    e: Counter[tuple[int, int]] = Counter()
    print(e)
    print(c.most_common())
    dd = defaultdict(int)
    dd[(1, 2)] += 3
    dd[(4, 2)] = 5
    print(dd)
    dl = defaultdict(list)
    dl[(1, 2)].append((3, 4))
    dl[(1, 2)].append((5, 6))
    dl[(0, 0)].append((7, 8))
    print(dl)
    od = OrderedDict()
    od[(1, 2)] = 3
    od[(4, 5)] = 6
    od.move_to_end((1, 2))
    print(od)
    ds = defaultdict(str)
    ds[(1, 1)] += "ab"
    print(ds)
    df = defaultdict(float)
    df[3] += 1.5
    print(df)
    return 0


main()
'''
TUPLE_SNIPPETS['sets_and_orders'] = r'''from collections import defaultdict, OrderedDict, deque


def main() -> int:
    groups = defaultdict(set)
    named = defaultdict(set)
    for i in range(40):
        groups[i % 3].add((i % 5, i % 2))
        named[(i % 2, "k")].add((i % 4, "v" + str(i % 3)))
    for k in groups:
        print(k, len(groups[k]), sorted(groups[k]))
    for k2 in named:
        print(k2, len(named[k2]), sorted(named[k2]))
    print((0, 0) in groups[0], (9, 9) in groups[0])
    lru = OrderedDict()
    miss = 0
    for i in range(80):
        key = ((i * 7) % 6, (i * 3) % 4)
        if key in lru:
            lru.move_to_end(key)
        else:
            miss += 1
            lru[key] = i
            if len(lru) > 5:
                ek, ev = lru.popitem(last=False)
                print("evict", ek, ev)
    print(miss, list(lru.items()))
    w = deque(maxlen=3)
    for i in range(10):
        w.append((i, i * i))
    print(list(w), sum(a * b for a, b in w))
    return 0


main()
'''

TUPLE_SNIPPETS['bool_in_tuple'] = r'''from collections import Counter, defaultdict, deque, OrderedDict


def main() -> int:
    q = deque([(1, True)])
    q.append((2, False))
    q.appendleft((0, True))
    print(q, len(q))
    while q:
        n, f = q.popleft()
        print(n, f, not f)
    c = Counter()
    c[(True, 1)] += 2
    c[(False, 1)] += 1
    c[(True, 1)] += 1
    print(c)
    for k, v in c.most_common():
        print(k, v, k[0])
    d = defaultdict(int)
    d[(1, True)] += 3
    d[(2, False)] += 1
    print(d, d[(1, True)])
    r = defaultdict(list)
    r[1].append((True, 5))
    r[1].append((False, 6))
    for ok, w in r[1]:
        print(ok, w)
    od = OrderedDict()
    od[(False, 2)] = 7
    od[(True, 2)] = 8
    print(od)
    seen = set()
    seen.add((True, True))
    print((True, True) in seen, (True, False) in seen)
    flags = deque()
    flags.append((True, 1.5))
    f0, g0 = flags[0]
    print(f0, g0, flags)
    return 0

main()
'''

TUPLE_SNIPPETS['str_rows_ascii_flag'] = r'''from collections import deque

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def rows(n: int, wide: bool) -> list[str]:
    s = 99
    grid = []
    for r in range(n):
        row = []
        for c in range(n):
            s = (s * 1103515245 + 12345) % 2147483648
            if wide and s % 17 == 0:
                row.append("é")
            elif wide and s % 29 == 0:
                row.append("ツ")
            else:
                row.append("#" if s % 100 < 26 and r + c > 0 else ".")
        grid.append("".join(row))
    return grid


def bfs(grid: list[str], n: int) -> tuple[int, int, int]:
    q = deque()
    q.append((0, 0))
    seen = set()
    seen.add((0, 0))
    far = 0
    odd = 0
    while q:
        r, c = q.popleft()
        far = max(far, r + c)
        if grid[r][c] != ".":
            odd += 1
        for dr, dc in DIRS:
            nr, nc = r + dr, c + dc
            if nr < 0 or nc < 0 or nr >= n or nc >= n:
                continue
            if grid[nr][nc] == "#" or (nr, nc) in seen:
                continue
            seen.add((nr, nc))
            q.append((nr, nc))
    return len(seen), far, odd


def take(names: list[str]) -> list[str]:
    out = []
    for x in names:
        out.append(x)
    return out


def main() -> int:
    g = rows(60, False)
    a, b, c = bfs(g, 60)
    print(a, b, c, len(g[3]), g[3][5], g[59][-1], g[7][2:9])
    g = rows(60, True)
    a, b, c = bfs(g, 60)
    print(a, b, c, len(g[3]), g[3][5], g[59][-1], g[7][2:9])
    mixed = take(["abc", "déf", "", "ツx", "plain"])
    for w in mixed:
        print(len(w))
    print(len(mixed), mixed[1][1], mixed[3][0], mixed[4][2], mixed[1][-1])
    popped = mixed.pop(1)
    print(popped, len(popped), popped[1], mixed)
    names: dict[str, int] = {}
    names["k1"] = 1
    names["ké"] = 2
    names["k3"] = 3
    keys = list(names.keys())
    print(keys[1], len(keys[1]), keys[1][1])
    lone: set[str] = set()
    lone.add("ツツ")
    only = lone.pop()
    print(only, len(only), only[1])
    return 0


main()
'''

TUPLE_REFUSALS = {}
TUPLE_REFUSALS['nested_tuple'] = (r'''from collections import Counter


def main() -> int:
    c = Counter([((1, 2), 3), ((1, 2), 3)])
    print(len(c))
    return 0

main()
''', 'tuple')
TUPLE_REFUSALS['set_row_print'] = (r'''from collections import defaultdict


def main() -> int:
    d = defaultdict(set)
    d[1].add((1, 2))
    print(d)
    return 0

main()
''', 'defaultdict(set)')
TUPLE_REFUSALS['lambda_factory_print'] = (r'''from collections import defaultdict


def main() -> int:
    d = defaultdict(lambda: 5)
    d[(1, 2)] += 1
    print(d)
    return 0

main()
''', 'print() of this defaultdict')


# ---- generators ------------------------------------------------------------------
HEAD = '''from collections import Counter, defaultdict, deque, OrderedDict


def nxt(s: int) -> int:
    return (s * 1103515245 + 12345) % 2147483648
'''


def build(rng, init, ops, final, steps, every=400, extra_defs=""):
    """One program: `init` lines, a loop of `steps` iterations choosing one of `ops` by the LCG, a checkpoint
    line every `every` steps and the `final` dump.  Each op is a block of lines (relative indentation)."""
    lines = [HEAD.rstrip("\n"), "", ""]
    if extra_defs:
        lines += [extra_defs.rstrip("\n"), "", ""]
    lines += ["def main() -> int:"]
    lines += ["    " + l for l in init]
    lines += ["    s = %d" % rng.randrange(1, 2 ** 30), "    acc = 0", "    errs = 0",
              "    for step in range(%d):" % steps,
              "        s = nxt(s)",
              "        op = (s // 7) %% %d" % len(ops),
              "        s = nxt(s)",
              "        a = (s // 3) % KEYS",
              "        s = nxt(s)",
              "        b = (s // 5) % 11 - 3"]
    for i, block in enumerate(ops):
        lines.append("        %s op == %d:" % ("if" if i == 0 else "elif", i))
        for l in block.split("\n"):
            lines.append("            " + l)
    lines.append("        if step %% %d == 0:" % every)
    lines.append("            print(step, acc, errs, STATE)")
    lines += ["    print(acc, errs)"]
    lines += ["    " + l for l in final]
    lines += ["    return 0", "", "", "main()", ""]
    return "\n".join(lines)


def subst(text, **kw):
    for k, v in kw.items():
        text = re.sub(r"\b%s\b" % k, lambda m: v, text)
    return text


def weighted(rng, table, count):
    """`count` op blocks drawn (with repeats allowed, every block at least once if possible)."""
    pool = []
    for block, w in table:
        pool += [block] * w
    out = [b for b, _ in table]
    while len(out) < count:
        out.append(pool[rng.randrange(len(pool))])
    rng.shuffle(out)
    return out


ELEMS = {"int": ("a", "(%s)", "[1, 2, 3, 4]"),
         "str": ('"v" + str(a)', "len(%s)", '["a", "b", "c"]'),
         "tup": ("(a, b)", "(%s[0] * 3 + %s[1])", "[(1, 2), (3, 4)]"),
         "tups": ('(a, "v" + str(b + 3))', "(%s[0] * 3 + len(%s[1]))", '[(1, "a"), (2, "b")]')}


def hexpr(h, name):
    return h.replace("%s", name)


def deque_program(rng, elem="int", steps=6000):
    maxlen = rng.choice([None, None, 0, 1, 3, 8, 25])
    keys = rng.choice([5, 12, 40])
    mk = "q = deque(maxlen=%s)" % maxlen if maxlen is not None else "q = deque()"
    if rng.random() < 0.3:
        init = ELEMS[elem][2]
        mk = "q = deque(%s%s)" % (init, ", maxlen=%d" % maxlen if maxlen is not None else "")
    x, h = ELEMS[elem][0], ELEMS[elem][1]
    table = [
        ("q.append(X)", 4), ("q.appendleft(X)", 4), ("q.extend([X, X])", 1), ("q.extendleft([X, X])", 1),
        ("q.rotate(b)", 2), ("q.rotate()", 1),
        ("if len(q) > 0:\n    y = q.pop()\n    acc += H(y)", 3),
        ("if len(q) > 0:\n    y = q.popleft()\n    acc += H(y) * 2", 3),
        ("if q:\n    i = s % len(q)\n    y = q[i]\n    acc += H(y) * (i + 1)", 2),
        ("if q:\n    i = s % len(q) - len(q)\n    q[i] = X", 2),
        ("if len(q) > 1:\n    del q[s % len(q)]", 1),
        ("if X in q:\n    acc += 1", 2),
        ("acc += q.count(X)", 1),
        ("if X in q:\n    acc += q.index(X)", 1),
        ("if X in q:\n    q.remove(X)", 1),
        ("if len(q) < 30:\n    try:\n        q.insert(s % 5, X)\n    except IndexError:\n        errs += 1", 1),
        ("q.reverse()", 1),
        ("if s % 17 == 0:\n    q.clear()", 1),
        ("c = q.copy()\nc.append(X)\nacc += len(c)", 1),
        ("try:\n    q.popleft()\nexcept IndexError:\n    errs += 1", 1),
        ("try:\n    y = q[s % 70]\n    acc += H(y)\nexcept IndexError:\n    errs += 1", 1),
        ("if not q:\n    acc += 7", 1),
        ("if len(q) == 0:\n    acc += 3\nelse:\n    acc += len(q)", 1),
    ]
    ops = [subst(b, X=x).replace("H(y)", hexpr(h, "y")) for b in weighted(rng, table, 26)]
    final = ["for z in q:", "    print(z)", "print(len(q))", "print(q)"]
    return subst(build(rng, [mk], ops, final, steps), KEYS=str(keys), STATE="len(q)")


KEYS_OF = {"str": ('"w" + str(a)', '"w" + str(b + 3)', "len(w)"),
           "int": ("a - 3", "b", "w"),
           "tup": ("(a - 3, a % 3)", "(b, b % 2)", "w[0] * 3 + w[1]"),
           "tups": ('(a - 3, "w" + str(a % 4))', '(b, "w" + str(b + 3))', "w[0] + len(w[1])")}


def counter_program(rng, keytype="str", steps=6000):
    keys = rng.choice([4, 9, 30])
    k, kb, wexpr = KEYS_OF[keytype]
    table = [
        ("c[K] += b", 4), ("c[K] += 1", 5), ("c[K] = b + 2", 1), ("acc += c[K]", 3),
        ("acc += c.get(K, 100)", 1), ("if K in c:\n    acc += 1", 1),
        ("del c[K]", 2), ("x = c.pop(K, 0)\nacc += x", 1),
        ("c.update([K, KB, K])", 2), ("c.update(d)", 1), ("d[K] += 1", 2),
        ("d[KB] += 2", 1),
        ("for w, n in c.most_common(1 + a % 5):\n    acc += n * WEXPR", 3),
        ("for w, n in c.most_common():\n    acc = (acc * 3 + n) % 1000003", 1),
        ("acc += len(c) + sum(c.values())", 1),
        ("e = c + d\nfor w in e:\n    acc += e[w]", 1),
        ("e = c - d\nfor w in e:\n    acc += e[w] * 2", 1),
        ("e = c & d\nfor w in e:\n    acc += e[w] * 3", 1),
        ("e = c | d\nfor w in e:\n    acc += e[w] * 5", 1),
        ("for w in c.elements():\n    acc += 1\n    if acc % 5 == 3:\n        break", 1),
        ("if s % 29 == 0:\n    c = c + d", 1),
        ("if s % 31 == 0:\n    d = Counter()", 1),
        ("acc += c.total()", 1),
    ]
    ops = [subst(b, K=k, KB=kb, WEXPR=wexpr) for b in weighted(rng, table, 28)]
    init = ["c = Counter()", "d = Counter()"]
    final = ["for w, n in c.items():", "    print(w, n)", "print(c.most_common(3))", "print(c)"]
    return subst(build(rng, init, ops, final, steps), KEYS=str(keys), STATE="len(c)")


def dd_program(rng, kind="int", keytype="str", steps=6000):
    keys = rng.choice([4, 9, 30])
    k, kb, _ = KEYS_OF[keytype]
    if kind == "int":
        mk, v, zero = "defaultdict(int)", "b", "0"
    elif kind == "float":
        mk, v, zero = "defaultdict(float)", "b * 0.5", "0.0"
    elif kind == "str":
        mk, v, zero = "defaultdict(str)", '"s" + str(b)', '""'
    else:
        mk, v, zero = "defaultdict(lambda: -7)", "b", "-7"
    h = "len(Y)" if kind == "str" else "Y"
    table = [
        ("d[K] += V" if kind != "str" else "d[K] += V", 5),
        ("d[K] = V", 2),
        ("y = d[K]\nacc += H", 4),
        ("y = d.get(K, V)\nacc += H2", 2),
        ("if K in d:\n    acc += 1", 2),
        ("del d[K]" if False else "if K in d:\n    del d[K]", 2),
        ("y = d.pop(K, V)\nacc += H2", 1),
        ("y = d.setdefault(K, V)\nacc += H2", 1),
        ("acc += len(d)", 1),
        ("for k2 in d:\n    y = d[k2]\n    acc = (acc * 3 + HK2) % 1000003", 1),
        ("for k2, y in d.items():\n    acc = (acc * 5 + H3) % 1000003", 2),
        ("if s % 41 == 0:\n    d.clear()", 1),
        ("e = d.copy()\ne[K] = V\nacc += len(e)", 1),
        ("e = dict(d)\nacc += len(e)", 1),
    ]
    ops = [b for b in weighted(rng, table, 22)]
    h1 = h.replace("Y", "y")
    def fix(b):
        b = b.replace("HK2", "len(y)" if kind == "str" else "y").replace("H3", "len(y)" if kind == "str" else "y")
        b = b.replace("H2", "len(y)" if kind == "str" else "int(y * 2.0)" if kind == "float" else "y")
        b = b.replace("acc += H", "acc += " + ("len(y)" if kind == "str" else "int(y * 2.0)" if kind == "float" else "y"))
        return subst(b, K=k, KB=kb, V=v)
    ops = [fix(b) for b in ops]
    if kind == "float":
        ops = [o.replace("(acc * 3 + y)", "(acc * 3 + int(y * 2.0))").replace("(acc * 5 + y)", "(acc * 5 + int(y * 2.0))") for o in ops]
    init = ["d = %s" % mk]
    final = ["for k2 in d:", "    print(k2, d[k2])", "print(len(d))"]
    if kind != "lambda":
        final.append("print(d)")
    return subst(build(rng, init, ops, final, steps), KEYS=str(keys), STATE="len(d)")


DKEYS = {"int": "a", "str": '"k" + str(a)', "tup": "(a, a % 2)", "tups": '(a % 5, "k" + str(a % 3))'}
DELEMS = {"int": ("b", "(Y)"), "str": ('"e" + str(b + 3)', "len(Y)"), "tup": ("(b, b % 3)", "(Y[0] * 3 + Y[1])"),
          "tups": ('(b, "e" + str(b + 3))', "(Y[0] * 3 + len(Y[1]))")}


def ddl_program(rng, keytype="int", elem="int", steps=6000):
    keys = rng.choice([4, 9, 30])
    k = DKEYS[keytype]
    x, h = DELEMS[elem]
    table = [
        ("d[K].append(X)", 6),
        ("d[K].extend([X, X])", 1),
        ("d[K] += [X]", 1),
        ("acc += len(d[K])", 3),
        ("if len(d[K]) > 0:\n    y = d[K][0]\n    acc += H0", 2),
        ("if len(d[K]) > 1:\n    y = d[K].pop()\n    acc += H0", 2),
        ("if K in d:\n    acc += 3", 2),
        ("for y in d.get(K, []):\n    acc += H0", 2),
        ("acc += len(d)", 1),
        ("for k2 in d:\n    acc = (acc * 3 + len(d[k2])) % 1000003", 2),
        ("for k2, row in d.items():\n    acc = (acc * 5 + len(row)) % 1000003", 2),
        ("for row in d.values():\n    acc += len(row)", 1),
        ("d[K].sort()", 1),
        ("d[K] = [X, X, X]", 1),
        ("if s % 53 == 0:\n    d.clear()", 1),
        ("d.setdefault(K, []).append(X)", 1),
    ]
    ops = [subst(b, K=k, X=x).replace("H0", h.replace("Y", "y")) for b in weighted(rng, table, 22)]
    init = ["d = defaultdict(list)"]
    final = ["for k2 in d:", "    print(k2, len(d[k2]))", "    for y in d[k2]:", "        print(y)", "print(len(d))",
             "print(d)"]
    return subst(build(rng, init, ops, final, steps), KEYS=str(keys), STATE="len(d)")


def od_program(rng, keytype="str", steps=6000):
    keys = rng.choice([4, 9, 30])
    table = [
        ("od[K] = b", 5), ("od[K] += b" if False else "if K in od:\n    od[K] += b", 2),
        ("if K in od:\n    od.move_to_end(K)", 3),
        ("if len(od) > 0:\n    od.popitem(last=False)", 2),
        ("if len(od) > 0:\n    k2, v2 = od.popitem()\n    acc += v2", 2),
        ("if len(od) > 0:\n    k2, v2 = od.popitem(last=False)\n    acc += v2 * 3", 2),
        ("if K in od:\n    del od[K]", 2), ("y = od.pop(K, 5)\nacc += y", 1),
        ("acc += od.get(K, 9)", 2), ("if K in od:\n    acc += od[K]", 2),
        ("for k2 in od:\n    acc = (acc * 3 + od[k2]) % 1000003", 2),
        ("for k2, v2 in od.items():\n    acc = (acc * 7 + v2 + LK2) % 1000003", 2),
        ("acc += len(od)", 1),
        ("try:\n    od.popitem()\nexcept KeyError:\n    errs += 1", 1),
    ]
    k, _, _ = KEYS_OF[keytype]
    lk2 = "len(k2)" if keytype == "str" else "k2[0]"
    ops = [subst(b, K=k, LK2=lk2) for b in weighted(rng, table, 20)]
    init = ["od = OrderedDict()"]
    final = ["for k2 in od:", "    print(k2, od[k2])", "print(od)"]
    return subst(build(rng, init, ops, final, steps), KEYS=str(keys), STATE="len(od)")


DSELEMS = {"int": ("b", "b + 1", "y"), "str": ('"e" + str(b + 3)', '"e" + str(b + 5)', "len(y)"),
           "tup": ("(b, b % 3)", "(b + 1, 0)", "y[0] * 3 + y[1]"),
           "tups": ('(b, "e" + str(b + 3))', '(b + 1, "e" + str(b + 5))', "y[0] * 3 + len(y[1])")}


def dss_program(rng, keytype="int", elem="int", steps=6000):
    keys = rng.choice([4, 9, 30])
    k = DKEYS[keytype]
    x, xb, h = DSELEMS[elem]
    table = [
        ("d[K].add(X)", 6), ("d[K].update([X, XB, X])", 1), ("d[K].discard(X)", 2),
        ("if X in d[K]:\n    d[K].remove(X)", 2),
        ("try:\n    d[K].remove(X)\nexcept KeyError:\n    errs += 1", 1),
        ("acc += len(d[K])", 3), ("if X in d[K]:\n    acc += 5", 3), ("if XB not in d[K]:\n    acc += 7", 1),
        ("ss = sorted(d[K])\nfor y in ss:\n    acc = (acc * 3 + H) % 1000003", 2),
        ("if K in d:\n    acc += 3", 2), ("acc += len(d)", 1),
        ("for k2 in d:\n    acc = (acc * 3 + len(d[k2])) % 1000003", 2),
        ("if s % 53 == 0:\n    d.clear()", 1),
    ]
    if elem == "int":
        table.append(("acc += sum(d[K])", 2))
        table.append(("if len(d[K]) > 0:\n    acc += max(d[K]) + 2 * min(d[K])", 2))
    ops = [subst(b, K=k, X=x, XB=xb, H=h) for b in weighted(rng, table, 22)]
    init = ["d = defaultdict(set)"]
    final = ["for k2 in d:", "    print(k2, len(d[k2]))", "    ss = sorted(d[k2])", "    for y in ss:", "        print(y)",
             "print(len(d))"]
    return subst(build(rng, init, ops, final, steps), KEYS=str(keys), STATE="len(d)")



PROGRAMS = {"deque": deque_program, "counter": counter_program, "dd": dd_program, "ddl": ddl_program,
            "dss": dss_program, "od": od_program}
# (generator, arguments, seed): every collections type and element / key flavour
FUZZ = [("counter", ("str",), 31), ("counter", ("int",), 32), ("dd", ("int", "str"), 33), ("dd", ("int", "int"), 34),
        ("dd", ("float", "str"), 35), ("dd", ("str", "int"), 36), ("dd", ("lambda", "str"), 37),
        ("ddl", ("int", "int"), 38), ("ddl", ("str", "str"), 39), ("ddl", ("str", "int"), 40),
        ("dss", ("int", "int"), 41), ("dss", ("str", "str"), 42), ("od", (), 43), ("deque", ("int",), 44),
        ("deque", ("str",), 45), ("deque", ("int",), 46), ("counter", ("str",), 47), ("ddl", ("int", "str"), 48)]
# the same operation sequences with tuples as keys / elements
TUPLE_FUZZ = [("deque", ("tup",), 61), ("deque", ("tups",), 62), ("deque", ("tup",), 63),
              ("counter", ("tup",), 64), ("counter", ("tups",), 65), ("counter", ("tup",), 66),
              ("dd", ("int", "tup"), 67), ("dd", ("float", "tups"), 68), ("dd", ("str", "tup"), 69),
              ("dd", ("lambda", "tup"), 70), ("dd", ("int", "tups"), 71),
              ("ddl", ("tup", "int"), 72), ("ddl", ("int", "tup"), 73), ("ddl", ("tups", "tups"), 74),
              ("ddl", ("tup", "str"), 75), ("ddl", ("str", "tup"), 76),
              ("dss", ("tup", "int"), 77), ("dss", ("int", "tup"), 78), ("dss", ("tups", "tups"), 79),
              ("dss", ("str", "tup"), 80), ("od", ("tup",), 81), ("od", ("tups",), 82)]


class CollectionsTests(unittest.TestCase):
    def same_as_cpython(self, text, name, stdin=b"", minimum_lines=1):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=600)
            expected = subprocess.run([sys.executable, str(source)], input=stdin, capture_output=True, timeout=600)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertGreaterEqual(expected.stdout.count(b"\n"), minimum_lines)
            if ran.stdout != expected.stdout:
                got, want = ran.stdout.split(b"\n"), expected.stdout.split(b"\n")
                for number, (a, b) in enumerate(zip(got, want)):
                    if a != b:
                        self.fail("%s: line %d differs:\n  compiled: %r\n  CPython:  %r" % (name, number + 1, a, b))
                self.fail("%s: lengths differ: %d vs %d lines" % (name, len(got), len(want)))
            self.assertEqual(ran.returncode, 0, ran.stderr)
            return expected.stdout

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "prog")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_counter_matches_cpython(self):
        out = self.same_as_cpython(COUNTER_PROGRAM, "coll_counter", minimum_lines=30)
        self.assertIn(b"Counter({3: 3, 1: 2, 2: 1})", out)

    def test_defaultdict_and_ordereddict_match_cpython(self):
        self.same_as_cpython(DEFAULTDICT_PROGRAM, "coll_dd", minimum_lines=20)

    def test_deque_matches_cpython(self):
        self.same_as_cpython(DEQUE_PROGRAM, "coll_deque", minimum_lines=15)

    def test_defaultdict_set_matches_cpython(self):
        self.same_as_cpython(DEFAULTDICT_SET_PROGRAM, "coll_dss", minimum_lines=8)

    def test_typical_programs_match_cpython(self):
        for name, text in SNIPPETS.items():
            with self.subTest(name):
                self.same_as_cpython(text, "coll_" + name, stdin=STDINS.get(name, STDIN), minimum_lines=1)

    def test_refusals_are_named(self):
        for name, (text, wanted) in REFUSALS.items():
            with self.subTest(name):
                self.refused(text, wanted)

    def test_generated_operation_sequences_match_cpython(self):
        """>= 5000 random operations per program: the same final state and checkpoints as CPython."""
        for index, (kind, args, seed) in enumerate(FUZZ):
            text = PROGRAMS[kind](random.Random(seed), *args)
            self.assertGreaterEqual(int(re.search(r"range\((\d+)\)", text).group(1)), 5000)
            with self.subTest("%s %s %d" % (kind, " ".join(args), seed)):
                out = self.same_as_cpython(text, "coll_fuzz_%d" % index, minimum_lines=8)
                self.assertIn(b" ", out)

    def test_tuple_programs_match_cpython(self):
        for name, text in TUPLE_SNIPPETS.items():
            with self.subTest(name):
                self.same_as_cpython(text, "coll_tup_" + name, minimum_lines=2)

    def test_tuple_refusals_are_named(self):
        for name, (text, wanted) in TUPLE_REFUSALS.items():
            with self.subTest(name):
                self.refused(text, wanted)

    def test_generated_tuple_operation_sequences_match_cpython(self):
        """>= 5000 random operations per program over tuple keys / elements: the same final state as CPython."""
        for index, (kind, args, seed) in enumerate(TUPLE_FUZZ):
            text = PROGRAMS[kind](random.Random(seed), *args)
            self.assertGreaterEqual(int(re.search(r"range\((\d+)\)", text).group(1)), 5000)
            with self.subTest("%s %s %d" % (kind, " ".join(args), seed)):
                out = self.same_as_cpython(text, "coll_tupfuzz_%d" % index, minimum_lines=8)
                self.assertIn(b" ", out)

    def test_programs_without_tuples_are_unchanged_by_the_tuple_support(self):
        import ail_syntax
        text = ("from collections import deque, Counter\n\n\ndef main() -> int:\n    q = deque([1])\n"
                "    q.append(2)\n    c = Counter('abca')\n    print(q.popleft(), c['a'])\n    return 0\n\n\nmain()\n")
        out = ail_syntax.python_surface(text)
        self.assertNotIn("tup", out)
        self.assertNotIn("_AilT_", out)

    def test_programs_without_collections_are_untouched(self):
        import ail_syntax
        text = "# collections is not imported here\ndef main() -> int:\n    s = \"collections\"\n    print(len(s))\n    return 0\n\n\nmain()\n"
        self.assertEqual(ail_syntax.python_surface(text),
                         ail_syntax.python_surface(text.replace("collections", "xyz")).replace("xyz", "collections"))
        for added in ("_ail_dq", "_ail_ctr", "_ail_ddl", "_AilDeque", "_AilDDL"):
            self.assertNotIn(added, ail_syntax.python_surface(text))

    def test_only_the_helpers_a_program_uses_are_added(self):
        import ail_syntax
        text = ("from collections import deque\n\n\ndef main() -> int:\n    q = deque([1])\n    q.append(2)\n"
                "    print(q.popleft())\n    return 0\n\n\nmain()\n")
        out = ail_syntax.python_surface(text)
        for used in ("_ail_dq_append_int", "_ail_dq_popleft_int", "_AilDeque_int"):
            self.assertIn(used, out)
        for unused in ("_ail_dq_rotate_int", "_ail_ctr_", "_AilDDL", "_ail_dq_new_str"):
            self.assertNotIn(unused, out)


if __name__ == "__main__":
    unittest.main()
