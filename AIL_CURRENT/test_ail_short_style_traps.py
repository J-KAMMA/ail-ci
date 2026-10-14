"""Compiler traps LLMs hit when writing the short, idiomatic style (2026-10-14).

1. A struct-field container read whose argument contains a call -- `st.d.get(int(s), -1)`,
   `st.d[str(i)]`, `st.xs[int(s)]`, `st.ws[len(x) - 1]` -- copied the WHOLE field per lookup
   (20,000 lookups of a 20,000-entry dict field took 7.5 s). The field is now read in place unless
   the argument can replace that field (a user function or method that stores it, function values,
   `:=`). Python reads the container object first and the arguments after, so changes the
   arguments make to its CONTENTS are visible to the lookup (a snapshot hid them), while a
   replaced field is not (the old snapshot path still handles that).
2. A list expression handed straight to a struct constructor or field (`St([0] * n, [])`,
   `[""] * n`, `[1, 2] * n`, `list(range(n))`, `dict()`) was refused with "a list field requires
   the matching numeric list".
3. A dict used as a dict of lists (`groups[k] = []` then `groups[k].append(w)`) is refused by
   naming that shape and its rewrite; a `def main() -> int:` program reached gcc through the
   general path and failed there ("too many arguments to function pf_main").
4. `let seat = f[1] + f[2];` (f = line.split("|")) inside a long line loop was pre-bound to int
   and refused as "assign str to int".
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LOOKUPS = """
struct It { x: int; }
struct St { d: dict[int, int]; sd: dict[str, int]; s: set[int]; xs: list[int]; fs: list[float];
            ws: list[str]; its: list[It]; ds: dict[str, str]; }
fn scan(st: St, n: int) -> int {
    let c = 0;
    for i in range(n) {
        let s = str(i);
        c += st.d.get(int(s), -1) + st.sd.get(s.strip(), -1) + st.d[int(s)] + st.sd[s + ""];
        if int(s) in st.d { c += 1; }
        if int(s) in st.s { c += 1; }
        c += st.xs[int(s)] + int(st.fs[int(s)]) + len(st.ws[int(s)]) + st.its[int(s)].x;
        c += len(st.ds.get(s.strip(), "")) + len(st.ds[s.strip()]);
        c += st.xs[len(st.xs) - 1];
    }
    return c;
}
fn main() {
    let st = St({}, {}, set(), [], [], [], [], {});
    let n = int(sys.argv[1]);
    for i in range(n) {
        st.d[i] = i; st.sd[str(i)] = i; st.s.add(i); st.xs.append(i); st.fs.append(float(i));
        st.ws.append(str(i)); st.its.append(It(i)); st.ds[str(i)] = str(i);
    }
    print(scan(st, n));
}
"""

LOOKUPS_PY = r'''
import sys
n = int(sys.argv[1])
d = {i: i for i in range(n)}; sd = {str(i): i for i in range(n)}; s = set(range(n))
xs = list(range(n)); fs = [float(i) for i in range(n)]; ws = [str(i) for i in range(n)]
ds = {str(i): str(i) for i in range(n)}
c = 0
for i in range(n):
    t = str(i)
    c += d.get(int(t), -1) + sd.get(t.strip(), -1) + d[int(t)] + sd[t + ""]
    c += (int(t) in d) + (int(t) in s)
    c += xs[int(t)] + int(fs[int(t)]) + len(ws[int(t)]) + xs[int(t)]
    c += len(ds.get(t.strip(), "")) + len(ds[t.strip()])
    c += xs[len(xs) - 1]
print(c)
'''

# Arguments that call user code: contents changes are seen (as in Python), a replaced field is not.
EFFECTS = """
struct St { d: dict[int, int]; xs: list[int]; ws: list[str]; sd: dict[str, int]; }
impl St {
    fn put(self, k: int) -> int { self.d[k] = 100 + k; self.xs[0] = 7; self.ws[0] = "w"; self.sd["a"] = 50; return k; }
    fn swap(self, k: int) -> int { self.d = {k: 5}; self.xs = [9, 9]; self.ws = ["z"]; self.sd = {"a": 1}; return k; }
}
fn key(st: St, k: int) -> str { st.sd["a"] = 60 + k; return "a"; }
fn main() {
    let st = St({3: 1}, [1, 2], ["a", "b"], {"a": 0});
    print(st.d.get(st.put(3), -1), st.xs[st.put(0)], st.ws[st.put(0)], st.sd.get(key(st, 1), 0), st.sd[key(st, 2)], st.d[st.put(4)]);
    print(st.d.get(st.swap(3), -1), st.xs[st.put(0) + 1]);
    print(st.xs[st.swap(0)], st.ws[st.swap(0)], st.sd.get(str(st.swap(1)) + "a", -1), st.sd[key(st, 3)]);
    print(st.d.get(int("3"), -2), st.xs[len(st.ws) - 1], st.sd.get("a" + "", 0));
}
"""

EFFECTS_PY = '''
class St:
    def __init__(s, d, xs, ws, sd): s.d, s.xs, s.ws, s.sd = d, xs, ws, sd
    def put(self, k):
        self.d[k] = 100 + k; self.xs[0] = 7; self.ws[0] = "w"; self.sd["a"] = 50; return k
    def swap(self, k):
        self.d = {k: 5}; self.xs = [9, 9]; self.ws = ["z"]; self.sd = {"a": 1}; return k
def key(st, k):
    st.sd["a"] = 60 + k; return "a"
st = St({3: 1}, [1, 2], ["a", "b"], {"a": 0})
print(st.d.get(st.put(3), -1), st.xs[st.put(0)], st.ws[st.put(0)], st.sd.get(key(st, 1), 0), st.sd[key(st, 2)], st.d[st.put(4)])
print(st.d.get(st.swap(3), -1), st.xs[st.put(0) + 1])
print(st.xs[st.swap(0)], st.ws[st.swap(0)], st.sd.get(str(st.swap(1)) + "a", -1), st.sd[key(st, 3)])
print(st.d.get(int("3"), -2), st.xs[len(st.ws) - 1], st.sd.get("a" + "", 0))
'''

CTOR = """
struct P { x: int; }
struct St { a: list[int]; b: list[str]; c: list[float]; d: dict[int, int]; e: set[str]; p: list[P]; }
fn f(k: int) -> int { print("f", k); return k; }
fn mk(n: int) -> St { return St([0] * n, [""] * n, [0.5] * n, dict(), set(), []); }
fn main() {
    let n = int(sys.argv[1]);
    let s = St([0] * n, [], [1.5, 2.0] * 2, {}, set(), []);
    print(len(s.a), len(s.b), len(s.c), s.c[3]);
    let t = St([f(1), f(2)] * f(2), n * ["q"], [1] * 3, dict(), set(), []);
    print(len(t.a), t.a[3], len(t.b), t.b[0], t.c[2]);
    let u = St([7] * (0 - 2), [str(i) for i in range(n) if i > 0], [float(i) / 2.0 for i in range(n)], {}, set(), []);
    u.a.append(1);
    print(len(u.a), len(u.b), u.c[1]);
    let v = St(list(range(n)), ["x", "y"], [], {}, set(), []);
    v.a = [5] * 4; v.b = ["z", "w"] * 2; v.c.extend([2.5] * 2);
    print(v.a[3], v.b[3], len(v.c), v.c[1]);
    let w = mk(n);
    w.a[n - 1] = 3; w.d[1] = 2; w.e.add("x"); w.b[0] = "h";
    print(len(w.a), w.a[n - 1], len(w.d), len(w.e), w.b[0], len(w.b), w.c[0]);
    w.b[1] += "x"; w.b[0] += "y"; w.b[1] += "z";
    print(w.b[0], w.b[1], w.b[n - 1] + "|");
}
"""

CTOR_PY = '''
import sys
def f(k):
    print("f", k); return k
n = int(sys.argv[1])
a, b, c = [0] * n, [], [1.5, 2.0] * 2
print(len(a), len(b), len(c), c[3])
a = [f(1), f(2)] * f(2); b = n * ["q"]; c = [float(x) for x in [1] * 3]
print(len(a), a[3], len(b), b[0], c[2])
a = [7] * (0 - 2); b = [str(i) for i in range(n) if i > 0]; c = [float(i) / 2.0 for i in range(n)]
a.append(1)
print(len(a), len(b), c[1])
a = [5] * 4; b = ["z", "w"] * 2; c = [2.5] * 2
print(a[3], b[3], len(c), c[1])
a, b, c, d, e = [0] * n, [""] * n, [0.5] * n, {}, set()
a[n - 1] = 3; d[1] = 2; e.add("x"); b[0] = "h"
print(len(a), a[n - 1], len(d), len(e), b[0], len(b), c[0])
b[1] += "x"; b[0] += "y"; b[1] += "z"
print(b[0], b[1], b[n - 1] + "|")
'''

# Statement-level sort-key lowering used to report the constructor refusal under "with key= columns".
SORT_AND_CTOR = """
struct St { start: list[int]; dep: list[int]; }
fn main() {
    let ids = [5, 3, 9];
    let byid = [i for i in range(3)];
    byid.sort(key=lambda i: ids[i]);
    let s = St([0] * 3, []);
    print(byid[0], len(s.start), len(s.dep));
}
"""

GROUPS_AIL = """
fn main() {
    let words = ["apple", "banana", "avocado"];
    let groups = {};
    for w in words {
        let k = w[0:1];
        if k not in groups { groups[k] = []; }
        groups[k].append(w);
    }
    print(len(groups));
}
"""

GROUPS_PY_SYNTAX = """def main() -> int:
    groups = {}
    for line in sys.stdin:
        w = line.strip()
        k = w[0:1]
        if k not in groups:
            groups[k] = []
        groups[k].append(w)
    for k in sorted(groups.keys()):
        print(k, len(groups[k]))
    return 0
"""

GROUPS_REWRITE = """
struct G { items: list[str]; }
fn main() {
    let idx: dict[str, int] = {};
    let groups: list[G] = [];
    for line in sys.stdin {
        let w = line.strip();
        let k = w[0:1];
        if k not in idx { idx[k] = len(groups); groups.append(G([])); }
        groups[idx[k]].items.append(w);
    }
    for k in sorted(idx.keys()) { print(k, len(groups[idx[k]].items), ",".join(groups[idx[k]].items)); }
}
"""

INT_ADJACENCY = """
fn main() {
    let adj = {};
    let us = [1, 1, 2];
    let vs = [2, 3, 3];
    for i in range(3) {
        if us[i] not in adj { adj[us[i]] = []; }
        adj[us[i]].append(vs[i]);
    }
    print(len(adj), len(adj[1]));
}
"""

SEAT = """
fn text_of(path: str) -> str {
    let out: list[str] = [];
    for x in range(int(path)) { out.append("S|" + str(x % 3) + "|A" + str(x % 2)); out.append("V|" + str(x)); }
    return "\\n".join(out);
}
fn run(path: str) -> int {
    let text = text_of(path);
    let sold: set[str] = set();
    let c = 0;
    for line in text.split("\\n") {
        let f = line.split("|");
        let t = f[0];
        if t == "S" {
            let seat = f[1] + f[2];
            let tag = f[1].strip() + "-" + f[2][1:];
            if seat in sold { c += 1; }
            sold.add(seat);
            print(seat, tag);
        } else {
            let seat2 = int(f[1]) * 2;
            c += seat2;
        }
    }
    return c;
}
fn main() { print(run(sys.argv[1])); }
"""

SEAT_PY = '''
import sys
out = []
for x in range(int(sys.argv[1])):
    out.append("S|" + str(x % 3) + "|A" + str(x % 2)); out.append("V|" + str(x))
sold, c = set(), 0
for line in "\\n".join(out).split("\\n"):
    f = line.split("|")
    if f[0] == "S":
        seat = f[1] + f[2]
        tag = f[1].strip() + "-" + f[2][1:]
        if seat in sold: c += 1
        sold.add(seat)
        print(seat, tag)
    else:
        c += int(f[1]) * 2
print(c)
'''


def build(directory, text, name="p", env=None):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300, env=env)
    return built, exe, debug / "program.c"


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


def python(directory, text, *args, stdin=None):
    oracle = Path(directory, "oracle.py")
    oracle.write_text(text)
    ran = subprocess.run([sys.executable, str(oracle), *args], capture_output=True, text=True,
                         timeout=60, input=stdin)
    assert ran.returncode == 0, ran.stderr
    return ran.stdout


class ShortStyleTrapTests(unittest.TestCase):
    def test_field_lookup_with_call_argument_reads_in_place(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, LOOKUPS)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            for n in ("0", "7", "3000"):
                ran = subprocess.run([str(exe), n], capture_output=True, text=True, timeout=60)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout, python(directory, LOOKUPS_PY, n))
            body = body_of(c_file.read_text(), "scan")
            for copy in ("_copy(", "_snapshot("):
                self.assertNotIn(copy, body)

    def test_arguments_running_user_code_keep_python_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, EFFECTS)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, python(directory, EFFECTS_PY))

    def test_list_expressions_in_constructors_and_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, CTOR)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            for n in ("2", "4"):
                ran = subprocess.run([str(exe), n], capture_output=True, text=True, timeout=60)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout, python(directory, CTOR_PY, n))
            built, exe, _ = build(directory, SORT_AND_CTOR, name="sorted")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "1 3 0\n")

    def test_list_expression_refusals_name_the_route(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = [
                ('struct P { x: int; } struct St { a: list[P]; } fn main() { let s = St([P(0)] * 2); }',
                 'build it with a loop'),
                ('struct St { a: list[int]; } fn main() { let s = St("abc"); }', 'is a str'),
            ]
            for index, (text, hint) in enumerate(cases):
                built, exe, _ = build(directory, text, name="r%d" % index)
                self.assertNotEqual(built.returncode, 0)
                self.assertIn(hint, built.stdout + built.stderr)

    def test_dict_of_lists_is_refused_by_name_never_by_gcc(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, text in enumerate((GROUPS_AIL, GROUPS_PY_SYNTAX)):
                built, exe, _ = build(directory, text, name="g%d" % index)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0)
                self.assertFalse(exe.exists())
                self.assertIn('dict of containers', output)
                self.assertIn('dict[str, int]', output)
                self.assertNotIn('C compiler rejected', output)
                self.assertNotIn('pf_main', output)
            # the suggested rewrite compiles and matches Python
            built, exe, _ = build(directory, GROUPS_REWRITE, name="rewrite")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60,
                                 input="apple\nbanana\navocado\n")
            self.assertEqual(ran.stdout, "a 2 apple,avocado\nb 1 banana\n")
            # an int-keyed dict of int lists still compiles
            built, exe, _ = build(directory, INT_ADJACENCY, name="adj")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "2 2\n")

    def test_str_built_from_split_fields_inside_line_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, _ = build(directory, SEAT)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe), "9"], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, python(directory, SEAT_PY, "9"))


if __name__ == "__main__":
    unittest.main()
