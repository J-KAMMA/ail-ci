"""bool, set/dict API gaps and container-argument semantics, each checked against CPython.

* `bool`: `-> bool`, `x: bool`, `let ok: bool`, struct fields, `list[bool]`, True/False, `not`,
  `and`/`or` of bools, `bool(x)`. A bool is an int64 0/1 (arithmetic, `sum(flags)`, conditions), and
  prints as Python does: `print`, `str()`, a spec-less f-string/`.format()` field and `%s` show
  True/False; `{b:>5}` and `%d` format the number. Comparisons, `in`, `is`, `not` and the predicates
  are bools too, so `print(3 > 2)` shows True (it showed 1). A declared bool slot refuses an int.
* sets: `list(s)`, `== != < <= > >=`, union/intersection/difference/symmetric_difference (and the
  `*_update` statements), issubset/issuperset/isdisjoint, `s.pop()` (the newest element: AIL sets
  keep insertion order; KeyError when empty), for set[int], set[str], fields and unannotated int sets.
* dicts: `list(d)`, `list(d.keys())`, `list(d.values())`; one-argument `d.get(k)` is refused (no None
  for a value) with the `d.get(k, default)` rewrite.
* list fields: `x in st.xs` and `st.xs.count(x)` read the field in place (no copy in the C).
* `f(d, d.pop(3))`: every container argument is the caller's object after all arguments ran, as in
  CPython (a dict argument used to be copied before the pop), for locals and for fields changed in
  place; a field replaced by a callee still passes the old object.
* `xs[f()] += v` (locals, fields, dicts) evaluates the index once, as Python does.
* `let flat = items;` copying an annotated `list[int]` keeps its kind, so `show(flat)` compiles.
* a 9-field struct local in main passed field by field (`total += f(s.d, ...)`) compiles.
* sorting empty lists never calls qsort(NULL, 0, ...); every program here also runs clean under
  ASan+UBSan.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BOOL_AIL = """
struct Flag { ok: bool; n: int; marks: list[bool]; }
impl Flag {
    fn good(self) -> bool { return self.ok and self.n > 0; }
    fn flip(self) -> void { self.ok = not self.ok; }
}
fn pos(x: int) -> bool { return x > 0; }
fn both(a: bool, b: bool) -> bool { return a and b; }
fn count_true(xs: list[bool]) -> int {
    let c = 0;
    for x in xs { if x { c += 1; } }
    return c;
}
fn as_int(x: int) -> int { return x > 2; }
fn evens(n: int) -> list[bool] { return [i % 2 == 0 for i in range(n)]; }
fn main() {
    let t = True;
    let f: bool = False;
    let cmp = 3 < 2;
    let fl = Flag(True, 3, [False] * 3);
    print(t, f, cmp, not t, t and f, t or f, pos(5), pos(-5), both(t, pos(1)));
    print(fl.ok, fl.good(), fl.marks[0], len(fl.marks));
    fl.flip();
    fl.marks[1] = True;
    print(fl.ok, fl.good(), fl.marks[1], count_true(fl.marks), Flag(ok=False, n=1, marks=[]).ok);
    print(str(t), str(3 == 3), f"{t}|{f}|{1 < 2}", "%s %s" % (t, 2 > 3), "{} {}".format(f, t));
    print(f"{t:>5}|{f:d}|{t:<3}|", "%d" % t, "%5s|" % f);
    print(t + t, f * 3, as_int(5), int(t) + 1, -t);
    let xs = [1, 2, 3];
    print(2 in xs, 9 in xs, 9 not in xs, len(xs) == 3 and xs[0] == 1, xs[0] == 1 or xs[1] == 5);
    let mk = fl.marks;
    print("ab".startswith("a"), "x1".isdigit(), "AB".isupper(), bool(0), bool(5), bool(""), bool(xs), any(mk), all(mk));
    let seen = [False] * 4;
    seen[2] = True;
    for i in range(4) { if seen[i] { print("seen", i, seen[i]); } }
    let ok = True;
    for x in xs { ok = ok and x > 0; }
    print(ok, ok == True, ok != False);
    let c = 3 > 1;
    c += 1;
    print(c);
    let flags = [x > 1 for x in xs];
    print(flags[0], flags[2], len(flags));
    for g in flags { print("flag", g); }
    let total = 0;
    for x in xs { total += x > 1; }
    print(total, sum(flags));
    let e = 5;
    print(e if t else 0, t if e > 3 else f, not e, not 0);
    let ev = evens(3);
    print(ev[0], ev[1], len(ev));
    let found = False;
    for x in xs { if x == 2 { found = True; } }
    print("found", found);
    let w = "hello";
    print(w == "hello", w < "abc", "ell" in w, b"ab" == b"ab");
    for g in flags { print(g); }
    let strs = [str(q) for q in flags];
    print(",".join(strs), "%s|%5s|" % (flags[0], 1 > 0));
    return 0;
}
"""

BOOL_PY = """
class Flag:
    def __init__(self, ok, n, marks): self.ok, self.n, self.marks = ok, n, marks
    def good(self): return self.ok and self.n > 0
    def flip(self): self.ok = not self.ok


def pos(x): return x > 0
def both(a, b): return a and b
def count_true(xs): return sum(1 for x in xs if x)
def as_int(x): return int(x > 2)
def evens(n): return [i % 2 == 0 for i in range(n)]


def main():
    t = True
    f = False
    cmp = 3 < 2
    fl = Flag(True, 3, [False] * 3)
    print(t, f, cmp, not t, t and f, t or f, pos(5), pos(-5), both(t, pos(1)))
    print(fl.ok, fl.good(), fl.marks[0], len(fl.marks))
    fl.flip()
    fl.marks[1] = True
    print(fl.ok, fl.good(), fl.marks[1], count_true(fl.marks), Flag(ok=False, n=1, marks=[]).ok)
    print(str(t), str(3 == 3), f"{t}|{f}|{1 < 2}", "%s %s" % (t, 2 > 3), "{} {}".format(f, t))
    print(f"{t:>5}|{f:d}|{t:<3}|", "%d" % t, "%5s|" % f)
    print(t + t, f * 3, as_int(5), int(t) + 1, -t)
    xs = [1, 2, 3]
    print(2 in xs, 9 in xs, 9 not in xs, len(xs) == 3 and xs[0] == 1, xs[0] == 1 or xs[1] == 5)
    mk = list(fl.marks)
    print("ab".startswith("a"), "x1".isdigit(), "AB".isupper(), bool(0), bool(5), bool(""), bool(xs), any(mk), all(mk))
    seen = [False] * 4
    seen[2] = True
    for i in range(4):
        if seen[i]:
            print("seen", i, seen[i])
    ok = True
    for x in xs:
        ok = ok and x > 0
    print(ok, ok == True, ok != False)
    c = 3 > 1
    c += 1
    print(c)
    flags = [x > 1 for x in xs]
    print(flags[0], flags[2], len(flags))
    for g in flags:
        print("flag", g)
    total = 0
    for x in xs:
        total += x > 1
    print(total, sum(flags))
    e = 5
    print(e if t else 0, t if e > 3 else f, not e, not 0)
    ev = evens(3)
    print(ev[0], ev[1], len(ev))
    found = False
    for x in xs:
        if x == 2:
            found = True
    print("found", found)
    w = "hello"
    print(w == "hello", w < "abc", "ell" in w, b"ab" == b"ab")
    for g in flags:
        print(g)
    strs = [str(q) for q in flags]
    print(",".join(strs), "%s|%5s|" % (flags[0], 1 > 0))


main()
"""

SETS_AIL = """
struct Bag { s: set[int]; t: set[str]; xs: list[int]; ws: list[str]; fs: list[float]; d: dict[str, int]; }
fn show(xs: list[int]) -> str {
    let parts: list[str] = [];
    for x in xs { parts.append(str(x)); }
    return ",".join(parts);
}
fn shows(s: set[int]) -> str { let l = sorted(s); return show(l); }
fn showt(s: set[str]) -> str { let l = sorted(s); return ",".join(l); }
fn field_hits(b: Bag, x: int, w: str) -> int {
    let n = b.xs.count(x) + b.ws.count(w);
    if x in b.xs { n += 10; }
    if w not in b.ws { n += 100; }
    return n;
}
fn main() {
    let a: set[int] = {5, 1, 3};
    let b: set[int] = {3, 4};
    let c: set[int] = {9};
    print(shows(a.union(b)), shows(a.union(b, c)), shows(a.intersection(b)), shows(a.difference(b)), shows(a.symmetric_difference(b)));
    print(a.issubset(b), a.issuperset({1, 3}), a.isdisjoint(b), a.isdisjoint(c), {1, 3}.issubset(a));
    let a2: set[int] = {3, 1, 5};
    print(a == a2, a != a2, a == b, a != b, a <= a2, a < a2, a < a.union(c), a > {1}, a >= b);
    let e: set[int] = set();
    print(e == set(), e <= a, e < a, a > e, e.isdisjoint(a));
    let u: set[int] = {1, 2, 3, 4};
    u.intersection_update({2, 3, 7});
    print(shows(u));
    u.difference_update({3});
    print(shows(u));
    u.symmetric_difference_update({2, 8});
    print(shows(u));
    let one: set[int] = {42};
    print(one.pop(), len(one));
    try { one.pop(); print("no"); } except KeyError { print("empty pop"); }
    let many: set[int] = {4, 8, 15, 16};
    let popped: list[int] = [];
    while len(many) > 0 { popped.append(many.pop()); }
    popped.sort();
    print(show(popped));
    let l = list(a);
    l.sort();
    print(show(l), len(list(e)));
    let s1: set[str] = {"b", "a"};
    let s2: set[str] = {"a", "c"};
    print(showt(s1.union(s2)), showt(s1 & s2), s1 == {"a", "b"}, s1 <= s2, s1.isdisjoint({"z"}), s1.issuperset({"a"}));
    let sone: set[str] = {"zz"};
    print(sone.pop(), len(sone));
    let words = list(s1);
    words.sort();
    print(",".join(words));
    let d: dict[int, int] = {3: 30, 1: 10, 2: 20};
    let dk = list(d);
    let dk2 = list(d.keys());
    let dv = list(d.values());
    print(show(dk), show(dk2), show(dv), d.get(1, -1), d.get(9, -1));
    let ds: dict[str, str] = {"x": "1", "y": "2"};
    print(",".join(list(ds)), ",".join(list(ds.values())));
    let df: dict[str, float] = {"p": 1.5};
    let fv = list(df.values());
    print(fv[0]);
    let chars = list("héllo");
    print(len(chars), chars[1], len(list("")) == 0);
    let bag = Bag({1, 2}, {"p", "q"}, [4, 5, 5, 6], ["a", "b", "a"], [1.5, 2.0, 1.5], {"k": 1});
    print(5 in bag.xs, 7 in bag.xs, 7 not in bag.xs, bag.xs.count(5), bag.xs.count(9));
    print("a" in bag.ws, "z" in bag.ws, "z" not in bag.ws, bag.ws.count("a"), bag.fs.count(1.5), bag.fs.count(2));
    print(bag.s == {2, 1}, bag.s.issubset(a), bag.t.isdisjoint(s1), shows(bag.s | a));
    print(field_hits(bag, 5, "a"), field_hits(bag, 9, "z"));
    let ok12: set[int] = {1, 2};
    print(bag.s.pop() in ok12, len(bag.s));
    let un = {7, 3};
    let un2 = {3, 7};
    print(un == un2, un != un2, un <= un2, un.isdisjoint({1}), len(un.union(un2)));
    let k = un.pop();
    print(k == 3 or k == 7, len(un));
    let r = list(range(3));
    print(show(r), show(list(r)));
    return 0;
}
"""

SETS_PY = """
class Bag:
    def __init__(self, s, t, xs, ws, fs, d): self.s, self.t, self.xs, self.ws, self.fs, self.d = s, t, xs, ws, fs, d


def show(xs): return ",".join(str(x) for x in xs)
def shows(s): return show(sorted(s))
def showt(s): return ",".join(sorted(s))


def field_hits(b, x, w):
    n = b.xs.count(x) + b.ws.count(w)
    if x in b.xs:
        n += 10
    if w not in b.ws:
        n += 100
    return n


def main():
    a = {5, 1, 3}
    b = {3, 4}
    c = {9}
    print(shows(a.union(b)), shows(a.union(b, c)), shows(a.intersection(b)), shows(a.difference(b)), shows(a.symmetric_difference(b)))
    print(a.issubset(b), a.issuperset({1, 3}), a.isdisjoint(b), a.isdisjoint(c), {1, 3}.issubset(a))
    a2 = {3, 1, 5}
    print(a == a2, a != a2, a == b, a != b, a <= a2, a < a2, a < a.union(c), a > {1}, a >= b)
    e = set()
    print(e == set(), e <= a, e < a, a > e, e.isdisjoint(a))
    u = {1, 2, 3, 4}
    u.intersection_update({2, 3, 7})
    print(shows(u))
    u.difference_update({3})
    print(shows(u))
    u.symmetric_difference_update({2, 8})
    print(shows(u))
    one = {42}
    print(one.pop(), len(one))
    try:
        one.pop()
        print("no")
    except KeyError:
        print("empty pop")
    many = {4, 8, 15, 16}
    popped = []
    while len(many) > 0:
        popped.append(many.pop())
    popped.sort()
    print(show(popped))
    l = list(a)
    l.sort()
    print(show(l), len(list(e)))
    s1 = {"b", "a"}
    s2 = {"a", "c"}
    print(showt(s1.union(s2)), showt(s1 & s2), s1 == {"a", "b"}, s1 <= s2, s1.isdisjoint({"z"}), s1.issuperset({"a"}))
    sone = {"zz"}
    print(sone.pop(), len(sone))
    words = list(s1)
    words.sort()
    print(",".join(words))
    d = {3: 30, 1: 10, 2: 20}
    print(show(list(d)), show(list(d.keys())), show(list(d.values())), d.get(1, -1), d.get(9, -1))
    ds = {"x": "1", "y": "2"}
    print(",".join(list(ds)), ",".join(list(ds.values())))
    df = {"p": 1.5}
    fv = list(df.values())
    print(fv[0])
    chars = list("héllo")
    print(len(chars), chars[1], len(list("")) == 0)
    bag = Bag({1, 2}, {"p", "q"}, [4, 5, 5, 6], ["a", "b", "a"], [1.5, 2.0, 1.5], {"k": 1})
    print(5 in bag.xs, 7 in bag.xs, 7 not in bag.xs, bag.xs.count(5), bag.xs.count(9))
    print("a" in bag.ws, "z" in bag.ws, "z" not in bag.ws, bag.ws.count("a"), bag.fs.count(1.5), bag.fs.count(2))
    print(bag.s == {2, 1}, bag.s.issubset(a), bag.t.isdisjoint(s1), shows(bag.s | a))
    print(field_hits(bag, 5, "a"), field_hits(bag, 9, "z"))
    ok12 = {1, 2}
    print(bag.s.pop() in ok12, len(bag.s))
    un = {7, 3}
    un2 = {3, 7}
    print(un == un2, un != un2, un <= un2, un.isdisjoint({1}), len(un.union(un2)))
    k = un.pop()
    print(k == 3 or k == 7, len(un))
    r = list(range(3))
    print(show(r), show(list(r)))


main()
"""

ORDER_AIL = """
fn f(d: dict[int, int], x: int) -> int { return len(d) * 100 + x; }
fn g(xs: list[int], x: int) -> int { return len(xs) * 100 + x; }
fn h(s: set[int], x: int) -> int { return len(s) * 100 + x; }
fn w(ws: list[str], x: str) -> int { return len(ws) * 100 + len(x); }
fn sd(d: dict[str, int], x: int) -> int { return len(d) * 100 + x; }
fn fl(xs: list[float], x: float) -> float { return float(len(xs)) * 100.0 + x; }
struct Box { d: dict[int, int]; xs: list[int]; ws: list[str]; fs: list[float]; s: set[str]; }
fn reset(b: Box) -> int { b.d = {}; return 7; }
fn ss(s: set[str], x: str) -> int { return len(s) * 100 + len(x); }
fn order_local() -> int {
    let d: dict[int, int] = {1: 10, 3: 30, 5: 50};
    return f(d, d.pop(3)) + f(d, d.pop(5, 0)) * 1000;
}
fn main() {
    let d: dict[int, int] = {1: 10, 3: 30};
    print(f(d, d.pop(3)), len(d));
    let xs = [1, 2, 3];
    print(g(xs, xs.pop()), len(xs));
    let s: set[int] = {7};
    print(h(s, s.pop()), len(s));
    let ws = ["a", "bb"];
    print(w(ws, ws.pop()), len(ws));
    let e: dict[str, int] = {"a": 1, "b": 2};
    print(sd(e, e.pop("a")));
    let bx = Box({1: 1, 2: 2}, [1, 2, 3], ["x", "yy"], [1.5, 2.5], {"q"});
    print(f(bx.d, bx.d.pop(1)), g(bx.xs, bx.xs.pop()), w(bx.ws, bx.ws.pop()), fl(bx.fs, bx.fs.pop()), ss(bx.s, bx.s.pop()));
    print(f(bx.d, reset(bx)), len(bx.d));
    print(order_local());
    return 0;
}
"""

ORDER_PY = """
def f(d, x): return len(d) * 100 + x
def g(xs, x): return len(xs) * 100 + x
def h(s, x): return len(s) * 100 + x
def w(ws, x): return len(ws) * 100 + len(x)
def sd(d, x): return len(d) * 100 + x
def fl(xs, x): return float(len(xs)) * 100.0 + x


class Box:
    def __init__(self, d, xs, ws, fs, s): self.d, self.xs, self.ws, self.fs, self.s = d, xs, ws, fs, s


def reset(b):
    b.d = {}
    return 7


def ss(s, x): return len(s) * 100 + len(x)


def order_local():
    d = {1: 10, 3: 30, 5: 50}
    return f(d, d.pop(3)) + f(d, d.pop(5, 0)) * 1000


def main():
    d = {1: 10, 3: 30}
    print(f(d, d.pop(3)), len(d))
    xs = [1, 2, 3]
    print(g(xs, xs.pop()), len(xs))
    s = {7}
    print(h(s, s.pop()), len(s))
    ws = ["a", "bb"]
    print(w(ws, ws.pop()), len(ws))
    e = {"a": 1, "b": 2}
    print(sd(e, e.pop("a")))
    bx = Box({1: 1, 2: 2}, [1, 2, 3], ["x", "yy"], [1.5, 2.5], {"q"})
    print(f(bx.d, bx.d.pop(1)), g(bx.xs, bx.xs.pop()), w(bx.ws, bx.ws.pop()), fl(bx.fs, bx.fs.pop()), ss(bx.s, bx.s.pop()))
    print(f(bx.d, reset(bx)), len(bx.d))
    print(order_local())


main()
"""

NINE_AIL = """
struct S { d: dict[int, int]; sd: dict[str, int]; si: set[int]; ss: set[str]; xs: list[int]; fs: list[float]; ws: list[str]; t: str; b: bytes; }
fn dget(d: dict[int, int], k: int) -> int { if k in d { return d[k]; } return -1; }
fn sdget(d: dict[str, int], k: str) -> int { return d.get(k, -1); }
fn sihas(s: set[int], k: int) -> int { if k in s { return 1; } return 0; }
fn xsat(xs: list[int], k: int) -> int { return xs[k] + len(xs); }
fn fsat(fs: list[float], k: int) -> float { return fs[k]; }
fn wslen(ws: list[str], k: int) -> int { return len(ws[k]) + len(ws); }
fn tlen(t: str, k: int) -> int { return len(t) + k; }
fn blen(b: bytes, k: int) -> int { return len(b) + b[k]; }
fn main() {
    let s = S({}, {}, set(), set(), [], [], [], "text", b"bytes");
    for i in range(50) { s.d[i] = i; s.sd["k" + str(i)] = i; s.si.add(i); s.ss.add(str(i)); s.xs.append(i); s.fs.append(float(i)); s.ws.append("w"); }
    let total = 0;
    for i in range(50) {
        total += dget(s.d, i) + sdget(s.sd, "k" + str(i)) + sihas(s.si, i);
        total += xsat(s.xs, i) + int(fsat(s.fs, i)) + wslen(s.ws, i) + tlen(s.t, i) + blen(s.b, 1);
    }
    print(total);
}
"""

NINE_PY = """
class S:
    def __init__(self, d, sd, si, ss, xs, fs, ws, t, b):
        self.d, self.sd, self.si, self.ss, self.xs, self.fs, self.ws, self.t, self.b = d, sd, si, ss, xs, fs, ws, t, b


def dget(d, k): return d[k] if k in d else -1
def sdget(d, k): return d.get(k, -1)
def sihas(s, k): return 1 if k in s else 0
def xsat(xs, k): return xs[k] + len(xs)
def fsat(fs, k): return fs[k]
def wslen(ws, k): return len(ws[k]) + len(ws)
def tlen(t, k): return len(t) + k
def blen(b, k): return len(b) + b[k]


def main():
    s = S({}, {}, set(), set(), [], [], [], "text", b"bytes")
    for i in range(50):
        s.d[i] = i
        s.sd["k" + str(i)] = i
        s.si.add(i)
        s.ss.add(str(i))
        s.xs.append(i)
        s.fs.append(float(i))
        s.ws.append("w")
    total = 0
    for i in range(50):
        total += dget(s.d, i) + sdget(s.sd, "k" + str(i)) + sihas(s.si, i)
        total += xsat(s.xs, i) + int(fsat(s.fs, i)) + wslen(s.ws, i) + tlen(s.t, i) + blen(s.b, 1)
    print(total)


main()
"""

AUG_AIL = """
struct C { n: int; xs: list[int]; fs: list[float]; }
impl C { fn next(self) -> int { self.n += 1; return self.n - 1; } }
fn show(xs: list[int]) -> str { return str(len(xs)) + ":" + str(xs[0]); }
fn main() {
    let c = C(0, [0, 0, 0, 0], [0.0, 0.0, 0.0]);
    let ys = [0, 0, 0, 0];
    ys[c.next()] += 5;
    ys[c.next()] += 7;
    c.xs[c.next()] += 3;
    c.fs[c.next() - 3] += 1.5;
    print(c.n, ys[0], ys[1], ys[2], c.xs[2], c.fs[0]);
    let items = [4, 5, 6];
    let flat = items;
    print(show(flat));
    let held: list[int] = [];
    held.append(3);
    let copy = held;
    copy.append(9);
    print(show(copy), len(held));
    let d = {0: 1, 1: 1};
    d[c.next() - 4] += 4;
    let ws = ["a", "b"];
    ws[c.next() - 4] += "z";
    print(c.n, d[0], d[1], ws[0], ws[1]);
    return 0;
}
"""

AUG_PY = """
class C:
    def __init__(self, n, xs, fs): self.n, self.xs, self.fs = n, xs, fs
    def next(self):
        self.n += 1
        return self.n - 1


def show(xs): return str(len(xs)) + ":" + str(xs[0])


def main():
    c = C(0, [0, 0, 0, 0], [0.0, 0.0, 0.0])
    ys = [0, 0, 0, 0]
    ys[c.next()] += 5
    ys[c.next()] += 7
    c.xs[c.next()] += 3
    c.fs[c.next() - 3] += 1.5
    print(c.n, ys[0], ys[1], ys[2], c.xs[2], c.fs[0])
    items = [4, 5, 6]
    flat = list(items)
    print(show(flat))
    held = []
    held.append(3)
    copy = list(held)
    copy.append(9)
    print(show(copy), len(held))
    d = {0: 1, 1: 1}
    d[c.next() - 4] += 4
    ws = ["a", "b"]
    ws[c.next() - 4] += "z"
    print(c.n, d[0], d[1], ws[0], ws[1])


main()
"""

EMPTY_AIL = """
struct P { a: int; b: str; w: float; }
struct H { ps: list[P]; xs: list[int]; }
fn main() {
    let xs: list[int] = [];
    xs.sort();
    xs.sort(reverse=True);
    let ys = sorted(xs);
    let zs = sorted(xs, reverse=True);
    let fs: list[float] = [];
    fs.sort();
    fs.sort(reverse=True);
    let ws: list[str] = [];
    ws.sort();
    ws.sort(reverse=True);
    let vs = sorted(ws);
    let ps: list[P] = [];
    ps.sort(key=lambda p: p.a);
    ps.sort(key=lambda p: (-p.a, p.b));
    ps.sort(key=lambda p: p.w);
    let qs = sorted(ps, key=lambda p: p.b);
    let idx: list[int] = [];
    idx.sort(key=lambda i: (-xs[i], ws[i]));
    let d: dict[str, int] = {};
    let dk = sorted(d);
    for k, v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])) { print(k, v); }
    let di: dict[int, int] = {};
    let dik = sorted(di);
    let s: set[int] = set();
    let sk = sorted(s);
    let ss: set[str] = set();
    let ssk = sorted(ss);
    let bs: list[bytes] = [];
    bs.sort();
    let h = H([], []);
    h.ps.sort(key=lambda p: p.a);
    let hx = h.xs;
    hx.sort();
    let one = [5];
    one.sort();
    let us = {3, 1};
    let ul = sorted(us);
    let ue = set();
    ue.add(1);
    ue.discard(1);
    let uel = sorted(ue);
    print(len(ys), len(zs), len(vs), len(qs), len(dk), len(dik), len(sk), len(ssk), len(bs), len(h.ps), len(one), len(ul), len(uel), len(idx));
    return 0;
}
"""

EMPTY_OUT = "0 0 0 0 0 0 0 0 0 0 1 2 0 0\n"

REFUSED = [
    # (source, location prefix, the rewrite the message must give)
    ('fn f() -> bool { return 1; }\nfn main() { print(f()); }', 'prog.ail:1:', '1 != 0'),
    ('fn main() {\n    let ok: bool = 1;\n    print(ok);\n}', 'prog.ail:2:', '1 != 0'),
    ('struct S { ok: bool; }\nfn main() { let s = S(2); print(s.ok); }', 'prog.ail:2:', '2 != 0'),
    ('fn g(b: bool) -> int { return 1; }\nfn main() {\n    print(g(5));\n}', 'prog.ail:3:', '5 != 0'),
    ('fn main() {\n    let fl: list[bool] = [False] * 3;\n    fl[0] = 1;\n    print(fl[0]);\n}', 'prog.ail:3:', '1 != 0'),
    ('fn main() {\n    let ok: bool = True;\n    ok += 1;\n    print(ok);\n}', 'prog.ail:3:', 'assign a bool'),
    ('fn main() {\n    let d: dict[int, int] = {1: 2};\n    print(d.get(1));\n}', 'prog.ail:3:', 'd.get(k, -1)'),
    ('fn main() {\n    let d = {1: 2};\n    print(d.get(1));\n}', 'prog.ail:3:', 'd.get(k, -1)'),
    ('fn main() {\n    let d: dict[int, int] = {1: 2};\n    let l = list(d.items());\n    print(len(l));\n}',
     'prog.ail:3:', 'for k, v in d.items()'),
    ('fn main() {\n    let s: set[int] = {1};\n    let xs = [1];\n    print(s == xs);\n}', 'prog.ail:4:', 'compare two sets'),
    ('fn main() {\n    let s: set[int] = {1};\n    let xs = [1, 2];\n    let u = s.union(xs);\n    print(len(u));\n}',
     'prog.ail:4:', 'set(xs)'),
    ('fn main() {\n    let s = set();\n    s.add("a");\n    print(s.pop());\n}', 'prog.ail:4:', 'let s: set[str] = set();'),
    ('fn main() {\n    let s: set[int] = {1};\n    print(s.pop(1));\n}', 'prog.ail:3:', 's.remove(x)'),
    ('fn main() {\n    let a: set[int] = {1};\n    print(a <= a <= a);\n}', 'prog.ail:3:', 'a <= b and b <= c'),
    ('fn main() {\n    let xs = [1];\n    xs.frob();\n    print(1);\n}', 'prog.ail:3:', 'a list has append'),
]


def build(directory, text, name="p"):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


def sanitized(test, c_file, directory, name):
    """Build the generated C with ASan+UBSan (no recovery) and return the run, or skip."""
    gcc = shutil.which("gcc")
    if gcc is None:
        test.skipTest("gcc not found")
    exe = Path(directory, name + "-san")
    built = subprocess.run([gcc, "-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                            "-std=gnu11", "-o", str(exe), str(c_file), "-lm"],
                           capture_output=True, text=True, timeout=300)
    if built.returncode != 0:
        test.skipTest("gcc cannot build with sanitizers here: " + built.stderr[-300:])
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)


class LangGapTests(unittest.TestCase):
    def check(self, source, oracle, name, sanitize=True):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, source, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", oracle], capture_output=True, text=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            if sanitize:
                san = sanitized(self, c_file, directory, name)
                self.assertEqual((san.returncode, san.stderr), (0, ""))
                self.assertEqual(san.stdout, expected.stdout)
            return c_file.read_text()

    def test_bool_matches_cpython(self):
        program = self.check(BOOL_AIL, BOOL_PY, "bools")
        self.assertIn('"True"', program)

    def test_sets_dicts_and_list_fields_match_cpython(self):
        program = self.check(SETS_AIL, SETS_PY, "sets")
        body = body_of(program, "field_hits")
        for call in ("ail_list_count(&(v_b)->f_xs", "ail_slist_count(&(v_b)->f_ws",
                     "ail_list_has(&(v_b)->f_xs", "ail_slist_has(&(v_b)->f_ws"):
            self.assertIn(call, body)
        for copy in ("snapshot", "_copy", "ail_list_push", "ail_slist_push"):
            self.assertNotIn(copy, body)

    def test_container_arguments_follow_cpython(self):
        program = self.check(ORDER_AIL, ORDER_PY, "order")
        body = body_of(program, "order_local")
        self.assertNotIn("ail_idict_copy", body)

    def test_augmented_index_runs_once_and_list_copies_keep_their_kind(self):
        self.check(AUG_AIL, AUG_PY, "aug")

    def test_nine_field_struct_local_in_main(self):
        self.check(NINE_AIL, NINE_PY, "nine", sanitize=False)

    def test_empty_sorts_are_clean_under_sanitizers(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, EMPTY_AIL, "empty")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual((ran.returncode, ran.stdout), (0, EMPTY_OUT), ran.stderr)
            san = sanitized(self, c_file, directory, "empty")
            self.assertEqual((san.returncode, san.stderr, san.stdout), (0, "", EMPTY_OUT))

    def test_refusals_name_the_rewrite(self):
        for source, where, hint in REFUSED:
            with self.subTest(source=source[:60]), tempfile.TemporaryDirectory() as tmp:
                Path(tmp, "prog.ail").write_text(source + "\n", encoding="utf-8")
                proc = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                                       "prog.ail", "-o", "prog"], cwd=tmp, capture_output=True,
                                      text=True, timeout=300)
                self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
                self.assertTrue(proc.stderr.startswith(where), proc.stderr)
                self.assertIn(hint, proc.stderr)
                self.assertFalse(Path(tmp, "prog").exists())


if __name__ == "__main__":
    unittest.main()
