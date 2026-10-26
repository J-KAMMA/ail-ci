"""AIL_UNIFIED=1: type inference and unboxing on the general path (docs/design/UNIFIED_IR.md, prototype).

U1  hand-written programs: the general path, AIL_UNIFIED=1 and AIL_UNIFIED=1 with AIL_NO_MIX=1 print the same
    bytes and exit the same way, and the same as CPython 3.12 where the output does not depend on the version
U2  random integer and float programs near the int64 edges (overflow, zero divisors, shifts, floor division and
    modulo of negative numbers): the same output, stderr and exit status on the general path and AIL_UNIFIED=1
U3  the inference proves what it should: unboxed locals, a specialised body behind an entry guard, a boxed
    variable where a value is not proven, and no unboxed code at all when the flag is off
U4  step 2 (unified_lists.py, the draws, constant tables): programs that share, change, escape and over-index
    lists and tables, forced onto the general path: the same bytes with and without AIL_UNIFIED=1, and CPython's
U5  step 2 proves what it should (typed element reads, the C draws, vector loops) and nothing without the flag
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
ON_312 = sys.version_info[:2] == (3, 12)


def build(directory, text, name, env_extra):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(k, None)
    env.update(env_extra)
    env['AIL_NO_CACHE'] = '1'
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                        '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True, text=True,
                       timeout=900, env=env)
    return r, exe


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding='utf-8')
    return r.returncode, r.stdout, r.stderr


MODES = {'general': {'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED': '1'}, 'unified_nomix': {'AIL_UNIFIED': '1', 'AIL_NO_MIX': '1'}}

NAN_ID = '''
from dataclasses import dataclass


@dataclass
class W:
    v: float


def main() -> None:
    nan = float("nan")
    w = W(nan)
    print(w == w, W(nan) == W(nan), W(1.0) == W(1))
    xs = [nan]
    ys = [nan]
    print(xs == ys, (nan,) == (nan,), nan in xs)
    d = {nan: 1}
    print(nan in d, d.get(nan), W(nan) in [W(nan)])


main()
'''

PROGRAMS = {
    'numeric': '''
import json
CONFIG = json.loads('{"n": 2000, "label": "steps"}')
K = 7
F = 2.5


def collatz(n):
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


def arith(a, b):
    return (a // b, a % b, a << 3, a >> 2, (a ^ b) & (a | b), -a, ~b, a / b)


def mixed(n):
    total = 0
    acc = 0.0
    for i in range(n):
        total += i * K
        acc += i / 3
        if i % 3 == 0 and i > 2 or i == 1:
            acc -= F
    return total, acc


def loops():
    out = []
    for i in range(10, 0, -3):
        out.append(i)
    for j in range(5):
        if j == 3:
            break
    else:
        out.append("no-break")
    m = 99
    for m in range(0):
        pass
    n = 0
    while n < 5:
        n += 2
    else:
        out.append(("while-else", n, m))
    return out


def floats():
    a = 0.1 + 0.2
    b = -0.0
    c = 1e308 * 10
    d = c - c
    return a, b, c, d, 7.0 // 2, -7.5 % 2, min(3.5, 2.25, 9.0), max(1, 5, 3), a == 0.3, d != d


def fdiv(a, b):
    try:
        x = a / b
    except ZeroDivisionError as e:
        print("zde", e)
        x = -1.0
    return x


def poly(x):
    y = x + x
    return y


def gen(limit: int):
    for k in range(limit):
        yield poly(k)


def count_down(n: int) -> int:
    if n <= 0:
        return 0
    return 1 + count_down(n - 1)


def lens(s):
    n = len(s)
    c = ord(s[0])
    k = int("12") + n
    f = float(n) / 4
    return n, c, k, f, "a" in s, round(2.675), abs(-4), abs(-2.5)


def bools(x):
    seen = False
    for i in range(x):
        if i == 2:
            seen = True
    return seen, seen and True, seen + 1, 1 if seen else 2


def main():
    best = 0
    arg = 0
    i = 1
    while i < CONFIG["n"]:
        s = collatz(i)
        if s > best:
            best = s
            arg = i
        i += 1
    print(CONFIG["label"], arg, best)
    print(arith(17, 5), arith(-17, 5), arith(17, -5), arith(-17, -5))
    print(mixed(10), loops(), floats())
    print(fdiv(1, 4), fdiv(3, 0), fdiv(2.5, 0.5))
    print(poly(2), poly(2.5), poly("z"), poly([1]), list(map(poly, [1, 2, 3])), list(gen(4)))
    f = count_down
    print(f(5), count_down(7), lens("hello"), bools(4), bools(1))
    total = 0
    for x in json.loads("[3, -7, 2.5]"):
        total = total + x
    print(total)


main()
''',
}


# step 2 (element types, draws, tables): forced onto the general path, with and without AIL_UNIFIED=1
STEP2 = {
    'grid': '''# grids: shared rows, negative and out-of-range indexes, None, mutation while iterating
def make(n: int) -> list[list[int]]:
    return [[r * n + c for c in range(n)] for r in range(n)]


def get(g: list[list[int]], r: int, c: int) -> int:
    return g[r][c]


def shared_rows(n: int) -> list[list[int]]:
    row = [0] * n
    return [row] * n


def maybe(n: int) -> list[int] | None:
    if n > 2:
        return [n, n + 1]
    return None


def main() -> None:
    g = make(4)
    print(get(g, 1, 2), get(g, -1, -1), g[3][0] + g[0][3])
    try:
        print(get(g, 4, 0))
    except IndexError as e:
        print("IndexError", e)
    try:
        print(get(g, 0, -5))
    except IndexError as e:
        print("IndexError", e)
    s = shared_rows(3)
    s[0][1] = 7
    print(s, s[2][1])
    t = 0
    for r in range(3):
        for c in range(3):
            t += s[r][c]
    print(t)
    x = maybe(1)
    try:
        print(x[0])
    except TypeError as e:
        print("TypeError", e)
    y = maybe(5)
    if y is not None:
        print(y[0] * y[1])
    xs = [1, 2, 3]
    total = 0
    for v in xs:
        total += v
        if v < 3:
            xs.append(v + 10)
    print(total, xs)
    ys = [5, 6, 7, 8]
    for v in ys:
        if v == 6:
            ys.pop()
        total += v
    print(total, ys)
    z = [True, False, True]
    n = 0
    for b in z:
        if b:
            n += 1
    print(n, z[0] and z[2])
    fl = [0.5, 1.5]
    fl[1] += 2
    print(fl[0] * fl[1], fl)
    ii = [1, 2]
    ii[0] += 0.5
    print(ii)
    try:
        print(g["a"])
    except TypeError as e:
        print("TypeError", e)
    print(g[True][True], g[0][False])


main()
''',
    'tables': '''# constant tables, tuple loops, row variables, pair assignment
DIRS = ((0, 1), (1, 0), (0, -1), (-1, 0))
STEPS = [1, 2, 3]
MOVES: list[tuple[int, int]] = [(1, 2), (2, 1), (-1, -2)]


def walk(x: int, y: int) -> int:
    t = 0
    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        t += nx * 10 + ny
    for s in STEPS:
        t += s
    for a, b in MOVES:
        t += a - b
    for d in (-1, 0, 1):
        t += d * x
    return t


def swap(a: int, b: int) -> int:
    a, b = b, a
    return a * 10 + b


def last(xs: list[tuple[int, int]]) -> int:
    v = 0
    for p, q in xs:
        v = p * q
    return v


def mutate() -> int:
    table = [(1, 1), (2, 2)]
    table.append((3, 3))
    s = 0
    for p, q in table:
        s += p + q
    return s


def loop_else(n: int) -> int:
    for d in (1, 2, 3):
        if d == n:
            break
    else:
        return -1
    return d


def main() -> None:
    print(walk(3, 4), swap(1, 2), last(MOVES), mutate(), loop_else(2), loop_else(9))
    k = 5
    print(k in (2, 3), k not in (4, 5), 3 in [1, 2, 3])


main()
''',
    'random': '''# random draws: results, bad arguments, subclasses, the module functions
import random


class Loud(random.Random):
    def seed(self, a=None):
        super().seed(a)


def draws(rng: random.Random) -> float:
    s = 0.0
    for _ in range(1000):
        s += rng.random() + rng.uniform(1, 3) + rng.uniform(0.5, 2) + rng.gauss(0.0, 2.0) + rng.expovariate(2)
        s += rng.randint(1, 6) + rng.randrange(10) + rng.randrange(2, 20, 3) + rng.getrandbits(5)
        s += rng.gauss() + rng.gauss(1.0)
    return s


def main() -> None:
    rng = random.Random(7)
    print("%.6f" % draws(rng))
    random.seed(3)
    t = 0.0
    for _ in range(100):
        t += random.random() * random.expovariate(0.5) + random.uniform(-1, 1)
    print("%.6f" % t, random.randint(1, 100))
    lo = Loud(5)
    print("%.6f" % lo.random(), lo.randint(1, 9))
    c = rng.choice((-1, 1)) + rng.choice([3, 4])
    print(c)
    try:
        print(rng.expovariate(0))
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    try:
        print(rng.randrange(0))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(rng.uniform("a", 2))
    except TypeError as e:
        print("TypeError", type(e).__name__)
    big = 2 ** 62
    print(rng.uniform(big, big + 3) - big >= 0)


main()
''',
    'escape': '''# lists that escape: closures, globals, attributes, sort keys, comparisons with objects, copies
CACHE = []


class Box:
    def __init__(self, xs):
        self.xs = xs


class Eq:
    def __eq__(self, other):
        if isinstance(other, list):
            other.append("eq")
        return False


def sink(xs: list[int]) -> None:
    global CACHE
    CACHE = xs


def closure(xs: list[int]) -> int:
    f = lambda: xs.append("c")
    f()
    return len(xs)


def compare(xs: list[int]) -> bool:
    return xs == Eq()


def main() -> None:
    a = [1, 2, 3]
    sink(a)
    CACHE.append("g")
    print(a, a[-1])
    b = [4, 5]
    print(closure(b), b)
    c = [6, 7]
    box = Box(c)
    box.xs.append(8.5)
    t = 0.0
    for v in c:
        t += v
    print(t)
    d = [3, 1, 2]
    d.sort(key=lambda v: -v)
    print(d[0] + d[2], d)
    e = [1, 2]
    print(compare(e), e)
    f = [[1, 2], [3]]
    g = f[:]
    g[0].append(9)
    print(f, f[0][2])
    h = [[1], [2]]
    k = h.copy()
    k[1].append("s")
    print(h)
    m = [[1, 2]]
    for row in m:
        row.append("r")
    print(m)
    n = [5, 6]
    print(Eq() in [n], n)
    p = [[0, 1]]
    q = sorted(p)
    q[0].append(2)
    print(p)
    r = [1, 2]
    s = r + [3]
    s.append(4)
    print(r, s, r[1])


main()
''',
    'tables_mut': '''# tables that are changed through another name, or in place: they must be walked as they are
PAIRS = [(1, 2), (3, 4)]
ROWS = [(5, 6), (7, 8)]
ONES = [1, 2, 3]


def grow(t):
    t.append((9, 9))


def through_alias() -> int:
    table = [(1, 1), (2, 2)]
    other = table
    other[0] = (5, 5)
    s = 0
    for a, b in table:
        s += a * b
    return s


def through_call() -> int:
    table = [(1, 1), (2, 2)]
    grow(table)
    s = 0
    for a, b in table:
        s += a + b
    return s


def sorted_in_place() -> int:
    table = [(3, 1), (1, 2), (2, 3)]
    table.sort()
    s = 0
    k = 1
    for a, b in table:
        s += a * k
        k *= 10
    return s


def reversed_and_deleted() -> int:
    table = [(1, 0), (2, 0), (3, 0)]
    table.reverse()
    del table[0]
    s = 0
    for a, b in table:
        s = s * 10 + a
    return s


def module_tables() -> int:
    s = 0
    for a, b in PAIRS:
        s += a * b
    for x, y in ROWS:
        s += x - y
    for v in ONES:
        s += v
    return s


def main() -> None:
    print(through_alias(), through_call(), sorted_in_place(), reversed_and_deleted(), module_tables())
    ROWS.append((100, 1))
    print(module_tables())


main()
''',
    'types': '''# element types that must not be proven, and ones that must survive comprehension scopes
class Holder:
    def __init__(self):
        self.xs = [1, 2, 3]

    def total(self) -> int:
        return add_all(self.xs)


def add_all(xs: list[int]) -> int:
    t = 0
    for v in xs:
        t += v
    return t


def put(xs, k):
    xs.append(k)


def build(n: int, acc: list[int]) -> list[int]:
    if n == 0:
        return acc
    acc.append(n * n)
    return build(n - 1, acc)


def main() -> None:
    a = [1, 2]
    put(a, 3)
    b = [1.5]
    put(b, 2)
    print(a, b, a[2] * 2, b[1] * 2)
    h = Holder()
    h.xs.append(4.5)
    print(h.total())
    print(add_all([4, 5]), build(4, []))
    fl = [0.5]
    fl.append(1)
    print(fl[1], fl[0] + fl[1], fl)
    xs = [1, 2]
    xs[0] = True
    print(xs[0], xs[0] + xs[1], xs)
    sq = [v * 2 for v in [3, 4, 5]]
    print(sq[2] + 1, sum(sq) / len(sq))
    x = 1.5
    ys = [x for x in range(3)]
    zs = [x] * 2
    print(ys, zs, zs[1] * 2, ys[2] * 2)
    acc = []
    [acc.append(i * 3) for i in range(4)]
    print(acc[3] + acc[0], acc)
    gen = list(v + 1 for v in sq)
    print(gen[0] * 3, gen)
    m = [[1.0, 2.0], [3.0]]
    m[1].append(4)
    print(m[1][1] * 2, m)
    n = [[1, 2]]
    n.append([0.5])
    print(n[1][0] + n[0][0], n)
    w = [1, 2, 3]
    w += [4.5]
    print(w[3] * 2, w)
    e = [1, 2]
    e.extend("ab")
    print(e[2], e)
    neg = [5, 6, 7]
    print(neg[-1] - neg[-3], neg[-2])


main()
''',
    'sliceobj': '''# a list of ints indexed by a slice object (a list, not an element), by a bool, by an object with __index__
class Two:
    def __index__(self):
        return 2


def pick(xs: list[int], k) -> int:
    v = xs[k]
    return v if isinstance(v, int) else len(v)


def main() -> None:
    xs = [10, 20, 30, 40]
    sl = slice(1, 3)
    print(xs[sl], [1, 2, 3][sl], pick(xs, sl), pick(xs, 1), pick(xs, True), pick(xs, Two()))
    ys = [[1, 2], [3, 4]]
    row = ys[sl]
    print(row, ys[0][sl])
    xs[sl] = [7, 8, 9]
    print(xs, xs[3] + xs[0])


main()
''',
}

STEP3 = {
    'pairs': '''
import random


def pairs(n):
    out = []
    for i in range(n):
        out.append((i * 1.5, i % 3))
    return out


def total(ps):
    s = 0.0
    c = 0
    for t, d in ps:
        s += t
        c += d
    return s, c


def main():
    ps = pairs(10)
    print(ps)
    print(total(ps))
    a = ps[3]
    b = ps[3]
    print(a is b, a == (4.5, 0), hash(a) == hash((4.5, 0)))
    d = {}
    for x, y in ps:
        d[(x, y)] = d.get((x, y), 0) + 1
    print(sorted(d.items())[:3])
    s = set(ps)
    print(len(s), (1.5, 1) in s, (1.5, 2) in s)
    # negative and out-of-range constant indices
    t = ps[2]
    print(t[-1], t[-2], t[0] + t[1])
    try:
        print(t[2])
    except IndexError as e:
        print("IndexError", e)
    try:
        print(t[1.0])
    except TypeError as e:
        print("TypeError", e)
    # nested and mixed
    nest = ((1, 2.5), 3)
    print(nest[0][1] * 2, nest[1])
    rows = [(1, True), (2, False), (3, True)]
    cnt = 0
    for n, flag in rows:
        if flag:
            cnt += n
    print(cnt, rows)
    # a pair whose component changes type in another place: stays correct
    mix = [(1, 2), (1, 2.5)]
    print(sum(a + b for a, b in mix))
    z = 0
    for a, b in mix:
        z += a * b
    print(z)
    # unpack from a call result
    s1, c1 = total(ps)
    print(s1, c1)
    lo, hi = min(ps), max(ps)
    print(lo, hi)
    # sort by key and stability
    ev = []
    for a, b in ps:
        ev.append((a, -1))
        ev.append((a, +1))
    ev.sort(key=lambda e: e[0])
    print(ev[:6])
    area = 0.0
    prev = 0.0
    n = 0
    for t, d2 in ev:
        area += n * (t - prev)
        n += d2
        prev = t
    print(area, prev, n)
    # wrong-shape element: not a pair
    odd = [(1, 2), (3, 4, 5)]
    try:
        for p, q in odd:
            print(p, q)
    except ValueError as e:
        print("ValueError", e)


main()
''',
    'zip': '''
def f(xs, ys):
    out = []
    for a, b in zip(xs, ys):
        out.append(a * b)
    return out


def g(xs, ys):
    acc = 0.0
    for a, b in zip(xs, ys):
        if a > 100:
            break
        acc += a - b
    else:
        acc = -acc
    return acc


def grow(xs, ys):
    # the first list grows while zipped
    n = 0
    for a, b in zip(xs, ys):
        if len(xs) < 6:
            xs.append(a + 1)
        n += a + b
    return n


def three(xs, ys, zs):
    t = 0
    for a, b, c in zip(xs, ys, zs):
        t += a * b + c
    return t


def mixed(xs):
    # a list that holds an int and a str: no proof
    for a, b in zip(xs, xs):
        print(a, b)


def main():
    print(f([1.5, 2.5, 3.5], [2.0, 4.0]))
    print(f([1, 2, 3], [4, 5, 6, 7]))
    print(g([1.0, 2.0, 3.0], [0.5, 0.5, 0.5]))
    print(g([1.0, 200.0, 3.0], [0.5, 0.5, 0.5]))
    print(grow([1, 2], [10, 20, 30, 40, 50, 60, 70]))
    print(three([1, 2, 3], [4, 5, 6], [7, 8, 9]))
    mixed([1, "a", 2.5])
    # zip with an unequal length: the first list's extra element is consumed, not the second's
    it = iter([1, 2, 3])
    for a, b in zip(it, [9]):
        print(a, b)
    print(list(it))
    try:
        for a, b in zip(None, [1]):
            pass
    except TypeError as e:
        print("TypeError", e)
    try:
        for a, b in zip([1], 5):
            pass
    except TypeError as e:
        print("TypeError", e)
    xs = [1.0, 2.0]
    ys = [3, 4]
    for a, b in zip(xs, ys):
        xs.append(5.0)
        ys.append(6)
        if len(xs) > 8:
            break
    print(xs, ys)
    # names bound by the loop stay visible after it
    for p, q in zip([1, 2, 3], [4, 5, 6]):
        pass
    print(p, q)
    for p, q in zip([], []):
        pass
    print(p, q)


main()
''',
    'alias': '''
def push(t):
    t[0].append("x")


def make():
    lst = [1, 2, 3]
    return lst, 5


def two(a):
    return a, a * 2


def maybe(flag):
    if flag:
        return 1, 2
    return None


def main():
    # a list inside a tuple, changed through the tuple
    row = ([1, 2], 5)
    row[0].append(2.5)
    s = 0
    for v in row[0]:
        s += v
    print(s, row)
    # a list inside a tuple, changed by a function that stores a str
    r2 = ([1, 2, 3], 7)
    push(r2)
    t = 0
    try:
        for v in r2[0]:
            t += v
    except TypeError as e:
        print("TypeError", e)
    print(r2, t)
    # the list and the tuple both alias
    xs = [10, 20]
    pr = (xs, 1)
    xs.append(30)
    print(pr, sum(pr[0]))
    pr[0][0] = 1.5
    print(xs)
    a, n = make()
    print(a, n)
    a.append(4)
    print(sum(a))
    p, q = two(3)
    print(p, q)
    p, q = two(2.5)
    print(p, q)
    print(maybe(True), maybe(False))
    u = maybe(True)
    if u:
        x, y = u
        print(x + y)
    # list of tuples of lists
    lt = [([1], 2), ([3, 4], 5)]
    tot = 0
    for l, k in lt:
        for v in l:
            tot += v * k
    print(tot)
    lt[0][0].append(100)
    print(lt)
    # tuple in list built by comprehension
    cs = [(i, i * i) for i in range(5)]
    print(cs)
    ss = 0
    for i, sq in cs:
        ss += sq - i
    print(ss)
    print(cs[2][1] + cs[3][0])
    # identity and equality of tuples held in a list
    e = (1, 2)
    holder = [e, (1, 2), e]
    print(holder[0] is holder[2], holder[0] == holder[1], holder.count(e), holder.index((1, 2)))


main()
''',
    'bytes': '''
class Loud(bytearray):
    def __getitem__(self, i):
        print("loud", i)
        return bytearray.__getitem__(self, i)


class Plain:
    def __init__(self):
        self.d = {1: 2}

    def __getitem__(self, k):
        return self.d[k] * 10


class Sub(bytearray):
    pass


def make(n):
    return bytearray(range(n))


def total(b):
    t = 0
    for i in range(len(b)):
        t += b[i]
    return t


def pick(c, k):
    return c[k]


def main():
    b = make(10)
    print(b[0], b[3], b[9], b[-1], b[-10])
    print(total(b))
    try:
        print(b[10])
    except IndexError as e:
        print("IndexError", e)
    try:
        print(b[-11])
    except IndexError as e:
        print("IndexError", e)
    try:
        print(b[1.5])
    except TypeError as e:
        print("TypeError", e)
    print(b[True], b[False])
    print(b[2:5], b[::3], type(b[2:5]).__name__)
    b[4] = 200
    print(b[4], total(b))
    l = Loud(b"abc")
    print(l[1], pick(l, 2))
    print(pick(b, 7), pick([5, 6, 7], 1), pick({3: "x"}, 3), pick("hello", 1), pick(Plain(), 1), pick((1, 2), 0))
    print(pick(b"xyz", 1), pick(bytes([7, 8]), -1))
    b.append(77)
    print(b[10], len(b))
    del b[0]
    print(b[0])
    s = Sub(b"hi")
    print(s[0], s[-1], pick(s, 1))
    big = bytearray(1000)
    for i in range(1000):
        big[i] = i % 256
    acc = 0
    for i in range(1000):
        if big[i] > 100:
            acc += big[i]
    print(acc)


main()
''',
    'enum': '''
def sums(xs, ys):
    total = 0.0
    for i, x in enumerate(xs):
        total += x * i
    for i, y in enumerate(ys, 3):
        total += y + i
    return total


def pairs(n):
    ps = []
    for i in range(n):
        ps.append((i, i * i))
    return ps


def main():
    print(sums([1.5, 2.5, 3.5], [1, 2]))
    ps = pairs(6)
    stack = [(0, 0)]
    seen = 0
    while stack:
        r, c = stack.pop()
        seen += r + c
        if r < 3:
            stack.append((r + 1, c))
            stack.append((r, c + 1)) if c < 1 else None
    print(seen)
    q, w = ps[3]
    print(q, w)
    for k, v in enumerate(ps):
        print(k, v)
    xs = [1.0, 2.0]
    for i, x in enumerate(xs):
        if i < 3:
            xs.append(x + 1)
    print(xs)
    try:
        for i, x in enumerate(None):
            pass
    except TypeError as e:
        print("TypeError", e)


main()
''',
}

IDENT = '''
def floats(x):
    y = x
    print((x and "a") is not x, (x and "a") is x, y is x, x is y, x is not y)
    z = x + 0.0
    print(z is x, z is not x, (z or 1.0) is z)
    w = x * 0.0
    print((w and "a") is not w, (w or 5) is w, (w if w else 2.5) is w)
    return w


def tup(t):
    a = t[0]
    b = t[1]
    print(t[0] is a, a is t[0], t[1] is not b, a is b)


def nones(x, y):
    q = None
    print(x is None, y is not None, q is None, x is q)
    r = 1.5
    return r


def main():
    x = float("0")
    print((x and "a") is not x)
    floats(0.0)
    floats(2.5)
    tup((1.5, 2.5))
    tup((3, 3))
    print(nones(None, 1.0), nones(2.0, None))
    for i in range(3):
        f = i * 0.5
        g = f
        print(f is g, f is not g, (f or g) is g)
    v = float("1.25")
    u = v
    while u is v:
        v = v + 1.0
        print(u is v)


main()
'''


PALIN = '''
def is_pal(s):
    return s == s[::-1]


def not_pal(s):
    return s != s[::-1]


def flipped(s):
    return s[::-1] == s


def in_if(s):
    if s == s[::-1]:
        return "yes"
    return "no"


def count(limit):
    n = 0
    for i in range(limit):
        t = str(i)
        if t == t[::-1]:
            n += 1
    return n


def main():
    for v in ["", "a", "ab", "aba", "abba", "abca", "\u00e9a\u00e9", "\u3042\u3044\u3042", "A man", "racecar" * 3]:
        print(repr(v), is_pal(v), not_pal(v), flipped(v), in_if(v))
    for v in [[], [1], [1, 2, 1], [1, 2], (1, 2, 1), (1, 2), b"aba", b"ab", "ab" * 4]:
        print(repr(v), is_pal(v), not_pal(v), flipped(v), in_if(v))
    for v in [5, 1.5, None]:
        try:
            print(is_pal(v))
        except (TypeError, KeyError) as e:
            print(type(e).__name__, e)
    print(count(2000))
    parts = ["x", "xyx", "xy"]
    for p in parts:
        print(p == p[::-1], p != p[::-1], p[::-1] != p, p == p[::2], p == p[::-2])


main()
'''


def random_program(rng):
    """Integer and float arithmetic in one function whose locals the inference unboxes, with operands near
    the int64 edges: every edge (overflow, zero divisor, negative shift) takes the general runtime's path."""
    edges = ['0', '1', '-1', '2', '-2', '7', '-7', '63', '64', '9223372036854775807', '-9223372036854775807',
             '4611686018427387904', '3037000499', '-3037000500']
    ops = ['+', '-', '*', '//', '%', '<<', '>>', '&', '|', '^']
    lines = ['def f(a, b, c):', '    x = a', '    y = b', '    z = 0.5']
    for i in range(12):
        op = rng.choice(ops)
        lhs, rhs = rng.choice(['x', 'y', 'c']), rng.choice(['x', 'y', 'c', rng.choice(edges)])
        if op in ('<<', '>>'):
            rhs = rng.choice(['0', '1', '3', '62', '63', '64', 'c'])
        lines.append('    x = %s %s %s' % (lhs, op, rhs))
        lines.append('    if x > y or x == c:')
        lines.append('        y = y - 1')
        lines.append('    z = z * 1.5 + x / 3 if y != 0 else z - 1.0')
        lines.append('    print(%d, x, y, z, x < z, -y)' % i)
    lines.append('    return x')
    calls = ['f(%s, %s, %s)' % (rng.choice(edges), rng.choice(edges), rng.choice(['0', '1', '-1', '5', '63']))
             for _ in range(3)]
    body = ['def main():'] + ['    try:\n        print(%s)\n    except ZeroDivisionError as e:\n        print("zde", e)'
                             % c for c in calls] + ['', 'main()']
    return '\n'.join(lines) + '\n\n\n' + '\n'.join(body) + '\n'


IDENT_MIX = '''
D = {1: "a", "b": 2.5, (1,2): [3]}
class Box:
    def __init__(self, v):
        self.v = v

def keep(v):
    return v

def ident(v):
    return v

def f1(x):
    print(keep(x) is x, ident(x) is not x)

def g(a, b):
    return a is b

def h(a, b):
    return a is not b

def holder(x):
    lst = [x]
    b = Box(x)
    print(lst[0] is x, b.v is x, keep(lst[0]) is x, keep(b.v) is b.v)

f1(0.0)
f1(1.5)
f1(7)
f1(-3)
holder(2.5)
holder(100)
x = 3.25
print(g(x, x), h(x, x), g(5, 5), g(-5, -5), h(256, 256))
w = float("2.0")
print(g(w, w), keep(w) is w)
print(len(D))
'''


POOL = '''
M = {1: "a", "b": 2.5}


def work(n):
    keep = []
    total = 0
    for i in range(n):
        s = str(i)
        total += len(s)
        if i % 1000 == 0:
            keep.append(s + "!")
    d = {}
    for i in range(0, n, 7):
        d[str(i)] = i * 0.5
    fl = [i / 3 for i in range(0, n, 11)]
    big = ["x" * (i % 90) for i in range(2000)]
    return total, keep[-1], len(keep), len(d), sum(d.values()), len(fl), sum(fl), sum(len(b) for b in big)


for r in range(3):
    print(work(300000 + r))
print(len(M), M)
'''


SORTPRIM = r'''
INF = 1e308 * 10
import math

def show(tag, v):
    print(tag, v)

# float keys: ties (stability), reverse stability, runs, descending, equal, -0.0, inf
pairs = [(2.5, "a"), (1.0, "b"), (2.5, "c"), (0.5, "d"), (1.0, "e"), (-0.0, "f"), (0.0, "g"), (INF, "h"), (-INF, "i")]
show("f1", sorted(pairs, key=lambda e: e[0]))
show("f2", sorted(pairs, key=lambda e: e[0], reverse=True))
ev = []
for i in range(40):
    ev.append((i * 1.5, 1))
for i in range(40):
    ev.append((i * 1.5 + 0.7, -1))
for i in range(40):
    ev.append((i * 1.5, 7))
ev.sort(key=lambda e: e[0])
show("f3", ev[:12] + ev[-6:])
ev.sort(key=lambda e: e[0], reverse=True)
show("f4", ev[:12] + ev[-6:])
desc = [(100.0 - i, i) for i in range(50)]
desc.sort(key=lambda e: e[0])
show("f5", desc[:5] + desc[-3:])
mixed = [(5.0 - (i % 7) * 0.25 * (1 - 2 * (i % 2)), i) for i in range(60)]   # not `** i`: a variable exponent can need a big int (BIGINT.md), which leaves the plan off
mixed.sort(key=lambda e: e[0])
show("f6", mixed)
# ints
ints = [(i * 7919 % 101, i) for i in range(100)]
ints.sort(key=lambda e: e[0])
show("i1", ints)
ints.sort(key=lambda e: -e[0])
show("i2", ints[:20])
ints.sort(key=lambda e: e[0], reverse=True)
show("i3", ints[:20])
big = [(9223372036854775807, 1), (-9223372036854775807 - 1, 2), (0, 3), (9223372036854775806, 4), (-1, 5)]
big.sort(key=lambda e: e[0])
show("i4", big)
show("i5", sorted([3, 1, 2, 3, 1, 5, -4, 0]))
show("i6", sorted([3.5, 1.25, 2.0, 3.5, -1.0, 1e300, -1e300]))
show("i7", sorted(range(30), key=lambda x: (x * 17) % 11))
# trivial sizes
show("n0", sorted([], key=lambda e: e))
show("n1", sorted([(1.5, 2)], key=lambda e: e[0]))
show("n2", sorted([(2.5, 2), (1.5, 3)], key=lambda e: e[0]))
big2 = list(range(1000, 0, -1))
big2.sort()
show("n3", big2[:5] + big2[-3:])
big3 = [float(i % 13) for i in range(1000)]
big3.sort()
show("n4", big3[:20] + big3[-5:], )
big3.sort(reverse=True)
show("n5", big3[:20] + big3[-5:], )
# keys of other kinds: generic path
show("g1", sorted([(1, "b"), (1.5, "a"), (0, "c"), (True, "d")], key=lambda e: e[0]))
show("g2", sorted(["pear", "fig", "apple", "kiwi"], key=len))
show("g3", sorted(["pear", "fig", "apple", "kiwi"], key=lambda s: s))
show("g4", sorted([(2, 1.0), (1, 5.0), (2, 0.5)]))
show("g5", sorted([[3, 1], [1, 2], [3, 0]]))
show("g6", sorted([True, False, True, False]))
# mixed int / float keys
show("m1", sorted([(1, "a"), (0.5, "b"), (2, "c"), (1.0, "d"), (-1, "e")], key=lambda e: e[0]))
# nn
nn = INF - INF
show("x1", sorted([3.0, 1.0, 2.0, 5.0, 4.0]))
v = sorted([(1.0, 1), (2.0, 2), (0.0, 3)], key=lambda e: e[0])
show("x2", v)
try:
    sorted([1, "a", 2])
except TypeError as e:
    print("TypeError")
try:
    sorted([(1.0, 1), (2.0, 2)], key=lambda e: e[2])
except IndexError as e:
    print("IndexError")
cnt = [0]
def kf(e):
    cnt[0] += 1
    return e[0]
sorted(ev, key=kf)
print(cnt[0] == len(ev))
# nsmallest-like use
import heapq
show("h1", heapq.nsmallest(3, [(2.5, 1), (0.5, 2), (1.5, 3), (0.1, 4)]))
show("h2", heapq.nlargest(2, [5, 3, 9, 1]))
# min / max with keys
show("mm", min([(2.5, 1), (0.5, 2)], key=lambda e: e[0]), )
show("mx", max([(2.5, 1), (0.5, 2), (2.5, 3)], key=lambda e: e[0]))
'''


SORTNAN = r'''
INF = 1e308 * 10
nn = INF - INF
a = [(3.0, 1), (nn, 2), (1.0, 3), (2.0, 4), (nn, 5), (0.0, 6)]
a.sort(key=lambda e: e[0])
print(a)
b = [3.0, nn, 1.0, 2.0]
b.sort()
print(b)
c = [(float(i % 5), i) for i in range(30)]
c.append((nn, 99))
c.sort(key=lambda e: e[0], reverse=True)
print(c)
'''


TUPLES15 = r'''
# tuples: sizes around the inline limit, growth by + and *, keys, sets, nesting, many of them across collections
def mk(n):
    return tuple(range(n))

for n in (0, 1, 2, 7, 8, 9, 10, 40):
    t = mk(n)
    print(n, len(t), t[-1] if n else None, sum(t), t + (99,), (t * 2)[:5], t[1:4])
x = (1, 2.5, "s", None, (3, 4), [5, 6], True, -1)
print(x, x[4][1], x[5][0], len(x))
x[5].append(7)
print(x)
y = x + (9,)
print(len(y), y[-1], y[8 - 1])
a, b, *rest = y
print(a, b, rest)
d = {}
for i in range(300):
    d[(i, i * 0.5)] = (i, i + 1, i + 2)
print(len(d), d[(7, 3.5)], d[(299, 149.5)])
s = set((i % 10, i % 3) for i in range(1000))
print(len(s), sorted(s)[:5])
lst = []
for i in range(60000):
    lst.append((i * 0.25, i, "k"))
    if i % 3 == 0:
        lst.append((i, i * 0.5))
print(len(lst), lst[-1], lst[100], sum(p[1] for p in lst))
keep = lst[::1000]
del lst
tot = 0.0
for i in range(50000):
    q = (i, i * 1.5, i * 2)
    tot += q[1] - q[0]
print(tot, keep[3])
print(tuple(range(100))[50], tuple([1, 2, 3]), tuple("abcdefghijkl")[10], tuple(d)[5])
print((1, 2) < (1, 3), (1, 2, 3) == (1, 2, 3), min((3, 1), (2, 9)), max([(1, 2), (1, 3)]))
big = tuple(range(1000))
print(sum(big), big.count(5), big.index(900))
def gen(n):
    for i in range(n):
        yield (i, i + 1)
print(sum(a + b for a, b in gen(1000)))
print(list(zip(range(5), "abcde", [1.5] * 5)))
print(dict(zip("abc", (1, 2, 3))))
print(list(enumerate("xyz")), sorted(zip([3, 1, 2], "abc")))
'''


class Unified(unittest.TestCase):
    def test_u1_programs(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in PROGRAMS.items():
                outs = {}
                for mode, env in MODES.items():
                    r, exe = build(d, text, '%s_%s' % (name, mode), env)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    outs[mode] = run([str(exe)])
                self.assertEqual(outs['general'], outs['unified'], name)
                self.assertEqual(outs['general'], outs['unified_nomix'], name)
                if ON_312:
                    src = Path(d, name + '_cpython.py')
                    src.write_text(text, encoding='utf-8')
                    self.assertEqual(run([sys.executable, str(src)])[:2], outs['unified'][:2], name)

    def test_u2_random_edges(self):
        rng = random.Random(20261020)
        with tempfile.TemporaryDirectory() as d:
            for k in range(int(os.environ.get('AIL_UNIFIED_FUZZ', '6'))):
                text = random_program(rng)
                outs = []
                for mode in ('general', 'unified_nomix'):
                    r, exe = build(d, text, 'r%d_%s' % (k, mode), MODES[mode])
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    outs.append(run([str(exe)]))
                self.assertEqual(outs[0], outs[1], text)

    def test_u3_plan(self):
        sys.path[:0] = [str(PKG), str(ROOT)]
        import pyboxed2
        import unified
        text = PROGRAMS['numeric']
        saved = os.environ.get('AIL_UNIFIED')
        try:
            os.environ['AIL_UNIFIED'] = '0'
            plain = pyboxed2.build(text, {}, allow_mix=False)
            self.assertNotIn('pfu_', plain)
            self.assertNotIn('int64_t u_', plain)
            os.environ['AIL_UNIFIED'] = '1'
            del unified.STATS[:]
            c = pyboxed2.build(text, {}, allow_mix=False)
        finally:
            if saved is None:
                os.environ.pop('AIL_UNIFIED', None)
            else:
                os.environ['AIL_UNIFIED'] = saved
        stats = unified.STATS[-1]
        self.assertIn('collatz', stats['specialised'])
        self.assertIn('static ail_st pfu_collatz(ail_ctx *cx, int64_t *out, int64_t pv_n)', c)
        self.assertIn('if (pv_n.tag == AIL_T_INT) {', c)          # the boxed body's entry guard
        self.assertIn('int64_t u_steps = 0;', c)
        self.assertIn('double u_acc = 0;', c)                    # mixed(): a float accumulator
        self.assertIn('int u_seen = 0;', c)                       # bools(): a bool
        self.assertEqual(stats['constants'], ['F', 'K'])
        self.assertNotIn('u_total', c.split('static ail_st pf_main(')[1].split('\n}\n')[0])  # json values stay boxed

    def test_u4_step2_programs(self):
        """Lists shared, changed, escaped, read out of range; tables changed through another name; the draws:
        forced onto the general path, the same bytes with and without AIL_UNIFIED=1, and CPython's."""
        forced = {'general': {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '1'}}
        with tempfile.TemporaryDirectory() as d:
            for name, text in STEP2.items():
                outs = {}
                for mode, env in forced.items():
                    r, exe = build(d, text, '%s_%s' % (name, mode), env)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    outs[mode] = run([str(exe)])
                self.assertEqual(outs['general'], outs['unified'], name)
                if ON_312:
                    src = Path(d, name + '_cpython.py')
                    src.write_text(text, encoding='utf-8')
                    self.assertEqual(run([sys.executable, str(src)])[:2], outs['unified'][:2], name)

    def test_u5_step2_plan(self):
        """The element types and the draws are proven where they should be, and nothing of them without the flag.

        This is the type-inference plan (the base behavior), so the unified build runs with AIL_BIGINT=off. On this
        branch the plan boxes an unproven int (BIGINT.md section 6): get() keeps its int index parameters as int64 but
        its list element, make()'s `r * n + c` and the random draws stay boxed, so the old `_uv` in-place forms are
        gone."""
        import json
        text = (STEP2['grid'].replace('\nmain()\n', '\n') + '\n'
                + STEP2['random'].replace('def main()', 'def main2()').replace('\nmain()\n', '\n')
                + '\nmain()\nmain2()\n')
        text = 'import random\n' + text.replace('import random\n', '')
        with tempfile.TemporaryDirectory() as d:
            cs = {}
            for mode, env in (('plain', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}),
                              ('unified', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '1', 'AIL_BIGINT': 'off',
                                           'AIL_UNIFIED_STATS': str(Path(d, 'stats.jsonl'))})):
                source = Path(d, 'p_%s.py' % mode)
                source.write_text(text, encoding='utf-8')
                envs = dict(os.environ)
                for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_UNIFIED_STATS'):
                    envs.pop(k, None)
                envs.update(env, AIL_NO_CACHE='1')
                r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                                    '--syntax', 'python', '-o', 'x_' + mode, '--debug-dir', 'd_' + mode], cwd=d,
                                   capture_output=True, text=True, timeout=900, env=envs)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                cs[mode] = Path(d, 'd_' + mode, 'program.c').read_text(encoding='utf-8')
            stats = json.loads(Path(d, 'stats.jsonl').read_text().splitlines()[-1])
        plain, c = cs['plain'], cs['unified']
        for form in ('_uv->p[', 'ail2r_rand(_urp', 'ail2r_gauss_u', 'for (int64_t _uvk'):
            self.assertNotIn(form, plain)
            self.assertNotIn(form, c)
        self.assertIn('static ail_st pfu_get(ail_ctx', c)
        self.assertNotIn('static ail_st pfu_get(ail_ctx', plain)
        self.assertIn('get', stats['specialised'])
        self.assertNotIn('get', stats['closed'])                 # the closed-list plan stays off for these shapes
        self.assertIn('random', stats['draws'])
        self.assertGreater(stats['typed_elements'], 0)
        get = c.split('static ail_st pfu_get(ail_ctx')[2].split('\n}\n')[0]
        head = get.split('\n')[0]
        self.assertIn('ail_obj *out', head)                      # g[r][c] is still an unproven int: boxed
        self.assertIn('int64_t pv_r', head)                      # the index parameters stay int64
        self.assertIn('int64_t pv_c', head)
        self.assertIn('ail_op_getitem', get)                     # the element read goes through the runtime

    def test_u6_step3_programs(self):
        """Tuples: pairs read in place, zip and enumerate loops, unpacking, tuples holding lists, the wrong shapes:
        forced onto the general path, the same bytes with and without AIL_UNIFIED=1 (and CPython's, where the
        general path itself agrees: its two message texts for a failed unpack and `+=` differ from CPython's)."""
        forced = {'general': {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '1'}}
        with tempfile.TemporaryDirectory() as d:
            for name, text in STEP3.items():
                outs = {}
                for mode, env in forced.items():
                    r, exe = build(d, text, '%s_%s' % (name, mode), env)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    outs[mode] = run([str(exe)])
                self.assertEqual(outs['general'], outs['unified'], name)
                if ON_312 and name in ('zip', 'enum'):
                    src = Path(d, name + '_cpython.py')
                    src.write_text(text, encoding='utf-8')
                    self.assertEqual(run([sys.executable, str(src)])[:2], outs['unified'][:2], name)

    def test_u7_step3_plan(self):
        """The unannotated tuple loops have unproven int locals, so the plan boxes them: the unified build is the
        general build's C, with none of the old in-place `_utk` loops."""
        text = STEP3['enum'].replace('\nmain()\n', '\n') + STEP3['zip'].replace('def main()', 'def main2()') \
            + '\nmain()\nmain2()\n'
        with tempfile.TemporaryDirectory() as d:
            cs = {}
            for mode, env in (('plain', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}),
                              ('unified', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '1'})):
                source = Path(d, 'p_%s.py' % mode)
                source.write_text(text, encoding='utf-8')
                envs = dict(os.environ)
                for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_UNIFIED_STATS'):
                    envs.pop(k, None)
                envs.update(env, AIL_NO_CACHE='1')
                r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                                    '--syntax', 'python', '-o', 'x_' + mode, '--debug-dir', 'd_' + mode], cwd=d,
                                   capture_output=True, text=True, timeout=900, env=envs)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                cs[mode] = Path(d, 'd_' + mode, 'program.c').read_text(encoding='utf-8')
        plain, c = cs['plain'], cs['unified']
        for form in ('for (int64_t _utk', 'a tuple component of another type than unified.py proved',
                     'for (int64_t _uvk', '_uv->p['):
            self.assertNotIn(form, plain)
            self.assertNotIn(form, c)
        # the unannotated tuple loops are boxed: no unboxed local; only the run-time changes every plan gets (section 15) differ
        sys.path[:0] = [str(PKG)]
        try:
            import safetyrt
            plain = safetyrt.patch_tuples(safetyrt.patch_sortprim(plain))
        finally:
            sys.path.remove(str(PKG))
        self.assertEqual(plain, c)
        self.assertIn('static ail_st pf_f(ail_ctx *cx, ail_obj *out, ail_obj pv_xs, ail_obj pv_ys)', c)
        self.assertIn('ail_iter_zip', c.split('static ail_st pf_f(ail_ctx')[-1].split('\n}\n')[0])

    def test_u8_bytearray_plan(self):
        """`b[i]` of a bytearray is read in C (exact prelude class, `_a` list, int index in range) only with the flag."""
        with tempfile.TemporaryDirectory() as d:
            cs = {}
            for mode, env in (('plain', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}),
                              ('unified', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '1'})):
                source = Path(d, 'p_%s.py' % mode)
                source.write_text(STEP3['bytes'], encoding='utf-8')
                envs = dict(os.environ)
                for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL', 'AIL_UNIFIED_STATS'):
                    envs.pop(k, None)
                envs.update(env, AIL_NO_CACHE='1')
                r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                                    '--syntax', 'python', '-o', 'x_' + mode, '--debug-dir', 'd_' + mode], cwd=d,
                                   capture_output=True, text=True, timeout=900, env=envs)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                cs[mode] = Path(d, 'd_' + mode, 'program.c').read_text(encoding='utf-8')
        self.assertNotIn('ail2u_ba_get(', cs['plain'])
        self.assertIn('ail2u_ba_get(', cs['unified'])


    def test_u9_identity(self):
        """C101: `is` / `is not` on a local that holds a number: the same answers as CPython's, with the flag."""
        with tempfile.TemporaryDirectory() as d:
            outs = {}
            for mode, env in {'general': {'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED': '1'},
                              'unified_force': {'AIL_UNIFIED': '1', 'AIL_UNIFIED_FORCE': '1'}}.items():
                r, exe = build(d, IDENT, 'ident_' + mode, env)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                outs[mode] = run([str(exe)])
            self.assertEqual(outs['general'], outs['unified'])
            self.assertEqual(outs['general'][:2], outs['unified_force'][:2])
            if ON_312:
                src = Path(d, 'ident_cpython.py')
                src.write_text(IDENT, encoding='utf-8')
                self.assertEqual(run([sys.executable, str(src)])[:2], outs['unified'][:2])


    def test_u10_palindrome(self):
        """Step 4: `s == s[::-1]` of a str is read in place (no reversed copy); a list, tuple, bytes, a number: the
        general path's own comparison. The same bytes as CPython's and as the general path's; the C changes only
        with the flag."""
        with tempfile.TemporaryDirectory() as d:
            outs = {}
            for mode, env in {'general': {'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED': '1'},
                              'unified_force': {'AIL_UNIFIED': '1', 'AIL_UNIFIED_FORCE': '1'}}.items():
                r, exe = build(d, PALIN, 'palin_' + mode, env)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                outs[mode] = run([str(exe)])
            self.assertEqual(outs['general'][:2], outs['unified'][:2])
            self.assertEqual(outs['general'][:2], outs['unified_force'][:2])
            if ON_312:
                src = Path(d, 'palin_cpython.py')
                src.write_text(PALIN, encoding='utf-8')
                cp = run([sys.executable, str(src)])
                self.assertEqual(cp[:2], outs['unified'][:2])
            # the fast path is emitted with the flag only
            for mode, env, want in (('off', {'AIL_UNIFIED': '0'}, False), ('on', {'AIL_UNIFIED': '1'}, True)):
                dbg = Path(d, 'dbg_' + mode)
                e = dict(os.environ)
                for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE'):
                    e.pop(k, None)
                e.update(env)
                e['AIL_NO_CACHE'] = '1'
                subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', 'palin_unified.py',
                                '--syntax', 'python', '-o', 'x_' + mode, '--debug-dir', str(dbg)],
                               cwd=d, capture_output=True, text=True, timeout=900, env=e)
                self.assertEqual('ail2u_palindrome' in Path(dbg, 'program.c').read_text(), want, mode)


    def test_u11_identity_mixed(self):
        """C102: `keep(x) is x`, `ident(x) is not x`, `a is b` in a typed function, values through a list, an
        attribute and a return (float, small int; an `is` on equal ints outside -5..256 is refused, C114): the same as CPython's in the default build, with AIL_NO_MIX=1
        and with the flag. A program with no number `is` keeps its typed clones (`__typed` in the C)."""
        plain = 'def half(n):\n    return n / 2\n\n\nD = {1: "a", "b": 2.5}\nprint(half(5), len(D))\n'
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, 'ident_mix_cpython.py')
            src.write_text(IDENT_MIX, encoding='utf-8')
            cp = run([sys.executable, str(src)]) if ON_312 else None
            outs = {}
            for mode, env in {'default': {}, 'nomix': {'AIL_NO_MIX': '1', 'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED': '1'}}.items():
                r, exe = build(d, IDENT_MIX, 'im_' + mode, env)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                outs[mode] = run([str(exe)])
                self.assertEqual(outs[mode][0], 0, outs[mode])
                if cp:
                    self.assertEqual(outs[mode][:2], cp[:2], mode)
            self.assertEqual(outs['default'][:2], outs['nomix'][:2])
            r, exe = build(d, plain, 'im_plain', {})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r2 = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', 'im_plain.py', '--syntax',
                                 'python', '-o', 'im_plain2', '--debug-dir', 'im_plain.d'], cwd=d, capture_output=True,
                                text=True, env=dict(os.environ, AIL_NO_CACHE='1'))
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            self.assertIn('__typed', ''.join(p.read_text(encoding='utf-8', errors='replace')
                                              for p in Path(d, 'im_plain.d').glob('*.c')))


    def test_u13_nan_identity(self):
        """C117: NaN held in a dataclass field, a list, a tuple or a dict key is one object in CPython, so the
        container `==`, `in` and dict lookup (which test `a is b` first) find it; an unboxed double would be boxed
        afresh at each store. A program that names nan / inf keeps its floats boxed under the flag."""
        text = NAN_ID
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, 'nan_id.py')
            src.write_text(text, encoding='utf-8')
            cp = run([sys.executable, str(src)]) if ON_312 else None
            outs = {}
            for mode in ('general', 'unified'):
                r, exe = build(d, text, 'nan_' + mode, MODES[mode])
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                outs[mode] = run([str(exe)])
            self.assertEqual(outs['general'][:2], outs['unified'][:2])
            if cp:
                self.assertEqual(outs['unified'][1].splitlines()[:2], cp[1].splitlines()[:2])


    def test_u12_gc_pool(self):
        """Step 5: the size-class free list under the collector (AIL_UNIFIED=1 with AIL_UNIFIED_POOL=1, not with threads): small strings,
        float boxes, dicts and lists over several collections print what CPython prints; the C has the pool only
        with the flag."""
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, 'pool_cpython.py')
            src.write_text(POOL, encoding='utf-8')
            cp = run([sys.executable, str(src)]) if ON_312 else None
            outs, cs = {}, {}
            for mode, env in {'plain': {'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED': '1', 'AIL_UNIFIED_POOL': '1'},
                              'nopool': {'AIL_UNIFIED': '1'}}.items():
                source = Path(d, 'pool_' + mode + '.py')
                source.write_text(POOL, encoding='utf-8')
                e = dict(os.environ, AIL_NO_CACHE='1')
                for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE'):
                    e.pop(k, None)
                e.update(env)
                r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                                    '--syntax', 'python', '-o', 'pool_' + mode, '--debug-dir', 'pool_' + mode + '.d'],
                                   cwd=d, capture_output=True, text=True, env=e, timeout=900)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                outs[mode] = run([str(Path(d, 'pool_' + mode))])
                cs[mode] = ''.join(p.read_text(encoding='utf-8', errors='replace')
                                   for p in sorted(Path(d, 'pool_' + mode + '.d').glob('*.c')))
            self.assertEqual(outs['plain'][0], 0, outs['plain'])
            self.assertEqual(outs['plain'][:2], outs['unified'][:2])
            if cp:
                self.assertEqual(cp[:2], outs['unified'][:2])
            self.assertNotIn('ail2u_pool', cs['plain'])
            self.assertIn('ail2u_pool', cs['unified'])
            self.assertNotIn('ail2u_pool', cs['nopool'])  # opt-in: +4% RSS geomean (up to +30%) for 1.045x
            self.assertEqual(outs['nopool'][:2], outs['unified'][:2])


    def test_u14_sort_tuples(self):
        """Step 6: a sort on float or int keys (natural merge sort on (key, index) records) and a tuple of up to 8 items in
        one allocation. Floats (ties, -0.0, inf, runs, descending), ints (int64 ends), reverse, mixed and generic keys, NaN
        (the old path, the same bytes as before), tuples of every size around the inline limit, growth, keys, GC. Same bytes as CPython
        (NaN: as the general path); the C has the fast paths with the plan only."""
        with tempfile.TemporaryDirectory() as d:
            res = {}
            for name, src in (('sortprim', SORTPRIM), ('tuples15', TUPLES15), ('sortnan', SORTNAN)):
                Path(d, name + '.py').write_text(src, encoding='utf-8')
                for mode, env in {'general': {'AIL_UNIFIED': '0'}, 'unified': {'AIL_UNIFIED': '1', 'AIL_UNIFIED_FORCE': '1'}}.items():
                    e = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                    for k in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE'):
                        e.pop(k, None)
                    e.update(env)
                    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', name + '.py', '--syntax', 'python',
                                        '-o', name + '_' + mode, '--debug-dir', name + '_' + mode + '.d'],
                                       cwd=d, capture_output=True, text=True, env=e, timeout=900)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    res[name, mode] = run([str(Path(d, name + '_' + mode))])
                    c = Path(d, name + '_' + mode + '.d', 'program.c').read_text(encoding='utf-8', errors='replace')
                    self.assertEqual('ail2u_sort_prim' in c, mode == 'unified', (name, mode))
                    self.assertEqual('ail2u_sort_prim' in c, 'ktmp = NULL' in c, (name, mode))
                self.assertEqual(res[name, 'general'][0], 0, res[name, 'general'])
                self.assertEqual(res[name, 'general'][:2], res[name, 'unified'][:2], name)
                if ON_312 and name != "sortnan":
                    cp = run([sys.executable, str(Path(d, name + '.py'))])
                    self.assertEqual(cp[:2], res[name, 'unified'][:2], name)


if __name__ == '__main__':
    unittest.main()
