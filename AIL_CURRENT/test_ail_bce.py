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
    ('echo_like_ok', r"""
fn cmp(d: bytes, j: int) -> int {
    let n = len(d);
    let hits = 0;
    let i = 0;
    while i < n {
        let maxm = n - i;
        if maxm > 3 { maxm = 3; }
        let m = 1;
        while m < maxm and d[i + m] == d[j + m] { m += 1; }
        if m > 1 { hits += m; }
        i += 1;
    }
    return hits;
}
fn main() {
    print(cmp(b"abababab", 0));
    print(cmp(b"", 0));
    print(cmp(b"a", 0));
    print(cmp(b"abcdef", 0));
}
"""),
    ('echo_like_offbyone', r"""
fn cmp(d: bytes, j: int) -> int {
    let n = len(d);
    let hits = 0;
    let i = 0;
    while i < n {
        let maxm = n - i + 1;
        if maxm > 3 { maxm = 3; }
        let m = 1;
        while m < maxm and d[i + m] == d[j + m] { m += 1; }
        hits += m;
        i += 1;
    }
    return hits;
}
fn main() { print(cmp(b"aaaaaa", 0)); }
"""),
    ('echo_cap_n', r"""
fn f(d: bytes) -> int {
    let n = len(d);
    let i = 0;
    let s = 0;
    while i < n {
        let maxm = n - i;
        if maxm > 3 { maxm = n; }
        let m = 1;
        while m < maxm and d[i + m] == d[m] { m += 1; }
        s += m;
        i += 1;
    }
    return s;
}
fn main() { print(f(b"")); print(f(b"ab")); }
"""),
    ('induction_zero_step', r"""
fn main() {
    let xs = [5, 7, 11];
    let k = len(xs) - len(xs);
    let i = 0;
    let guard = 0;
    let s = 0;
    while i < len(xs) and guard < 10 {
        s += xs[i];
        i += k;
        guard += 1;
    }
    print(s, i, guard);
}
"""),
    ('induction_unknown_step', r"""
fn make() -> str { return "2"; }
fn main() {
    let xs = [5, 7, 11, 13];
    let k = int(make());
    let i = 0;
    let s = 0;
    while i < len(xs) and i >= 0 {
        s += xs[i];
        i += k;
    }
    print(s, i);
}
"""),
    ('induction_big_text', r"""
fn make() -> str { return "9223372036854775808"; }
fn main() {
    let xs = [1, 2, 3];
    let k = int(make());
    let i = 0;
    while i < len(xs) and i >= 0 { i += k; }
    print(i);
}
"""),
    ('list_get_guard_ok', BOX + r"""
fn get(b: Box, i: int) -> int {
    let n = len(b.v);
    if i >= 0 and i < n { return b.v[i]; }
    return 0;
}
fn main() {
    let b = Box([10, 20, 30], 3);
    print(get(b, 0), get(b, 2), get(b, 3), get(b, -1));
}
"""),
    ('list_get_after_clear', BOX + r"""
fn get(b: Box, i: int) -> int {
    let n = len(b.v);
    if i >= 0 and i < n {
        b.v.clear();
        return b.v[i];
    }
    return 0;
}
fn main() {
    let b = Box([10, 20, 30], 3);
    print(get(b, 2));
}
"""),
    ('list_get_append_fn', BOX + r"""
fn add(b: Box) { b.v.append(42); }
fn get(b: Box, i: int) -> int {
    let n = len(b.v);
    if i >= 0 and i < n { add(b); return b.v[i]; }
    return 0;
}
fn main() {
    let b = Box([1, 2, 3], 3);
    print(get(b, 1));
}
"""),
    ('list_loop_read', BOX + r"""
fn total(b: Box) -> int {
    let s = 0;
    let i = 0;
    while i < len(b.v) { s += b.v[i]; i += 1; }
    return s;
}
fn main() {
    let b = Box([1, 2, 3, 4], 4);
    print(total(b));
}
"""),
    ('entry_emit_guard', r"""
fn emit_all(data: bytes, a: int, b: int) -> void {
    let i = a;
    while i < b {
        print(data[i]);
        i += 1;
        let j = i;
        while j < b {
            print(data[j]);
            j += 1;
        }
    }
}
fn main() {
    let data = b"abc";
    emit_all(data, 0, len(data));
    emit_all(data, len(data), len(data));
    try { emit_all(data, 0, len(data) + 1); } except IndexError { print("hi"); }
    emit_all(data, -1, 3);
    try { emit_all(data, 3, 4); } except IndexError { print("lo"); }
}
"""),
    ('echo_while_guard', r"""
fn run_match(d: bytes, p: int, like: bytes, maxm: int) -> int {
    let m = 0;
    let n = 0;
    while m < maxm and d[p + m] == like[m] {
        n += 1;
        m += 1;
    }
    return n;
}
fn main() {
    let data = b"abcabc";
    let pat = b"abc";
    print(run_match(data, 0, pat, 3));
    print(run_match(data, 3, pat, 3));
    print(run_match(data, -1, pat, 1));
    print(run_match(data, -2, pat, 2));
    try { print(run_match(data, 0, pat, len(data) + 1)); } except IndexError { print("hi"); }
}
"""),
    ('dec_while_guard', r"""
fn scan(d: bytes, a: int, b: int) -> int {
    let i = a + 1;
    let count = 0;
    let s = 0;
    while i < b {
        if count == 3 { break; }
        s += d[i];
        i -= 1;
        count += 1;
    }
    return s;
}
fn main() {
    print(scan(b"abcde", 0, 3));
}
"""),
    ('while_access_before_bound', r"""
fn f(d: bytes, v: int, b: int) -> int {
    let e = b - 1;
    let n = 0;
    while d[v] == 0 and v < e {
        n += 1;
        v += 1;
    }
    return n;
}
fn main() {
    try { print(f(b"abc", 5, 2)); } except IndexError { print("a"); }
    try { print(f(b"\x00\x00\x00", 4, 3)); } except IndexError { print("b"); }
    print(f(b"\x00\x00\x00", 0, 3));
}
"""),
    ('while_bound_reassigned', r"""
fn scan(d: bytes, e: int) -> int {
    let i = 0;
    let s = 0;
    while i < e {
        s += d[i];
        i += 1;
        if i == 1 { e = len(d) + 2; }
    }
    return s;
}
fn main() {
    print(scan(b"abc", 1));
}
"""),
    ('while_list_append', r"""
struct Bag { xs: list[int]; }
fn grow(b: Bag, n: int) -> int {
    let i = 0;
    let s = 0;
    while i < n {
        s += b.xs[i];
        b.xs.append(i);
        i += 1;
    }
    return s;
}
fn main() {
    let b = Bag([10, 20, 30]);
    print(grow(b, 3));
    print(len(b.xs));
}
"""),
    ('while_bound_bigtext', r"""
fn make() -> str { return "9223372036854775808"; }
fn emit_all(data: bytes, a: int, b: int) -> void {
    let i = a;
    while i < b { print(data[i]); i += 1; }
}
fn main() {
    let b = int(make());
    emit_all(b"abc", 0, b);
}
"""),
]

# A list parameter is read-only in this language, so the "list param appended inside the loop"
# shape cannot be written at all: pin the named refusal instead of a program that cannot compile.
LIST_PARAM_APPEND = r"""
fn grow(xs: list[int], n: int) -> int {
    let i = 0;
    while i < n { xs.append(i); i += 1; }
    return len(xs);
}
fn main() { print(grow([1, 2], 2)); }
"""

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
    'induction_big_text': 'OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)',
    'while_bound_bigtext': 'OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)',
}

S3_PROVEN = {
    'echo_like_ok': ('cmp', 1),
    'list_get_guard_ok': ('get', 1),
    'list_loop_read': ('total', 1),
}
S3_UNPROVEN = {
    'echo_like_offbyone': 'cmp',
    'echo_cap_n': 'f',
    'list_get_after_clear': 'get',
    'list_get_append_fn': 'get',
}

S7_ENTRY = {
    'entry_emit_guard': ('emit_all', 1, 2),
}
S7_WHILE = {
    'echo_while_guard': ('run_match', 1),
}
S7_UNVERSIONED = {
    'dec_while_guard': ('scan', 0),
    'while_access_before_bound': ('f', 0),
    'while_bound_reassigned': ('scan', 0),
    'while_list_append': ('grow', 0),
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


    def test_s3_rules_are_visible_in_the_stats(self):
        sources = dict(PROBES)
        with tempfile.TemporaryDirectory(prefix='ail-bce-s3-') as directory:
            for name, (fn, least) in S3_PROVEN.items():
                entries = _ir_stats(directory, name, sources[name])
                found = [e for e in entries if e.get('fn') == fn]
                self.assertTrue(found, '%s: no IR stats for %s' % (name, fn))
                proven = found[-1].get('passes', {}).get('idx_ssa_proven', 0)
                self.assertGreaterEqual(proven, least, '%s: %s' % (name, proven))
            for name, fn in S3_UNPROVEN.items():
                entries = _ir_stats(directory, name, sources[name])
                found = [e for e in entries if e.get('fn') == fn]
                self.assertTrue(found, '%s: no IR stats for %s' % (name, fn))
                proven = found[-1].get('passes', {}).get('idx_ssa_proven', 0)
                self.assertEqual(proven, 0, '%s: %s' % (name, proven))

    def test_s7_while_and_entry_versioning_are_visible_in_the_stats(self):
        sources = dict(PROBES)
        with tempfile.TemporaryDirectory(prefix='ail-bce-s7-') as directory:
            for name, (fn, least_entry, least_idx) in S7_ENTRY.items():
                entries = _ir_stats(directory, name, sources[name])
                found = [e for e in entries if e.get('fn') == fn]
                self.assertTrue(found, '%s: no IR stats for %s' % (name, fn))
                passes = found[-1].get('passes', {})
                self.assertGreaterEqual(passes.get('entry_versioned', 0), least_entry, name)
                self.assertGreaterEqual(passes.get('idx_ssa_proven', 0), least_idx, name)
            for name, (fn, least) in S7_WHILE.items():
                entries = _ir_stats(directory, name, sources[name])
                found = [e for e in entries if e.get('fn') == fn]
                self.assertTrue(found, '%s: no IR stats for %s' % (name, fn))
                versioned = found[-1].get('passes', {}).get('versioned', 0)
                self.assertGreaterEqual(versioned, least, '%s: %s' % (name, versioned))
            for name, (fn, want) in S7_UNVERSIONED.items():
                entries = _ir_stats(directory, name, sources[name])
                found = [e for e in entries if e.get('fn') == fn]
                self.assertTrue(found, '%s: no IR stats for %s' % (name, fn))
                versioned = found[-1].get('passes', {}).get('versioned', 0)
                self.assertEqual(versioned, want, '%s: %s' % (name, versioned))

    def test_list_param_append_is_refused_by_name(self):
        # Only the .ail surface has read-only list parameters; the forced Python surface is a
        # different language surface, so pin the refusal where it exists (default and audit builds
        # compile the same .ail source).
        with tempfile.TemporaryDirectory(prefix='ail-bce-refuse-') as directory:
            for mode in ('default', 'audit'):
                got, err = _build_run(directory, 'list_param_append', LIST_PARAM_APPEND, mode)
                self.assertIsNone(got, '%s: list parameter append compiled' % mode)
                self.assertIn('is a list parameter, which is read-only here', err, mode)


if __name__ == '__main__':
    unittest.main()
