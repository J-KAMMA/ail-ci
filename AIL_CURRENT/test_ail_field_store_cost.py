"""Single-element mutation of a list[str] field costs the new text, not the whole field, and a
list[int] field buffer swap moves the lists instead of copying them.

An LLM-written tree folder (`t.name[v] = "+".join(parts)` in a loop over 3M nodes) ran for more
than 300 s against C's 1 s: every element store repacked the whole packed field. A string field is
still one allocation (spine, then text; freeing p frees all), but it now carries slack: a store
copies only its text into the free text and repoints its slot, and the block is repacked when the
slack runs out, which garbage can never outgrow. A Game of Life (`let tmp = g.cur; g.cur = g.nxt;
g.nxt = tmp;` per generation over 4M cells) copied each 32 MB list five times per generation.

Checked against CPython: element stores of varied lengths (empty to long), `+=` on an element,
append/extend/pop/del/slice assignment interleaved with reads, values read out of the field into
another list and a dict staying unchanged when the field changes, and IndexError mid-loop leaving
the field intact. Then that the stores run in time and memory bounded by the live text, and that
the generated swap has no list copy while the cases that must copy still do.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct Rng { s: int; }
impl Rng {
    fn next(self, m: int) -> int {
        self.s = (self.s * 1103515245 + 12345) % 2147483648;
        return (self.s >> 8) % m;
    }
}
struct T { name: list[str]; w: list[int]; }
fn word(r: Rng, k: int) -> str {
    let n = r.next(k);
    let parts: list[str] = [];
    for i in range(n) { parts.append(chr(97 + r.next(26))); }
    return "".join(parts);
}
fn main() {
    let r = Rng(int(sys.argv[1]));
    let t = T([], []);
    for i in range(20) { t.name.append(word(r, 6)); t.w.append(i); }
    let kept: list[str] = [];
    let seen: dict[str, int] = {};
    let errors = 0;
    for step in range(3000) {
        let op = r.next(14);
        let n = len(t.name);
        if op < 4 and n > 0 {
            let i = r.next(n);
            let big = r.next(10) == 0;
            t.name[i] = word(r, 300 if big else 8);
        } elif op == 4 and n > 0 {
            let i = r.next(n);
            t.name[i] += word(r, 5);
        } elif op == 5 {
            t.name.append(word(r, 12));
        } elif op == 6 and n > 0 {
            let i = r.next(n);
            kept.append(t.name[i]);
            seen[t.name[i]] = step;
            t.name[i] = "x" + t.name[(i + 1) % n];
        } elif op == 7 and n > 2 {
            let p = t.name.pop(r.next(n));
            kept.append(p);
        } elif op == 8 and n > 2 {
            let x = t.name.pop();
            kept.append(x);
        } elif op == 9 and n > 3 {
            let a = r.next(n);
            let b = a + r.next(n - a);
            t.name[a:b] = [word(r, 4), word(r, 40)];
        } elif op == 10 and n > 4 {
            del t.name[r.next(n)];
        } elif op == 11 {
            try {
                t.name[n + r.next(3)] = "never";
                print("stored");
            } except IndexError {
                errors += 1;
            }
        } elif op == 12 and n > 1 {
            t.name.extend([word(r, 6), "", word(r, 20)]);
        } elif n > 0 {
            let i = r.next(n);
            t.name[i] = t.name[i];
            t.name[-1] = t.name[0] + "/" + t.name[-1];
        }
        if step % 97 == 0 {
            print(step, len(t.name), ",".join(t.name));
        }
        if len(t.name) > 60 { t.name = t.name[10:]; }
    }
    print("final", ",".join(t.name));
    print("kept", len(kept), ",".join(kept));
    let ks: list[str] = [];
    for k in seen.keys() { ks.append(k); }
    ks.sort();
    for k in ks { print(k, seen[k]); }
    print("errors", errors);
}
"""

PYTHON = r'''
import sys
class Rng:
    def __init__(self, s): self.s = s
    def next(self, m):
        self.s = (self.s * 1103515245 + 12345) % 2147483648
        return (self.s >> 8) % m
def word(r, k):
    n = r.next(k)
    return "".join(chr(97 + r.next(26)) for _ in range(n))
def main():
    r = Rng(int(sys.argv[1]))
    name, w = [], []
    for i in range(20):
        name.append(word(r, 6)); w.append(i)
    kept, seen, errors = [], {}, 0
    for step in range(3000):
        op = r.next(14)
        n = len(name)
        if op < 4 and n > 0:
            i = r.next(n)
            big = r.next(10) == 0
            name[i] = word(r, 300 if big else 8)
        elif op == 4 and n > 0:
            i = r.next(n)
            name[i] += word(r, 5)
        elif op == 5:
            name.append(word(r, 12))
        elif op == 6 and n > 0:
            i = r.next(n)
            kept.append(name[i])
            seen[name[i]] = step
            name[i] = "x" + name[(i + 1) % n]
        elif op == 7 and n > 2:
            kept.append(name.pop(r.next(n)))
        elif op == 8 and n > 2:
            kept.append(name.pop())
        elif op == 9 and n > 3:
            a = r.next(n)
            b = a + r.next(n - a)
            name[a:b] = [word(r, 4), word(r, 40)]
        elif op == 10 and n > 4:
            del name[r.next(n)]
        elif op == 11:
            try:
                name[n + r.next(3)] = "never"
                print("stored")
            except IndexError:
                errors += 1
        elif op == 12 and n > 1:
            name.extend([word(r, 6), "", word(r, 20)])
        elif n > 0:
            i = r.next(n)
            name[i] = name[i]
            name[-1] = name[0] + "/" + name[-1]
        if step % 97 == 0:
            print(step, len(name), ",".join(name))
        if len(name) > 60:
            name = name[10:]
    print("final", ",".join(name))
    print("kept", len(kept), ",".join(kept))
    for k in sorted(seen):
        print(k, seen[k])
    print("errors", errors)
main()
'''

# Many stores into a large field: quadratic before (every store repacked all 200k strings).
STORES = """
struct T { name: list[str]; }
fn main() {
    let n = int(sys.argv[1]);
    let t = T([]);
    for i in range(n) { t.name.append("n" + str(i)); }
    let total = 0;
    for k in range(int(sys.argv[2])) {
        let i = (k * 7919) % n;
        t.name[i] = t.name[i] + "+" + str(k % 10);
        if k % 3 == 0 { t.name[(i + 1) % n] = ""; }
        total += len(t.name[i]);
    }
    print(total, len(t.name), t.name[0], t.name[n - 1]);
}
"""

# A small field rewritten with long strings over and over: garbage must not pile up. The store is
# in its own function so the concatenation's arena is released per call.
CHURN = """
struct T { name: list[str]; }
fn put(t: T, k: int, chunk: str) -> void { t.name[k % 100] = chunk + str(k); }
fn main() {
    let t = T([]);
    for i in range(100) { t.name.append(""); }
    let chunk = "abcdefghij" * 20;
    for k in range(int(sys.argv[1])) { put(t, k, chunk); }
    print(len(t.name[7]), t.name[99]);
}
"""

SWAP = """
struct G { cur: list[int]; nxt: list[int]; f: list[float]; h: list[float]; }
fn step(g: G, n: int) -> void {
    for i in range(n) { g.nxt[i] = g.cur[i] + g.cur[(i + 1) % n]; }
    let tmp = g.cur;
    g.cur = g.nxt;
    g.nxt = tmp;
    let ft = g.f;
    g.f = g.h;
    g.h = ft;
}
fn keep(g: G) -> int {
    let tmp = g.cur;
    g.cur = g.nxt;
    g.nxt = tmp;
    tmp[0] = 1000;
    return tmp[0] + g.nxt[0];
}
fn peek(g: G) -> int {
    let tmp = g.cur;
    let seen = len(g.cur);
    g.cur = g.nxt;
    g.nxt = tmp;
    return seen;
}
fn show(xs: list[int]) -> str {
    let parts: list[str] = [];
    for x in xs { parts.append(str(x)); }
    return ",".join(parts);
}
fn main() {
    let n = 5;
    let g = G([1, 2, 3, 4, 5], [0, 0, 0, 0, 0], [0.5], [1.5, 2.5]);
    for k in range(4) { step(g, n); }
    print(show(g.cur), show(g.nxt), len(g.f), len(g.h));
    print(keep(g), g.nxt[0], peek(g));
    let a = g;
    let t2 = a.cur;
    a.cur = g.nxt;
    g.nxt = t2;
    print(g.cur[0], a.nxt[0]);
}
"""


def build(directory, text, name="p"):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def body_of(program, name):
    match = re.search(r"\n[\w *]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


def run_measured(argv, timeout):
    """(exit code, stdout, peak RSS in KiB or None) of the program alone. GNU time reports the
    program's own peak; the rusage of a child forked from this interpreter would include the
    interpreter's pages from before the exec."""
    timer = Path("/usr/bin/time")
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory, "rss")
        prefix = [str(timer), "-f", "%M", "-o", str(report)] if timer.exists() else []
        ran = subprocess.run(prefix + argv, capture_output=True, text=True, timeout=timeout)
        rss = int(report.read_text().split()[-1]) if prefix and report.exists() else None
        return ran.returncode, ran.stdout, rss


class FieldStoreCostTests(unittest.TestCase):
    def test_random_mutations_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, SOURCE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, "oracle.py")
            oracle.write_text(PYTHON)
            for seed in (1, 5, 2026, 77777):
                with self.subTest(seed=seed):
                    ran = subprocess.run([str(exe), str(seed)], capture_output=True, text=True, timeout=60)
                    expected = subprocess.run([sys.executable, str(oracle), str(seed)],
                                              capture_output=True, text=True, timeout=60)
                    self.assertEqual(expected.returncode, 0, expected.stderr)
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                    self.assertEqual(ran.stdout, expected.stdout)
                    self.assertIn("errors ", ran.stdout)
                    self.assertNotIn("stored", ran.stdout)

    def test_element_store_does_not_copy_the_field(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, STORES, name="stores")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            n, k = 200000, 200000
            expected_total = 0
            names = ["n%d" % i for i in range(n)]
            for step in range(k):
                i = (step * 7919) % n
                names[i] = names[i] + "+" + str(step % 10)
                if step % 3 == 0:
                    names[(i + 1) % n] = ""
                expected_total += len(names[i])
            # Repacking the whole field per store took minutes here; amortised stores take well
            # under a second even on a loaded machine.
            code, out, rss = run_measured([str(exe), str(n), str(k)], timeout=60)
            self.assertEqual(code, 0)
            self.assertEqual(out, "%d %d %s %s\n" % (expected_total, n, names[0], names[n - 1]))
            self.assertIn("ail_sfield_set(", body_of(c_file.read_text(), "py_main"))
            built, exe, _ = build(directory, CHURN, name="churn")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            # 300k stores of ~205 bytes (60 MB stored in all) into a 100-element field: the field
            # never holds more than its live text plus the slack.
            code, out, rss = run_measured([str(exe), "300000"], timeout=60)
            self.assertEqual(code, 0)
            self.assertEqual(out, "206 %s\n" % ("abcdefghij" * 20 + "299999"))
            if rss is not None:
                self.assertLess(rss, 20000, rss)

    def test_buffer_swap_moves_and_copies_stay_where_observable(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, SWAP, name="swap")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            # Same program in Python, copying where AIL copies a list (a read of a list field,
            # `let ys = xs`); the struct alias `a = g` stays an alias.
            cur, nxt, f, h = [1, 2, 3, 4, 5], [0] * 5, [0.5], [1.5, 2.5]
            for _ in range(4):
                for i in range(5):
                    nxt[i] = cur[i] + cur[(i + 1) % 5]
                cur, nxt, f, h = nxt, cur, h, f
            lines = [",".join(map(str, cur)) + " " + ",".join(map(str, nxt)) + " %d %d" % (len(f), len(h))]
            tmp = list(cur); cur = list(nxt); nxt = list(tmp)
            tmp[0] = 1000
            kept = tmp[0] + nxt[0]
            first = nxt[0]
            seen = len(cur); tmp = list(cur); cur = list(nxt); nxt = tmp
            lines.append("%d %d %d" % (kept, first, seen))
            t2 = list(cur); cur = list(nxt); nxt = t2
            lines.append("%d %d" % (cur[0], nxt[0]))
            self.assertEqual(ran.stdout, "\n".join(lines) + "\n")
            program = c_file.read_text()
            swap = body_of(program, "step")
            self.assertNotIn("_snapshot", swap)
            self.assertNotIn("ail_obj_field_list(", swap)
            self.assertIn("ail_obj_field_list_move(", swap)
            self.assertIn("ail_obj_field_flist_move(", swap)
            # tmp is read after the store: the field gets a copy and keeps it
            self.assertIn("ail_list_snapshot", body_of(program, "keep"))
            # g.cur is read between the read and its store: it is copied, not taken
            peek = body_of(program, "peek")
            self.assertIn("ail_list_snapshot(_source.p, _source.n); ail_list_free(&v__t", peek)
            self.assertNotIn("&(v_g)->f_cur; ail_list _moved", peek)


# These tests pin the C text of the legacy emitter, the AIL_IR=0 opt-out (the IR is the default since
# 2026-10-19 and has its own text, pinned in test_ail_ir_*): the whole module builds with AIL_IR=0
# unless the caller set AIL_IR.
_SAVED_AIL_IR = []


def setUpModule():
    import os as _os
    _SAVED_AIL_IR.append(_os.environ.get('AIL_IR'))
    if _SAVED_AIL_IR[-1] is None:
        _os.environ['AIL_IR'] = '0'


def tearDownModule():
    import os as _os
    if _SAVED_AIL_IR.pop() is None:
        _os.environ.pop('AIL_IR', None)


if __name__ == "__main__":
    unittest.main()
