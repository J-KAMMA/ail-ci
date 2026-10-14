"""Nested lists: list[list[int]], list[list[float]], list[list[str]] and list[list[Struct]].

LLM-written AIL built adjacency lists, grids and buckets by hand (parallel lists, offset arrays,
`[0] * (n * w)` with index math) where Python writes `adj = [[] for _ in range(n)]`. A nested list
is now lowered to a list of hidden row structs (python/pkg-v12/nested_lists.py), so locals, struct
fields, parameters and results all work, with Python's semantics: a row read from the list is the
same list (`r = g[i]; r.append(x)` is seen through `g`), `[[0] * w] * h` is refused, and a bad
index raises IndexError.

The oracle is CPython running the very same source (`ail_syntax.translate`, then `exec`): a
random operation stream over adjacency lists (BFS), grids (DP), word buckets, struct rows and one
list mutated by 16 kinds of operation, plus a fixed program for aliasing, parameters, results,
comprehensions, live iteration and IndexError. Also checked: the generated C reads and writes
`g[i][j]` and appends to `g[i]` in place (no copy, no retain of the row) and walks `for x in g[i]`
without a snapshot; the programs are clean under ASan+UBSan with leak detection; refusals.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STREAM = r'''
struct Rng { s: int; }
impl Rng {
    fn next(self, m: int) -> int {
        self.s = (self.s * 1103515245 + 12345) % 2147483648;
        return (self.s >> 8) % m;
    }
}
struct Item { w: int; tag: str; }
struct Graph { n: int; adj: list[list[int]]; }
impl Graph {
    fn add(self, u: int, v: int) -> void { self.adj[u].append(v); self.adj[v].append(u); }
    fn degree(self, u: int) -> int { return len(self.adj[u]); }
    fn bfs(self, src: int) -> list[int] {
        let dist = [-1] * self.n;
        dist[src] = 0;
        let q = [src];
        let head = 0;
        while head < len(q) {
            let u = q[head];
            head += 1;
            for v in self.adj[u] {
                if dist[v] < 0 { dist[v] = dist[u] + 1; q.append(v); }
            }
        }
        return dist;
    }
}
fn show(xs: list[int]) -> str {
    let parts: list[str] = [];
    for x in xs { parts.append(str(x)); }
    return "[" + ",".join(parts) + "]";
}
fn show_grid(g: list[list[int]]) -> str {
    let parts: list[str] = [];
    for row in g { parts.append(show(row)); }
    return "[" + ",".join(parts) + "]";
}
fn showf(g: list[list[float]]) -> str {
    let parts: list[str] = [];
    for row in g {
        let cells: list[str] = [];
        for x in row { cells.append(f"{x:.2f}"); }
        parts.append("|".join(cells));
    }
    return "/".join(parts);
}
fn total(g: list[list[int]]) -> int {
    let s = 0;
    for row in g { s += sum(row); }
    return s;
}
fn bump_rows(g: list[list[int]], k: int) -> void {
    for i in range(len(g)) { g[i].append(k + i); }
}
fn make_grid(h: int, w: int, r: Rng) -> list[list[int]] {
    return [[r.next(10) for _ in range(w)] for _ in range(h)];
}
fn transpose(g: list[list[int]]) -> list[list[int]] {
    let t: list[list[int]] = [];
    if len(g) == 0 { return t; }
    for j in range(len(g[0])) {
        let col: list[int] = [];
        for i in range(len(g)) { col.append(g[i][j]); }
        t.append(col);
    }
    return t;
}
fn min_path(g: list[list[int]]) -> int {
    let h = len(g);
    let w = len(g[0]);
    let dp = [[0] * w for _ in range(h)];
    for i in range(h) {
        for j in range(w) {
            let best = 0;
            if i > 0 and j > 0 { best = min(dp[i - 1][j], dp[i][j - 1]); }
            elif i > 0 { best = dp[i - 1][j]; }
            elif j > 0 { best = dp[i][j - 1]; }
            dp[i][j] = best + g[i][j];
        }
    }
    return dp[h - 1][w - 1];
}
fn lcs(a: str, b: str) -> int {
    let dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)];
    for i in range(1, len(a) + 1) {
        for j in range(1, len(b) + 1) {
            if a[i - 1] == b[j - 1] { dp[i][j] = dp[i - 1][j - 1] + 1; }
            else { dp[i][j] = max(dp[i - 1][j], dp[i][j - 1]); }
        }
    }
    return dp[len(a)][len(b)];
}
fn word(r: Rng) -> str {
    let letters = "abcde";
    let n = 1 + r.next(4);
    let s = "";
    for _ in range(n) { s += letters[r.next(5)]; }
    return s;
}
fn main() {
    let r = Rng(int(sys.argv[1]));
    # adjacency lists and BFS
    let n = 5 + r.next(30);
    let gr = Graph(n, [[] for _ in range(n)]);
    for _ in range(r.next(3 * n)) { gr.add(r.next(n), r.next(n)); }
    for u in range(n) { gr.adj[u].sort(); }
    print("bfs", show(gr.bfs(0)), gr.degree(n - 1), show(gr.adj[0]));
    # grid DP
    let h = 1 + r.next(6);
    let w = 1 + r.next(6);
    let g = make_grid(h, w, r);
    print("grid", show_grid(g), min_path(g), show_grid(transpose(g)), total(g));
    print("lcs", lcs(word(r) + word(r), word(r) + word(r)));
    # float grid
    let fg: list[list[float]] = [[0.0] * w for _ in range(h)];
    for i in range(h) { for j in range(w) { fg[i][j] = float(g[i][j]) / 4.0; } }
    for i in range(1, h) { for j in range(w) { fg[i][j] += fg[i - 1][j] * 0.5; } }
    print("fgrid", showf(fg), f"{sum(fg[h - 1]):.3f}", f"{max(fg[0]):.2f}");
    # buckets of words
    let buckets: list[list[str]] = [[] for _ in range(5)];
    let letters = "abcde";
    for _ in range(r.next(25)) {
        let s = word(r);
        buckets[letters.find(s[0])].append(s);
    }
    for b in buckets { b.sort(); }
    let lens = [len(b) for b in buckets];
    print("buckets", show(lens), "/".join([",".join(b) for b in buckets]), 1 if "a" in buckets[0] else 0, 1 if "eee" not in buckets[4] else 0);
    # structs in rows
    let shelves: list[list[Item]] = [[] for _ in range(3)];
    for _ in range(r.next(9)) { shelves[r.next(3)].append(Item(r.next(100), word(r))); }
    for shelf in shelves { shelf.sort(key=lambda it: (it.w, it.tag)); }
    let names: list[str] = [];
    for shelf in shelves { for it in shelf { names.append(it.tag + str(it.w)); } }
    print("items", ",".join(names), len(shelves[0]));
    # a random stream of operations on one nested list
    let m: list[list[int]] = [[1, 2], [3]];
    for step in range(60 + r.next(60)) {
        let op = r.next(16);
        let i = r.next(len(m) + 2) - 1;
        let v = r.next(50) - 10;
        try {
            if op == 0 { m.append([v]); }
            elif op == 1 { m[i].append(v); }
            elif op == 2 { print("pop", m[i].pop()); }
            elif op == 3 { m[i][r.next(3) - 1] = v; }
            elif op == 4 { m[i][r.next(3)] += v; }
            elif op == 5 { m[i].sort(); }
            elif op == 6 { m[i].sort(reverse=True); }
            elif op == 7 { let cur = m[i]; cur.append(v); cur.append(v + 1); }
            elif op == 8 { if len(m) > 1 { m[(i + 1) % len(m)] = m[i]; } }
            elif op == 9 { m.insert(r.next(len(m) + 1), [v, v]); }
            elif op == 10 { m[i].extend([v, -v]); }
            elif op == 11 { if len(m) > 2 { let dropped = m.pop(); print("drop", show(dropped)); } }
            elif op == 12 { m[i] = [x * 2 for x in m[i] if x % 3 != 0]; }
            elif op == 13 { print("q", len(m[i]), 1 if v in m[i] else 0, sum(m[i])); }
            elif op == 14 { m[i].insert(0, v); m[i].reverse(); }
            else { let fresh = [list_copy for list_copy in m[i]]; fresh.append(99); print("copy", len(fresh), len(m[i])); }
        } except IndexError {
            print("IndexError", op, i);
        }
        if step % 10 == 0 { print("m", show_grid(m)); }
    }
    bump_rows(m, 100);
    print("final", show_grid(m), total(m), len(m));
    let flat: list[int] = [];
    for mrow in m { for x in mrow { flat.append(x); } }
    let widths = [len(wr) for wr in m if len(wr) > 1];
    print("flat", len(flat), show(widths));
    return 0;
}
'''

FEATURES = r'''
struct P { x: int; name: str; }
struct Board { cells: list[list[int]]; tags: list[list[str]]; heat: list[list[float]]; }
impl Board {
    fn put(self, i: int, j: int, v: int) -> void { self.cells[i][j] = v; self.cells[i][j] += 1; }
    fn row_total(self, i: int) -> int { return sum(self.cells[i]); }
    fn widest(self) -> int {
        let best = 0;
        for row in self.cells { if len(row) > best { best = len(row); } }
        return best;
    }
}
fn show(xs: list[int]) -> str {
    let parts: list[str] = [];
    for x in xs { parts.append(str(x)); }
    return "[" + ",".join(parts) + "]";
}
fn show2(g: list[list[int]]) -> str {
    let parts: list[str] = [];
    for row in g { parts.append(show(row)); }
    return "[" + ",".join(parts) + "]";
}
fn add_edge(adj: list[list[int]], u: int, v: int) -> void { adj[u].append(v); }
fn degrees(adj: list[list[int]]) -> list[int] { return [len(r) for r in adj]; }
fn identity(n: int) -> list[list[int]] {
    let m = [[0] * n for _ in range(n)];
    for i in range(n) { m[i][i] = 1; }
    return m;
}
fn row_of(g: list[list[int]], i: int) -> list[int] { return g[i]; }
fn words() -> list[list[str]] { return [["b", "a"], [], ["c"]]; }
fn main() {
    let b = Board([[0] * 3 for _ in range(2)], [[] for _ in range(2)], [[0.5, 1.5], [2.0]]);
    b.put(1, 2, 7);
    b.tags[0].append("x"); b.tags[0].append("y");
    b.heat[1][0] *= 1.5;
    b.cells.append([1, 2, 3, 4]);
    print(show2(b.cells), b.row_total(1), b.widest(), ",".join(b.tags[0]), len(b.tags[1]), b.heat[1][0], sum(b.heat[0]));
    let adj: list[list[int]] = [[] for _ in range(4)];
    add_edge(adj, 0, 1); add_edge(adj, 0, 2); add_edge(adj, 3, 0);
    print(show(degrees(adj)), show2(identity(3)), show(row_of(adj, 0)));
    let ws = words();
    ws[0].sort();
    ws[1].append("z");
    print(",".join(ws[0]), ws[1][0], len(ws), ws[-1][-1]);
    # aliasing, as in Python
    let g = [[1, 2], [3]];
    let r = g[0];
    r.append(9);
    g[0] += [5];
    print(show2(g), show(r));
    g[0] = g[0] + [6];
    print(show2(g), show(r));
    let h = g;
    h.append([7]);
    let c = g.copy();
    c.append([8]);
    c[0].append(0);
    print(len(g), len(h), len(c), show(g[0]));
    g[1] = g[2];
    g[2].append(70);
    print(show2(g));
    # a row walked while it grows: Python's list iterator sees the appends
    let grow = [[1, 2, 3]];
    for x in grow[0] { if len(grow[0]) < 6 { grow[0].append(x * 10); } }
    print(show(grow[0]));
    # comprehensions, enumerate, slices, membership, folds
    let k = [[i * j for j in range(4)] for i in range(3) if i != 1];
    let flat = [x for row in k for x in row if x > 0];
    let lens = [len(row) for row in k];
    print(show2(k), show(flat), show(lens), sum(k[1]), max(k[1]), min(k[1]), 1 if 6 in k[1] else 0);
    for i, row in enumerate(k) { print(i, show(row[1:3]), show(row[::-1]), len(row[-2:])); }
    let fl: list[list[float]] = [[2.5, 0.5], [1.0]];
    fl[0].sort();
    fl[1].append(fl[0][1] * 2.0);
    print(fl[0][0], fl[1][-1], sum(fl[1]), max(fl[0]));
    let pts: list[list[P]] = [[] for _ in range(2)];
    pts[1].append(P(4, "d")); pts[1].append(P(2, "b")); pts[0].append(P(9, "z"));
    pts[1].sort(key=lambda p: p.x);
    let names = [p.name for p in pts[1]];
    print(pts[1][0].name, pts[1][-1].x, ",".join(names), len(pts[0]));
    let srt = [[3, 1], [2, 9, 4], []];
    for row in srt { row.sort(reverse=True); }
    srt.sort(key=lambda row: len(row));
    print(show2(srt));
    let popped = srt.pop();
    print(show(popped), len(srt), srt[-1].pop(), show2(srt));
    # IndexError like Python
    try { print(g[10][0]); } except IndexError { print("outer IndexError"); }
    try { print(g[0][10]); } except IndexError { print("inner IndexError"); }
    try { g[0][-10] = 1; } except IndexError { print("store IndexError"); }
    try { g[10].append(1); } except IndexError { print("append IndexError"); }
    let e: list[list[int]] = [];
    try { e.pop(); } except IndexError { print("pop IndexError"); }
    e.append([]);
    try { e[0].pop(); } except IndexError { print("row pop IndexError"); }
    return 0;
}
'''

ORACLE = r'''
import sys
sys.path.insert(0, sys.argv[1])
from ail_syntax import translate
source = translate(open(sys.argv[2]).read())
sys.argv = sys.argv[2:]
exec(compile("from __future__ import annotations\n" + source, "oracle", "exec"), {"__name__": "__main__"})
'''

REFUSED = [
    ('fn main() { let n = 3; let g = [[0] * 3] * n; print(len(g)); }', '[[0] * 3 for _ in range(n)]'),
    ('fn main() { let g = [[]] * 2; print(len(g)); }', '[[] for _ in range(2)]'),
    ('fn main() { let row = [1]; let g = [row] * 3; print(len(g)); }', '[row.copy() for _ in range(3)]'),
    ('fn main() { let g: list[list[bytes]] = []; print(len(g)); }', 'rows of int, float, str or a struct'),
    ('fn main() { let g: list[list[list[int]]] = []; print(len(g)); }', 'rows of int, float, str or a struct'),
    ('fn main() { let g = [[3, 1]]; g[0].sort(key=lambda x: -x); }', 'key= is not built'),
    ('fn main() { let g = [[1]]; let w = [["a"]]; for r in g { print(len(r)); } for r in w { print(len(r)); } }',
     'a local keeps one type'),
    ('fn main() { let c = 1; let g = [[1] for _ in range(2)] if c else [[2]]; print(len(g)); }',
     'build it first with a let'),
    ('fn main() { let g = [[1]]; print(g); }', 'list[list[int]]'),
]


def build(directory, text, name):
    source, exe, debug = Path(directory, name + '.ail'), Path(directory, name), Path(directory, name + '-debug')
    source.write_text(text)
    built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                            '-o', str(exe), '--debug-dir', str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / 'program.c'


def oracle(directory, source, *args):
    script = Path(directory, 'oracle.py')
    script.write_text(ORACLE)
    return subprocess.run([sys.executable, str(script), str(ROOT), str(source), *map(str, args)],
                          capture_output=True, text=True, timeout=120)


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, program)
    assert match, name
    return program[match.end():program.index('\n}\n', match.end())]


class NestedListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.mkdtemp(prefix='ail-nested-')
        cls.stream = build(cls.directory, STREAM, 'stream')
        cls.features = build(cls.directory, FEATURES, 'features')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory, ignore_errors=True)

    def compare(self, built, name, args):
        compiled, exe, _ = built
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        ran = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=60)
        expected = oracle(self.directory, Path(self.directory, name + '.ail'), *args)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout)
        return ran.stdout

    def test_random_streams_match_cpython(self):
        seen = []
        for seed in (1, 2, 6, 7, 2026, 99991):
            with self.subTest(seed=seed):
                seen.append(self.compare(self.stream, 'stream', [seed]))
        text = ''.join(seen)
        for word in ('bfs [0,', 'grid [[', 'lcs ', 'fgrid ', 'buckets ', 'items ', 'IndexError ', 'pop ',
                     'drop [', 'q ', 'copy ', 'final [[', 'flat '):
            self.assertIn(word, text)

    def test_aliasing_parameters_results_and_errors_match_cpython(self):
        out = self.compare(self.features, 'features', [])
        # r = g[0] shares the row; g[0] += [5] extends it in place; g[0] = g[0] + [6] rebinds.
        self.assertIn('[[1,2,9,5],[3]] [1,2,9,5]\n[[1,2,9,5,6],[3]] [1,2,9,5]\n', out)
        self.assertIn('[1,2,3,10,20,30]\n', out)  # a row walked while it grows
        for word in ('outer', 'inner', 'store', 'append', 'pop', 'row pop'):
            self.assertIn(word + ' IndexError\n', out)

    def test_generated_c_accesses_rows_in_place(self):
        program = self.stream[2].read_text()
        for name in ('Graph__add', 'Graph__bfs', 'min_path', 'lcs', 'bump_rows'):
            body = body_of(program, name)
            for copy in ('_snapshot', 'ail_list_copy', 'ail_olist_copy'):
                self.assertNotIn(copy, body, name)
        # g[i].append(x), g[i][j] and g[i][j] = v: bounds-checked, then the row is used in place
        add = body_of(program, 'Graph__add')
        self.assertIn('ail_numfield_list_append(&((ail_obj__AilRow_int *)((v_self)->f_adj)->p[', add)
        self.assertNotIn('ail_obj_retain(ail_olist_get', add)
        path = body_of(program, 'min_path')
        self.assertIn('ail_numfield_list_set(&((ail_obj__AilRow_int *)(v_dp)->p[', path)
        self.assertIn('ail_list_span_get(((ail_obj__AilRow_int *)(v_dp)->p[', path)
        self.assertNotIn('ail_obj_retain(ail_olist_get', path)
        # for v in self.adj[u]: the row is held for the loop and walked live (length re-read)
        self.assertRegex(body_of(program, 'Graph__bfs'), r'for \(v__t\d+ = 0; v__t\d+ < v__t\d+->f_v\.n; v__t\d+\+\+\)')

    def test_sanitizers_report_nothing(self):
        compiler = os.environ.get('PIPE_CC') or shutil.which('gcc')
        if not compiler or os.name == 'nt':
            self.skipTest('needs gcc with ASan/UBSan')
        for built, name, runs in ((self.stream, 'stream', ([1], [6], [2026])), (self.features, 'features', ([],))):
            exe = Path(self.directory, name + '-asan')
            compiled = subprocess.run([compiler, '-O1', '-g', '-fsanitize=address,undefined',
                                       '-fno-sanitize-recover=all', '-o', str(exe), str(built[2]), '-lm'],
                                      capture_output=True, text=True, timeout=300)
            if compiled.returncode and 'sanitize' in compiled.stderr:
                self.skipTest('sanitizers unavailable: ' + compiled.stderr[-200:])
            self.assertEqual(compiled.returncode, 0, compiled.stderr[-2000:])
            for args in runs:
                with self.subTest(program=name, args=args):
                    ran = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=120,
                                         env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1'))
                    self.assertEqual(ran.returncode, 0, ran.stderr[-3000:])
                    self.assertEqual(ran.stderr, '')

    def test_misuse_is_refused_with_a_route(self):
        for index, (text, hint) in enumerate(REFUSED):
            with self.subTest(text=text):
                built, exe, _ = build(self.directory, text, 'refused%d' % index)
                self.assertNotEqual(built.returncode, 0)
                self.assertFalse(exe.exists())
                self.assertIn(hint, built.stdout + built.stderr)
                self.assertNotIn('_AilRow', built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
