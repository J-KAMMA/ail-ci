"""Special methods, class attributes, @staticmethod / @classmethod / @property on the typed path (dunders.py).

D1  fixed programs, built on the typed path alone (AIL_NO_GENERAL=1) with AIL_IR=0 and AIL_IR=1, print what
    CPython 3.12 prints: str/repr through print, str(), f-strings, %-formats, str.format and the repr of lists
    and tuples of instances; == != < <= > >= (reflected forms, total_ordering, __ne__), sorted/min/max/sort of
    instances; len (checked >= 0), truth through __bool__ / __len__, in, [] and []=; every __iter__ form (iter(E),
    yield from, a generator inlined into its loop with break / continue / else, run into a list for list() and
    sum(), spread by print(*x)); numeric operators, their reflected and in-place forms, unary operators, abs;
    with-statements (enter/exit order, return / break / continue inside, exceptions propagated or suppressed by
    a true __exit__, issubclass on the exception class); class attributes read through the class, self and cls,
    and rebound through the class; static and class methods; properties; a dataclass's generated __eq__ and
    __repr__ (eq=False, compare=False); the order of evaluation of print(), str.format and `x[k] = v`
D2  a shape that is not built is refused by name on the typed path (no wrong answer, no crash):
    an iterator class (__next__), `x == None` with __eq__, hash(),
    a value-comparing instance as a set element or dict key, a slice of __getitem__, a format spec on an
    instance, __exit__ reading the exception value, a return inside a generator __iter__
D3  random class programs (classes with random subsets of the special methods, random uses of them) print what
    CPython prints, in both IR modes
D4  a program that uses none of these is left exactly as parsed, so its C is unchanged
"""
import ast
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]
CLI = str(ROOT / 'ail_chatgpt.py')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-dunders-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source):
        path = self.dir / 'cpython_main.py'
        path.write_text(source, encoding='utf-8')
        ran = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120)
        return ran

    def build(self, source, ir='0', typed=True, out='out'):
        entry = self.dir / 'main.py'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('%s_ir%s' % (out, ir))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_IR=ir)
        env.pop('AIL_NO_GENERAL', None)
        if typed:
            env['AIL_NO_GENERAL'] = '1'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(entry), '--syntax', 'python', '-o', str(exe)],
                               cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same(self, source, irs=('0', '1')):
        """Built on the typed path alone, the program prints what CPython prints (and exits the same way)."""
        expected = self.cpython(source)
        for ir in irs:
            built, exe = self.build(source, ir)
            self.assertEqual(built.returncode, 0, 'AIL_IR=%s: %s' % (ir, built.stderr))
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.decode(), expected.stdout.decode(), 'AIL_IR=%s' % ir)
            self.assertEqual(ran.returncode, expected.returncode, 'AIL_IR=%s' % ir)
        return expected.stdout.decode()

    def refused(self, source, *needles):
        """The typed path refuses by name (the general path's answer is that path's own business)."""
        built, _ = self.build(source, '0')
        self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
        self.assertNotIn('Traceback', built.stderr)
        for needle in needles:
            self.assertIn(needle, built.stderr)


SHOW = r'''
class P:
    def __init__(self, x: int, name: str) -> None:
        self.x = x
        self.name = name

    def __repr__(self) -> str:
        return f"P({self.x}, {self.name!r})"

    def __str__(self) -> str:
        return self.name + ":" + str(self.x)


class T:
    def __init__(self, k: int) -> None:
        self.k = k

    def __repr__(self):
        return "T<%d>" % self.k


def bump(p: P) -> int:
    p.x += 100
    return p.x


def main() -> None:
    p = P(1, "a")
    q = P(2, "b")
    print(p)
    print(str(p), repr(p))
    print(f"{p} {p!r} {q!s}")
    ps = [p, q]
    print(ps)
    print(f"{ps}", str(ps), repr(ps))
    print("%s and %r" % (p, q), "[%8s|%-9r]" % (p, q))
    print("{} {!r}".format(p, q), "{0} {0!r} {1}".format(q, 3))
    print((p, q), (p,))
    t = T(4)
    print(t, str(t), [t, T(5)])
    print(p, bump(p), p)
    print("{} {}".format(q, q.x), "{1}-{0}".format(q, p))
    print(p, q, sep=" | ", end="!\n")


main()
'''

COMPARE = r'''
from functools import total_ordering


@total_ordering
class Card:
    def __init__(self, rank: int, suit: str) -> None:
        self.rank = rank
        self.suit = suit

    def __eq__(self, other):
        return self.rank == other.rank

    def __lt__(self, other):
        return self.rank < other.rank

    def __repr__(self) -> str:
        return f"Card({self.rank}, {self.suit!r})"


@total_ordering
class Ver:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    def __eq__(self, other: "Ver") -> bool:
        return self.major == other.major and self.minor == other.minor

    def __ne__(self, other: "Ver") -> bool:
        print("ne")
        return not (self.major == other.major and self.minor == other.minor)

    def __gt__(self, other: "Ver") -> bool:
        return (self.major, self.minor) > (other.major, other.minor)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


class Box:
    def __init__(self, w: int) -> None:
        self.w = w

    def __gt__(self, other: "Box") -> bool:
        return self.w > other.w


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __eq__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents == other.cents

    def __str__(self) -> str:
        return "$%d.%02d" % (self.cents // 100, self.cents % 100)


def main() -> None:
    cs = [Card(5, "h"), Card(2, "s"), Card(5, "d"), Card(9, "c")]
    print(sorted(cs))
    print(sorted(cs, reverse=True))
    print(min(cs), max(cs))
    a, b = cs[0], cs[2]
    print(a < b, a <= b, a > b, a >= b, a == b, a != b)
    cs.sort()
    print(cs)
    cs.sort(reverse=True)
    print(cs)
    print(max(cs[1], cs[3]), min(cs[0], cs[1], cs[2]))
    v1 = Ver(1, 2)
    v2 = Ver(1, 10)
    print(v1 < v2, v1 <= v2, v1 > v2, v1 >= v2, v1 != v2, v1 == v2)
    vs = [v2, v1, Ver(0, 9)]
    vs.sort()
    print(vs[0], vs[1], vs[2])
    x = Box(3)
    y = Box(1)
    print(y < x, x < y, x > y)
    bs = [Box(5), x, y, Box(2)]
    sb = sorted(bs)
    print(sb[0].w, sb[3].w, min(bs).w, max(bs).w, max(x, y).w)
    m = [Money(150), Money(5), Money(150)]
    print(m[0] == m[2], m[0] != m[1], Money(5) in m, Money(7) in m, m.index(Money(5)), m.count(Money(150)))
    m.remove(Money(150))
    print(len(m), m[0], m[1])
    lo, mid, hi = Card(1, "a"), Card(4, "b"), Card(8, "c")
    print(lo < mid < hi, lo < hi < mid)


main()
'''

CONTAINER = r'''
class Stack:
    def __init__(self) -> None:
        self.items: list[int] = []

    def push(self, x: int) -> None:
        self.items.append(x)

    def pop(self) -> int:
        return self.items.pop()

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, v: int) -> bool:
        return v in self.items


class Reg:
    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        self.vals: dict[str, int] = {}

    def __getitem__(self, k: str) -> int:
        return self.vals[k]

    def __setitem__(self, k: str, v: int) -> None:
        print("set", k, v)
        self.vals[k] = v

    def __len__(self) -> int:
        return len(self.vals)


class Flag:
    def __init__(self, on: bool) -> None:
        self.on = on

    def __bool__(self) -> bool:
        return self.on


class L:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self) -> int:
        return self.n


def pick(f: Flag | None) -> str:
    if f:
        return "yes"
    return "no"


def val(x: int) -> int:
    print("val", x)
    return x


def main() -> None:
    s = Stack()
    print(len(s), bool(s), not s, 3 in s)
    if not s:
        print("empty")
    s.push(3)
    s.push(4)
    print(3 in s, 5 not in s)
    while s:
        print(s.pop())
    r = Reg(["a"])
    r["a"] = val(3)
    r["b"] = 4
    r["a"] += 10
    print(r["a"], r["b"], len(r))
    try:
        print(r["zz"])
    except KeyError:
        print("missing")
    a = Flag(True)
    b = Flag(False)
    print(bool(a), bool(b), not a, pick(a), pick(b), pick(None))
    n = 0
    while b or n < 2:
        n += 1
    print(n, "t" if a and not b else "f")
    print(len(L(2)), bool(L(0)))
    try:
        print(len(L(-1)))
    except ValueError:
        print("negative length")


main()
'''

ITERATE = r'''
class Bag:
    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, s: str) -> None:
        self.items.append(s)

    def __iter__(self):
        return iter(self.items)


class Pair:
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b

    def __iter__(self):
        yield self.a
        yield self.b


class Back:
    def __init__(self) -> None:
        self.vals: list[int] = []

    def push(self, v: int) -> None:
        self.vals.append(v)

    def __iter__(self):
        i = len(self.vals) - 1
        while i >= 0:
            yield self.vals[i]
            i -= 1


class Wrap:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self):
        yield from self.xs


def main() -> None:
    b = Bag()
    b.add("x")
    b.add("y")
    for s in b:
        print(s)
    l1 = list(b)
    print(",".join(l1), "x" in b, "z" in b)
    for i, s in enumerate(b):
        print(i, s)
    p = Pair(3, 4)
    for v in p:
        if v == 4:
            break
        print("v", v)
    else:
        print("no break")
    for v in p:
        print("w", v)
    else:
        print("done")
    print(sum(p), max(p))
    lp = list(p)
    print(lp[0], lp[1], len(lp))
    print(*p)
    print(*p, "end")
    bk = Back()
    for i in range(6):
        bk.push(i * i)
    for v in bk:
        if v == 9:
            continue
        if v == 1:
            break
        print("bk", v)
    total = 0
    for v in bk:
        for w in bk:
            if w > v:
                break
            total += w
    print(total, sum(bk))
    xs = [v + 1 for v in bk]
    print(xs[0], len(xs))
    w = Wrap([5, 6, 7])
    for v in w:
        print("wrap", v)
    print(sum(w))


main()
'''

ARITH = r'''
class V:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __add__(self, other: "V") -> "V":
        return V(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return V(self.x - other.x, self.y - other.y)

    def __mul__(self, k: int) -> "V":
        return V(self.x * k, self.y * k)

    def __rmul__(self, k: int) -> "V":
        return V(self.x * k, self.y * k)

    def __neg__(self) -> "V":
        return V(-self.x, -self.y)

    def __abs__(self) -> int:
        return abs(self.x) + abs(self.y)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, V):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __repr__(self) -> str:
        return "V(%d, %d)" % (self.x, self.y)


class Num:
    def __init__(self, v: int) -> None:
        self.v = v

    def __pos__(self) -> "Num":
        return Num(self.v + 1000)

    def __invert__(self) -> "Num":
        return Num(~self.v)

    def __iadd__(self, other: "Num") -> "Num":
        self.v += other.v
        return self

    def __add__(self, other: "Num") -> "Num":
        return Num(self.v + other.v + 1)

    def __radd__(self, k: int) -> "Num":
        return Num(self.v + k)

    def __mod__(self, k: int) -> int:
        return self.v % k

    def __floordiv__(self, k: int) -> int:
        return self.v // k

    def __truediv__(self, k: int) -> float:
        return self.v / k

    def __pow__(self, k: int) -> int:
        return self.v ** k

    def __repr__(self) -> str:
        return "Num(" + str(self.v) + ")"


class Holder:
    def __init__(self, a: V) -> None:
        self.a = a

    def bump(self, o: V) -> None:
        self.a += o


def main() -> None:
    a = V(1, 2)
    b = V(3, 4)
    c = a + b
    print(c, a - b, a * 3, 2 * a, -a, abs(b))
    print(a == b, a != b, a + b == V(4, 6))
    t = V(0, 0)
    vs = [a, b, c]
    for v in vs:
        t += v
    print(t)
    t -= a
    print(t, sum(vs, V(0, 0)))
    biggest = max(vs, key=abs)
    print(biggest, sorted(vs, key=abs))
    n = Num(5)
    m = n
    n += Num(2)
    print(n, m, n is m, +n, ~n, n + Num(1), 10 + n)
    print(n % 4, n // 2, n / 2, n ** 2)
    h = Holder(V(1, 1))
    h.bump(V(4, 5))
    print(h.a)


main()
'''

WITH = r'''
class Guard:
    def __init__(self, line: str) -> None:
        self.line = line

    def __enter__(self) -> "Guard":
        print("enter")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        print("exit")
        if exc_type is ValueError:
            print("swallowed")
            return True
        return False


class Res:
    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self):
        print("open", self.name)
        return self

    def __exit__(self, et, ev, tb):
        print("close", self.name, et is None)
        return False


class Quiet:
    def __init__(self) -> None:
        self.n = 0

    def __enter__(self) -> None:
        print("q in")

    def __exit__(self, exc_type, exc, tb) -> bool:
        print("q out")
        return issubclass(exc_type, (KeyError, IndexError)) if exc_type is not None else False


def first(xs: list[int]) -> int:
    with Res("f"):
        if not xs:
            return -1
        return xs[0]


def main() -> None:
    for line in ["3", "x", "4"]:
        with Guard(line) as g:
            print(int(g.line) * 2)
    try:
        with Guard("0") as g:
            print(10 // int(g.line))
    except ZeroDivisionError:
        print("zde")
    print(first([]), first([7]))
    for i in range(4):
        with Res("loop") as r:
            if i == 1:
                continue
            if i == 3:
                break
            print("body", i, r.name)
    with Res("a") as a, Res("b") as b:
        print(a.name + b.name)
    try:
        with Res("err"):
            raise ValueError("boom")
    except ValueError:
        print("caught")
    xs = [1]
    with Quiet():
        print(xs[5])
    d = {"a": 1}
    with Quiet():
        print(d["b"])
    try:
        with Quiet():
            print(int("zz"))
    except ValueError:
        print("passed through")


main()
'''

CLASSLEVEL = r'''
class Counter:
    total = 0
    step = 2
    label = "cnt"

    def __init__(self, start: int) -> None:
        self.n = start

    def bump(self) -> None:
        Counter.total += self.step
        self.n += Counter.step

    def show(self) -> str:
        return self.label + ":" + str(self.n) + "/" + str(Counter.total)


class Student:
    __slots__ = ("name", "score")
    PASS = 50

    def __init__(self, name: str, score: int) -> None:
        self.name = name
        self.score = score

    @classmethod
    def from_line(cls, line: str) -> "Student":
        n, s = line.split()
        return cls(n, int(s))

    @staticmethod
    def bucket_of(score: int) -> int:
        return score // 10

    @property
    def bucket(self) -> int:
        return self.bucket_of(self.score)

    def passed(self) -> bool:
        return self.score >= self.PASS

    def __str__(self) -> str:
        return f"{self.name}({self.score})"


class Geo:
    unit = "cm"

    def __init__(self, r: float) -> None:
        self.r = r

    @staticmethod
    def sq(x: float) -> float:
        return x * x

    def area(self) -> float:
        return 3.0 * self.sq(self.r)

    @classmethod
    def unit_circle(cls) -> "Geo":
        return cls(1.0)

    @property
    def desc(self) -> str:
        return str(self.area()) + self.unit


def main() -> None:
    c = Counter(1)
    d = Counter(5)
    c.bump()
    d.bump()
    d.bump()
    print(c.show(), d.show(), Counter.total, c.total)
    ss = []
    for line in ["a 55", "b 42", "c 90"]:
        ss.append(Student.from_line(line))
    for s in ss:
        print(str(s), s.bucket, s.passed(), Student.PASS, Student.bucket_of(s.score))
    for s in sorted(ss, key=lambda s: (s.bucket, s.name)):
        print(s.bucket, s)
    g = Geo(2.0)
    print(g.area(), Geo.area(g), Geo.sq(3.0), Geo.unit_circle().r, g.desc, Geo.unit)


main()
'''

DATACLASS = r'''
from dataclasses import dataclass, field


@dataclass
class Item:
    name: str
    price: float
    qty: int = 1


@dataclass
class Order:
    oid: int
    item: Item
    note: str = field(default="", compare=False)


@dataclass(eq=False)
class Ident:
    k: int


def main() -> None:
    a = Order(1, Item("pen", 1.5, 2), "x")
    b = Order(1, Item("pen", 1.5, 2), "y")
    print(a)
    print(a == b, a.item == b.item, Item("a", 2.0) == Item("a", 2.0, 2), a != b)
    print(f"{a.item!r} and {a.item}", [a.item, b.item])
    i = Ident(1)
    print(i, i is i)


main()
'''


class FixedPrograms(Base):
    """D1"""

    def test_str_repr_and_formatting(self):
        self.same(SHOW)

    def test_comparisons_and_ordering(self):
        self.same(COMPARE)

    def test_len_bool_contains_and_items(self):
        self.same(CONTAINER)

    def test_iteration_forms(self):
        self.same(ITERATE)

    def test_numeric_operators(self):
        self.same(ARITH)

    def test_with_statements(self):
        self.same(WITH)

    def test_class_attributes_static_class_methods_properties(self):
        self.same(CLASSLEVEL)

    def test_dataclass_eq_and_repr(self):
        self.same(DATACLASS)


REFUSALS = [
    ('''
class It:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0
    def __iter__(self):
        return self
    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i
def main() -> None:
    for v in It(3):
        print(v)
main()
''', 'an iterator class with __next__ is not built'),
    ('''
class P:
    def __init__(self, x: int) -> None:
        self.x = x
    def __eq__(self, other: "P") -> bool:
        return self.x == other.x
def main() -> None:
    print(P(1) == None)
main()
''', 'which defines __eq__, with None'),
    ('''
class P:
    def __init__(self, x: int) -> None:
        self.x = x
    def __hash__(self) -> int:
        return self.x
def main() -> None:
    print(hash(P(3)))
main()
''', 'hash() of a P instance'),
    ('''
class P:
    def __init__(self, x: int) -> None:
        self.x = x
    def __hash__(self) -> int:
        return self.x
    def __eq__(self, other: "P") -> bool:
        return self.x == other.x
def main() -> None:
    s = set()
    s.add(P(1))
    s.add(P(1))
    print(len(s), P(1) in s)
main()
''', 'a set element or dict key that compares with __eq__ / __hash__'),
    ('''
class S:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs
    def __getitem__(self, i: int) -> int:
        return self.xs[i]
def main() -> None:
    s = S([1, 2, 3])
    print(s[0], s[1:2])
main()
''', 'slicing a S'),
    ('''
class S:
    def __init__(self, x: int) -> None:
        self.x = x
    def __str__(self) -> str:
        return "S"
def main() -> None:
    try:
        print(f"{S(1):>5}")
    except TypeError:
        print("TypeError")
main()
''', 'a format spec on a S'),
    ('''
class G:
    def __init__(self) -> None:
        self.n = 0
    def __enter__(self) -> "G":
        return self
    def __exit__(self, t, v, tb) -> bool:
        print("got", v)
        return True
def main() -> None:
    with G():
        int("x")
main()
''', "__exit__ uses 'v'"),
    ('''
class G:
    def __init__(self, n: int) -> None:
        self.n = n
    def __iter__(self):
        for i in range(self.n):
            if i == 2:
                return
            yield i
def main() -> None:
    for v in G(5):
        print(v)
main()
''', 'a return inside the generator __iter__'),
    ('''
class P:
    def __init__(self, x: int) -> None:
        self.x = x
    def __str__(self) -> str:
        return "P" + str(self.x)
def bump(p: P) -> int:
    p.x += 1
    return p.x
def main() -> None:
    p = P(1)
    print("{} {}".format(p, bump(p)))
main()
''', 'str.format with a class instance and arguments that call functions'),
]


class Refusals(Base):
    """D2"""

    def test_refused_by_name(self):
        for source, needle in REFUSALS:
            with self.subTest(needle=needle):
                self.refused(source, needle)


# -- D3: random class programs ---------------------------------------------------------------------------

FEATURES = ('str', 'repr', 'eq', 'lt', 'add', 'sub', 'mul', 'rmul', 'neg', 'abs', 'len', 'bool', 'contains',
            'getitem', 'setitem', 'iter_list', 'iter_gen', 'attr', 'static')


def random_program(rng):
    lines = []
    classes = []
    for ci in range(rng.randint(1, 2)):
        name = 'K%d' % ci
        feats = set(rng.sample(FEATURES, rng.randint(3, 8)))
        if 'iter_list' in feats and 'iter_gen' in feats:
            feats.discard(rng.choice(['iter_list', 'iter_gen']))
        if 'lt' in feats and rng.random() < 0.5:
            feats.add('total')
        classes.append((name, feats))
        if 'total' in feats:
            lines.append('@total_ordering')
        lines.append('class %s:' % name)
        if 'attr' in feats:
            lines.append('    SCALE = %d' % rng.randint(2, 5))
        lines.append('    def __init__(self, a: int, b: int, items: list[int]) -> None:')
        lines += ['        self.a = a', '        self.b = b', '        self.items = items']
        if 'str' in feats:
            lines += ['    def __str__(self) -> str:', '        return f"%s<{self.a},{self.b}>"' % name]
        if 'repr' in feats:
            lines += ['    def __repr__(self):', '        return "%s(%%d, %%d)" %% (self.a, self.b)' % name]
        if 'eq' in feats:
            if rng.random() < 0.5:
                lines += ['    def __eq__(self, other):', '        if not isinstance(other, %s):' % name,
                          '            return NotImplemented', '        return self.a == other.a']
            else:
                lines += ['    def __eq__(self, other: "%s") -> bool:' % name, '        return self.a == other.a']
        if 'lt' in feats:
            lines += ['    def __lt__(self, other: "%s") -> bool:' % name,
                      '        return (self.a, self.b) < (other.a, other.b)']
        if 'add' in feats:
            lines += ['    def __add__(self, other: "%s") -> "%s":' % (name, name),
                      '        return %s(self.a + other.a, self.b + other.b, [0, 0, 0])' % name]
        if 'sub' in feats:
            lines += ['    def __sub__(self, other):',
                      '        return %s(self.a - other.a, self.b - other.b, [1, 1, 1])' % name]
        if 'mul' in feats:
            lines += ['    def __mul__(self, k: int) -> "%s":' % name,
                      '        return %s(self.a * k, self.b * k, [2, 2, 2])' % name]
        if 'rmul' in feats:
            lines += ['    def __rmul__(self, k: int) -> "%s":' % name,
                      '        return %s(self.a * k + 1, self.b * k, [3, 3, 3])' % name]
        if 'neg' in feats:
            lines += ['    def __neg__(self) -> "%s":' % name, '        return %s(-self.a, -self.b, [4, 4, 4])' % name]
        if 'abs' in feats:
            lines += ['    def __abs__(self) -> int:', '        return abs(self.a) + abs(self.b)']
        if 'len' in feats:
            lines += ['    def __len__(self) -> int:', '        return len(self.items)']
        if 'bool' in feats:
            lines += ['    def __bool__(self) -> bool:', '        return self.a != 0']
        if 'contains' in feats:
            lines += ['    def __contains__(self, v: int) -> bool:', '        return v in self.items']
        if 'getitem' in feats:
            lines += ['    def __getitem__(self, i: int) -> int:', '        return self.items[i] + self.a']
        if 'setitem' in feats:
            lines += ['    def __setitem__(self, i: int, v: int) -> None:', '        self.items[i] = v - self.b']
        if 'iter_list' in feats:
            lines += ['    def __iter__(self):', '        return iter(self.items)']
        if 'iter_gen' in feats:
            lines += ['    def __iter__(self):', '        yield self.a', '        for v in self.items:',
                      '            if v % 2 == 0:', '                yield v * 10', '        yield self.b']
        if 'static' in feats:
            lines += ['    @staticmethod', '    def twice(v: int) -> int:', '        return 2 * v']
    lines.append('def main() -> None:')
    body = []
    for ci, (name, feats) in enumerate(classes):
        objs = []
        for k in range(3):
            v = '%s%d' % (name.lower(), k)
            objs.append(v)
            body.append('%s = %s(%d, %d, [%s])' % (v, name, rng.randint(-5, 9), rng.randint(-5, 9),
                                                   ', '.join(str(rng.randint(0, 9)) for _ in range(3))))
        x, y, z = objs
        ops = []
        shown = 'str' in feats or 'repr' in feats
        if shown:
            ops.append(['print(%s)' % x, 'print(f"[{%s}]")' % y, 'print(str(%s), %s.a)' % (z, z)])
        if 'repr' in feats:
            ops.append(['print(repr(%s))' % x, 'print([%s, %s])' % (x, y), 'print(f"{%s!r}")' % z])
        if 'eq' in feats:
            ops.append(['print(%s == %s, %s != %s, %s == %s)' % (x, y, x, z, y, y)])
        if 'lt' in feats:
            ops.append(['print(%s < %s, %s > %s)' % (x, y, y, z)])
            ops.append(['objs%d = [%s, %s, %s]' % (ci, x, y, z), 'ss%d = sorted(objs%d)' % (ci, ci),
                    'print(ss%d[0].a, ss%d[1].a, ss%d[2].a)' % (ci, ci, ci),
                    'print(min(objs%d).b, max(objs%d).a)' % (ci, ci)])
            if 'total' in feats:
                ops.append(['print(%s <= %s, %s >= %s)' % (x, y, z, x)])
        if 'add' in feats:
            ops.append(['w%d = ' % ci + '%s + %s' % (x, y), 'print(w%d.a, w%d.b)' % (ci, ci), 'w%d += %s' % (ci, z), 'print(w%d.a)' % ci])
        if 'sub' in feats:
            ops.append(['w%d = ' % ci + '%s - %s' % (z, x), 'print(w%d.a, w%d.b)' % (ci, ci)])
        if 'mul' in feats:
            ops.append(['w%d = ' % ci + '%s * %d' % (y, rng.randint(2, 4)), 'print(w%d.a, w%d.b)' % (ci, ci)])
        if 'rmul' in feats:
            ops.append(['w%d = ' % ci + '%d * %s' % (rng.randint(2, 4), x), 'print(w%d.a, w%d.b)' % (ci, ci)])
        if 'neg' in feats:
            ops.append(['w%d = ' % ci + '-%s' % z, 'print(w%d.a, w%d.b)' % (ci, ci)])
        if 'abs' in feats:
            ops.append(['print(abs(%s), abs(%s))' % (x, y)])
        if 'len' in feats:
            ops.append(['print(len(%s))' % x])
        if 'bool' in feats or 'len' in feats:
            ops.append(['print(bool(%s), not %s)' % (y, z), 'if %s:\n        print("truthy")\n    else:\n        print("falsy")' % x])
        if 'contains' in feats:
            ops.append(['print(%d in %s, %d not in %s)' % (rng.randint(0, 9), x, rng.randint(0, 9), y)])
        if 'getitem' in feats:
            ops.append(['print(%s[%d], %s[-1])' % (y, rng.randint(0, 2), z)])
        if 'setitem' in feats:
            ops.append(['%s[%d] = %d' % (x, rng.randint(0, 2), rng.randint(0, 20)), 'print(%s.items[0], %s.items[2])' % (x, x)])
        if 'iter_list' in feats or 'iter_gen' in feats:
            ops.append(['for v in %s:\n        print("it", v)' % y, 'print(sum(%s))' % z])
            if 'iter_list' in feats:
                ops.append(['print(%d in %s)' % (rng.randint(0, 9), x)])
        if 'attr' in feats:
            ops.append(['print(%s.SCALE * %s.a, %s.SCALE)' % (name, x, y)])
        if 'static' in feats:
            ops.append(['print(%s.twice(%s.a), %s.twice(3))' % (name, x, y)])
        rng.shuffle(ops)
        body += [line for group in ops for line in group]
    lines += ['    ' + line for line in body]
    lines.append('main()')
    head = 'from functools import total_ordering\n' if any('total' in f for _, f in classes) else ''
    return head + '\n'.join(lines) + '\n'


class RandomPrograms(Base):
    """D3"""

    def test_random_class_programs(self):
        rng = random.Random(20261019)
        for index in range(int(os.environ.get('AIL_DUNDERS_RANDOM', '6'))):
            source = random_program(rng)
            with self.subTest(index=index):
                if self.cpython(source).returncode != 0:
                    continue
                try:
                    self.same(source)
                except AssertionError:
                    print(source, file=sys.stderr)
                    raise


class Untouched(unittest.TestCase):
    """D4"""

    def test_programs_without_special_methods_keep_their_tree(self):
        import ail_syntax
        import dunders
        from pyfront import Unsupported
        sources = [
            'class P:\n    def __init__(self, x: int) -> None:\n        self.x = x\n'
            '    def get(self) -> int:\n        return self.x\n'
            'def main() -> None:\n    print(P(1).get())\nmain()\n',
            'from dataclasses import dataclass\n@dataclass\nclass Q:\n    a: int\n    b: float\n'
            'def main() -> None:\n    q = Q(1, 2.0)\n    print(q.a, q.b)\nmain()\n',
            'def main() -> None:\n    xs = [3, 1, 2]\n    print(sorted(xs), len(xs))\nmain()\n',
        ]
        for text in sources:
            source = ail_syntax.python_surface(text)
            tree = ast.parse(source.strip())
            before = ast.dump(tree, include_attributes=True)
            self.assertFalse(dunders.rewrite(tree, source, Unsupported))
            self.assertEqual(ast.dump(tree, include_attributes=True), before)
            self.assertEqual(dunders.ACCEPTED, {})
            self.assertEqual(dunders.TRUTH, set())


if __name__ == '__main__':
    unittest.main()
