"""Bounds-check-elision probes (bce s1): the checks the IR already drops must be sound.

Every program in `PROBES` is compiled and run three ways -- the default build, the forced general
path (`AIL_UNIFIED_FORCE=1`) and the audit build (`AIL_BCE_AUDIT=1`, where every removed index check
is emitted again as a loud stop).  A .ail probe's oracle is the Python `tools/ail2py.py` produces,
run under CPython 3.12.  stdout, the exit status and the last stderr line must agree; the audit
build must never print AIL-BCE-AUDIT or exit 86.  Later bce steps append their probes here.

The one exception is `big_text_index`: `int("9223372036854775808")` stops at int() in this language
(ints are 64-bit) while CPython goes on to the index.  It stays the same stop as today in all three
builds; the test pins that, rather than pretending it matches CPython.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None
sys.path.insert(0, str(REPO / 'tools'))
import ail2py  # noqa: E402

BOX = "struct Box { v: list[int]; n: int; }\n"

PROBES = [
    ('range_read_store', r"""
fn main() {
    let xs = [5, 7, 11, 13, 17, 19];
    for i in range(len(xs)) { xs[i] = xs[i] * 2 + i; }
    let s = 0;
    for i in range(len(xs)) { s += xs[i]; }
    print(s);
    print(xs[0], xs[len(xs) - 1]);
}
"""),
    ('range_offset_read', r"""
fn main() {
    let xs = [3, 1, 4, 1, 5, 9, 2, 6];
    let s = 0;
    for i in range(1, len(xs)) { s += xs[i] - xs[i - 1]; }
    print(s);
}
"""),
    ('guarded_next_read', r"""
fn main() {
    let xs = [1, 2, 3, 4, 5];
    let s = 0;
    for i in range(len(xs)) {
        if i + 1 < len(xs) { s += xs[i + 1]; } else { s += xs[i]; }
    }
    print(s);
}
"""),
    ('bytes_scan', r"""
fn main() {
    let d = b"\x41\x42\x0a\x43\x44\x0a\x45";
    let n = len(d);
    let i = 0;
    let lines = 0;
    while i < n {
        while i < n and d[i] != 10 { i += 1; }
        if i < n { i += 1; lines += 1; }
    }
    print(lines);
    let j = 0;
    while j < n and d[j] != 10 { j += 1; }
    print(j);
}
"""),
    ('list_boundaries_ok', r"""
fn main() {
    let xs = [10, 20, 30, 40];
    print(xs[-1], xs[-len(xs)], xs[0], xs[len(xs) - 1]);
}
"""),
    ('list_index_len_raises', r"""
fn main() {
    let xs = [10, 20, 30];
    print(xs[len(xs)]);
}
"""),
    ('list_index_neg_len_minus_one_raises', r"""
fn main() {
    let xs = [10, 20, 30];
    print(xs[-len(xs) - 1]);
}
"""),
    ('bytes_boundaries_ok', r"""
fn main() {
    let d = b"\x0a\x14\x1e\x28";
    print(d[-1], d[-len(d)], d[0], d[len(d) - 1]);
}
"""),
    ('bytes_index_len_raises', r"""
fn main() {
    let d = b"\x0a\x14\x1e";
    print(d[len(d)]);
}
"""),
    ('bytes_index_neg_len_minus_one_raises', r"""
fn main() {
    let d = b"\x0a\x14\x1e";
    print(d[-len(d) - 1]);
}
"""),
    ('field_boundaries_ok', BOX + r"""
fn main() {
    let b = Box([100, 200, 300, 400], 4);
    print(b.v[-1], b.v[-len(b.v)], b.v[0], b.v[len(b.v) - 1]);
}
"""),
    ('field_index_len_raises', BOX + r"""
fn main() {
    let b = Box([100, 200, 300], 3);
    print(b.v[len(b.v)]);
}
"""),
    ('field_index_neg_len_minus_one_raises', BOX + r"""
fn main() {
    let b = Box([100, 200, 300], 3);
    print(b.v[-len(b.v) - 1]);
}
"""),
    ('mutation_pop_in_loop', r"""
fn main() {
    let xs = [10, 20, 30, 40, 50];
    for i in range(len(xs)) {
        xs.pop();
        print(xs[i]);
    }
}
"""),
    ('big_text_index', r"""
fn make() -> str { return "9223372036854775808"; }
fn main() {
    let xs = [10, 20, 30];
    let k = int(make());
    print(xs[k]);
}
"""),
    ('depth_49999', r"""
fn rec(n: int) -> int {
    if n == 0 { return 0; }
    return rec(n - 1) + 1;
}
fn main() -> int {
    print(rec(49998));
    return 0;
}
"""),
    ('depth_50000', r"""
fn rec(n: int) -> int {
    if n == 0 { return 0; }
    return rec(n - 1) + 1;
}
fn main() -> int {
    print(rec(49999));
    return 0;
}
"""),
    ('depth_50001', r"""
fn rec(n: int) -> int {
    if n == 0 { return 0; }
    return rec(n - 1) + 1;
}
fn main() -> int {
    print(rec(50000));
    return 0;
}
"""),
    ('depth_from_mutual', r"""
fn f(n: int) -> int {
    if n == 0 { return 0; }
    return f(n - 1) + 1;
}
fn g(n: int) -> int {
    if n == 0 { return f(20); }
    return h(n - 1);
}
fn h(n: int) -> int {
    if n == 0 { return f(20); }
    return g(n - 1);
}
fn main() -> int {
    print(g(49990));
    return 0;
}
"""),
    ('depth_raise_reuse', r"""
fn f(n: int, mode: int) -> int {
    if n == 0 {
        if mode == 1 { raise ValueError("boom"); }
        return 0;
    }
    return f(n - 1, mode) + 1;
}
fn main() -> int {
    let caught = 0;
    try { print(f(29999, 1)); } except ValueError { caught = 1; }
    print(caught);
    print(f(48999, 0));
    return 0;
}
"""),
    ('depth_helper_ok', r"""
fn helper(x: int) -> int { return x * 2 + 1; }
fn f(n: int) -> int {
    if n == 0 { return helper(3); }
    return helper(f(n - 1));
}
fn main() -> int { print(f(30)); return 0; }
"""),
    ('depth_helper_guarded', r"""
fn other(n: int) -> int {
    if n == 0 { return 0; }
    return other(n - 1) + 1;
}
fn f(n: int) -> int {
    if n == 0 { return 0; }
    return f(n - 1) + other(n);
}
fn main() -> int { print(f(30)); return 0; }
"""),
    ('depth_inner_symbol_collision', r"""
fn f__d(n: int) -> int { return n + 1000; }
fn f(n: int) -> int {
    if n == 0 { return f__d(5); }
    return f(n - 1) + 1;
}
fn main() -> int { print(f(3)); return 0; }
"""),
    ('tally_like_eval', r"""
struct Expr {
    ops: list[int]; left: list[int]; right: list[int]; vals: list[int];
}
fn make(e: Expr, op: int, l: int, r: int, v: int) -> int {
    e.ops.append(op); e.left.append(l); e.right.append(r); e.vals.append(v);
    return len(e.ops) - 1;
}
fn popcnt(x: int) -> int {
    let c = 0;
    let v = x;
    while v != 0 { c += v & 1; v = v >> 1; }
    return c;
}
fn ev(e: Expr, i: int) -> int {
    let op = e.ops[i];
    if op == 100 { return e.vals[i]; }
    if op == 20 { return 0 - ev(e, e.left[i]); }
    if op == 13 { return popcnt(ev(e, e.left[i])); }
    let l = ev(e, e.left[i]);
    let r = ev(e, e.right[i]);
    if op == 1 { if l > r { return l; } return r; }
    if op == 2 { if l < r { return l; } return r; }
    if op == 7 { return (l + r) & 4294967295; }
    if op == 8 { return (l - r) & 4294967295; }
    if op == 9 { let p = l * r; return p & 4294967295; }
    if op == 10 { if r == 0 { raise ValueError("r"); } return l // r; }
    if op == 11 { if r == 0 { raise ValueError("r"); } return l % r; }
    return l;
}
fn main() -> int {
    let e = Expr([], [], [], []);
    let n = 300;
    let i = 0;
    let root = 0;
    while i < n {
        if i < 10 {
            root = make(e, 100, 0, 0, i + 1);
        } else {
            let l = root;
            let r = make(e, 100, 0, 0, i % 7);
            let op = 7 + (i % 3);
            root = make(e, op, l, r, 0);
        }
        i += 1;
    }
    print(ev(e, root));
    return 0;
}
"""),
]

DEPTH_ORACLE = {
    'depth_49999', 'depth_50000', 'depth_50001', 'depth_from_mutual',
    'depth_raise_reuse', 'depth_helper_ok', 'depth_helper_guarded',
    'depth_inner_symbol_collision',
}
DEPTH_STATS = {
    'depth_helper_ok': ('f', 'param'),
    'depth_helper_guarded': ('f', 'callee other can reach a guarded function'),
    'depth_inner_symbol_collision': ('f', 'inner symbol f__d is taken'),
}

STOPS = {
    'big_text_index': 'OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)',
}


def _last_line(data):
    # The runtime appends a "  raised near <file>:<line>" continuation to an uncaught exception;
    # the message is the line before it.
    lines = [x for x in data.decode('utf-8', 'replace').splitlines()
             if x.strip() and not x.startswith('  raised near ')]
    return lines[-1] if lines else ''


def _same_last_line(got, want):
    if got == want:
        return True
    # this runtime's index traps print the message alone, and name the sequence they indexed;
    # CPython prefixes the exception name and, for bytes, leaves the message generic.
    if want.startswith('IndexError: '):
        msg = want[len('IndexError: '):]
        if got.startswith('IndexError: '):
            got = got[len('IndexError: '):]
        return got in (msg, 'bytes ' + msg)
    return False


def _cpython(directory, name, source):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(ail2py.convert(source), encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, source, mode, bce=None, tag=''):
    text, suffix, flags = source, '.ail', []
    if mode == 'force':
        # the forced general path is a Python-surface build; the .ail oracle is the same program
        text, suffix, flags = ail2py.convert(source), '.py', ['--syntax', 'python']
    src = Path(directory) / (name + '_' + mode + suffix)
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode + tag)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_BCE', 'AIL_BCE_AUDIT'):
        env.pop(key, None)
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'audit':
        env['AIL_BCE_AUDIT'] = '1'
    if bce is not None:
        env['AIL_BCE'] = str(bce)
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '-o', exe.name] + flags
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-2000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr),
            got.stderr.decode('utf-8', 'replace')), None


def _ir_stats(directory, name, source):
    src = Path(directory) / (name + '_stats.ail')
    src.write_text(source, encoding='utf-8')
    stats = Path(directory) / (name + '_stats.jsonl')
    if stats.exists():
        stats.unlink()
    exe = Path(directory) / ('exe_' + name + '_stats')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', AIL_IR_STATS=str(stats))
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_BCE', 'AIL_BCE_AUDIT'):
        env.pop(key, None)
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        raise AssertionError((built.stdout + built.stderr)[-2000:])
    return [json.loads(line) for line in stats.read_text(encoding='utf-8').splitlines() if line.strip()]


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class BceProbeTests(unittest.TestCase):
    maxDiff = None

    def _runs(self, directory, name, source):
        runs = {}
        for mode in ('default', 'force', 'audit'):
            got, err = _build_run(directory, name, source, mode)
            self.assertIsNotNone(got, '%s (%s build)\n%s' % (name, mode, err))
            runs[mode] = got
        return runs

    def test_probes_match_cpython_and_audit_is_quiet(self):
        with tempfile.TemporaryDirectory(prefix='ail-bce-') as directory:
            for name, source in PROBES:
                with self.subTest(probe=name):
                    runs = self._runs(directory, name, source)
                    for mode, got in runs.items():
                        self.assertNotEqual(got[1], 86, '%s (%s) hit the audit stop\n%s'
                                            % (name, mode, got[3]))
                        self.assertNotIn('AIL-BCE-AUDIT', got[3], '%s (%s)' % (name, mode))
                    if name in STOPS:
                        self.assertEqual({got[:3] for got in runs.values()}, {runs['default'][:3]}, name)
                        self.assertEqual(runs['default'][2], STOPS[name], name)
                        self.assertEqual(runs['default'][1], 1, name)
                        continue
                    if name in DEPTH_ORACLE:
                        for mode, got in runs.items():
                            # Same source name as the head build: the runtime's "raised near"
                            # line prints the compiled path, and only the program should differ.
                            want, err = _build_run(directory, name, source, mode, bce=0,
                                                   tag='_oracle')
                            self.assertIsNotNone(want, '%s (%s) AIL_BCE=0 oracle\n%s'
                                                 % (name, mode, err))
                            self.assertEqual(got[0], want[0], '%s (%s) stdout' % (name, mode))
                            self.assertEqual(got[1], want[1], '%s (%s) status' % (name, mode))
                            self.assertEqual(got[2], want[2], '%s (%s) stderr' % (name, mode))
                        if name in DEPTH_STATS:
                            fn, depth = DEPTH_STATS[name]
                            entries = _ir_stats(directory, name, source)
                            found = [e for e in entries if e.get('fn') == fn]
                            self.assertTrue(found, '%s: no IR stats for %s' % (name, fn))
                            self.assertEqual(found[-1].get('depth'), depth, '%s: %s' % (name, fn))
                        continue
                    want = _cpython(directory, name, source)
                    for mode, got in runs.items():
                        self.assertEqual(got[0], want[0], '%s (%s) stdout' % (name, mode))
                        self.assertEqual(got[1], want[1], '%s (%s) status' % (name, mode))
                        self.assertTrue(_same_last_line(got[2], want[2]),
                                        '%s (%s) stderr: %r != %r' % (name, mode, got[2], want[2]))


FACT_GROUP_POSITIVE = r"""
struct P { a: list[int]; b: list[int]; }
fn push(p: P) { p.a.append(1); p.b.append(2); }
fn main() { let p = P([], []); push(p); print(len(p.a)); }
"""

FACT_GROUP_INVALID = {
    'pass_list': r"""
struct P { a: list[int]; b: list[int]; }
fn take(x: list[int]) -> int { return len(x); }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); print(take(p.a)); }
""",
    'bind_name': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); let q = p.a; print(len(q)); }
""",
    'return_list': r"""
struct P { a: list[int]; b: list[int]; }
fn bad(p: P) -> list[int] { return p.a; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); print(len(bad(p))); }
""",
    'store_in_field': r"""
struct Box { v: list[int]; }
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); let box = Box(p.a); print(len(box.v)); }
""",
    'insert': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); p.a.insert(0, 3); print(len(p.a)); }
""",
    'extend': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); p.a.extend([3]); print(len(p.a)); }
""",
    'pop_index': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); p.a.pop(0); print(len(p.a)); }
""",
    'remove': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); p.a.remove(1); print(len(p.a)); }
""",
    'slice_store': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([], []); p.a.append(1); p.b.append(2); p.a[0:1] = [9]; print(len(p.a)); }
""",
    'unequal_construction': r"""
struct P { a: list[int]; b: list[int]; }
fn main() { let p = P([1], []); p.a.append(1); p.b.append(2); print(len(p.a)); }
""",
    'raising_between_appends': r"""
struct P { a: list[int]; b: list[int]; }
fn main() {
    let p = P([], []);
    let s = "not a number";
    try { p.a.append(1); p.b.append(int(s)); } except ValueError as e { print(0); }
    print(len(p.a));
}
""",
    'side_effect_receiver': r"""
struct P { a: list[int]; b: list[int]; }
struct S { sel: list[int]; }
fn pick(items: list[P], s: S) -> P {
    let i = s.sel[0];
    s.sel[0] += 1;
    return items[i];
}
fn main() {
    let items: list[P] = [P([], []), P([], [])];
    let s = S([0]);
    pick(items, s).a.append(1);
    pick(items, s).b.append(2);
    print(len(items[0].a), len(items[1].b));
}
""",
}

FACT_LOCAL = r"""
fn main() {
    let ops: list[int] = [];
    let xs: list[int] = [];
    let ys: list[int] = [];
    let zs: list[int] = [];
    let i = 0;
    while i < 3 { ops.append(i); xs.append(i); ys.append(i); zs.append(i); i += 1; }
    print(len(ops), len(xs), len(ys), len(zs));
}
"""

FACT_LOCAL_EXTRA = r"""
fn main() {
    let ops: list[int] = [];
    let xs: list[int] = [];
    let ys: list[int] = [];
    let zs: list[int] = [];
    let i = 0;
    while i < 3 { ops.append(i); xs.append(i); ys.append(i); zs.append(i); i += 1; }
    xs.append(7);
    print(len(ops), len(xs), len(ys), len(zs));
}
"""

FACT_PYTHON = r"""
class P:
    def __init__(self):
        self.a = []
        self.b = []
    def add(self, x: int, y: int) -> None:
        self.a.append(x)
        self.b.append(y)

def main() -> int:
    p = P()
    p.add(1, 2)
    print(len(p.a))
    return 0

main()
"""

FACT_PYTHON_LAMBDA = r"""
class P:
    def __init__(self):
        self.a = []
        self.b = []
def main() -> int:
    p = P()
    p.a.append(1)
    p.b.append(2)
    f = lambda: len(p.a)
    print(f())
    return 0
main()
"""

FACT_NONNEG_POSITIVE = r"""
struct R { pos: int; }
fn main() { let r = R(6); r.pos += 1; print(r.pos); }
"""

FACT_NONNEG_INVALID = {
    'assign_negative': r"""
struct R { pos: int; }
fn main() { let r = R(6); if len(sys.argv) > 1 { r.pos = -1; } print(r.pos); }
""",
    'minus_equals': r"""
struct R { pos: int; }
fn main() { let r = R(6); r.pos -= 1; print(r.pos); }
""",
    'int_of_text': r"""
struct R { pos: int; }
fn main() { let text = "9223372036854775808"; let r = R(6); r.pos = int(text); print(r.pos); }
""",
}


def _dump_facts(directory, name, source, syntax='ail'):
    src = Path(directory) / (name + ('.py' if syntax == 'python' else '.ail'))
    src.write_text(source, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    facts = Path(directory) / (name + '.facts.json')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_BCE_FACTS=str(facts))
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '-o', exe.name]
    if syntax == 'python':
        cmd += ['--syntax', 'python']
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    if built.returncode:
        raise AssertionError('%s failed\n%s' % (name, (built.stdout + built.stderr)[-2000:]))
    return json.loads(facts.read_text(encoding='utf-8'))


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class FieldFactsTests(unittest.TestCase):
    def test_parallel_groups_positive(self):
        with tempfile.TemporaryDirectory(prefix='ail-facts-') as directory:
            data = _dump_facts(directory, 'positive', FACT_GROUP_POSITIVE)
            self.assertIn({'struct': 'P', 'fn': None, 'members': ['a', 'b'], 'grow_only': True},
                          data['groups'])

    def test_parallel_groups_invalidated(self):
        with tempfile.TemporaryDirectory(prefix='ail-facts-') as directory:
            for name, source in FACT_GROUP_INVALID.items():
                with self.subTest(probe=name):
                    data = _dump_facts(directory, 'bad_' + name, source)
                    self.assertEqual(data['groups'], [], name)

    def test_local_group_and_extra_append(self):
        with tempfile.TemporaryDirectory(prefix='ail-facts-') as directory:
            data = _dump_facts(directory, 'local', FACT_LOCAL)
            self.assertTrue(any(g['fn'] == 'main' and g['struct'] is None
                                and {'ops', 'xs', 'ys', 'zs'} <= set(g['members'])
                                for g in data['groups']), data['groups'])
            data = _dump_facts(directory, 'local_extra', FACT_LOCAL_EXTRA)
            self.assertEqual(data['groups'], [])

    def test_python_syntax_group_and_lambda(self):
        with tempfile.TemporaryDirectory(prefix='ail-facts-') as directory:
            data = _dump_facts(directory, 'python', FACT_PYTHON, syntax='python')
            self.assertIn({'struct': 'P', 'fn': None, 'members': ['a', 'b'], 'grow_only': True},
                          data['groups'])
            data = _dump_facts(directory, 'python_lambda', FACT_PYTHON_LAMBDA, syntax='python')
            self.assertEqual(data['groups'], [])

    def test_nonneg_fields(self):
        with tempfile.TemporaryDirectory(prefix='ail-facts-') as directory:
            data = _dump_facts(directory, 'nonneg', FACT_NONNEG_POSITIVE)
            self.assertIn(['R', 'pos'], data['nonneg'])
            for name, source in FACT_NONNEG_INVALID.items():
                with self.subTest(probe=name):
                    data = _dump_facts(directory, 'nonneg_' + name, source)
                    self.assertNotIn(['R', 'pos'], data['nonneg'])


if __name__ == '__main__':
    unittest.main()
