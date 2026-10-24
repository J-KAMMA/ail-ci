"""Library batch 5: fractions, enum, namedtuple / NamedTuple / ChainMap, random.Random, keyword, calendar, abc, array,
io.StringIO, and the operator-method dispatch of the general path, each compared with CPython 3.12.

Three layers:

* the preludes (prelude_fraction.py, prelude_random.py) are plain Python, so they run under CPython next to
  fractions.Fraction and random.Random: tens of thousands of generated operations must agree, exceptions included;
* ordinary Python programs (below) are compiled with the Python syntax, once with the default build and once with
  AIL_IR=1, run on generated stdin, and must print the same bytes as CPython (and exit with the same status);
  keyword / calendar are also built by the typed path alone (AIL_NO_GENERAL=1) because both paths build them;
* programs that import none of the modules keep the text they have (stdlib5 returns the same string), and a
  general-path program without operator methods gets the runtime text it always had (no dunderrt patch).

The declared differences (DIFFERENCES.md C-series): int is 64-bit, so a Fraction beyond it is an OverflowError;
an IntEnum member is not an int (`isinstance(m, int)` is False); an abstract class can be instantiated; no
NotImplemented in operator methods.
"""
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROGRAMS = {}
PROGRAMS['f1'] = r"""from fractions import Fraction
import math
import sys


def show(label: str, x) -> None:
    print(label, x, repr(x))


def main() -> None:
    vals = [int(t) for t in sys.stdin.read().split()]
    fr = []
    i = 0
    while i + 1 < len(vals):
        d = vals[i + 1]
        if d == 0:
            d = 1
        fr.append(Fraction(vals[i], d))
        i += 2
    if len(fr) < 2:
        print("short")
        return
    total = sum(fr)
    show("sum", total)
    print(float(total), int(total), math.floor(total), math.ceil(total), round(total), round(total, 2), round(total, -1))
    print(min(fr), max(fr), sorted(fr)[0], sorted(fr, reverse=True)[0])
    for k in range(len(fr) - 1):
        a, b = fr[k], fr[k + 1]
        print(a, b, a + b, a - b, a * b, a == b, a != b, a < b, a <= b, a > b, a >= b)
        if b != 0:
            print(a / b, a // b, a % b)
        else:
            try:
                print(a / b)
            except ZeroDivisionError as e:
                print("ZeroDivisionError", e)
            try:
                print(a // b)
            except ZeroDivisionError:
                print("ZeroDivisionError")
        print(a ** 2, a ** 0, abs(a), -a, +a, bool(a), a * 3, 2 * a, a + 1, 1 - a, a / 3, a - 0.5, 0.25 + a)
        if a != 0:
            print(a ** -2, 3 / a, 7 // a, 7 % a)
        print(a.numerator, a.denominator, a.limit_denominator(7), a.limit_denominator(1), float(a))
        print(a == 2, a < 0.5, 3 > a, a >= 1, a.is_integer())
    counts = {}
    for f in fr:
        counts[f] = counts.get(f, 0) + 1
    for key in sorted(counts):
        print(key, counts[key])
    print(Fraction("3/4"), Fraction(" -7/21 "), Fraction("0.125"), Fraction("1e-3"), Fraction("+5"), Fraction(0.75), Fraction(5), Fraction(Fraction(3, 6)))
    print(Fraction(3, Fraction(6, 4)), Fraction(Fraction(1, 3), Fraction(2, 9)), Fraction(-3, -6), Fraction(3, -6))
    for bad in ["abc", "1/0", "", "1.2.3", "3/"]:
        try:
            print(Fraction(bad))
        except ValueError as e:
            print("ValueError", e)
        except ZeroDivisionError as e:
            print("ZeroDivisionError", e)
    try:
        print(Fraction(1, 0))
    except ZeroDivisionError as e:
        print("ZeroDivisionError", e)
    s = {Fraction(1, 2), Fraction(2, 4), Fraction(3, 4)}
    print(len(s), Fraction(1, 2) in s, Fraction(2) == 2, hash(Fraction(1, 2)) == hash(Fraction(2, 4)))
    print(f"{Fraction(7, 3)} {Fraction(7, 3)!r} {str(Fraction(6, 3))}")


main()
"""

PROGRAMS['e1'] = r"""from enum import Enum, IntEnum, StrEnum, auto, unique
import sys


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
    CRIMSON = 1

    def describe(self) -> str:
        return self.name.lower() + ":" + str(self.value)


class Level(IntEnum):
    LOW = 1
    MID = 5
    HIGH = 10


class Mode(StrEnum):
    FAST = auto()
    SLOW = auto()


class Auto(Enum):
    A = auto()
    B = auto()
    C = auto()


class Planet(Enum):
    MERCURY = (3.3e23, 2.44e6)
    EARTH = (5.97e24, 6.37e6)


def pick(n: int) -> Color:
    return Color(n)


def main() -> None:
    for tok in sys.stdin.read().split():
        try:
            c = Color(int(tok))
            lv = Level(int(tok))
            print(tok, c, c.name, lv, repr(lv))
        except ValueError as e:
            print("ValueError", e)
    print(Color.RED, repr(Color.GREEN), Color.CRIMSON is Color.RED, Color.CRIMSON.name)
    print([c.name for c in Color], list(Color)[1], len(Color))
    print(pick(2).describe(), Color["BLUE"].value, Color.RED == Color.RED, Color.RED != Color.BLUE)
    print(Color.__members__["CRIMSON"], list(Color.__members__))
    try:
        Color(9)
    except ValueError as e:
        print("ValueError", e)
    try:
        Color["NOPE"]
    except KeyError as e:
        print("KeyError", e)
    d = {Color.RED: "r", Color.BLUE: "b"}
    print(d[Color.RED], Color.GREEN in d, Color.BLUE in d, len({Color.RED, Color.CRIMSON, Color.GREEN}))
    print(f"{Color.RED} {Color.RED!r} {Level.MID} {Level.MID!r} {Mode.FAST} {Mode.SLOW!r}")
    print(Level.LOW < Level.HIGH, Level.MID == 5, Level.HIGH + 1, int(Level.MID), max(Level), sorted([Level.HIGH, Level.LOW]))
    print(sum(l.value for l in Level), Level(5).name, Level.HIGH > 3, 3 < Level.HIGH, bool(Level.LOW))
    print(Mode.FAST == "fast", Mode.SLOW.value, str(Mode.FAST), Mode("slow").name, Mode.FAST + "!")
    print(Auto.A.value, Auto.B.value, Auto.C.value, Auto(2))
    print(Planet.EARTH.value[0], Planet.MERCURY.name, Planet((3.3e23, 2.44e6)))
    n = 0
    for c in Color:
        n += c.value
    print(n, Color.RED in Color, isinstance(Color.RED, Color), isinstance(Level.LOW, Level))
    print(sorted(Color, key=lambda c: -c.value)[0], max(Color, key=lambda c: c.value))
    m = {c: i for i, c in enumerate(Color)}
    print(m[Color.GREEN], [str(x) for x in Level], [x.value for x in Mode])


main()
"""

PROGRAMS['nt1'] = r"""from collections import namedtuple, ChainMap, defaultdict
from typing import NamedTuple
import sys

Point = namedtuple("Point", ["x", "y"])
Rec = namedtuple("Rec", "name score tag", defaults=["none"])


class Item(NamedTuple):
    name: str
    qty: int
    price: float = 1.5

    def total(self) -> float:
        return self.qty * self.price

    def label(self) -> str:
        return self.name.upper() + "#" + str(self.qty)


class Pt3(namedtuple("Pt3", "a b c")):
    def norm1(self) -> int:
        return abs(self.a) + abs(self.b) + abs(self.c)


def main() -> None:
    rows = [line.split() for line in sys.stdin.read().splitlines() if line.strip()]
    pts = [Point(int(r[0]), int(r[1])) for r in rows]
    print(pts[0], repr(pts[-1]), len(pts), pts[0].x + pts[0].y, pts[0][1], pts[0][-1])
    x, y = pts[0]
    print(x, y, tuple(pts[0]), list(pts[0]), pts[0] == Point(x, y), pts[0] == (x, y), pts[0] != pts[1])
    print(sorted(pts)[:3], max(pts), min(pts), max(pts, key=lambda p: p.y))
    print(pts[0]._asdict(), pts[0]._replace(x=99), Point._fields, Point._make([7, 8]))
    seen = {}
    for p in pts:
        seen[p] = seen.get(p, 0) + 1
    print(len(seen), sum(seen.values()), Point(1, 2) in seen)
    for a, b in pts[:3]:
        print(a * b, end=" ")
    print()
    recs = [Rec(r[2], int(r[0])) for r in rows] + [Rec("zed", 5, "t")]
    print(recs[0], recs[-1], recs[0].tag, recs[-1].tag, sorted(recs, key=lambda r: (-r.score, r.name))[0])
    items = [Item(r[2], int(r[0]), float(r[1])) for r in rows]
    items.append(Item("plain", 3))
    print(items[0], items[-1], items[0].total(), items[-1].total(), items[1].label())
    print(sum(it.total() for it in items), [it.qty for it in items if it.qty > 0][:4])
    best = max(items, key=lambda it: it.total())
    print(best.name, best._replace(qty=1), best == best._replace(), best._asdict())
    q = Pt3(1, -2, 3)
    print(q, q.norm1(), q[2], len(q), q.count(-2), q.index(3), q + (4,) if False else "skip")
    print(isinstance(q, Pt3), isinstance(q, Point), Pt3._fields)
    base = {"a": 1, "b": 2}
    over = {"b": 20, "c": 30}
    cm = ChainMap(over, base)
    print(cm["a"], cm["b"], cm["c"], cm.get("z", -1), "a" in cm, "z" in cm, len(cm), list(cm), list(cm.items()))
    cm["new"] = 5
    print(over, base, cm.maps, dict(cm))
    child = cm.new_child({"a": 100})
    print(child["a"], child["b"], len(child.maps), child.parents["a"], repr(cm))
    del cm["new"]
    print(over, cm.pop("c"), over)
    try:
        cm["nope"]
    except KeyError as e:
        print("KeyError", e)
    try:
        del cm["a"]
    except KeyError as e:
        print("KeyError", e)


main()
"""

PROGRAMS['r1'] = r"""import random
import sys


def roll(rng: random.Random, n: int) -> int:
    return rng.randint(1, n)


class Sim:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.hits = 0

    def step(self) -> int:
        v = self.rng.randrange(0, 100, 7)
        if v > 40:
            self.hits += 1
        return v


def main() -> None:
    seeds = [int(t) for t in sys.stdin.read().split()]
    for seed in seeds:
        rng = random.Random(seed)
        print(seed, rng.random(), rng.randint(-5, 5), rng.randrange(10), rng.randrange(3, 40, 4), rng.getrandbits(7), rng.getrandbits(40))
        items = list(range(12))
        rng.shuffle(items)
        print(items, rng.choice(items), rng.sample(items, 4), rng.sample(range(200), 30)[:6])
        print(rng.uniform(1.5, 9.5), rng.gauss(0.0, 1.0), rng.gauss(10, 2), rng.choices(items, k=5), rng.choices("abc", weights=[1, 5, 2], k=6))
        print(rng.expovariate(2.0), rng.triangular(0.0, 10.0, 3.0), roll(rng, 6), rng.sample("hello world", 3))
        other = random.Random(seed + 1)
        mix = [rng.random() < 0.5 for _ in range(5)] + [other.randint(1, 3) for _ in range(5)]
        print(mix, rng.random() == other.random())
        rng.seed(seed * 3)
        print(rng.randint(0, 10 ** 9), other.getrandbits(32))
        sim = Sim(seed)
        print([sim.step() for _ in range(8)], sim.hits)
        try:
            rng.randrange(5, 5)
        except ValueError as e:
            print("ValueError", e)
        try:
            rng.choice([])
        except IndexError as e:
            print("IndexError", e)
        try:
            rng.sample([1, 2], 5)
        except ValueError as e:
            print("ValueError", e)
    random.seed(7)
    print(random.random(), random.randint(1, 100))
    r2 = random.Random(7)
    print(r2.random(), r2.randint(1, 100))


main()
"""

PROGRAMS['k1'] = r"""import calendar
import keyword
import sys
from abc import ABC, abstractmethod
from array import array
import io
import csv


class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        ...

    def describe(self) -> str:
        return type(self).__name__ + ":" + str(self.area())


class Sq(Shape):
    def __init__(self, s: float) -> None:
        self.s = s

    def area(self) -> float:
        return self.s * self.s


class Rc(Shape):
    def __init__(self, w: float, h: float) -> None:
        self.w, self.h = w, h

    def area(self) -> float:
        return self.w * self.h


def main() -> None:
    toks = sys.stdin.read().split()
    for w in toks:
        if keyword.iskeyword(w):
            print(w, "keyword", keyword.issoftkeyword(w))
        elif keyword.issoftkeyword(w):
            print(w, "soft")
        else:
            print(w, w.isidentifier())
    print(len(keyword.kwlist), keyword.kwlist[:4], keyword.softkwlist)
    years = [int(t) for t in toks if t.isdigit()]
    for y in years[:6]:
        print(y, calendar.isleap(y), calendar.monthrange(y, 2), calendar.leapdays(y, y + 20), calendar.weekday(y, 3, 14))
        for m in (1, 2, 12):
            print(calendar.monthrange(y, m)[1], calendar.month_name[m], calendar.month_abbr[m], end="; ")
        print()
    print(calendar.day_name[0], list(calendar.day_abbr), calendar.month_name[1:3], calendar.MONDAY, calendar.SUNDAY)
    if years:
        print(calendar.monthcalendar(years[0], 2))
        print(calendar.month(years[0], 5))
        calendar.prmonth(years[0], 12)
        print(calendar.month(years[0], 2, 3, 1))
    try:
        calendar.monthrange(2020, 13)
    except ValueError as e:
        print("ValueError", e)
    shapes = [Sq(2.0), Rc(2.0, 3.5)]
    print([s.describe() for s in shapes], sum(s.area() for s in shapes))
    a = array("i", years[:5])
    a.append(7)
    a.extend([1, 2])
    print(a, a.typecode, a.itemsize, len(a), a[0], a[-1], sum(a), a.tolist(), max(a), 7 in a)
    a.reverse()
    last = a.pop()
    asl = list(a)
    print(last, a.index(7), a.count(7), asl)
    d = array("d", [1.5, 2])
    print(d, d.itemsize)
    try:
        array("b", [300])
    except OverflowError as e:
        print("OverflowError", e)
    try:
        array("i", [1.5])
    except TypeError as e:
        print("TypeError", e)
    buf = io.StringIO()
    buf.write("one\ntwo\n")
    print("three", 3, file=buf)
    buf.write("four")
    print(repr(buf.getvalue()), buf.tell())
    buf.seek(0)
    print(buf.readline(), buf.read(3), buf.readlines())
    for line in io.StringIO("x\ny\nz"):
        print(repr(line), end=" ")
    print()
    rows = list(csv.DictReader(io.StringIO("a,b\n1,2\n3,4\n")))
    print(rows, [r["b"] for r in rows])
    for r in csv.reader(io.StringIO("p,q\n\"x,y\",z\n")):
        print(r)


main()
"""

PROGRAMS['d1'] = r"""import sys


class Vec:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __add__(self, o):
        return Vec(self.x + o.x, self.y + o.y)

    def __sub__(self, o):
        return Vec(self.x - o.x, self.y - o.y)

    def __mul__(self, k):
        return Vec(self.x * k, self.y * k)

    def __rmul__(self, k):
        return Vec(self.x * k, self.y * k)

    def __neg__(self):
        return Vec(-self.x, -self.y)

    def __abs__(self):
        return self.x * self.x + self.y * self.y

    def __eq__(self, o):
        return self.x == o.x and self.y == o.y

    def __lt__(self, o):
        return (self.x, self.y) < (o.x, o.y)

    def __hash__(self):
        return hash((self.x, self.y))

    def __bool__(self):
        return self.x != 0 or self.y != 0

    def __len__(self):
        return 2

    def __getitem__(self, i):
        if i == 0:
            return self.x
        if i == 1:
            return self.y
        raise IndexError("Vec index out of range")

    def __contains__(self, v):
        return v == self.x or v == self.y

    def __repr__(self):
        return "Vec(%d, %d)" % (self.x, self.y)

    def __radd__(self, o):
        return self if o == 0 else self + o

    def __floordiv__(self, k):
        return Vec(self.x // k, self.y // k)

    def __mod__(self, k):
        return Vec(self.x % k, self.y % k)

    def __int__(self):
        return self.x

    def __float__(self):
        return float(self.y)


class Grid:
    def __init__(self) -> None:
        self.cells = {}

    def __setitem__(self, k, v):
        self.cells[k] = v

    def __getitem__(self, k):
        return self.cells[k]

    def __delitem__(self, k):
        del self.cells[k]

    def __len__(self):
        return len(self.cells)

    def __contains__(self, k):
        return k in self.cells


def main() -> None:
    nums = [int(t) for t in sys.stdin.read().split()]
    vs = [Vec(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
    a, b = vs[0], vs[1]
    print(a + b, a - b, a * 3, 2 * a, -a, abs(a), a == b, a != b, a < b, a > b)
    print(sum(vs), sorted(vs)[0], max(vs), min(vs), bool(a), bool(Vec(0, 0)), len(a), a[0], a[1], 3 in a, 99 in a)
    d = {}
    for v in vs:
        d[v] = d.get(v, 0) + 1
    print(len(d), len(set(vs)), a in d, Vec(12345, 6) in d, d[a])
    print(a // 2, a % 3, int(a), float(a), [v.x for v in vs if v], [v for v in vs if not v])
    print(a is a, a == a, vs.index(b), vs.count(a), a in vs)
    g = Grid()
    g["k"] = 1
    g[a] = 2
    print(g["k"], g[a], len(g), "k" in g, "z" in g, bool(g))
    del g["k"]
    print(len(g), "k" in g)
    try:
        a[5]
    except IndexError as e:
        print("IndexError", e)
    try:
        a + 1
    except AttributeError as e:
        print("AttributeError")


main()
"""

PROGRAMS['ty1'] = r"""import calendar
import keyword
import sys


def main() -> None:
    for w in sys.stdin.read().split():
        if keyword.iskeyword(w):
            print(w, "keyword")
        elif keyword.issoftkeyword(w):
            print(w, "soft")
        elif w.isdigit():
            y = int(w)
            m = y % 12 + 1
            print(y, calendar.isleap(y), calendar.monthrange(y, m)[0], calendar.monthrange(y, m)[1],
                  calendar.leapdays(y - 30, y), calendar.month_name[m], calendar.month_abbr[m])
            weeks = calendar.monthcalendar(y, m)
            print(len(weeks), sum(weeks[0]), sum(weeks[-1]), weeks[1][3])
            print(calendar.month(y, m))
        else:
            print(w, w.isalpha())
    print(len(keyword.kwlist), keyword.kwlist[0], keyword.kwlist[-1], len(keyword.softkwlist))


main()
"""

PROGRAMS['o1'] = r"""import csv
import io
import sys
from collections import OrderedDict


class LRU:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.data: OrderedDict[str, int] = OrderedDict()
        self.misses = 0

    def put(self, key: str, value: int) -> None:
        if key in self.data:
            self.data.move_to_end(key)
        self.data[key] = value
        if len(self.data) > self.capacity:
            evicted = self.data.popitem(last=False)
            print("evict", evicted[0], evicted[1])

    def get(self, key: str) -> int:
        if key not in self.data:
            self.misses += 1
            return -1
        self.data.move_to_end(key)
        return self.data[key]


class Num:
    def __init__(self, v: int) -> None:
        self.v = v

    def __pos__(self):
        return Num(self.v + 100)

    def __neg__(self):
        return Num(-self.v)

    def __repr__(self):
        return "Num(%d)" % self.v


def main() -> None:
    cache = LRU(3)
    for tok in sys.stdin.read().split():
        if tok.startswith("g"):
            print("get", tok[1:], cache.get(tok[1:]))
        else:
            cache.put(tok, len(tok))
    print(cache.data, len(cache.data), list(cache.data.items()), cache.misses)
    cache.data.move_to_end(next(iter(cache.data)), last=False)
    print(list(cache.data), cache.data.popitem(), repr(OrderedDict()), +Num(1), -Num(2), +5, +True)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["a", "b c", 'q"r', 3])
    w.writerows([[1, 2], ["x,y", ""]])
    dw = csv.DictWriter(out, fieldnames=["k", "v"])
    dw.writeheader()
    dw.writerow({"k": "z", "v": 9})
    text = out.getvalue()
    print(repr(text), text.count("\n"))


main()
"""

PROGRAMS['st3'] = r"""import statistics
import sys


def main() -> None:
    fs: list[float] = [float(t) for t in sys.stdin.read().split()]
    ys: list[int] = [int(x * 4) for x in fs]
    print(statistics.median(fs), statistics.median_low(fs), statistics.median_high(fs))
    print(statistics.mode(fs), len(statistics.multimode(fs)), statistics.fmean(fs))
    modes = statistics.multimode(fs)
    print(" ".join([str(m) for m in modes]))
    print(statistics.median(ys), statistics.median_low(ys), statistics.mode(ys), statistics.fmean(ys))
    print(statistics.stdev(ys), statistics.pstdev(ys), statistics.variance(ys), statistics.mean(ys))
    print(f"{statistics.median(fs):.3f} {statistics.mean(ys):.3f}")
    empty: list[float] = []
    try:
        print(statistics.median(empty))
    except statistics.StatisticsError:
        print("StatisticsError")


main()
"""

PROGRAMS['idn'] = r"""import sys


class Color:
    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return "<Color.%s: %d>" % (self.name, self.value)

    def __str__(self) -> str:
        return "Color." + self.name


class A:
    def __init__(self, v: int) -> None:
        self.v = v

    def __str__(self) -> str:
        return "a"


class B(A):
    def __repr__(self) -> str:
        return "b"


class V:
    def __init__(self, x: int) -> None:
        self.x = x

    def f(self, o):
        return self.x + o.x


RED = Color("RED", 1)
GREEN = Color("GREEN", 2)


def nxt(c: Color) -> Color:
    if c is RED:
        return GREEN
    return RED


def main() -> None:
    n = int(sys.stdin.read().split()[0])
    c = RED
    for i in range(n):
        c = nxt(c)
        print(c, repr(c), c.name, c.value, c == RED, c is GREEN, c != GREEN)
    d = {RED: 1, GREEN: 2}
    print(d[RED], d[c], RED in d, len({RED, GREEN, c}), [RED, GREEN].index(c), c in [GREEN])
    items = [B(1), A(2)]
    print(items[0], items[1], "%s|%r" % (items[0], items[0]), str(items[0]))
    v = V(1)
    try:
        print(v.f(3))
    except AttributeError:
        print("AttributeError")
    print(v.f(V(4)), bool(v), not v, 1 if v else 0)


main()
"""


def numbers(rnd, count, lo, hi):
    return " ".join(str(rnd.randint(lo, hi)) for _ in range(count)) + "\n"


def fraction_inputs():
    out = []
    for seed in (3, 11, 29, 41):
        rnd = random.Random(seed)
        toks = []
        for _ in range(rnd.randint(2, 8)):
            toks += [rnd.randint(-100, 100), rnd.choice([1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 0, -3])]
        out.append(" ".join(map(str, toks)) + "\n")
    out.append("1 2 3 4\n")
    return out


def enum_inputs():
    return ["1 2 5 3 10 7 1\n", "3 3 3\n", "\n"]


def namedtuple_inputs():
    out = []
    for seed in (4, 7, 19):
        rnd = random.Random(seed)
        rows = ["%d %s %s" % (rnd.randint(-9, 9), rnd.choice(["1.5", "2.25", "0.5", "4.0"]),
                              rnd.choice(["pear", "fig", "plum", "kiwi", "lime"])) for _ in range(rnd.randint(3, 10))]
        out.append("\n".join(rows) + "\n")
    return out


def random_inputs():
    out = []
    for seed in (5, 6):
        rnd = random.Random(seed)
        out.append(" ".join(str(rnd.choice([0, 1, 2, 3, -7, 42, 12345, 2 ** 33 + 5, 99999999, rnd.randint(-10 ** 9, 10 ** 9)]))
                            for _ in range(6)) + "\n")
    out.append("2024 -1 31337\n")
    return out


def small_inputs():
    return ["for def foo if match case type _ 2000 1900 2024 2023 None True x1 9a class lambda import\n",
            "1 400 9999 12 not async await\n", "2100 2096 1 3\n"]


def ordered_inputs():
    return ["a b c g a d g b e g z f\n", "x y z w g x ga gb\n", "\n"]


def float_stat_inputs():
    out = []
    for seed in (21, 22, 23):
        rnd = random.Random(seed)
        out.append(" ".join(rnd.choice(["0.5", "1.25", "2.0", "3.75", "4.0", "-1.5", "10.25"])
                            for _ in range(rnd.randint(1, 14))) + "\n")
    return out


def dunder_inputs():
    out = []
    for seed in (8, 9, 10):
        rnd = random.Random(seed)
        nums = [rnd.randint(-9, 9) for _ in range(rnd.randint(4, 7) * 2)]
        nums[4:6] = nums[0:2]
        out.append(" ".join(map(str, nums)) + "\n")
    return out


CASES = [
    ("fraction", PROGRAMS["f1"], fraction_inputs),
    ("enum", PROGRAMS["e1"], enum_inputs),
    ("namedtuple_chainmap", PROGRAMS["nt1"], namedtuple_inputs),
    ("random", PROGRAMS["r1"], random_inputs),
    ("small_modules", PROGRAMS["k1"], small_inputs),
    ("operator_methods", PROGRAMS["d1"], dunder_inputs),
    ("ordereddict_csv_stringio", PROGRAMS["o1"], ordered_inputs),
    ("statistics_floats", PROGRAMS["st3"], float_stat_inputs),
    ("identity_str_attribute", PROGRAMS["idn"], lambda: ["1\n", "4\n", "0\n"]),
]
TYPED = ("keyword_calendar", PROGRAMS["ty1"], small_inputs)


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


class PreludeFraction(unittest.TestCase):
    """prelude_fraction.py (the code the compiler adds) against fractions.Fraction."""

    def test_matches_fractions(self):
        import fractions
        import prelude_fraction as P
        F = fractions.Fraction
        rnd = random.Random(5)

        def pair(x):
            return (x.numerator, x.denominator)

        for _ in range(4000):
            n = rnd.randint(-10 ** rnd.randint(1, 18), 10 ** rnd.randint(1, 18))
            d = rnd.randint(1, 10 ** rnd.randint(1, 18))
            self.assertEqual(P._ail_fr_to_float(n, d), n / d, (n, d))
        for _ in range(1500):
            s = rnd.choice(["3/4", " -3/4 ", "0.75", "1e3", "-2.5e-2", "1_000/3", "+7", ".5", "5.", "1/0", "abc", "1/",
                            "/2", "1.2.3", "", "1e", "-", "3 /4", "3/ 4", "1_/2", "1__0", "0.0", "00012/00030", "1E2",
                            "2.50E+1", "12e-2", "1 2", "- 1"])
            got = want = None
            try:
                got = pair(P.Fraction(s))
            except Exception as e:
                got = (type(e).__name__, str(e))
            try:
                want = pair(F(s))
            except Exception as e:
                want = (type(e).__name__, str(e))
            self.assertEqual(got, want, s)
        for x in (0.1, 0.5, 2.5, -3.75, 1e-5, 123456.789, 0.3333333333333333, 1e10, -0.0, 7.0, 1e300, float("inf")):
            got = want = None
            try:
                got = pair(P.Fraction(x))
            except OverflowError:
                got = "overflow"
            try:
                want = pair(F(x))
            except OverflowError:
                want = "overflow"
            if got != "overflow":
                self.assertEqual(got, want, x)
        ops = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a / b,
               "//": lambda a, b: a // b, "%": lambda a, b: a % b, "**": lambda a, b: a ** b}

        def operand(kind):
            if kind == "f":
                n, d = rnd.randint(-30, 30), rnd.randint(1, 20)
                return P.Fraction(n, d), F(n, d)
            if kind == "i":
                k = rnd.randint(-6, 6)
                return k, k
            x = rnd.choice([0.5, -1.25, 2.0, 0.0, 3.5, 1e-3])
            return x, x
        for _ in range(8000):
            ka, kb = rnd.choice("ffi"), rnd.choice("fif")
            if rnd.random() < 0.15:
                kb = "x"
            if rnd.random() < 0.15:
                ka = "x"
            if (ka == "i" and kb != "f") or (ka == "x" and kb == "x"):
                continue
            (pa, qa), (pb, qb) = operand(ka), operand(kb)
            op = rnd.choice(list(ops))
            try:
                rp = ops[op](pa, pb)
            except Exception as e:
                rp = ("EXC", type(e).__name__)
            try:
                rq = ops[op](qa, qb)
            except Exception as e:
                rq = ("EXC", type(e).__name__)
            if isinstance(rp, tuple) or isinstance(rq, tuple):
                self.assertEqual(rp, rq, (op, pa, pb))
                continue
            if isinstance(rp, P.Fraction):
                self.assertEqual(pair(rp), pair(rq), (op, str(pa), str(pb)))
            else:
                self.assertEqual((type(rp), rp), (type(rq), rq), (op, pa, pb))
            for c in ("<", "<=", ">", ">=", "==", "!="):
                try:
                    x1 = eval("pa %s pb" % c)
                except Exception as e:
                    x1 = type(e).__name__
                try:
                    x2 = eval("qa %s qb" % c)
                except Exception as e:
                    x2 = type(e).__name__
                self.assertEqual(x1, x2, (c, pa, pb))
        for _ in range(3000):
            n, d = rnd.randint(-10 ** 6, 10 ** 6), rnd.randint(1, 10 ** 6)
            p, q = P.Fraction(n, d), F(n, d)
            def norm(items):
                return [pair(i) if hasattr(i, "numerator") and hasattr(i, "denominator") and not isinstance(i, int) else i
                        for i in items]
            self.assertEqual(norm((float(p), int(p), math.floor(p), math.ceil(p), round(p), round(p, 2), round(p, -1), str(p), repr(p), bool(p))),
                             norm((float(q), int(q), math.floor(q), math.ceil(q), round(q), round(q, 2), round(q, -1), str(q), repr(q), bool(q))))
            m = rnd.choice([1, 7, 100, 1000, 10 ** 6])
            self.assertEqual(pair(p.limit_denominator(m)), pair(q.limit_denominator(m)), (n, d, m))


class PreludeRandom(unittest.TestCase):
    """prelude_random.py against random.Random: the same draws for the same seed."""

    def test_matches_random(self):
        import prelude_random as P
        P.math = math
        rnd = random.Random(11)
        seeds = [0, 1, 2, 42, -1, -42, 12345, 2 ** 31, 2 ** 32, 2 ** 32 + 7, 2 ** 40 + 5, 2 ** 62 + 1, -(2 ** 50), 7919]
        seeds += [rnd.randint(-10 ** 15, 10 ** 15) for _ in range(12)]
        for seed in seeds:
            a, b = P.Random(seed), random.Random(seed)
            for step in range(250):
                op = rnd.choice(["random", "randint", "randrange", "randrange3", "choice", "shuffle", "sample", "uniform",
                                 "gauss", "bits", "choices", "wchoices", "expo", "tri"])
                if op == "random":
                    x, y = a.random(), b.random()
                elif op == "randint":
                    lo = rnd.randint(-100, 100)
                    hi = lo + rnd.randint(0, 10 ** rnd.randint(1, 12))
                    x, y = a.randint(lo, hi), b.randint(lo, hi)
                elif op == "randrange":
                    n = rnd.randint(1, 10 ** rnd.randint(1, 15))
                    x, y = a.randrange(n), b.randrange(n)
                elif op == "randrange3":
                    lo, hi, st = rnd.randint(-50, 50), rnd.randint(-50, 200), rnd.choice([1, 2, 3, -1, -3, 7, 0])
                    try:
                        y = b.randrange(lo, hi, st)
                    except Exception as e:
                        y = (type(e).__name__, str(e))
                    try:
                        x = a.randrange(lo, hi, st)
                    except Exception as e:
                        x = (type(e).__name__, str(e))
                elif op == "choice":
                    seq = [rnd.randint(0, 99) for _ in range(rnd.randint(1, 30))]
                    x, y = a.choice(seq), b.choice(seq)
                elif op == "shuffle":
                    seq = list(range(rnd.randint(0, 40)))
                    s1, s2 = list(seq), list(seq)
                    a.shuffle(s1)
                    b.shuffle(s2)
                    x, y = s1, s2
                elif op == "sample":
                    n = rnd.randint(0, 120)
                    k = rnd.randint(0, n)
                    pop = [rnd.randint(0, 999) for _ in range(n)]
                    x, y = a.sample(pop, k), b.sample(pop, k)
                elif op == "uniform":
                    x, y = a.uniform(-3.5, 17.25), b.uniform(-3.5, 17.25)
                elif op == "gauss":
                    x, y = a.gauss(2.0, 3.0), b.gauss(2.0, 3.0)
                elif op == "bits":
                    k = rnd.randint(1, 62)
                    x, y = a.getrandbits(k), b.getrandbits(k)
                elif op == "choices":
                    pop = [rnd.randint(0, 9) for _ in range(rnd.randint(1, 20))]
                    k = rnd.randint(1, 10)
                    x, y = a.choices(pop, k=k), b.choices(pop, k=k)
                elif op == "wchoices":
                    n = rnd.randint(1, 15)
                    w = [rnd.randint(1, 9) for _ in range(n)]
                    k = rnd.randint(1, 8)
                    x, y = a.choices(list(range(n)), w, k=k), b.choices(list(range(n)), w, k=k)
                elif op == "expo":
                    x, y = a.expovariate(1.5), b.expovariate(1.5)
                else:
                    x, y = a.triangular(1.0, 9.0, 3.0), b.triangular(1.0, 9.0, 3.0)
                self.assertEqual((type(x), x), (type(y), y), (seed, step, op))
        for args in [(0,), (-3,), (5, 5), (5, 1), (0, 10, 0), (0, 10, -1), (10, 0, -3)]:
            r1 = r2 = None
            try:
                P.Random(1).randrange(*args)
            except Exception as e:
                r1 = (type(e).__name__, str(e))
            try:
                random.Random(1).randrange(*args)
            except Exception as e:
                r2 = (type(e).__name__, str(e))
            self.assertEqual(r1, r2, args)
        for f, args in (("choice", ([],)), ("sample", ([1, 2], 3)), ("sample", ([1, 2], -1))):
            r1 = r2 = None
            try:
                getattr(P.Random(1), f)(*args)
            except Exception as e:
                r1 = (type(e).__name__, str(e))
            try:
                getattr(random.Random(1), f)(*args)
            except Exception as e:
                r2 = (type(e).__name__, str(e))
            self.assertEqual(r1, r2, (f, args))


class StatisticsFloats(unittest.TestCase):
    """The float forms of strt.py (median, median_low, median_high, mode, multimode) against the statistics module."""

    def test_matches_statistics(self):
        import statistics
        import strt
        rnd = random.Random(2)
        for _ in range(3000):
            xs = [rnd.choice([0.5, 1.0, 2.25, -3.5, 7.0, 1e-3, 100.0, -0.0, 0.0, rnd.uniform(-5, 5)])
                  for _ in range(rnd.randint(1, 30))]
            for mine, ref in ((strt.median_f, statistics.median), (strt.median_low_f, statistics.median_low),
                              (strt.median_high_f, statistics.median_high), (strt.mode_f, statistics.mode),
                              (strt.multimode_f, statistics.multimode)):
                got, want = mine(list(xs)), ref(list(xs))
                self.assertEqual((type(got), got), (type(want), want), (mine.__name__, xs))
        for mine in (strt.median_f, strt.median_low_f, strt.median_high_f, strt.mode_f):
            with self.assertRaises(ValueError):
                mine([])
        self.assertEqual(strt.multimode_f([]), [])


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, inputs, ir, **env):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(env, AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))], input=stdin.encode(),
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, "%s input %d: %s" % (name, k, got.stderr[-300:]))
                if got.stdout != want.stdout:
                    a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                    for n, (x, y) in enumerate(zip(a, b)):
                        if x != y:
                            self.fail("%s input %d (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r" % (name, k, env["AIL_IR"], n + 1, x, y))
                    self.fail("%s input %d: %d lines against %d" % (name, k, len(a), len(b)))

    def test_programs_match_cpython(self):
        for name, text, inputs in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, inputs(), ir)

    def test_typed_path_builds_keyword_and_calendar(self):
        name, text, inputs = TYPED
        data = ["for 2000 1999 match foo 2024 type 1 9999 400\n", "2100 x 1900 def\n"]
        for ir in (False, True):
            with self.subTest(path="typed", ir=ir):
                self.check(name, text, data, ir, AIL_NO_GENERAL="1")
            with self.subTest(path="default", ir=ir):
                self.check(name, text, data, ir)


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        cases = {
            "decimal": ("from decimal import Decimal\n\nprint(Decimal('1.10') + Decimal('2.20'))\n", "decimal"),
            "flag": ("from enum import Flag\n\nclass P(Flag):\n    A = len('ab')\n\nprint(P.A)\n", "Flag member"),
            "mixin": ("from enum import Enum\n\nclass P(str, Enum):\n    A = 'a'\n\nprint(P.A)\n", "mixed-in"),
            "unseeded": ("import random\n\nr = random.Random()\nprint(r.random())\n", "seed"),
            "rename": ("from collections import namedtuple\n\nP = namedtuple('P', 'x y', rename=True)\nprint(P(1, 2))\n", "namedtuple"),
            "calendar": ("import calendar\n\nprint(calendar.calendar(2024))\n", "calendar.calendar"),
            "bytesio": ("import io\n\nb = io.BytesIO(b'x')\nprint(b.read())\n", "io.BytesIO"),
        }
        for name, (text, wanted) in cases.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    PLAIN = [
        "import sys\n\nfor i, line in enumerate(sys.stdin):\n    print(i, line.strip())\n",
        "import string\nimport sys\n\nprint(string.ascii_lowercase[:3])\n",
        "import random\n\nrandom.seed(3)\nprint(random.randint(1, 6))\n",
        "from collections import Counter, deque\n\nc = Counter('abca')\nprint(c)\nprint(deque([1]))\n",
        "class P:\n    def __init__(self, x: int) -> None:\n        self.x = x\n\nprint(P(3).x)\n",
        "# mentions fractions and enum and namedtuple only in a comment\nprint(1)\n",
    ]

    def test_other_programs_keep_their_text(self):
        import stdlib5
        for text in self.PLAIN:
            with self.subTest(text[:30]):
                notes = []
                self.assertIs(stdlib5.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])

    def test_runtime_patch_is_on_where_a_class_exists(self):
        import dunderrt
        import pyboxed2
        plain = pyboxed2.Compiler()
        body = plain.compile("print(sum([1, 2]), {1: [2]})\n")
        self.assertFalse(plain.dunder_ops)
        self.assertNotIn("ail_dun1", body)
        text = ("class Box:\n    def __init__(self, v: int) -> None:\n        self.v = v\n"
                "    def __repr__(self) -> str:\n        return 'Box(%d)' % self.v\n\n"
                "print([Box(1), Box(2)], {1: Box(3)})\n")
        with_class = pyboxed2.Compiler()
        patched = with_class.compile(text)
        self.assertTrue(with_class.dunder_ops)
        self.assertIn("ail_dun1", dunderrt.patch(patched))


# a program that draws from every Random method (and the module-level functions) for many seeds; the general
# path runs it with the Mersenne Twister in C (randrt.py) and its output must be CPython 3.12's byte for byte
BOXED_RANDOM = r"""import random
import sys


def pick_op(ctl: random.Random) -> int:
    return ctl.randrange(16)


def main() -> None:
    seeds = [int(t) for t in sys.stdin.read().split()]
    for seed in seeds:
        rng = random.Random(seed)
        ctl = random.Random(seed ^ 12345)
        pool = [ctl.randint(-50, 50) for _ in range(ctl.randint(0, 40))]
        big = list(range(ctl.choice([30, 200, 1000, 5000])))
        out = []
        for step in range(60):
            op = pick_op(ctl)
            try:
                if op == 0:
                    out.append(rng.random())
                elif op == 1:
                    a = ctl.randint(-1000, 1000)
                    b = ctl.randint(-1000, 1000)
                    out.append(rng.randint(a, b))
                elif op == 2:
                    a = ctl.randint(-100, 100)
                    b = ctl.randint(-100, 300)
                    c = ctl.choice([1, 2, 3, -1, -3, 7, 0])
                    out.append(rng.randrange(a, b, c))
                elif op == 3:
                    out.append(rng.randrange(ctl.randint(-3, 10 ** 12)))
                elif op == 4:
                    out.append(rng.getrandbits(ctl.randint(0, 62)))
                elif op == 5:
                    out.append(rng.choice(pool))
                elif op == 6:
                    rng.shuffle(pool)
                    out.append(pool[:5])
                elif op == 7:
                    out.append(rng.sample(pool, ctl.randint(0, len(pool))))
                elif op == 8:
                    out.append(rng.sample(big, ctl.randint(0, 40)))
                elif op == 9:
                    out.append(rng.uniform(ctl.random() * 10 - 5, ctl.randint(-3, 9)))
                elif op == 10:
                    out.append(rng.gauss(ctl.random(), 2))
                elif op == 11:
                    out.append(rng.gauss())
                elif op == 12:
                    out.append(rng.expovariate(ctl.random() + 0.5))
                elif op == 13:
                    out.append(rng.triangular(0.0, 10.0, ctl.random() * 10))
                elif op == 14:
                    out.append(rng.choices(pool, k=3))
                else:
                    rng.seed(ctl.randint(-10 ** 12, 10 ** 12))
                    out.append(rng.random())
            except Exception as e:
                out.append((type(e).__name__, str(e)))
        print(seed, out)
        words = rng.sample("the quick brown fox jumps".split(), 3)
        print(words, rng.sample(range(100), 5), rng.sample("hello world", 3), rng.choice("abc"))
    random.seed(7)
    print(random.random(), random.randint(1, 100), random.gauss(0, 1), random.choice([4, 5, 6]))
    lst = list(range(20))
    random.shuffle(lst)
    print(lst, random.sample(lst, 4), random.uniform(1, 3))


main()
"""


class BoxedRandom(unittest.TestCase):
    def seeds(self, batch):
        rnd = random.Random(batch)
        pool = [0, 1, -1, 2 ** 32, 2 ** 32 - 1, 2 ** 33 + 5, -2 ** 40]
        return " ".join(str(rnd.choice(pool + [rnd.randint(-10 ** 9, 10 ** 9), rnd.randint(0, 2 ** 62)])) for _ in range(120)) + "\n"

    def test_every_method_matches_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, BOXED_RANDOM, "boxed_random")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            Path(directory, "oracle.py").write_text(BOXED_RANDOM, encoding="utf-8")
            for batch in (1, 2, 3):
                stdin = self.seeds(batch).encode()
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))], input=stdin,
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
                self.assertEqual(got.stdout, want.stdout, "batch %d" % batch)

    def c_of(self, text, name):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, name + ".ail")
            source.write_text(text, encoding="utf-8")
            # The class Random now builds on the typed path too; this test is about the general
            # (boxed) path's C primitives, so ask for it explicitly.
            built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                                    "-o", name, "--debug-dir", "dbg"], cwd=directory, capture_output=True, text=True, timeout=1800,
                                   env=dict(os.environ, AIL_UNIFIED_FORCE="1"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            return Path(directory, "dbg", "program.c").read_text(encoding="utf-8")

    def test_c_only_where_random_objects_are(self):
        body = self.c_of("import random\n\nr = random.Random(3)\nprint(r.random(), r.randint(1, 6))\n", "uses")
        self.assertIn("ail2r_new", body)
        self.assertNotIn("pm_Random__genrand", body)
        self.assertNotIn("pm_Random__refill", body)
        body = self.c_of("class Box:\n    def __init__(self, v):\n        self.v = v\n\nprint(Box(1).v, [Box(2)][0].v)\n", "plain")
        self.assertNotIn("ail2r_", body)
        body = self.c_of("class Random:\n    def __init__(self):\n        self.x = 1\n\nprint(Random().x)\n", "own")
        self.assertNotIn("ail2r_", body)


if __name__ == "__main__":
    unittest.main()
