"""Branch cov2: enum.Flag / IntFlag, `with` / contextlib, str.format with keywords and nested specs, and csv over
io.StringIO on the general path, each compared with CPython 3.12.

* PROGRAMS are compiled twice (AIL_UNIFIED_FORCE=1, the general path; and the default build, which falls back to it) and must
  print what CPython prints;
* prelude_csv.py is plain Python: random readers / writers / DictReader / DictWriter are compared with CPython's csv;
* uses that are not built must be refused by name (a Flag member past 63 bits, a csv.Dialect subclass).
"""
import io
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

PROGRAMS = {}
PROGRAMS['sh1'] = r'''from enum import IntFlag, Flag, IntEnum
class Q(IntFlag):
    A = 1
    B = 2
print(Q.B >> 1, Q.A << 2, 2 << Q.A, 8 >> Q.A)
print(repr(Q.B >> 1), repr(Q.A << 1))
def f(x, n):
    return x << n, x >> n
print(f(Q.B, 1), f(Q.B, Q.A))
l = [Q.A, Q.B]
print(l[1] << l[0], 1 << l[1], l[1] >> 1)
class H:
    def __init__(self): self.q = Q.B
h = H()
print(h.q << 3, h.q >> Q.A)
d = {'k': Q.A}
print(d['k'] << 4, 16 >> d['k'])
print(Q(3) << 1, Q(3) >> 1)
try:
    print(Q.A << -1)
except ValueError as e:
    print(e)
'''
PROGRAMS['big'] = r'''from enum import Flag, IntFlag
class V(Flag):
    A = 1
    C = 1 << 62
print(repr(~V.A), repr(V.A | V.C))
print(~V.C, V.C in V.A | V.C, list(V.A | V.C))
class U(Flag):
    A = 1
    B = 1 << 61
print(repr(~U.A), repr(U.A | U.B))
def g(x): return x | V.A
print(repr(g(V.C)))
class I(IntFlag):
    A = 1
    Z = 1 << 62
    Y = 1 << 40
x = I.A | I.Z
print(repr(x), int(x), repr(~I.A), repr(~x), repr(I.Z >> 61), I.Z in x, list(x | I.Y))
print(repr(I(1<<62)), repr(I((1<<62)+5)), repr(I(-1)), repr(I(-(1<<62))))
print(x & I.A, bool(I.Z & I.A), x ^ I.Z, I.Z == 1<<62, hash(I.Z) == hash(1<<62))
try:
    V(1 << 61)
except ValueError as e:
    print(e)
try:
    V(3 << 61)
except ValueError as e:
    print(e)
try:
    V(-5)
except ValueError as e:
    print(e)
class L:
    def __init__(self): self.f = V.C
d = {'a': V.C | V.A}
print(repr(L().f | d['a']), [v for v in d['a']], len(d['a']))
'''
PROGRAMS['pct'] = r'''from enum import IntFlag, IntEnum, Flag
class N(IntFlag):
    A = 1
    B = 2
class E(IntEnum):
    X = 5
class F(Flag):
    P = 1
print('%s' % N.A, '%d' % N.A, '%s' % N(3), '%d' % N(3), '%i' % N.B, '%5d|' % N.B, '%x' % N.B)
print('%s' % E.X, '%d' % E.X, '%r' % N.A, '%s' % F.P, '%r' % F.P)
print('%s-%d' % (N.A, N.B))
l=[N.A, N.B]
print('%d %s' % (l[0], l[1]), '%d' % E.X)
class H:
    def __init__(self): self.q = N.B
print('%d %s' % (H().q, H().q))
print('%s' % {'a': N.A}['a'], '%f' % N.A)
'''
PROGRAMS['pct2'] = r'''from enum import IntFlag, IntEnum, Flag, Enum
class N(IntFlag):
    A = 1
    B = 2
class E(IntEnum):
    X = 5
    Y = 12
class C(Enum):
    R = 1
class F(Flag):
    P = 1
class U:
    def __init__(self, v): self.v = v
    def __str__(self): return 'U<%d>' % self.v
    def __repr__(self): return 'ur'
    def __int__(self): return self.v
    def __float__(self): return self.v + 0.5
    def __format__(self, spec): return 'FMT' + spec
class T:
    pass
a = N.A | N.B
print('%5s|%-5s|%05d|%+d|% d|%x|%X|%o|%.2f|%8.3f' % (a, a, a, a, a, a, a, a, a, a))
print('%5d|%-6d|%s|%r' % (E.Y, E.Y, E.Y, E.Y))
print('%s %r %s' % (C.R, C.R, F.P))
print('%5s|%d|%s|%.1f|%r' % (U(3), U(4), U(5), U(6), U(7)))
fmt = '%d-%s-%x'
print(fmt % (E.Y, a, E.Y))
print(fmt % (a, a, a))
print('%s' % (a,), '%d' % (E.X,), '%s' % [a, E.X], '%s' % {'k': a})
print('%(k)s %(k)d' % {'k': a})
def f(v): return '[%3d|%-3s]' % (v, v)
print(f(E.X), f(a), f(7))
def g(f_, v): return f_ % v
print(g('%d', E.Y), g('%s', N.B), g('%s %s', (N.A, E.X)))
print(str(a) + '%s' % a, 'x%dy' % N.B)
for bad in ('%d', '%x', '%f', '%c'):
    try:
        print(bad % T())
    except TypeError as e:
        print(bad, e)
try:
    print('%d' % C.R)
except TypeError as e:
    print(e)
try:
    print('%x' % U(1))
except TypeError as e:
    print(e)
print('%d%%' % E.X, '%c' % E.X)
'''
PROGRAMS['attr'] = r'''from enum import Enum, Flag, IntEnum, IntFlag
class P(Enum):
    A = 1
    def hello(self):
        return 'hi'
class Q(Flag):
    A = 1
class R(IntEnum):
    A = 1
class S(IntFlag):
    A = 1
try:
    P.Z
except AttributeError as e:
    print(e)
try:
    Q.Z
except AttributeError as e:
    print(e)
try:
    R.Z
except AttributeError as e:
    print(e)
try:
    print(S.Z)
except AttributeError as e:
    print(e)
print(P.A.hello(), Q.A.name, S.A.value)
def f():
    try:
        return P.Nope
    except AttributeError as e:
        return str(e)
print(f())
'''
PROGRAMS['ie'] = r'''from enum import IntEnum, IntFlag
class E(IntEnum):
    X = 5
    Y = 12
print(E.X << 2, 1 << E.X, E.Y >> 2, 100 >> E.X, E.X & E.Y, E.X | 2, 3 ^ E.X, ~E.X, E.Y & 4, 6 & E.X)
print(isinstance(E.X | 2, E), repr(E.X << 1))
class F(IntFlag):
    A = 1
    B = 4
x = F.A | F.B
print(x << 1, 1 << x, x >> 1, 20 >> F.A, x & 1, 5 & x, x | 2, repr(x | 2), repr(2 | x), ~x, repr(~F.A))
print(F.A << E.X, E.X << F.A, E.Y & F.B, F.B & E.Y)
'''
PROGRAMS['fl1'] = r'''from enum import Flag, IntFlag, auto
class P(Flag):
    R=auto(); W=auto(); X=auto()
    RW = R|W
    ALL = R|W|X
class Q(IntFlag):
    A=1; B=2; C=4; N=0
    AB=3
print(list(P), list(Q), len(P))
for x in (P.R|P.W, P.RW, P(0), P(7), ~P.R, ~P.RW, P.ALL, P.R&P.W, P.R^P.W,P.R^P.R):
    print(repr(x), str(x), bool(x), x.value, x.name, hash(x)==hash(x))
for x in (Q.A|Q.B, Q(0), Q(8), Q(9), ~Q.A, Q.A|8, Q(3), Q.N, Q(-1),Q.AB):
    print(repr(x), str(x), bool(x), x.value, x.name, int(x), format(x), f"{x}", f"{x:d}", "%d"%x)
print(P.R in P.RW, P.RW in P.R, P(0) in P.R, P.R in P)
print(list(P.RW), list(Q.AB), list(P(0)))
print(P.__members__.keys(), Q.__members__.keys())
try: P(8)
except ValueError as e: print(e)
try: P(-1)
except ValueError as e: print(e)
try: P.R|1
except TypeError as e: print(e)
print(P.R==P.R, P.R==1, Q.A==1, Q.A<Q.B, P.R|P.R, {P.R:1}[P.R])
print(Q.A|Q.B==3, Q(3)==Q.AB, Q(3) is Q.AB, P(3) is (P.R|P.W), P(3) is P.RW)
print(bool(P.R&P.W), P.R.name, (P.R|P.W).name, P.RW.name, P(0).name)
print(P["R"], len(list(P.RW)), Q.A|1, Q.A & 3, 3 & Q.A, 5|Q.A)
'''
PROGRAMS['fl2b'] = r'''from enum import Flag, IntFlag, auto, unique
from functools import reduce


@unique
class Perm(Flag):
    """perms"""
    R = auto()
    W = auto()
    X = auto()
    RW = R | W

    def can(self, other):
        return other in self

    def label(self) -> str:
        return "+".join(f.name for f in self) or "none"


class Sparse(Flag):
    A = 1
    C = 4
    D = 16


class Out(Flag):
    B = 2
    A = 1
    C = 4


class Dup(IntFlag):
    ONE = 1
    UNO = 1
    TWO = 2
    BIG = 1 << 10
    MASK = ONE | TWO


def show(x):
    print(repr(x), str(x), x.value, x.name)


class Holder:
    def __init__(self, p):
        self.p = p


def take(p: Perm) -> Perm:
    return p | Perm.X


show(take(Perm.R))
h = Holder(Perm.W)
show(h.p | Perm.R)
d = {"a": Perm.R, "b": Perm.X}
show(d["a"] | d["b"])
lst = [Perm.R, Perm.W, Perm.X]
show(reduce(lambda a, b: a | b, lst))
show(lst[0] ^ lst[1])
acc = Perm(0)
for f in lst:
    acc |= f
show(acc)
acc &= ~Perm.W
show(acc)
acc ^= Perm.R
show(acc)
print(Perm.RW.can(Perm.R), Perm.R.can(Perm.RW), Perm.RW.label(), Perm(0).label(), Perm.X.label())
print([p.name for p in Perm], len(Perm), Perm.RW in Perm, Perm.X in Perm, 3 in Perm, 8 in Perm, 1 in Perm)
print(list(Perm.RW | Perm.X), len(Perm.RW | Perm.X), len(Perm(0)))
print(Perm["RW"], Perm(1), Perm(3) is Perm.RW, Perm.R is Perm(1), Perm(6))
for bad in (8, 16, -9, 100):
    try:
        print(repr(Perm(bad)))
    except ValueError as e:
        print("ValueError", e)
print(repr(Perm(-1)), repr(Perm(-2)), repr(~Perm.RW), repr(~Perm(0)), repr(~Perm.RW | Perm.W))
try:
    Perm["Z"]
except KeyError as e:
    print("KeyError", e)
for bad in (1, "x", 1.5, None, [1]):
    try:
        Perm.R | bad
    except TypeError as e:
        print("TypeError", e)
    try:
        bad | Perm.R
    except TypeError as e:
        print("TypeError", e)
    try:
        Perm.R & bad
    except TypeError as e:
        print("TypeError", e)
    try:
        bad in Perm.R
    except TypeError as e:
        print("TypeError", e)
print(Sparse.A | Sparse.C, list(Sparse), repr(Sparse(5)), repr(~Sparse.A), repr(Sparse(0)))
for bad in (2, 3, 32):
    try:
        print(repr(Sparse(bad)))
    except ValueError as e:
        print("ValueError", e)
print(list(Out), list(Out.A | Out.B | Out.C), repr(Out.A | Out.C), repr(Out(7)))
print(repr(Dup.UNO), Dup.ONE is Dup.UNO, list(Dup), repr(Dup.MASK), repr(Dup(3)), repr(Dup(1024 + 1)), repr(Dup(4)), repr(Dup(1030)))
print(list(Dup.__members__), repr(Dup(-1)), repr(~Dup.ONE), repr(Dup.ONE | 4), repr(4 | Dup.ONE), repr(Dup.ONE & 3), repr(7 ^ Dup.ONE))
print(Dup.ONE + 1, Dup.TWO * 3, Dup.TWO == 2, 2 == Dup.TWO, Dup.ONE < Dup.TWO, Dup.TWO - 1, int(Dup.BIG), Dup.BIG > 1000)
print(sorted([Dup.TWO, Dup.BIG, Dup.ONE]), max(Dup.ONE, Dup.TWO), {Dup.ONE: "a"}[1], {1: "b"}[Dup.ONE])
print(f"{Perm.R:>10}|{Perm.RW:<8}|{Perm.R!r}|{Perm.R}|{Perm(0)}|{Perm(0)!r}|{Perm.R|Perm.X}")
print(f"{Dup.TWO:>6}|{Dup.TWO:#x}|{Dup.BIG:,}|{Dup.TWO}|{Dup.TWO!r}")
print(bool(Perm(0)), bool(Perm.R), bool(Dup(0)), bool(Dup.ONE), not Perm(0))
if Perm.R & Perm.W:
    print("bad")
if Perm.RW & Perm.W:
    print("ok")
print(Perm.R == Perm.R, Perm.R == Perm.W, Perm.R != Perm.W, Perm.R == 1, Perm.R | Perm.W == Perm.RW, hash(Perm.R) == hash(Perm.R))
print(len({Perm.R, Perm.R, Perm.W, Perm.R | Perm.W, Perm.RW}))
print(isinstance(Perm.R, Perm))
'''
PROGRAMS['w1'] = r'''class Res:
    def __init__(self, name, swallow=False):
        self.name = name
        self.swallow = swallow

    def __enter__(self):
        print("enter", self.name)
        return self

    def __exit__(self, exc_type, exc, tb):
        print("exit", self.name, exc_type is None, exc)
        return self.swallow


def f(x):
    with Res("a") as r:
        print("in", r.name, x)
        if x > 1:
            return x * 2
    return -1


with Res("top") as t:
    print("body", t.name)
print(f(1), f(2))
try:
    with Res("b"):
        raise ValueError("boom")
except ValueError as e:
    print("caught", e)
with Res("c", True):
    raise KeyError("swallowed")
print("after c")
for i in range(3):
    with Res("L%d" % i):
        if i == 0:
            continue
        if i == 1:
            break
        print("not reached")
with Res("x") as a, Res("y", True) as b:
    print(a.name, b.name)
    raise RuntimeError("inner")
print("done")
'''
PROGRAMS['w2'] = r'''import contextlib
from contextlib import contextmanager, suppress, closing, nullcontext


@contextmanager
def tag(name):
    print("<" + name + ">")
    try:
        yield name.upper()
    finally:
        print("</" + name + ">")


@contextlib.contextmanager
def guard(label, swallow=False):
    print("setup", label)
    try:
        yield
    except ValueError as e:
        print("guard saw", label, e)
        if not swallow:
            raise
    else:
        print("clean", label)
    finally:
        print("teardown", label)


@contextmanager
def counter(box):
    box.append(1)
    yield box
    box.append(2)


class Holder:
    def __init__(self):
        self.log = []

    @contextmanager
    def section(self, n):
        self.log.append("open %d" % n)
        try:
            yield self
        finally:
            self.log.append("close %d" % n)


class Closer:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True
        print("closed")


with tag("a") as t:
    print("inside", t)
with tag("a"), tag("b") as u:
    print("nested", u)
with guard("g1"):
    print("ok body")
with guard("g2", True):
    raise ValueError("swallow me")
print("after g2")
try:
    with guard("g3"):
        raise ValueError("propagate")
except ValueError as e:
    print("outer got", e)
try:
    with guard("g4"):
        raise KeyError("other")
except KeyError as e:
    print("outer key", e)
b = []
with counter(b) as c:
    c.append(9)
print(b)
h = Holder()
with h.section(1) as s:
    with h.section(2):
        print("deep")
print(h.log)
for i in range(3):
    with tag("loop%d" % i):
        if i == 1:
            continue
        print("body", i)
def early(n):
    with tag("e"):
        if n:
            return "early"
    return "late"
print(early(1), early(0))
data = [1, 2, 3]
for idx in (0, 5, 1, 9):
    with suppress(IndexError):
        print(data[idx])
with suppress(KeyError, ValueError):
    int("x")
print("suppressed")
with suppress(KeyError):
    pass
try:
    with suppress(KeyError):
        raise ValueError("nope")
except ValueError:
    print("not suppressed")
cl = Closer()
with closing(cl) as z:
    print(z is cl, cl.closed)
print(cl.closed)
with nullcontext(5) as five:
    print(five)
with nullcontext():
    print("null")
'''
PROGRAMS['w3'] = r'''from contextlib import contextmanager


class AppError(Exception):
    pass


class Txn:
    def __init__(self, name):
        self.name = name
        self.state = "new"

    def __enter__(self):
        self.state = "open"
        print("begin", self.name)
        return self

    def __exit__(self, exc_type, exc_val, tb):
        if exc_type is None:
            self.state = "committed"
            print("commit", self.name)
            return False
        self.state = "rolled back"
        print("rollback", self.name, exc_type.__name__, str(exc_val), exc_type)
        if exc_type is AppError:
            return True
        if issubclass(exc_type, KeyError):
            print("keyerror swallowed")
            return True
        if exc_type in (ZeroDivisionError, TypeError):
            print("math/type swallowed")
            return True
        return False


t = Txn("t1")
with t:
    pass
print(t.state)
with Txn("t2") as t2:
    raise AppError("app")
print(t2.state)
with Txn("t3") as t3:
    d = {}
    d["x"]
print(t3.state)
with Txn("t4"):
    1 / 0
with Txn("t5"):
    "a" + 1
try:
    with Txn("t6"):
        raise ValueError("v")
except ValueError as e:
    print("escaped", e)


class BadEnter:
    def __enter__(self):
        raise RuntimeError("enter failed")

    def __exit__(self, a, b, c):
        print("never")


try:
    with BadEnter():
        print("no")
except RuntimeError as e:
    print(e)


class BadExit:
    def __enter__(self):
        return 1

    def __exit__(self, a, b, c):
        raise RuntimeError("exit failed")


try:
    with BadExit() as one:
        print("one", one)
except RuntimeError as e:
    print(e)
try:
    with BadExit():
        raise ValueError("orig")
except RuntimeError as e:
    print("replaced by", e)
except ValueError as e:
    print("orig survived", e)


@contextmanager
def no_yield():
    if False:
        yield 1


try:
    with no_yield():
        pass
except RuntimeError as e:
    print(e)


@contextmanager
def two_yields():
    yield 1
    yield 2


try:
    with two_yields():
        pass
except RuntimeError as e:
    print(e)


@contextmanager
def converts():
    try:
        yield
    except ValueError:
        raise AppError("converted")


try:
    with converts():
        raise ValueError("x")
except AppError as e:
    print("got", e)


@contextmanager
def yields_again():
    try:
        yield 1
    except ValueError:
        yield 2


try:
    with yields_again():
        raise ValueError("x")
except RuntimeError as e:
    print(e)


@contextmanager
def tx_value():
    v = yield "first"
    print("resumed with", v)


with tx_value() as q:
    print(q)
'''
PROGRAMS['fm1'] = r'''print('{x:{w}}|'.format(x=3, w=5))
print('{0} {name}'.format('a', name='b'))
print('{:>{w}.{p}f}'.format(3.14159, w=10, p=2))
d = {'k': 'v'}
print('{k}'.format_map(d))
print('{0[1]}'.format([1, 2]))
print('{!r:>8}'.format('s'))
print('{:^{}}'.format('ab', 6))
try:
    '{y}'.format(x=1)
except KeyError as e:
    print(e.args)
try:
    '{} {}'.format(1)
except IndexError as e:
    print(e)
'''
PROGRAMS['fm2'] = r'''class P:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def __format__(self, spec):
        return 'P(%s|%s)' % (self.x, spec)
    def __str__(self):
        return 'strP'
def row(name, qty, price, w=8):
    return '{name:<{w}}|{qty:>5d}|{price:>{pw}.{pp}f}'.format(name=name, qty=qty, price=price, w=w, pw=9, pp=2)
print(row('apple', 3, 1.5))
print(row('kiwi', 12, 22.456, w=3))
items = [('a', 1), ('b', 22)]
for k, v in items:
    print('{k}={v:03d}'.format(k=k, v=v))
d = {'name': 'z', 'w': 6}
print('{name:^{w}}|'.format(**d))
print('{a} {b}'.format(a=1, **{'b': 2}))
class H:
    def __init__(self): self.n = 'attr'; self.v = 7
h = H()
print('{h.n}:{h.v:>{h.v}}'.format(h=h))
print('{0:{1}}|{0:{2}.{3}}'.format(3.14159, 10, 8, 3))
print('{:{}{}}|'.format('ab', '*^', 7))
print('{p}|{p:xyz}|{p!s}|'.format(p=P(1, 2)))
print('{{}} {x!r} {x!a} {x}'.format(x='é'))
print('{0}{1}{0}'.format('ab', 'cd'))
print('{x:,} {y:_d} {z:+.1%} {n:#x} {n:#010b} {n:e}'.format(x=1234567, y=1000000, z=0.256, n=255))
print('{x:>{w}}'.format(x='r', w=0))
print('{0[0]} {0[1]} {1[k]}'.format([5, 6], {'k': 'dv'}))
def fmt(t, **kw):
    return t.format(**kw)
print(fmt('{a}-{b:>4}', a=1, b='x'))
tmpl = 'T:{v:{w}}'
print(tmpl.format(v=5, w=4), tmpl.format(v='s', w=3))
for bad in ('{', '}', '{0', '{x', '{!}', '{:{}', '{0.}', '{a:{b:{c}}}', '{:d}', '{!z}'):
    try:
        print(bad.format('s', a=1, b=2, c=3))
    except Exception as e:
        print(type(e).__name__, e)
try:
    '{} {0}'.format(1)
except ValueError as e:
    print(e)
try:
    '{0} {}'.format(1)
except ValueError as e:
    print(e)
try:
    print('{x:d}'.format(x='s'))
except ValueError as e:
    print(e)
try:
    print('{x:{w}}'.format(x=1, w='q'))
except ValueError as e:
    print(e)
try:
    print('{x:{w}}'.format(x=1))
except KeyError as e:
    print(e.args)
try:
    '{:{}}'.format(1)
except IndexError as e:
    print(e)
'''
PROGRAMS['cv1'] = r'''import csv
import io

rows = [['name', 'note', 'n'], ['a,b', 'say "hi"', 1], ['multi\nline', '', 2.5], [None, 'x y', True], ['', '', ''], []]
buf = io.StringIO()
w = csv.writer(buf)
for r in rows:
    w.writerow(r)
w.writerows([['p', 'q'], ['r,s', 't']])
text = buf.getvalue()
print(repr(text))
for row in csv.reader(io.StringIO(text)):
    print(row)
b2 = io.StringIO()
w2 = csv.writer(b2, delimiter=';', quotechar="'", quoting=csv.QUOTE_ALL, lineterminator='\n')
w2.writerow(['a', "it's", 3])
w2.writerow([])
w2.writerow([''])
print(repr(b2.getvalue()))
b3 = io.StringIO()
w3 = csv.writer(b3, quoting=csv.QUOTE_NONNUMERIC, lineterminator='|')
w3.writerow(['a', 1, 2.5, None, ''])
print(repr(b3.getvalue()))
b4 = io.StringIO()
w4 = csv.writer(b4, quoting=csv.QUOTE_NONE, escapechar='\\', lineterminator='\n')
w4.writerow(['a,b', 'c"d', 'e\\f'])
print(repr(b4.getvalue()))
try:
    csv.writer(io.StringIO(), quoting=csv.QUOTE_NONE).writerow(['a,b'])
except csv.Error as e:
    print('Error', e)
try:
    csv.writer(io.StringIO(), delimiter='ab')
except TypeError as e:
    print(e)
b5 = io.StringIO()
print(csv.writer(b5).writerow(['abc', 'd']))
def emit(out, data):
    wr = csv.writer(out, lineterminator='\n')
    for rec in data:
        wr.writerow(rec)
    return out.getvalue()
class Holder:
    def __init__(self):
        self.buf = io.StringIO()
        self.rows = {'k': ['v,1', 'v"2']}
h = Holder()
print(repr(emit(h.buf, [h.rows['k'], [rows[1][0], rows[1][2]]])))
print(repr(emit(io.StringIO(), [[1, 2], [3]])))
'''
PROGRAMS['cv2'] = r'''import csv
import io

text = 'id,name,score\r\n1,"Smith, J",9.5\r\n2,"say ""x""",\r\n\r\n3,"two\nlines",7\r\n4,short\r\n5,a,b,c\r\n'
r = csv.DictReader(io.StringIO(text))
print(r.fieldnames)
for row in r:
    print(row, r.line_num)
r2 = csv.DictReader(io.StringIO(text), restkey='extra', restval='?')
print([dict(x) for x in r2])
r3 = csv.DictReader(io.StringIO('1;2\n3;4\n'), fieldnames=['a', 'b'], delimiter=';')
print(list(r3))
rd = csv.reader(io.StringIO(text))
hdr = next(rd)
print(hdr, rd.line_num)
print(next(rd), rd.line_num)
rest = list(rd)
print(rest, rd.line_num)
print(next(rd, 'done'))
print(list(csv.reader(io.StringIO(''))), list(csv.reader(io.StringIO('\n'))), list(csv.reader(io.StringIO('a'))))
print(list(csv.reader(io.StringIO('a, "b" ,c\n'), skipinitialspace=True)))
for src in ['"abc', 'a"b"c\n', '"a"b\n', 'x\r\ny\n', 'p\nq\r\n']:
    for strict in (False, True):
        rr = csv.reader(io.StringIO(src), strict=strict)
        out = []
        while True:
            try:
                out.append(next(rr))
            except StopIteration:
                break
            except csv.Error as e:
                out.append('E:' + str(e))
        print(repr(src), strict, out, rr.line_num)
tot = 0
for row in csv.DictReader(io.StringIO('a,b\n1,2\n3,4\n')):
    tot += int(row['a']) * int(row['b'])
print(tot)
rows = [{'k': k, 'v': v} for k, v in csv.reader(io.StringIO('x,1\ny,2\n'))]
print(rows)
def load(s):
    return [row['name'] for row in csv.DictReader(io.StringIO(s))]
print(load('name,x\nA,1\nB,2\n'))
print(list(csv.reader(['1,2', '"3', '4"'])))
print(list(csv.reader(io.StringIO('1,2.5,"x"\n'), quoting=csv.QUOTE_NONNUMERIC)))
'''
PROGRAMS['cv3'] = r'''import csv
import io

fields = ['id', 'name', 'tag']
buf = io.StringIO()
dw = csv.DictWriter(buf, fieldnames=fields, restval='-', lineterminator='\n')
dw.writeheader()
dw.writerow({'id': 1, 'name': 'a,b', 'tag': 'q"r'})
dw.writerow({'id': 2, 'name': 'multi\nline'})
dw.writerows([{'id': 3}, {'name': 'z', 'id': 4, 'tag': None}])
out = buf.getvalue()
print(repr(out))
try:
    dw.writerow({'id': 5, 'bogus': 1})
except ValueError as e:
    print(e)
ig = csv.DictWriter(io.StringIO(), fields, extrasaction='ignore')
print(ig.writerow({'id': 5, 'bogus': 1}))
try:
    csv.DictWriter(io.StringIO(), fields, extrasaction='nope')
except ValueError as e:
    print(e)
back = list(csv.DictReader(io.StringIO(out)))
print(back)
def dump(rows):
    names = sorted({k for r in rows for k in r})
    b = io.StringIO()
    wr = csv.DictWriter(b, fieldnames=names, restval='', lineterminator='\n')
    wr.writeheader()
    wr.writerows(rows)
    return b.getvalue()
print(dump([{'b': 1, 'a': 2}, {'c': 'x,y'}]), end='')
with io.StringIO() as sio:
    csv.writer(sio, lineterminator='\n').writerow(['in', 'with'])
    print(sio.getvalue(), end='')
import sys
cw = csv.writer(sys.stdout, lineterminator='\n')
cw.writerow(['to', 'stdout', 'a,b'])
dw2 = csv.DictWriter(sys.stdout, ['x', 'y'], lineterminator='\n')
dw2.writeheader()
dw2.writerows([{'x': 1, 'y': 2}])
'''
PROGRAMS['cv6'] = r'''import csv
import io
text = 'a,b\n1,"x\ny"\n'
def rows(t):
    return list(csv.DictReader(io.StringIO(t, newline='')))
print(rows(text))
for r in csv.reader(io.StringIO(text, newline='')):
    print(r)
'''


PROGRAMS['fmtenum'] = r'''from enum import Enum, IntEnum, StrEnum, IntFlag, Flag
class N(IntEnum):
    A = 1
    B = 2
class C(IntFlag):
    R = 1
    W = 2
class S(StrEnum):
    X = "x"
class P(Enum):
    Q = 5
class F(Flag):
    A = 1
    B = 2
print(f"{N.A:03}")
print("{:>4}".format(N.A))
print(f"{C.R:03}", "{:>4}".format(C.R))
print(format(N.B, "5d"), format(N.B, ""), f"{N.B!s:>5}")
print(f"{S.X:>3}|{S.X}|{P.Q:>8}|{P.Q}|{F.A:>8}|{F.A|F.B}")
lst=[N.A, N.B]; d={"k":C.W}
print(f"{lst[1]:4d}|{d['k']:<4}|")
def f(x): return "{:x}".format(x) + f"{x:+}"
print(f(N.B), f(C.W|C.R))
try: print(f"{P.Q:d}")
except ValueError as e: print(e)
print(f"{N.A:x>5}", f"{N.A}", "%s %d" % (N.A, N.B))
'''
PROGRAMS['csverr'] = r'''import csv, io
out = io.StringIO()
w = csv.writer(out)
class K: pass
vals = [5, None, 2.5, True, K(), "ab", (1, 2), {"x": 1}, (i for i in range(3)), [], range(2)]
for v in vals:
    try:
        w.writerow(v)
    except csv.Error as e:
        print("E", e)
lst = [7, "z"]
try: w.writerow(lst[0])
except csv.Error as e: print("E", e)
dd = {"k": 3.5}
try: w.writerow(dd["k"])
except csv.Error as e: print("E", e)
def g(x):
    try: w.writerow(x)
    except csv.Error as e: print("E", e)
g(9)
try: w.writerows(5)
except TypeError as e: print("T", e)
try: w.writerows([5])
except csv.Error as e: print("E", e)
print(repr(out.getvalue()))
'''

def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name)


class Refused(unittest.TestCase):
    def refused(self, text, word):
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, text, "r", AIL_UNIFIED_FORCE="1")
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(word, built.stdout + built.stderr)

    def test_wide_flag_member(self):
        self.refused("from enum import Flag\n\nclass W(Flag):\n    A = 1\n    B = 1 << 63\n\nprint(W.A)\n", "63 bits")

    def test_csv_dialect_class(self):
        self.refused("import csv\nimport io\n\nclass D(csv.Dialect):\n    delimiter = ';'\n\nb = io.StringIO()\n"
                     "csv.writer(b, D).writerow([1])\n", "csv.Dialect")


class PreludeCsv(unittest.TestCase):
    """prelude_csv.py (the code the compiler adds) against the csv module."""

    @classmethod
    def setUpClass(cls):
        cls.ns = {}
        exec((PKG / "prelude_csv.py").read_text(encoding="utf-8"), cls.ns)

    @staticmethod
    def fix(x):
        if isinstance(x, list):
            return [(("Error" if i[0] == "_AilCsvError" else i[0]), i[1]) if isinstance(i, tuple) else i for i in x]
        return x

    def test_reader(self):
        import csv

        def compare(text, kw):
            lines = io.StringIO(text, newline="").readlines()

            def run(make):
                out = []
                try:
                    r = make(list(lines), **kw)
                except Exception as e:
                    return ("ctor", type(e).__name__.replace("_AilCsvError", "Error"), str(e))
                for _ in range(60):
                    try:
                        out.append(next(r))
                    except StopIteration:
                        out.append("STOP")
                        break
                    except Exception as e:
                        out.append((type(e).__name__, str(e)))
                out.append(r.line_num)
                return out
            self.assertEqual(self.fix(run(csv.reader)), self.fix(run(self.ns["_ail_csv_reader"])), (text, kw))

        # CI's Python 3.12.5+ parses a QUOTE_NONNUMERIC field that starts with the escapechar as a number;
        # 3.12.0-3.12.4 left it a str. The prelude follows the interpreter it is built with, which is the oracle.
        for text, kw in (("1\\.5,\\.5,.5", {"quoting": csv.QUOTE_NONNUMERIC, "escapechar": "\\"}),
                         ('\\a"1 xa; 1aa', {"quoting": csv.QUOTE_NONNUMERIC, "escapechar": "\\",
                                             "delimiter": "|"}),
                         ("\\1,\\ 2,\\0", {"quoting": csv.QUOTE_NONNUMERIC, "escapechar": "\\"}),
                         ('"'.join(["", "\\.5", ""]), {"quoting": csv.QUOTE_NONNUMERIC, "escapechar": "\\"})):
            compare(text, kw)
        rnd = random.Random(5)
        for _ in range(4000):
            kw = {}
            if rnd.random() < .3:
                kw["delimiter"] = rnd.choice([";", "|", "\t"])
            if rnd.random() < .2:
                kw["quotechar"] = rnd.choice(["'", '"', "|"])
            if rnd.random() < .2:
                kw["escapechar"] = rnd.choice(["\\", "x"])
            if rnd.random() < .2:
                kw["doublequote"] = rnd.random() < .5
            if rnd.random() < .2:
                kw["skipinitialspace"] = rnd.random() < .5
            if rnd.random() < .2:
                kw["strict"] = rnd.random() < .5
            if rnd.random() < .3:
                kw["quoting"] = rnd.choice([0, 1, 2, 3])
            text = "".join(rnd.choice('ab ,"\n\r;\\x1') for _ in range(rnd.randint(0, 25)))
            compare(text, kw)

    def test_reader_escape_numeric(self):
        # gh-113785 (CPython 3.12.5+, 3.13+): under QUOTE_NONNUMERIC a field that starts with the escapechar is
        # numeric. Older hosts (e.g. 3.12.3) keep it a string, and the prelude follows the host.
        rd = self.ns["_ail_csv_reader"]
        new = sys.version_info >= (3, 12, 5)
        self.assertEqual(list(rd(['1\\.5,\\.5,.5'], quoting=2, escapechar="\\")),
                         [[1.5, 0.5, 0.5]] if new else [[1.5, ".5", 0.5]])
        self.assertEqual(list(rd(['1\\.5,\\.5,"\\.5"'], quoting=2, escapechar="\\")),
                         [[1.5, 0.5, ".5"]] if new else [[1.5, ".5", ".5"]])
        if new:
            with self.assertRaises(Exception):
                list(rd(['\\a1'], quoting=2, escapechar="\\"))
        else:
            self.assertEqual(list(rd(['\\a1'], quoting=2, escapechar="\\")), [["a1"]])

    def test_writer(self):
        import csv
        rnd = random.Random(6)
        for _ in range(4000):
            kw = {}
            if rnd.random() < .3:
                kw["delimiter"] = rnd.choice([";", "|", "\t"])
            if rnd.random() < .2:
                kw["quotechar"] = rnd.choice(["'", '"', "|"])
            if rnd.random() < .3:
                kw["escapechar"] = rnd.choice(["\\", "x"])
            if rnd.random() < .2:
                kw["doublequote"] = rnd.random() < .5
            if rnd.random() < .3:
                kw["quoting"] = rnd.choice([0, 1, 2, 3])
            if rnd.random() < .3:
                kw["lineterminator"] = rnd.choice(["\n", "|", "\r\n"])
            rows = [[rnd.choice([None, "", 1, 2.5, True, "a b", "x,y", 'q"r', "l\nm", "\\", "|;", -3, "z"])
                     for _ in range(rnd.randint(0, 4))] for _ in range(rnd.randint(1, 4))]

            def run(make):
                f = io.StringIO()
                try:
                    w = make(f, **kw)
                except Exception as e:
                    return ("ctor", type(e).__name__)
                res = []
                for r in rows:
                    try:
                        res.append(w.writerow(r))
                    except Exception as e:
                        res.append((type(e).__name__.replace("_AilCsvError", "Error"), str(e)))
                return res, f.getvalue()
            self.assertEqual(run(csv.writer), run(self.ns["_ail_csv_writer"]), (rows, kw))

    def test_dict_reader_writer(self):
        import csv
        rnd = random.Random(7)
        for _ in range(2000):
            text = "".join(rnd.choice('ab,\n"') for _ in range(rnd.randint(0, 30)))
            fn = rnd.choice([None, ["x", "y"], ["p"]])
            rk = rnd.choice([None, "REST"])

            def rd(make):
                out = []
                r = make(text.splitlines(True), fieldnames=fn, restkey=rk, restval="RV")
                for _ in range(20):
                    try:
                        out.append(next(r))
                    except StopIteration:
                        out.append("S")
                        break
                    except Exception as e:
                        out.append(type(e).__name__.replace("_AilCsvError", "Error"))
                return out, r.fieldnames, r.line_num
            self.assertEqual(rd(csv.DictReader), rd(self.ns["_ail_csv_DictReader"]), (text, fn, rk))
        for _ in range(2000):
            names = rnd.choice([["a", "b"], ["b", "a", "c"]])
            extra = rnd.choice(["raise", "ignore"])
            rows = [{k: rnd.choice([1, "x,y", None, 2.5]) for k in rnd.sample(["a", "b", "c", "d"], rnd.randint(0, 3))}
                    for _ in range(3)]

            def dw(make):
                f = io.StringIO()
                w = make(f, names, restval="R", extrasaction=extra)
                res = [w.writeheader()]
                for r in rows:
                    try:
                        res.append(w.writerow(r))
                    except Exception as e:
                        res.append(type(e).__name__)
                return res, f.getvalue()
            self.assertEqual(dw(csv.DictWriter), dw(self.ns["_ail_csv_DictWriter"]), (rows, names, extra))


if __name__ == "__main__":
    unittest.main()
