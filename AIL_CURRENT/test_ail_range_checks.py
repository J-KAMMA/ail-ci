"""Overflow and index checks elided by the value-range analysis (python/pkg-v12/rangecheck.py).

The analysis may remove a `ck_add/ck_sub/ck_mul` or a list/bytes index check only where it can
never fire. These tests hold it to that: the edge programs below run against CPython (with every
int `+ - *` checked against int64, which is this language's rule), at values next to 2**63, over
negative ranges, with loop bounds changed inside the loop, with lists resized inside the loop and
through struct fields, under ASan+UBSan (a wrongly elided add is signed overflow, which UBSan
traps), and the generated C is checked for the checks that should be gone and the ones that must
stay.
"""
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
# The C-text assertions below describe the legacy emitter; with AIL_IR set, functions in the IR's
# subset are emitted by the IR (same behaviour, different text), so only the behaviour is checked.
LEGACY_C = os.environ.get('AIL_IR', '0').strip().lower() in ('', '0', 'off', 'no')
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

EDGES = r"""
const MAXV = 9223372036854775807;
const MINV = -9223372036854775808;

fn add1(a: int) -> int { return a + 1; }

fn top_loop() -> int {
    let last = 0;
    for i in range(MAXV - 3, MAXV) { last = i + 1; }
    return last;
}

fn bottom_loop(lo: int) -> int {
    let last = 0;
    for i in range(lo, lo + 3) { last = i - 1; }
    return last;
}

fn while_lt(n: int) -> int {
    let i = n - 3;
    while i < n { i += 1; }
    return i;
}

fn while_le(n: int) -> int {
    let i = n - 3;
    while i <= n { i += 1; }
    return i;
}

fn count_down(n: int) -> int {
    let i = n;
    let steps = 0;
    while i > 0 { i -= 1; steps += 1; }
    return steps;
}

fn neg_index(xs: list[int]) -> int {
    let s = 0;
    for i in range(-3, 3) { s = s + xs[i] * (i + 10); }
    return s;
}

fn local_neg(k: int) -> int {
    let xs = [10, 20, 30, 40];
    let s = 0;
    for i in range(k, 4) { s = s + xs[i] + i; }
    return s;
}

fn square_guard(w: int) -> int {
    if w < 0 or w > 3037000499 { return -1; }
    return w * w;
}

fn square_loose(w: int) -> int {
    if w > 3037000500 { return -1; }
    return w * w;
}

fn modified_bound(n0: int) -> int {
    let n = n0;
    let xs = [0] * n;
    let s = 0;
    for i in range(n) {
        n = n - 1;
        xs[i] = i + n;
        s = s + xs[i];
    }
    return s + n;
}

fn bound_grows(n0: int) -> int {
    let n = n0;
    let xs = [1] * n0;
    let s = 0;
    let i = 0;
    while i < n {
        s = s + xs[i];
        i += 1;
        if i == 3 { n = n + 2; }
    }
    return s;
}

fn shrinking(k: int) -> int {
    let xs = [1] * 10;
    let s = 0;
    for i in range(10) {
        if i == k { xs.pop(); xs.pop(); xs.pop(); xs.pop(); xs.pop(); xs.pop(); }
        s = s + xs[i];
    }
    return s;
}

fn growing() -> int {
    let xs = [3] * 4;
    let s = 0;
    let i = 0;
    while i < len(xs) {
        if len(xs) < 12 { xs.append(i); }
        s = s + xs[i];
        i += 1;
    }
    return s;
}

fn rebuilt(n: int) -> int {
    let xs = [1] * 8;
    let s = 0;
    for i in range(8) {
        if i == n { xs = [2] * 3; }
        s = s + xs[i];
    }
    return s;
}

fn elem_max(k: int) -> int {
    let xs = [1] * 6;
    xs[k] = MAXV;
    return xs[0] + xs[3];
}

fn elem_grow(n: int) -> int {
    let xs = [1] * 4;
    for r in range(n) {
        for i in range(4) { xs[i] = xs[i] * 3; }
    }
    return xs[0] + xs[1];
}

fn elem_small(n: int) -> int {
    if n < 1 or n > 100000 { return 0; }
    let xs = [0] * n;
    for i in range(n) { xs[i] = (i * 7 + 3) % 256; }
    let s = 0;
    for i in range(n - 1) { s = s + (xs[i] + xs[i + 1]); }
    return s;
}

fn ring(n: int) -> int {
    if n < 1 { return 0; }
    let h = [0.0] * n;
    for i in range(n) { h[i] = float(i % 5); }
    let acc = 0.0;
    for k in range(n) {
        let i = n - 1 - k;
        let li = i - 1;
        if li < 0 { li = n - 1; }
        let ri = i + 1;
        if ri == n { ri = 0; }
        acc = acc + h[li] * 2.0 + h[ri];
    }
    return int(acc);
}

fn bytes_sum(d: bytes) -> int {
    let n = len(d);
    let s = 0;
    let i = 0;
    while i + 1 < n {
        s = s + (d[i] + d[i + 1]) * 3;
        i += 2;
    }
    return s;
}

fn caught(a: int) -> int {
    let x = 7;
    try { x = a + 1; }
    except OverflowError { x = x - 1; }
    return x + 1;
}

fn mods(a: int, m: int) -> int {
    if m < 1 { return 0; }
    let r = a % m;
    return r + MAXV - m;
}

fn appended(n: int, at: int) -> int {
    let xs: list[int] = [];
    for i in range(n) { xs.append(i * 2); }
    return xs[at] + len(xs);
}

fn half_appended(n: int, at: int) -> int {
    let xs: list[int] = [];
    for i in range(n) { if i % 2 == 0 { xs.append(i); } }
    return xs[at];
}

fn broken_append(at: int) -> int {
    let xs: list[int] = [];
    for i in range(10) {
        if i == 5 { break; }
        xs.append(i);
    }
    return xs[at];
}

fn popped(at: int) -> int {
    let ys = [7] * 10;
    for i in range(5) { ys.pop(); }
    let s = 0;
    for i in range(len(ys)) { s = s + ys[i]; }
    return s + ys[at];
}

fn nested_append(at: int) -> int {
    let xs: list[int] = [];
    for i in range(3) { for j in range(4) { xs.append(i * 4 + j); } }
    return xs[at];
}

fn counted(n: int) -> int {
    let c = 0;
    let xs = [1] * 5;
    for i in range(n) { if i % 3 == 0 { c += 1; } }
    return xs[c];
}

fn run(k: int, a: int) -> str {
    try {
        if k == 0 { return str(add1(a)); }
        if k == 1 { return str(top_loop()); }
        if k == 2 { return str(bottom_loop(a)); }
        if k == 4 { return str(while_lt(a)); }
        if k == 5 { return str(while_le(a)); }
        if k == 6 { return str(count_down(a)); }
        if k == 7 { return str(square_guard(a)); }
        if k == 8 { return str(square_loose(a)); }
        if k == 9 { return str(modified_bound(a)); }
        if k == 10 { return str(shrinking(a)); }
        if k == 11 { return str(growing()); }
        if k == 12 { return str(elem_max(a)); }
        if k == 13 { return str(elem_small(a)); }
        if k == 14 { return str(ring(a)); }
        if k == 15 { return str(caught(a)); }
        if k == 16 { return str(mods(a, 1000)); }
        if k == 17 { return str(local_neg(a)); }
        if k == 18 { return str(bound_grows(a)); }
        if k == 19 { return str(rebuilt(a)); }
        if k == 21 { return str(appended(6, a)); }
        if k == 22 { return str(half_appended(6, a)); }
        if k == 23 { return str(broken_append(a)); }
        if k == 24 { return str(popped(a)); }
        if k == 25 { return str(nested_append(a)); }
        if k == 26 { return str(counted(a)); }
        return str(elem_grow(a));
    }
    except OverflowError { return "overflow"; }
    except IndexError { return "index"; }
}

fn main() {
    print(run(0, MAXV), run(0, MAXV - 1), run(0, MINV));
    print(run(1, 0), run(2, MINV), run(2, MINV + 1), run(2, MAXV - 2), run(2, MAXV - 3));
    print(run(4, MAXV), run(4, MINV + 3), run(5, MAXV), run(5, MAXV - 1));
    print(run(6, 5), run(6, -5), run(6, 0));
    print(run(7, 3037000499), run(7, 3037000500), run(7, -1), run(8, 3037000500), run(8, -3037000500), run(8, -3037000499));
    print(run(9, 6), run(9, 0), run(9, -4));
    print(run(10, 2), run(10, 4), run(10, 9), run(10, 11));
    print(run(11, 0), run(12, 3), run(12, 4), run(12, 9), run(13, 1000), run(13, 1));
    print(run(14, 7), run(14, 1), run(15, 5), run(15, MAXV));
    print(run(16, MINV), run(16, MAXV), run(16, -1), run(16, 999));
    print(run(17, -4), run(17, -5), run(17, 2), run(18, 3), run(18, 6), run(18, 1));
    print(run(19, 2), run(19, 3), run(19, 8), run(20, 3), run(20, 39), run(20, 40));
    print(run(21, 5), run(21, 6), run(21, -6), run(21, -7), run(22, 2), run(22, 3), run(22, 5));
    print(run(23, 4), run(23, 5), run(24, 4), run(24, 5), run(24, -5), run(25, 11), run(25, 12));
    print(run(26, 12), run(26, 13), run(26, 15), run(26, 0));
    print(neg_index([5, 6, 7, 8, 9, 10]));
    print(bytes_sum(b"\xff\xfe\x01\x02\x80"), bytes_sum(b""), bytes_sum(b"\x10"));
}
"""

# A struct field read is a copy in this language (CPython would alias), so these two are checked
# against the compiler's own answer from before the analysis existed, not against CPython.
FIELDS = r"""
struct Box { v: list[int]; n: int; }

fn through_field() -> int {
    let b = Box([0, 1, 2, 3, 4], 5);
    let xs = b.v;
    b.v.pop();
    b.v.pop();
    return xs[4] + len(b.v);
}

fn field_loop(b: Box) -> int {
    let s = 0;
    for i in range(b.n) { s = s + b.v[i]; b.v.pop(); }
    return s;
}

fn main() {
    print(through_field());
    let b = Box([1, 2, 3, 4, 5, 6], 6);
    try { print(field_loop(b)); }
    except IndexError { print("index", len(b.v)); }
}
"""
FIELDS_EXPECTED = "7\nindex 3\n"

# Codegen: which checks are gone (proven) and which stay (not provable).
CODEGEN = r"""
fn proven(n: int) -> int {
    if n < 0 or n > 1000000 { return 0; }
    let xs = [0] * n;
    for i in range(n) { xs[i] = i % 100 + 1; }
    let s = 0;
    for i in range(1, n) { s = s + (xs[i] - xs[i - 1]); }
    return s;
}

fn kept(xs: list[int], n: int) -> int {
    let t = 0;
    for i in range(n) { t = t + i; }
    return t + xs[n] + n * n;
}

fn main() {
    print(proven(10), kept([1, 2, 3], 2));
}
"""


def _ck(op):
    def f(a, b):
        r = op(a, b)
        if type(r) is int and not -(1 << 63) <= r < (1 << 63):
            raise OverflowError('integer overflow')
        return r
    return f


class _Checked(ast.NodeTransformer):
    """Every `a + b`, `a - b`, `a * b` and `-a` raises OverflowError outside int64, like AIL."""
    OPS = {ast.Add: '_ck_add', ast.Sub: '_ck_sub', ast.Mult: '_ck_mul'}

    def visit_BinOp(self, node):
        self.generic_visit(node)
        name = self.OPS.get(type(node.op))
        if name is None:
            return node
        return ast.copy_location(ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[node.left, node.right],
                                          keywords=[]), node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.USub) and not isinstance(node.operand, ast.Constant):
            return ast.copy_location(ast.Call(func=ast.Name(id='_ck_sub', ctx=ast.Load()),
                                              args=[ast.Constant(0), node.operand], keywords=[]), node)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        name = self.OPS.get(type(node.op))
        if name is None or not isinstance(node.target, ast.Name):
            return node
        load = ast.Name(id=node.target.id, ctx=ast.Load())
        call = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[load, node.value], keywords=[])
        return ast.copy_location(ast.Assign(targets=[node.target], value=call), node)


def cpython_reference(source):
    import ail_syntax
    tree = _Checked().visit(ast.parse(ail_syntax.translate(source)))
    tree.body = [st for st in tree.body if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
                                                and ast.unparse(st.value).startswith('sys.exit'))]
    ast.fix_missing_locations(tree)
    env = {'_ck_add': _ck(lambda a, b: a + b), '_ck_sub': _ck(lambda a, b: a - b),
           '_ck_mul': _ck(lambda a, b: a * b), '__name__': 'ail_ref'}
    for checked in ('__ail_checked_int__', '__ail_checked_str__', '__ail_checked_bool__', '__ail_checked_void__'):
        env[checked] = object
    out = io.StringIO()
    with redirect_stdout(out):
        exec(compile(tree, 'ail_ref', 'exec'), env)
        env['main']()
    return out.getvalue()


def build(directory, name, source):
    path, exe, debug = Path(directory, name + '.ail'), Path(directory, name), Path(directory, name + '.d')
    path.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '-o', str(exe),
                            '--debug-dir', str(debug)], capture_output=True, text=True, timeout=600)
    return built, exe, debug / 'program.c'


def function_text(c_source, name):
    m = re.search(r'^int64_t %s\([^;\n]*\) \{\n.*?^}\n' % re.escape(name), c_source, re.M | re.S)
    return m.group(0) if m else ''


class RangeCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.edges = build(cls.tmp.name, 'edges', EDGES)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_edges_match_cpython_with_int64_checks(self):
        built, exe, _ = self.edges
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, cpython_reference(EDGES))

    def test_edges_elide_checks(self):
        built, _, program = self.edges
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        c = program.read_text()
        self.assertNotIn('ck_add', function_text(c, 'top_loop'))          # i + 1 with i < MAXV
        self.assertIn('ck_sub', function_text(c, 'bottom_loop'))          # i - 1 with i >= lo unknown
        self.assertNotIn('ck_add', function_text(c, 'while_lt'))          # i += 1 under i < n
        self.assertIn('ck_add', function_text(c, 'while_le'))             # i <= n: i + 1 may overflow
        self.assertNotIn('ck_mul', function_text(c, 'square_guard'))
        self.assertIn('ck_mul', function_text(c, 'square_loose'))
        self.assertNotIn('ail_flist_get', function_text(c, 'ring'))       # h[li], h[ri] wrap-around
        self.assertNotIn('ail_bytes_get', function_text(c, 'bytes_sum'))
        if LEGACY_C:        # (the IR owns these lists and emits its own checked read)
            self.assertIn('ail_list_get', function_text(c, 'shrinking'))  # resized in the loop
            self.assertIn('ail_list_get', function_text(c, 'rebuilt'))    # rebound in the loop
        self.assertIn('ck_add', function_text(c, 'elem_max'))             # an element may be MAXV

    @unittest.skipUnless(shutil.which('gcc'), 'gcc is not available')
    def test_edges_under_sanitizers(self):
        built, _, program = self.edges
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        exe = Path(self.tmp.name, 'edges_san')
        cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                             '-o', str(exe), str(program), '-lm'], capture_output=True, text=True, timeout=600)
        self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(ran.returncode, 0, ran.stderr[-2000:])
        self.assertEqual(ran.stdout, cpython_reference(EDGES))

    def test_fields_keep_their_checks(self):
        built, exe, _ = build(self.tmp.name, 'fields', FIELDS)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, FIELDS_EXPECTED)

    def test_codegen_proven_and_kept(self):
        built, exe, program = build(self.tmp.name, 'codegen', CODEGEN)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.stdout, cpython_reference(CODEGEN))
        c = program.read_text()
        proven, kept = function_text(c, 'proven'), function_text(c, 'kept')
        self.assertTrue(proven and kept)
        for check in ('ail_list_get', 'ail_list_set', 'ck_sub'):
            self.assertNotIn(check, proven)
        sums = [line for line in proven.splitlines() if 'ck_add(' in line]
        if LEGACY_C:
            self.assertTrue(sums and all(line.strip().startswith('v_s = ') for line in sums), sums)  # only s
        self.assertIn('ck_add(', kept)                                    # t = t + i is unbounded
        self.assertIn('ck_mul(', kept)                                    # n * n, n unknown
        self.assertTrue('ail_list_get' in kept or 'ail_list_view_get' in kept)  # xs[n], len(xs) unknown

    def test_analysis_rules_directly(self):
        sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
        import rangecheck
        src = ('def f(n, d):\n'
               '    if n < 1 or n > 10:\n        return 0\n'
               '    xs = [0] * n\n'
               '    s = 0\n'
               '    for i in range(n):\n'
               '        xs[i] = d[i] + d[i]\n'
               '        s = s + xs[i]\n'
               '    j = n - 1\n'
               '    t = xs[j] + xs[0]\n'
               '    xs.append(5)\n'
               '    t = t + xs[j + 1]\n'
               '    xs.pop()\n'
               '    return xs[j + 1] - t\n')
        fn = ast.parse(src).body[0]
        kinds = {'n': 'int', 'i': 'int', 's': 'int', 'j': 'int', 't': 'int', 'xs': 'list', 'd': 'bytes'}
        proofs = rangecheck.analyze(fn, rangecheck.Info(kinds.get))
        marks = {ast.unparse(node): (proofs.ok_arith(node), proofs.ok_index(node)) for node in ast.walk(fn)
                 if isinstance(node, (ast.BinOp, ast.Subscript))}
        self.assertEqual(marks['xs[i]'], (False, True))
        self.assertEqual(marks['d[i] + d[i]'], (True, False))            # 0..510
        self.assertEqual(marks['d[i]'], (False, False))                  # len(d) unknown
        self.assertEqual(marks['s + xs[i]'], (False, False))             # s grows with the loop
        self.assertEqual(marks['xs[j] + xs[0]'], (True, False))          # elements are 0..510
        self.assertEqual(marks['xs[j]'], (False, True))                  # j == n - 1 == len - 1
        reads = [proofs.ok_index(node) for node in ast.walk(fn)
                 if isinstance(node, ast.Subscript) and ast.unparse(node) == 'xs[j + 1]']
        self.assertEqual(reads, [True, False])           # after the append len is n + 1; after the pop n
        self.assertEqual(marks['t + xs[j + 1]'], (True, False))
        self.assertEqual(marks['xs[j + 1] - t'], (True, False))
        # a lambda may shrink a list whenever it is called: such a list is never tracked
        lam = ast.parse('def g(n):\n    xs = [0] * 4\n    f = lambda: xs.pop()\n    f()\n'
                        '    return xs[3] + xs[n % 2]\n').body[0]
        proofs = rangecheck.analyze(lam, rangecheck.Info({'n': 'int', 'xs': 'list'}.get))
        self.assertFalse(any(proofs.ok_index(node) for node in ast.walk(lam) if isinstance(node, ast.Subscript)))


if __name__ == '__main__':
    unittest.main()
