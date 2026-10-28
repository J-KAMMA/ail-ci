"""A constructor takes over a list or dict local that is never read again, and copies it otherwise.

`T(a0, ..., a12)` with thirteen 3M-element list locals held every list three times: the caller
snapshotted each argument, the constructor snapshotted it again, and the locals stayed alive
(tree_fold: 943 MB peak against C's 215 MB). A numeric list or dict parameter whose only use in
`__init__` is `self.f = p` is now taken by pointer and moved into the field, and the call site
hands over either the local itself -- when liveness on the AST shows nothing can read it again --
or one private copy.

The cases below pin the observable value semantics (a copy wherever the local is used later, in a
loop that comes back to it, in a branch, from a parameter) against output recorded from the
compiler before this change, and the C shape: which arguments are moved and which copied.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct P { xs: list[int]; ys: list[float]; k: int; }
struct Q { n: int; xs: list[int]; }
struct Two { a: list[int]; b: list[int]; }
struct S { d: dict[str, int]; f: dict[str, float]; n: int; }

fn total(xs: list[int]) -> int {
    let s = 0;
    for v in xs { s += v; }
    return s;
}
fn qt(q: Q) -> int { return total(q.xs); }
fn from_param(xs: list[int]) -> Q { return Q(len(xs), xs); }
fn fresh(n: int) -> list[int] { let r = [n] * n; return r; }
fn made_here(n: int) -> Q {
    let local = [n, n + 1];
    local.append(n * 100);
    return Q(n, local);
}
fn dict_here(n: int) -> S {
    let m: dict[str, int] = {};
    for i in range(n) { m["k" + str(i)] = i; }
    let fm: dict[str, float] = {};
    fm["h"] = 0.5;
    return S(m, fm, n);
}
fn guarded(n: int) -> int {
    let gx = [n, n];
    try {
        let q = Q(1, gx);
        if n > 5 { raise ValueError("big"); }
        return qt(q);
    } except ValueError {
        return -1;
    }
}

fn main() -> int {
    let moved = [1, 2, 3];
    let mf = [0.5, 1.5];
    let p = P(moved, mf, 7);
    p.xs[0] = 100;
    print("moved", total(p.xs), len(p.ys), p.k);

    let kept = [4, 5, 6];
    let q = Q(1, kept);
    kept[0] = 40;
    q.xs.append(9);
    print("kept", total(kept), len(kept), total(q.xs), len(q.xs));

    let popped = [7, 8, 9];
    let q2 = Q(popped.pop(), popped);
    print("earlier", q2.n, total(q2.xs), len(q2.xs));

    let twice = [1, 1];
    let tw = Two(twice, twice);
    tw.a[0] = 5;
    print("twice", total(tw.a), total(tw.b));

    let outer = [10, 20];
    let qs: list[Q] = [];
    for i in range(3) {
        qs.append(Q(i, outer));
        qs[i].xs[0] = i;
    }
    print("outer", total(outer), qt(qs[0]), qt(qs[2]));

    let built: list[Q] = [];
    for i in range(3) {
        let row = [i, i + 1];
        row.append(i * 10);
        built.append(Q(i, row));
    }
    print("per-iteration", qt(built[0]), qt(built[1]), qt(built[2]));

    let nested: list[Q] = [];
    for i in range(2) {
        let shared = [i];
        for j in range(2) {
            let inner = [i, j];
            nested.append(Q(j, inner));
            nested.append(Q(j, shared));
        }
    }
    print("nested", len(nested), qt(nested[2]), qt(nested[3]), qt(nested[7]));

    let carry = [1];
    let chain: list[Q] = [];
    let j = 0;
    while j < 3 {
        chain.append(Q(j, carry));
        carry = [j, j];
        j += 1;
    }
    print("carry", qt(chain[0]), qt(chain[1]), qt(chain[2]), total(carry));

    let branch = [3, 3];
    let bq = Q(0, [0]);
    if len(branch) > 5 { bq = Q(1, branch); } else { branch.append(1); }
    print("branch", total(branch), total(bq.xs));

    let base = [5, 5, 5];
    let fq = from_param(base);
    fq.xs[0] = 0;
    print("param", total(base), total(fq.xs));

    let lit = Q(2, [1, 2] + fresh(2));
    print("expr", total(lit.xs));

    let last = [9];
    let after = Q(len(last), last);
    print("len-before", after.n, total(after.xs));

    let mh = made_here(3);
    print("returned", mh.n, total(mh.xs), guarded(2), guarded(9));

    let a: dict[str, int] = {};
    a["x"] = 1;
    let fa: dict[str, float] = {};
    fa["y"] = 2.5;
    let s = S(a, fa, 1);
    s.d["z"] = 3;
    let kd: dict[str, int] = {"k": 4};
    let t = S(kd, fa, 2);
    kd["k"] = 40;
    t.d["q"] = 5;
    let dh = dict_here(50);
    print("dict", len(s.d), s.d["x"], s.f["y"], len(t.d), t.d["k"], kd["k"], len(kd), len(dh.d), dh.d["k49"], dh.f["h"]);
    return 0;
}
"""

# Recorded from the compiler before constructors took arguments over (utf8-str 20cbb51).
EXPECTED = """moved 105 2 7
kept 51 3 24 4
earlier 9 15 2
twice 6 2
outer 30 20 22
per-iteration 1 13 25
nested 8 1 0 1
carry 1 0 2 4
branch 7 0
param 15 10
expr 7
len-before 1 9
returned 3 307 4 -1
dict 2 1 2.5 2 4 40 1 50 49 0.5
"""


def build(directory, text):
    source, exe, debug = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / "program.c").read_text(encoding="utf-8")


class ConstructorMoveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe, cls.program = build(cls.tmp.name, SOURCE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_value_semantics_unchanged(self):
        result = subprocess.run([str(self.exe)], capture_output=True, timeout=60)
        self.assertEqual((result.returncode, result.stdout.decode()), (0, EXPECTED),
                         result.stderr.decode(errors="replace"))

    def handed_over(self):
        """C names passed to a constructor by address of a source local (`&v_name`)."""
        names = set()
        for call in re.findall(r"ail_new_\w+\(([^;]*?)\)\)", self.program):
            names.update(re.findall(r"&\(?\*?v_([a-z]\w*)", call))
        return names

    def test_dead_locals_are_moved(self):
        moved = self.handed_over()
        for name in ("moved", "mf", "popped", "twice", "row", "inner", "last", "local", "gx", "a", "m", "fm"):
            self.assertIn(name, moved)

    def test_live_locals_are_copied(self):
        # used after the call, in a loop that comes back to it, read before reassignment in the
        # next iteration, mentioned in a later branch: each keeps its value and the object a copy.
        # (`fa` is copied into `s` and moved into `t`, its last use.)
        moved = self.handed_over()
        for name in ("kept", "outer", "shared", "carry", "branch", "base", "kd"):
            self.assertNotIn(name, moved)

    def test_constructor_does_not_copy_again(self):
        body = re.search(r"\nstatic ail_obj_Q \*ail_new_Q\(int64_t v_n, ail_list \*v_xs\) \{\n(.*?)\n\}\n",
                         self.program, re.S)
        self.assertIsNotNone(body)
        self.assertNotIn("snapshot", body.group(1))
        self.assertIn("ail_obj_field_list_move(&v_self->f_xs, v_xs);", body.group(1))
        self.assertIn("ail_sdict_replace(&v_self->f_d, ail_sdict_take(v_d));", self.program)


if __name__ == "__main__":
    unittest.main()
