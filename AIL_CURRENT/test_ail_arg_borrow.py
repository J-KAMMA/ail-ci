"""Container and text arguments are borrowed, not copied, when nothing can change them mid-call.

`list`/`dict`/`set` parameters are read-only, yet a call copied a typed dict or set argument
(dict[str|int, T], set[int|str]) and a list[str] spine on every call, and a FIELD argument of any
container (and str) kind -- `score(st.idx, k)` -- was snapshotted too. A read-only helper called
in a loop with a big container became O(n) per call, so the loop was quadratic.

Now such an argument is handed over as the caller's own value (a pointer, or a view struct):
* a local or parameter name, unless the call contains `:=` or the name is a loop variable
  (another argument changing it in place, `pair(d, d.pop(3))`, is no reason to copy: Python
  passes the same object, so the callee sees the change);
* a field `o.f` of a struct local or parameter, unless the callee (transitively) or another
  argument may store field `f` or change its contents on any object (whole-program mutation
  summary next to `_scan_field_stores`), or may run unknown code (a callable value).
The callee never frees or changes a parameter, so exceptions unwind as before.

Every case runs against CPython, written with explicit copies where AIL's value semantics differ
from Python aliasing: fields replaced or grown while the callee still holds the old value,
directly, transitively, by another argument, through a callback and by a method; exceptions raised
inside a callee with borrowed arguments; recursion passing the same field down.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct S { d: dict[int, int]; sd: dict[str, int]; si: set[int]; ss: set[str]; xs: list[int]; fs: list[float]; ws: list[str]; t: str; b: bytes; }

fn dget(d: dict[int, int], k: int) -> int { if k in d { return d[k]; } return -1; }
fn sdget(d: dict[str, int], k: str) -> int { return d.get(k, -1); }
fn sihas(s: set[int], k: int) -> int { if k in s { return 1; } return 0; }
fn sshas(s: set[str], k: str) -> int { if k in s { return 1; } return 0; }
fn xsat(xs: list[int], k: int) -> int { return xs[k] + len(xs); }
fn fsat(fs: list[float], k: int) -> float { return fs[k]; }
fn wslen(ws: list[str], k: int) -> int { return len(ws[k]) + len(ws); }
fn tlen(t: str, k: int) -> int { return len(t) + k; }
fn blen(b: bytes, k: int) -> int { return len(b) + b[k]; }

fn swap_d(d: dict[int, int], s: S) -> int {
    let nd: dict[int, int] = {};
    nd[1] = 100;
    s.d = nd;
    return len(d) * 1000 + len(s.d) * 100 + dget(d, 2);
}
fn swap_sd(d: dict[str, int], s: S) -> int {
    let nd: dict[str, int] = {};
    s.sd = nd;
    return len(d) * 10 + len(s.sd);
}
fn swap_si(x: set[int], s: S) -> int {
    let n: set[int] = set();
    s.si = n;
    return len(x) * 10 + len(s.si);
}
fn swap_ss(x: set[str], s: S) -> int {
    let n: set[str] = set();
    n.add("only");
    s.ss = n;
    return len(x) * 10 + len(s.ss) + sshas(x, "b");
}
fn grow_xs(xs: list[int], s: S) -> int {
    s.xs.append(7);
    s.xs[0] = 99;
    return xs[0] * 1000 + len(xs) * 10 + len(s.xs);
}
fn grow_ws(ws: list[str], s: S) -> int {
    for i in range(100) { s.ws.append("new" + str(i)); }
    s.ws[0] = "zzzzzz";
    return len(ws) * 1000 + len(ws[0]) * 100 + len(s.ws);
}
fn grow_fs(fs: list[float], s: S) -> float {
    s.fs.append(2.5);
    s.fs[0] = 9.0;
    return fs[0] * 100.0 + float(len(fs));
}
fn swap_t(t: str, s: S) -> str {
    s.t = "replaced";
    return t + "/" + s.t;
}
fn swap_b(b: bytes, s: S) -> int {
    s.b = b"q";
    return len(b) * 10 + len(s.b) + b[0];
}
fn deep_reset(s: S) -> void {
    let nd: dict[int, int] = {};
    s.d = nd;
    s.ws.clear();
    s.t = "deep";
}
fn via_deep(d: dict[int, int], ws: list[str], t: str, s: S) -> int {
    deep_reset(s);
    return len(d) * 10000 + len(ws) * 100 + len(t) * 10 + len(s.d);
}
fn reset_d(s: S) -> int {
    let nd: dict[int, int] = {};
    s.d = nd;
    s.xs.append(1000);
    return 5;
}
fn two(d: dict[int, int], k: int) -> int { return len(d) * 10 + k; }
fn twol(xs: list[int], k: int) -> int { return len(xs) * 10 + k; }
fn clobber(s: S) -> int {
    let nd: dict[int, int] = {};
    s.d = nd;
    return 0;
}
fn with_cb(d: dict[int, int], s: S, cb: Callable[[S], int]) -> int {
    cb(s);
    return len(d) * 10 + len(s.d);
}
impl S {
    fn msw(self, d: dict[int, int]) -> int {
        let nd: dict[int, int] = {};
        self.d = nd;
        return len(d) * 10 + len(self.d);
    }
    fn mread(self, d: dict[int, int], k: int) -> int { return dget(d, k) + len(self.ws); }
}
fn need(d: dict[int, int], k: int) -> int { return d[k]; }
fn need_ws(ws: list[str], k: int) -> int { return len(ws[k]); }
fn picky(ss: set[str], t: str) -> int {
    if t in ss { return 1; }
    raise ValueError("missing " + t);
}
fn rec(d: dict[int, int], k: int) -> int {
    if k <= 0 { return 0; }
    return dget(d, k) + rec(d, k - 1);
}
fn recs(s: S, k: int) -> int {
    if k <= 0 { return len(s.ws); }
    return dget(s.d, k) + wslen(s.ws, 0) + recs(s, k - 1);
}
fn rec_swap(d: dict[int, int], s: S, k: int) -> int {
    if k <= 0 {
        let nd: dict[int, int] = {};
        s.d = nd;
        return len(d);
    }
    return rec_swap(s.d, s, k - 1) + len(d);
}
fn ident(d: dict[int, int]) -> dict[int, int] { return d; }
fn identl(ws: list[str]) -> list[str] { return ws; }
fn pair(d: dict[int, int], v: int) -> int { return len(d) * 1000 + v; }

struct P { d: dict[int, int]; }
struct H { ps: list[P]; }
fn drop_all(d: dict[int, int], h: H) -> int {
    h.ps.clear();
    return len(d);
}

fn field_total(s: S) -> int {
    let total = 0;
    for i in range(60) {
        total += dget(s.d, i) + sdget(s.sd, "k" + str(i)) + sihas(s.si, i) + sshas(s.ss, str(i));
        if i < 50 { total += xsat(s.xs, i) + int(fsat(s.fs, i)) + wslen(s.ws, i) + tlen(s.t, i) + blen(s.b, 1); }
    }
    return total;
}

fn main() {
    let d: dict[int, int] = {};
    let sd: dict[str, int] = {};
    let si: set[int] = set();
    let ss: set[str] = set();
    let xs: list[int] = [];
    let fs: list[float] = [];
    let ws: list[str] = [];
    for i in range(50) {
        d[i] = i * 3;
        sd["k" + str(i)] = i;
        si.add(i * 2);
        ss.add(str(i));
        xs.append(i);
        fs.append(float(i) / 2.0);
        ws.append("w" + str(i));
    }
    ss.add("b");
    let total = 0;
    for i in range(60) {
        total += dget(d, i) + sdget(sd, "k" + str(i)) + sihas(si, i) + sshas(ss, str(i));
        if i < 50 { total += xsat(xs, i) + int(fsat(fs, i)) + wslen(ws, i); }
    }
    print("locals", total, tlen("abc", 1), blen(b"xyz", 0));
    let s = S(d, sd, si, ss, xs, fs, ws, "text", b"bytes");
    print("fields", field_total(s));
    print("swap_d", swap_d(s.d, s), len(s.d));
    print("swap_sd", swap_sd(s.sd, s), len(s.sd));
    print("swap_si", swap_si(s.si, s), len(s.si));
    print("swap_ss", swap_ss(s.ss, s), len(s.ss));
    print("grow_xs", grow_xs(s.xs, s), len(s.xs), s.xs[0]);
    print("grow_ws", grow_ws(s.ws, s), len(s.ws), s.ws[0]);
    print("grow_fs", grow_fs(s.fs, s), len(s.fs));
    print("swap_t", swap_t(s.t, s), s.t);
    print("swap_b", swap_b(s.b, s), len(s.b));
    s.d = d;
    s.ws = ws;
    s.t = "again";
    print("via_deep", via_deep(s.d, s.ws, s.t, s), len(s.d), len(s.ws), s.t);
    s.d = d;
    print("arg_order", two(s.d, reset_d(s)), len(s.d), twol(s.xs, reset_d(s)), len(s.xs));
    s.d = d;
    print("callback", with_cb(s.d, s, clobber), len(s.d));
    s.d = d;
    print("method", s.msw(s.d), len(s.d));
    s.d = d;
    s.ws = ws;
    print("mread", s.mread(s.d, 4), s.mread(d, 5));
    let caught = 0;
    for i in range(2000) {
        try { total += need(d, i % 60); } except KeyError { caught += 1; }
        try { total += need(s.d, i % 70); } except KeyError { caught += 1; }
        try { total += need_ws(ws, i % 55); } except IndexError { caught += 1; }
        try { total += need_ws(s.ws, i % 55); } except IndexError { caught += 1; }
        try { total += picky(s.ss, str(i % 60)); } except ValueError as e { caught += len(e.message); }
    }
    print("exceptions", caught, total);
    print("rec", rec(d, 40), recs(s, 30));
    s.d = d;
    print("rec_swap", rec_swap(s.d, s, 3), len(s.d));
    let ed = ident(d);
    ed[1000] = 1;
    let el = identl(ws);
    el.append("more");
    print("ident", len(d), len(ed), len(ws), len(el));
    let local: dict[int, int] = {};
    for i in range(10) { local[i] = i; }
    print("pair", pair(local, local.pop(3)), len(local));
    let lx: list[int] = [1, 2, 3];
    print("pairl", twol(lx, lx.pop()), len(lx));
    let h = H([]);
    for i in range(3) {
        let pd: dict[int, int] = {};
        for j in range(i + 2) { pd[j] = j; }
        h.ps.append(P(pd));
    }
    let dropped = 0;
    for p in h.ps { dropped += drop_all(p.d, h); }
    print("owner_dropped", dropped, len(h.ps));
}
"""

PYTHON = """
class S:
    def __init__(self, d, sd, si, ss, xs, fs, ws, t, b):
        # AIL value semantics: the constructor stores copies of containers.
        self.d, self.sd, self.si, self.ss = dict(d), dict(sd), set(si), set(ss)
        self.xs, self.fs, self.ws, self.t, self.b = list(xs), list(fs), list(ws), t, b

    def msw(self, d):
        self.d = {}
        return len(d) * 10 + len(self.d)

    def mread(self, d, k):
        return dget(d, k) + len(self.ws)


def dget(d, k): return d[k] if k in d else -1
def sdget(d, k): return d.get(k, -1)
def sihas(s, k): return 1 if k in s else 0
def sshas(s, k): return 1 if k in s else 0
def xsat(xs, k): return xs[k] + len(xs)
def fsat(fs, k): return fs[k]
def wslen(ws, k): return len(ws[k]) + len(ws)
def tlen(t, k): return len(t) + k
def blen(b, k): return len(b) + b[k]


def swap_d(d, s):
    s.d = {1: 100}
    return len(d) * 1000 + len(s.d) * 100 + dget(d, 2)
def swap_sd(d, s):
    s.sd = {}
    return len(d) * 10 + len(s.sd)
def swap_si(x, s):
    s.si = set()
    return len(x) * 10 + len(s.si)
def swap_ss(x, s):
    s.ss = {"only"}
    return len(x) * 10 + len(s.ss) + sshas(x, "b")
def grow_xs(xs, s):
    s.xs.append(7); s.xs[0] = 99
    return xs[0] * 1000 + len(xs) * 10 + len(s.xs)
def grow_ws(ws, s):
    for i in range(100): s.ws.append("new" + str(i))
    s.ws[0] = "zzzzzz"
    return len(ws) * 1000 + len(ws[0]) * 100 + len(s.ws)
def grow_fs(fs, s):
    s.fs.append(2.5); s.fs[0] = 9.0
    return fs[0] * 100.0 + float(len(fs))
def swap_t(t, s):
    s.t = "replaced"
    return t + "/" + s.t
def swap_b(b, s):
    s.b = b"q"
    return len(b) * 10 + len(s.b) + b[0]
def deep_reset(s):
    s.d = {}; s.ws.clear(); s.t = "deep"
def via_deep(d, ws, t, s):
    deep_reset(s)
    return len(d) * 10000 + len(ws) * 100 + len(t) * 10 + len(s.d)
def reset_d(s):
    s.d = {}; s.xs.append(1000)
    return 5
def two(d, k): return len(d) * 10 + k
def twol(xs, k): return len(xs) * 10 + k
def clobber(s):
    s.d = {}
    return 0
def with_cb(d, s, cb):
    cb(s)
    return len(d) * 10 + len(s.d)
def need(d, k): return d[k]
def need_ws(ws, k): return len(ws[k])
def picky(ss, t):
    if t in ss: return 1
    raise ValueError("missing " + t)
def rec(d, k):
    if k <= 0: return 0
    return dget(d, k) + rec(d, k - 1)
def recs(s, k):
    if k <= 0: return len(s.ws)
    return dget(s.d, k) + wslen(s.ws, 0) + recs(s, k - 1)
def rec_swap(d, s, k):
    if k <= 0:
        s.d = {}
        return len(d)
    return rec_swap(s.d, s, k - 1) + len(d)
def ident(d): return d
def identl(ws): return ws
def pair(d, v): return len(d) * 1000 + v
class P:
    def __init__(self, d): self.d = dict(d)
class H:
    def __init__(self, ps): self.ps = list(ps)
def drop_all(d, h):
    h.ps.clear()
    return len(d)
def field_total(s):
    total = 0
    for i in range(60):
        total += dget(s.d, i) + sdget(s.sd, "k" + str(i)) + sihas(s.si, i) + sshas(s.ss, str(i))
        if i < 50: total += xsat(s.xs, i) + int(fsat(s.fs, i)) + wslen(s.ws, i) + tlen(s.t, i) + blen(s.b, 1)
    return total


d, sd, si, ss, xs, fs, ws = {}, {}, set(), set(), [], [], []
for i in range(50):
    d[i] = i * 3; sd["k" + str(i)] = i; si.add(i * 2); ss.add(str(i))
    xs.append(i); fs.append(float(i) / 2.0); ws.append("w" + str(i))
ss.add("b")
total = 0
for i in range(60):
    total += dget(d, i) + sdget(sd, "k" + str(i)) + sihas(si, i) + sshas(ss, str(i))
    if i < 50: total += xsat(xs, i) + int(fsat(fs, i)) + wslen(ws, i)
print("locals", total, tlen("abc", 1), blen(b"xyz", 0))
s = S(d, sd, si, ss, xs, fs, ws, "text", b"bytes")
print("fields", field_total(s))
print("swap_d", swap_d(s.d, s), len(s.d))
print("swap_sd", swap_sd(s.sd, s), len(s.sd))
print("swap_si", swap_si(s.si, s), len(s.si))
print("swap_ss", swap_ss(s.ss, s), len(s.ss))
# A list parameter is the caller's value at the call: in-place changes to the field do not show.
print("grow_xs", grow_xs(list(s.xs), s), len(s.xs), s.xs[0])
print("grow_ws", grow_ws(list(s.ws), s), len(s.ws), s.ws[0])
print("grow_fs", grow_fs(list(s.fs), s), len(s.fs))
print("swap_t", swap_t(s.t, s), s.t)
print("swap_b", swap_b(s.b, s), len(s.b))
s.d = dict(d); s.ws = list(ws); s.t = "again"
print("via_deep", via_deep(s.d, list(s.ws), s.t, s), len(s.d), len(s.ws), s.t)
s.d = dict(d)
print("arg_order", two(s.d, reset_d(s)), len(s.d), twol(list(s.xs), reset_d(s)), len(s.xs))
s.d = dict(d)
print("callback", with_cb(s.d, s, clobber), len(s.d))
s.d = dict(d)
print("method", s.msw(s.d), len(s.d))
s.d = dict(d); s.ws = list(ws)
print("mread", s.mread(s.d, 4), s.mread(d, 5))
caught = 0
for i in range(2000):
    try: total += need(d, i % 60)
    except KeyError: caught += 1
    try: total += need(s.d, i % 70)
    except KeyError: caught += 1
    try: total += need_ws(ws, i % 55)
    except IndexError: caught += 1
    try: total += need_ws(s.ws, i % 55)
    except IndexError: caught += 1
    try: total += picky(s.ss, str(i % 60))
    except ValueError as e: caught += len(str(e))
print("exceptions", caught, total)
print("rec", rec(d, 40), recs(s, 30))
s.d = dict(d)
print("rec_swap", rec_swap(s.d, s, 3), len(s.d))
ed = dict(ident(d)); ed[1000] = 1
el = list(identl(ws)); el.append("more")
print("ident", len(d), len(ed), len(ws), len(el))
local = {i: i for i in range(10)}
print("pair", pair(local, local.pop(3)), len(local))
lx = [1, 2, 3]
print("pairl", twol(lx, lx.pop()), len(lx))
h = H([])
for i in range(3):
    h.ps.append(P({j: j for j in range(i + 2)}))
dropped = 0
for p in h.ps: dropped += drop_all(p.d, h)
print("owner_dropped", dropped, len(h.ps))
"""


def build(directory, text):
    source, exe, debug = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / "program.c").read_text(encoding="utf-8")


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+\b%s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


COPIES = ("_copy(_source)", "snapshot", "return_owned", "ail_slist_push(")


class ArgumentBorrowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.exe, cls.program = build(cls.directory.name, SOURCE)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_matches_cpython(self):
        ran = subprocess.run([str(self.exe)], capture_output=True, timeout=60)
        expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout)

    def test_read_only_field_arguments_are_borrowed(self):
        for name in ("field_total", "recs", "S__mread"):
            body = body_of(self.program, name)
            for copy in COPIES:
                self.assertNotIn(copy, body, (name, copy))
        body = body_of(self.program, "field_total")
        self.assertIn("(const ail_idict *)&(v_s)->f_d", body)
        self.assertIn("xsat((v_s)->f_xs.p, (v_s)->f_xs.n,", body)
        self.assertIn("wslen((v_s)->f_ws,", body)
        self.assertIn("fsat((v_s)->f_fs,", body)

    def test_local_arguments_are_borrowed(self):
        main = body_of(self.program, "py_main")
        self.assertRegex(main, r"sdget\(&\(?\*?v_sd\)?,")
        self.assertRegex(main, r"sihas\(&\(?\*?v_si\)?,")
        self.assertRegex(main, r"wslen\(\(?\*?v_ws\)?,")

    def test_field_changed_during_the_call_is_still_copied(self):
        self.assertIn("ail_idict_copy", body_of(self.program, "rec_swap"))


if __name__ == "__main__":
    unittest.main()
