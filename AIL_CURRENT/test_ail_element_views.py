"""Element views and per-call work removed from the short text style, checked against CPython:

* list[bytes]: `L[i]` is a VIEW of the slot's own payload (`ail_blist_view`) when its consumer is
  done with it before anything can replace, remove or free the slot -- `int()`, `len()`, `.decode()`
  and other read-only methods, a comparison, `R.append(L[i])` (the push copies), a call of a
  value-only function, or of any function returning a number when L is a private local -- and for
  `t = L[i]` when every later read of `t` in the same block is such a consumer and L is a private
  local never rebound there. Each read copied the element into the function's arena until it
  returned: a line loop kept every line's fields (705 MB for a 62 MB ticket file).
* list[bytes] runtime: list headers recycle, small payloads come from size-class free lists, and a
  local or parameter receiver is not retained around each read or append.
* list[str]: `xs.append(o.f[i])` pushes a view of the field element when no mention of `xs` follows
  the first statement that may change field `f`; a comparison, `s += o.f[i]` onto a builder and a
  builder's initial value read the element in place; `o.f = xs` copies the strings once, not twice.
* `raise E(...)` hands the new exception straight to the raise, so a recursive evaluator raising
  errors needs no temporary, no release on each return and no unwind frame.
* A loop calling an int-valued helper on int or bytes arguments (`if not isd(f[i])`) keeps no str
  arena checkpoint, and the helper's caller no arena.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_ail_text_views import body_of, build, peak_rss_kb

BYTES_SOURCE = r"""
struct Box { items: list[bytes]; n: int; }

fn isd(c: int) -> bool { return c >= 48 and c <= 57; }
fn digits(f: bytes, lo: int, hi: int) -> bool {
    let n = len(f);
    if n < lo or n > hi { return false; }
    for i in range(n) { if not isd(f[i]) { return false; } }
    return true;
}
fn ident(x: bytes) -> bytes { return x; }
fn steal(b: Box, x: bytes) -> int {
    b.items.pop();
    b.items.append(b"zz");
    return len(x) * 1000 + x[0];
}
fn rec(t: bytes, f: list[bytes]) -> int {
    if len(f) < 2 { return -1; }
    if not (digits(f[0], 1, 6) and digits(f[1], 1, 6)) { return -2; }
    let key = f[0].decode() + ":" + f[1].decode();
    return int(f[0]) * 7 + int(f[1]) + len(key) + len(t) + f[1].find(b"9");
}

fn main() {
    let data = read_stdin_bytes(1 << 30);
    let pos = 0;
    let total = len(data);
    let acc = 0;
    let lines = 0;
    let firsts: list[bytes] = [];
    while pos < total {
        let q = pos;
        while q < total and data[q] != 10 { q += 1; }
        let ln = data[pos:q];
        pos = q + 1;
        lines += 1;
        let fields: list[bytes] = [];
        let s = 0;
        for i in range(len(ln)) {
            if ln[i] == 124 { fields.append(ln[s:i]); s = i + 1; }
        }
        fields.append(ln[s:len(ln)]);
        let t = fields[0];
        let rest: list[bytes] = [];
        for i in range(1, len(fields)) { rest.append(fields[i]); }
        if t == b"END" { break; }
        let r = rec(t, rest);
        acc = (acc * 31 + r + 1000) % 1000000007;
        if len(firsts) < 4 { firsts.append(fields[0]); }
    }
    print(acc, lines, len(firsts), b"|".join(firsts).decode());
    let xs: list[bytes] = [b"one", b"two", b"three"];
    let a = xs[0];
    xs[0] = b"ONE";
    let b = xs[2];
    xs.pop();
    print(a.decode(), b.decode(), len(xs), xs[0].decode());
    let ys: list[bytes] = [b"keep"];
    let v = ys[0];
    ys = [b"new"];
    print(v.decode(), ys[0].decode());
    let box = Box([b"abc", b"de"], 0);
    let zs = box.items;
    print(steal(box, zs[0]), steal(box, zs[1]), len(zs), zs[len(zs) - 1].decode());
    let ws: list[bytes] = [b"orig", b"x"];
    let w = ident(ws[0]);
    ws[0] = b"repl";
    print(w.decode(), ws[0].decode(), ws[0] == ws[1], len(ws[1]));
    let src: list[bytes] = [b"p", b"q"];
    let dst: list[bytes] = [];
    for i in range(len(src)) { dst.append(src[i]); }
    let d0 = src[0].decode();
    src.clear();
    src.append(b"r");
    print(b",".join(dst).decode(), d0, src[0].decode());
}
"""

BYTES_PYTHON = r'''
import sys

class Box:
    def __init__(self, items, n):
        self.items, self.n = items, n

def isd(c): return 48 <= c <= 57
def digits(f, lo, hi):
    n = len(f)
    if n < lo or n > hi: return False
    return all(isd(c) for c in f)
def ident(x): return x
def steal(b, x):
    b.items.pop(); b.items.append(b"zz"); return len(x) * 1000 + x[0]
def rec(t, f):
    if len(f) < 2: return -1
    if not (digits(f[0], 1, 6) and digits(f[1], 1, 6)): return -2
    key = f[0].decode() + ":" + f[1].decode()
    return int(f[0]) * 7 + int(f[1]) + len(key) + len(t) + f[1].find(b"9")

def main():
    data = sys.stdin.buffer.read()
    acc = lines = 0
    firsts = []
    for ln in data.split(b"\n") if data else []:
        lines += 1
        fields = ln.split(b"|")
        t = fields[0]
        rest = fields[1:]
        if t == b"END": break
        acc = (acc * 31 + rec(t, rest) + 1000) % 1000000007
        if len(firsts) < 4: firsts.append(fields[0])
    print(acc, lines, len(firsts), b"|".join(firsts).decode())
    xs = [b"one", b"two", b"three"]
    a = xs[0]; xs[0] = b"ONE"; b = xs[2]; xs.pop()
    print(a.decode(), b.decode(), len(xs), xs[0].decode())
    ys = [b"keep"]; v = ys[0]; ys = [b"new"]
    print(v.decode(), ys[0].decode())
    box = Box([b"abc", b"de"], 0)
    zs = box.items
    print(steal(box, zs[0]), steal(box, zs[1]), len(zs), zs[len(zs) - 1].decode())
    ws = [b"orig", b"x"]; w = ident(ws[0]); ws[0] = b"repl"
    print(w.decode(), ws[0].decode(), ws[0] == ws[1], len(ws[1]))
    src = [b"p", b"q"]; dst = [src[i] for i in range(len(src))]; d0 = src[0].decode()
    src.clear(); src.append(b"r")
    print(b",".join(dst).decode(), d0, src[0].decode())

main()
'''


def bytes_input(n):
    rows = ["%d|%d|%s" % (i * 7919 % 100000, i % 977, "ab"[i % 2] * (i % 4)) for i in range(n)]
    if n > 5:
        rows[3] = "12x|5"
        rows[5] = "solo"
    return ("\n".join(rows) + "\nEND|0\ntail|1\n").encode()


STR_SOURCE = r"""
struct T { nm: list[str]; w: list[int]; }
fn clobber(t: T) -> void { t.nm[0] = "XX"; }
fn rebuild(t: T, order: list[int]) -> void {
    let nm: list[str] = [];
    let w: list[int] = [];
    for o in order { nm.append(t.nm[o]); w.append(t.w[o]); }
    t.nm = nm;
    t.w = w;
}
fn find(t: T, s: str) -> int {
    for i in range(len(t.nm)) { if t.nm[i] == s { return i; } }
    return -1;
}
fn path(t: T, i: int) -> str {
    let parts: list[str] = [];
    let j = i;
    while j >= 0 { parts.append(t.nm[j]); j -= 1; }
    parts.reverse();
    return "/".join(parts);
}
fn held_after_store(t: T) -> str {
    let held: list[str] = [];
    held.append(t.nm[0]);
    t.nm[0] = "YY";
    return held[0];
}
fn held_after_call(t: T) -> str {
    let held: list[str] = [];
    held.append(t.nm[1]);
    held.append(t.nm[0]);
    clobber(t);
    return "|".join(held);
}
fn store_then_read(t: T) -> int {
    let nm: list[str] = [];
    nm.append(t.nm[1]);
    nm.append(t.nm[0]);
    t.nm = nm;
    return len(nm[0]) * 10 + len(t.nm);
}
fn joined(t: T) -> str {
    let out = "";
    for i in range(len(t.nm)) { out += t.nm[i]; out += ","; }
    let name = t.nm[0];
    name += "+";
    name += t.nm[1];
    return out + name;
}
fn main() {
    let t = T([], []);
    for i in range(12) { t.nm.append(f"n{i * 7 % 12}"); t.w.append(i); }
    let order = [11 - i for i in range(12)];
    rebuild(t, order);
    print("|".join(t.nm), find(t, "n5"), find(t, "zz"), path(t, 4));
    print(held_after_store(t), t.nm[0]);
    print(held_after_call(t), t.nm[0]);
    print(store_then_read(t), "|".join(t.nm));
    print(joined(t));
    rebuild(t, [1, 0, 1]);
    print("|".join(t.nm), t.w[0], t.w[2]);
}
"""

STR_PYTHON = r'''
class T:
    def __init__(self, nm, w): self.nm, self.w = nm, w
def clobber(t): t.nm[0] = "XX"
def rebuild(t, order):
    t.nm = [t.nm[o] for o in order]; t.w = [t.w[o] for o in order]
def find(t, s):
    for i in range(len(t.nm)):
        if t.nm[i] == s: return i
    return -1
def path(t, i):
    parts = [t.nm[j] for j in range(i, -1, -1)]
    parts.reverse()
    return "/".join(parts)
def held_after_store(t):
    held = [t.nm[0]]; t.nm[0] = "YY"; return held[0]
def held_after_call(t):
    held = [t.nm[1], t.nm[0]]; clobber(t); return "|".join(held)
def store_then_read(t):
    nm = [t.nm[1], t.nm[0]]; t.nm = nm; return len(nm[0]) * 10 + len(t.nm)
def joined(t):
    out = ""
    for i in range(len(t.nm)): out += t.nm[i]; out += ","
    name = t.nm[0]; name += "+"; name += t.nm[1]
    return out + name
t = T([], [])
for i in range(12): t.nm.append(f"n{i * 7 % 12}"); t.w.append(i)
rebuild(t, [11 - i for i in range(12)])
print("|".join(t.nm), find(t, "n5"), find(t, "zz"), path(t, 4))
print(held_after_store(t), t.nm[0])
print(held_after_call(t), t.nm[0])
print(store_then_read(t), "|".join(t.nm))
print(joined(t))
rebuild(t, [1, 0, 1])
print("|".join(t.nm), t.w[0], t.w[2])
'''

RAISE_SOURCE = r"""
fn check(x: int) -> int {
    if x % 97 == 13 { raise ValueError(f"bad {x}"); }
    return x;
}
fn ev(depth: int, x: int) -> int {
    if x < 0 { raise ValueError("neg"); }
    if depth == 0 {
        if x % 89 == 7 { raise KeyError("odd"); }
        return check(x);
    }
    return ev(depth - 1, x + 1) + 1;
}
fn main() {
    let n = int(sys.argv[1]);
    let ok = 0;
    let bad = 0;
    let last = "";
    for i in range(n) {
        try { ok += ev(i % 5, i); }
        except ValueError as err1 { bad += 1 + len(err1.message); }
        except KeyError as err3 { bad += 1000; }
    }
    try { ok += ev(3, -1); } except ValueError as err2 { last = last + "/" + err2.message; }
    print(ok, bad, last);
}
"""

RAISE_PYTHON = r'''
import sys
def check(x):
    if x % 97 == 13: raise ValueError(f"bad {x}")
    return x
def ev(depth, x):
    if x < 0: raise ValueError("neg")
    if depth == 0:
        if x % 89 == 7: raise KeyError("odd")
        return check(x)
    return ev(depth - 1, x + 1) + 1
ok = bad = 0
last = ""
for i in range(int(sys.argv[1])):
    try: ok += ev(i % 5, i)
    except ValueError as e: bad += 1 + len(str(e))
    except KeyError: bad += 1000
try: ok += ev(3, -1)
except ValueError as e: last = last + "/" + str(e)
print(ok, bad, last)
'''

# The runtime's own boundaries: payload size classes (16-byte steps up to 64, malloc above, NULL for
# empty), the bounded per-class caches, the 8-entry header cache and its 64-slot limit, negative and
# out-of-range view indexes.
POOL_SOURCE = r"""
fn ck(xs: list[bytes]) -> int {
    let t = 0;
    for i in range(len(xs)) { t = (t * 131 + len(xs[i]) * 7 + i) % 1000003; }
    return t;
}
fn main() {
    let rounds = int(sys.argv[1]);
    let xs: list[bytes] = [];
    for n in [0, 1, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64, 65, 200] { xs.append(b"a" * n); }
    let acc = 0;
    for r in range(rounds) {
        for i in range(len(xs)) { xs[i] = xs[(i + r) % len(xs)][0:(i * 5 + r) % 70] + b"z"; }
        let ys: list[bytes] = [];
        let zs: list[bytes] = [];
        for i in range(len(xs)) { ys.append(xs[i]); zs.append(xs[len(xs) - 1 - i]); }
        for i in range(r % 90) { zs.append(xs[i % len(xs)]); }
        while len(ys) > 3 { ys.pop(); }
        let big: list[bytes] = [];
        for i in range(300 + r) { big.append(b"q" * (i % 70)); }
        acc = (acc * 31 + ck(ys) + ck(zs) * 3 + ck(big) + len(zs[-1]) + int(len(ys[-3]) > 0)) % 1000000007;
        big.clear();
        for i in range(40) { big.append(xs[i % len(xs)]); }
        acc = (acc + ck(big)) % 1000000007;
    }
    let caught = 0;
    try { acc += len(xs[99]); } except IndexError as err { caught = 1; }
    try { acc += int(xs[-99]); } except IndexError as err2 { caught += 2; }
    print(acc, caught, ck(xs), len(xs[-1]), xs[0].decode());
}
"""

POOL_PYTHON = r'''
import sys
def ck(xs):
    t = 0
    for i in range(len(xs)): t = (t * 131 + len(xs[i]) * 7 + i) % 1000003
    return t
rounds = int(sys.argv[1])
xs = [b"a" * n for n in [0, 1, 15, 16, 17, 31, 32, 33, 47, 48, 49, 63, 64, 65, 200]]
acc = 0
for r in range(rounds):
    for i in range(len(xs)): xs[i] = xs[(i + r) % len(xs)][0:(i * 5 + r) % 70] + b"z"
    ys = []; zs = []
    for i in range(len(xs)): ys.append(xs[i]); zs.append(xs[len(xs) - 1 - i])
    for i in range(r % 90): zs.append(xs[i % len(xs)])
    while len(ys) > 3: ys.pop()
    big = [b"q" * (i % 70) for i in range(300 + r)]
    acc = (acc * 31 + ck(ys) + ck(zs) * 3 + ck(big) + len(zs[-1]) + int(len(ys[-3]) > 0)) % 1000000007
    big.clear()
    for i in range(40): big.append(xs[i % len(xs)])
    acc = (acc + ck(big)) % 1000000007
caught = 0
try: acc += len(xs[99])
except IndexError: caught = 1
try: acc += int(xs[-99])
except IndexError: caught += 2
print(acc, caught, ck(xs), len(xs[-1]), xs[0].decode())
'''


# A user method named `split` returning a shared field list is not a fresh list: views of its
# elements would outlive a callee replacing them (found in review: use-after-free).
SPLIT_SOURCE = r"""
struct S { items: list[bytes]; }
impl S { fn split(self) -> list[bytes] { return self.items; } }
fn clob(s: S, x: bytes) -> int { s.items[0] = b"ZZZZZZZZ"; return len(x) * 1000 + x[0] * 10 + x[2]; }
fn main() {
    let s = S([b"abc", b"de"]);
    let L = s.split();
    print(clob(s, L[0]));
    let t = L[1];
    s.items[1] = b"QQQQQQQQQ";
    print(t.decode());
}
"""

SPLIT_PYTHON = r'''
class S:
    def __init__(self, items): self.items = items
    def split(self): return self.items
def clob(s, x):
    s.items[0] = b"ZZZZZZZZ"; return len(x) * 1000 + x[0] * 10 + x[2]
s = S([b"abc", b"de"])
L = s.split()
print(clob(s, L[0]))
t = L[1]
s.items[1] = b"QQQQQQQQQ"
print(t.decode())
'''

# Lists of 8-, 24-, 40- and 60-byte elements built and dropped in turn: released payloads must go
# back to malloc for the next class (found in review: fixed slabs held every class's peak at once).
CHURN_SOURCE = r"""
fn build(n: int, w: int) -> int {
    let L: list[bytes] = [];
    let src = b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    for i in range(n) { L.append(src[0:w]); }
    return len(L);
}
fn main() {
    let n = int(sys.argv[1]);
    let t = 0;
    for w in [8, 24, 40, 60] { t += build(n, w); }
    print(t);
}
"""


def run_pair(test, directory, source, oracle_text, argv=(), data=b""):
    directory = tempfile.mkdtemp(dir=directory)
    built, exe, c_file = build(directory, source)
    test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
    oracle = Path(directory, "oracle.py")
    oracle.write_text(oracle_text, encoding="utf-8")
    ran = subprocess.run([str(exe), *argv], input=data, capture_output=True, timeout=120)
    expected = subprocess.run([sys.executable, "-X", "utf8", str(oracle), *argv], input=data,
                              capture_output=True, timeout=120)
    test.assertEqual(expected.returncode, 0, expected.stderr)
    test.assertEqual(ran.returncode, 0, ran.stderr)
    test.assertEqual(ran.stdout.decode("utf-8"), expected.stdout.decode("utf-8"))
    return exe, c_file.read_text()


class ElementViewTests(unittest.TestCase):
    def test_bytes_list_views_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            for n in (0, 1, 9, 400):
                data = bytes_input(n) if n else b""
                exe, program = run_pair(self, directory, BYTES_SOURCE, BYTES_PYTHON, data=data)
            # the line loop and the record checker read every field in place: element copies are
            # left only for the aliases whose list is changed (xs), rebound (ys) or shared (zs)
            gets = re.findall(r"ail_blist_get\(&v__barena, (v_\w+), ", program)
            self.assertEqual(sorted(set(gets)), ["v_xs", "v_ys", "v_zs"], gets)
            for view in ("ail_blist_view(v_f, 0LL)", "ail_blist_view(v_f, 1LL)", "v_t = ail_blist_view(v_fields, 0LL);",
                         "ail_blist_push(v_rest, ail_blist_view(v_fields, v_i))",
                         "ail_blist_push(v_dst, ail_blist_view(v_src, v_i))"):
                self.assertIn(view, program)
            self.assertNotRegex(program, r"ail_blist_store\(&v__t\d+, v_fields, 0\)")
            # the int helper's loop keeps no str arena
            self.assertNotIn("sarena", body_of(program, "digits"))
            # a line loop keeps no per-line copies: the peak does not grow with the line count
            path = Path(directory, "big.txt")
            path.write_bytes(bytes_input(200000))
            path_small = Path(directory, "small.txt")
            path_small.write_bytes(bytes_input(2000))
            if Path("/usr/bin/time").exists():
                def peak(p):
                    with open(p, "rb") as stdin:
                        ran = subprocess.run(["/usr/bin/time", "-f", "%M", str(exe)], stdin=stdin,
                                             capture_output=True, timeout=120)
                    return int(ran.stderr.decode().strip().splitlines()[-1])
                small, large = peak(path_small), peak(path)
                # input 3.4 MB read whole; 200k lines x 3 fields of copies was ~25 MB more
                self.assertLess(large - small, 8 * 1024, (small, large))

    def test_payload_pool_and_list_cache_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            for rounds in ("0", "1", "7", "150"):
                _, program = run_pair(self, directory, POOL_SOURCE, POOL_PYTHON, argv=(rounds,))
            self.assertIn("ail__bpay_alloc(", program)
            self.assertIn("ail_blist_view(v_xs, ", program)

    def test_user_split_method_and_size_class_churn(self):
        with tempfile.TemporaryDirectory() as directory:
            _, program = run_pair(self, directory, SPLIT_SOURCE, SPLIT_PYTHON)
            self.assertNotIn("ail_blist_view(v_L", program)
            built, exe, _ = build(tempfile.mkdtemp(dir=directory), CHURN_SOURCE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe), "1000"], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, b"4000\n")
            peak = peak_rss_kb([str(exe), "300000"])
            if peak is not None:
                # the largest single list (300k x 64-byte chunks + slots) is ~25 MB; keeping every
                # class's chunks would add up to ~60 MB
                self.assertLess(peak, 40 * 1024, peak)

    def test_str_field_element_views_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            _, program = run_pair(self, directory, STR_SOURCE, STR_PYTHON)
            copy = "ail_str_return_owned(ail_slist_get(&(v_t)->f_nm"
            for name in ("rebuild", "find", "path"):
                self.assertNotIn(copy, body_of(program, name), name)
            self.assertIn("ail_bl_append(&v_out, ({ (void)0; int64_t _index = v_i; ail_slist_get(&(v_t)->f_nm, _index); }))",
                          body_of(program, "joined"))
            for name in ("held_after_store", "held_after_call", "store_then_read"):
                self.assertIn(copy, body_of(program, name), name)
            self.assertNotIn("ail_slist_snapshot(", body_of(program, "rebuild"))

    def test_raise_adopts_and_recursion_links_no_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            for n in ("0", "1", "300"):
                exe, program = run_pair(self, directory, RAISE_SOURCE, RAISE_PYTHON, argv=(n,))
            ev = body_of(program, "ev")
            self.assertIn("ail_raise_value_adopt(", ev)
            self.assertNotIn("v__cleanup_frame", ev)
            self.assertNotIn("ail_exception_release", ev)
            small, large = peak_rss_kb([str(exe), "1000"]), peak_rss_kb([str(exe), "4000000"])
            if small is not None:
                # 41,000 raised exceptions would leak ~4 MB if nothing released them
                self.assertLess(large - small, 1024, (small, large))


if __name__ == "__main__":
    unittest.main()
