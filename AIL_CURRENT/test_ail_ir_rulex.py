"""IR option A: value semantics for brace-syntax files, Python sharing for def-syntax files
(docs/design/IR_OWNERSHIP_DESIGN_v2.md section 15, python/pkg-v12/ir/ownership.py `resolve_value`).

* A brace-syntax file keeps value semantics until S6: where the sharing analysis would rename, borrow
  or refuse (Rule X), the IR inserts the copy that `ys = xs` means there. The function then enters the
  IR and prints exactly what the legacy build (AIL_IR=0) prints -- double buffers, swaps, alias then
  mutate then read, loops, struct fields.
* Where no write can be seen through the other name, the cheap rule stays (a dead source is a move, a
  harmless alias is a rename): no copy is inserted and the stats say so.
* A def-syntax file follows Python: the IR shares like CPython (no copy); shapes it does not take are
  refused by name by the legacy path (aliasrefuse.py), also tested in test_ail_fuzz_findings.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ail_testenv import ASAN_DETECT_LEAKS

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------------------------
# Brace-syntax programs: AIL_IR=1 must print what AIL_IR=0 prints. The `copies` entry is the number
# of copies the IR inserted in `main` (None: not pinned).
# --------------------------------------------------------------------------------------------

BRACE = {}

# grid_life-ail-2's shape: ga = gb with gb rebuilt and read in the next round
BRACE['double_buffer'] = ('''
fn main() {
    let ga = [1, 0, 1, 0, 1, 1];
    let gb = [0, 0, 0, 0, 0, 0];
    let t = 0;
    for r in range(5) {
        for i in range(6) { gb[i] = (ga[i] + ga[(i + 1) % 6] + r) % 3; }
        ga = gb;
        t = t + ga[0] * 7 + gb[1];
    }
    print(t, ga[0], ga[5], gb[2]);
}
''', 1)

# alias, then mutate through one name, then read the other
BRACE['alias_mutate_read'] = ('''
fn main() {
    let xs = [1, 2, 3];
    let ys = xs;
    ys.append(9);
    ys[0] = 5;
    print(len(xs), xs[0], len(ys), ys[0]);
}
''', 1)

BRACE['alias_mutate_source'] = ('''
fn main() {
    let xs = [1, 2, 3];
    let ys = xs;
    xs[1] = 40;
    xs.append(7);
    print(len(xs), xs[1], len(ys), ys[1]);
}
''', 1)

# a swap through a temporary is three moves, no copy
BRACE['swap'] = ('''
fn main() {
    let a = [1, 2];
    let b = [3, 4, 5];
    let t = a;
    a = b;
    b = t;
    a.append(6);
    print(len(a), a[0], len(b), b[1]);
}
''', 0)

# a swap whose temporary is still read afterwards: the alias has to be a copy
BRACE['swap_keep'] = ('''
fn main() {
    let a = [1, 2];
    let b = [3, 4, 5];
    let t = a;
    a = b;
    b = t;
    a.append(6);
    b.append(7);
    t[0] = 99;
    print(len(a), a[0], len(b), b[0], t[0], len(t));
}
''', None)

BRACE['alias_in_loop'] = ('''
fn main() {
    let xs = [1, 2];
    let ys = xs;
    for i in range(4) {
        print(len(ys), len(xs));
        xs.append(i);
    }
    let zs = xs;
    for i in range(3) {
        zs[i] = zs[i] + len(ys) * 10;
        print(xs[i], zs[i]);
    }
}
''', None)

BRACE['alias_chain'] = ('''
fn main() {
    let a = [1, 2, 3];
    let b = a;
    let c = b;
    c.append(4);
    b[0] = 10;
    print(len(a), a[0], len(b), b[0], len(c), c[0]);
}
''', None)

# harmless aliases (nothing is written, or the source dies): no copy is inserted
BRACE['alias_read_only'] = ('''
fn main() {
    let xs = [1, 2, 3];
    let ys = xs;
    let s = 0;
    for i in range(3) { s = s + ys[i] * xs[i]; }
    print(s, len(xs), len(ys));
}
''', 0)

BRACE['alias_source_dies'] = ('''
fn main() {
    let xs = [1, 2, 3];
    let ys = xs;
    ys.append(4);
    ys[0] = 8;
    print(len(ys), ys[0]);
}
''', 0)

# struct fields: a list stored into a field and written afterwards through the local or the field
BRACE['field_store'] = ('''
struct Box { v: list[int]; w: list[int]; }
fn fill(b: Box, n: int) -> int {
    let xs = [1, 2];
    b.v = xs;
    xs.append(n);
    xs[0] = 50;
    b.v.append(n + 1);
    return len(b.v) * 1000 + b.v[0] * 100 + len(xs) * 10 + xs[0];
}
fn load(b: Box) -> int {
    let ys = b.w;
    ys.append(3);
    ys[0] = 30;
    b.w.append(4);
    return len(ys) * 100 + len(b.w) * 10 + b.w[0];
}
fn main() {
    let b = Box([5, 6], [7]);
    print(fill(b, 3), load(b));
    print(len(b.v), b.v[0], len(b.w), b.w[0]);
}
''', None)

BRACE['field_to_field'] = ('''
struct Pair { a: list[int]; b: list[int]; }
fn copyover(p: Pair) -> int {
    p.a = p.b;
    p.b.append(1);
    p.a[0] = 77;
    return len(p.a) * 100 + len(p.b) * 10 + p.b[0];
}
fn main() {
    let p = Pair([1, 2], [3]);
    print(copyover(p), len(p.a), len(p.b));
}
''', None)

# a swap of two fields of a struct local through a temporary: three moves (each field is rebound before
# anything reads it), no copy (design section 23)
BRACE['field_swap'] = ('''
struct Gr { cur: list[int]; nxt: list[int]; }
fn main() {
    let gr = Gr([1, 2, 3], [4, 5]);
    for r in range(3) {
        for i in range(2) { gr.nxt[i] = gr.cur[i] + r; }
        let tmp = gr.cur; gr.cur = gr.nxt; gr.nxt = tmp;
        print(len(gr.cur), gr.cur[0], len(gr.nxt), gr.nxt[0]);
    }
}
''', 0)

# a local bound to a field list of a struct local and written: legacy emitter, the local is a copy
BRACE['field_to_local_write'] = ('''
struct Gr { cur: list[int]; nxt: list[int]; }
fn main() {
    let gr = Gr([1, 2, 3], [4, 5]);
    let tmp = gr.cur;
    tmp.append(9);
    tmp[0] = 7;
    gr.cur[1] = 8;
    print(len(tmp), tmp[0], tmp[1], len(gr.cur), gr.cur[0], gr.cur[1]);
}
''', 'legacy')

# Python-syntax programs: AIL_IR=1 must print what CPython prints (the IR shares)
DEF = {}

DEF['double_buffer'] = '''
def main() -> None:
    ga: list[int] = [1, 0, 1, 0, 1, 1]
    gb: list[int] = [0, 0, 0, 0, 0, 0]
    t: int = 0
    for r in range(5):
        for i in range(6):
            gb[i] = (ga[i] + ga[(i + 1) % 6] + r) % 3
        ga = gb
        t = t + ga[0] * 7 + gb[1]
    print(t, ga[0], ga[5], gb[2])


main()
'''

DEF['alias_mutate_read'] = '''
def main() -> None:
    xs: list[int] = [1, 2, 3]
    ys: list[int] = xs
    ys.append(9)
    ys[0] = 5
    print(len(xs), xs[0], len(ys), ys[0])


main()
'''

DEF['alias_chain_loop'] = '''
def main() -> None:
    a: list[int] = [1, 2, 3]
    b: list[int] = a
    c: list[int] = b
    c.append(4)
    b[0] = 10
    for i in range(3):
        print(len(a), a[0], len(b), len(c))
        a.append(i)
    print(c[0])


main()
'''

DEF['swap'] = '''
def main() -> None:
    a: list[int] = [1, 2]
    b: list[int] = [3, 4, 5]
    t: list[int] = a
    a = b
    b = t
    a.append(6)
    print(len(a), a[0], len(b), b[1])


main()
'''

DEF['copy_on_purpose'] = '''
def main() -> None:
    ga: list[int] = [1, 0, 1]
    gb: list[int] = [0, 0, 0]
    for r in range(4):
        for i in range(3):
            gb[i] = (ga[i] + ga[(i + 1) % 3] + r) % 3
        ga = gb.copy()
        gb[0] = gb[0] + 1
    print(ga[0], gb[0], ga[1], gb[1])


main()
'''


def have_cc():
    return subprocess.run(['which', 'gcc'], capture_output=True).returncode == 0


def compile_run(directory, name, text, tag, syntax, env_extra):
    source = Path(directory, name + '.ail')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory, '%s.%s' % (name, tag))
    stats = Path(directory, '%s.%s.stats' % (name, tag))
    env = dict(os.environ, AIL_IR_STATS=str(stats), **env_extra)
    env.pop('AIL_IR_EXC', None)
    env.update(env_extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', syntax, '-o', exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=600, env=env)
    entries = [json.loads(l) for l in stats.read_text().splitlines()] if stats.exists() else []
    ran = None
    if built.returncode == 0:
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return built, ran, entries


class BraceValueSemantics(unittest.TestCase):
    def check_program(self, name, text, copies):
        with tempfile.TemporaryDirectory() as directory:
            b0, r0, _ = compile_run(directory, name, text, 'legacy', 'ail', {'AIL_IR': '0'})
            self.assertEqual(b0.returncode, 0, b0.stdout + b0.stderr)
            for tag, extra in (('ir', {'AIL_IR': 'verify'}), ('irx', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                b1, r1, entries = compile_run(directory, name, text, tag, 'ail', extra)
                self.assertEqual(b1.returncode, 0, b1.stdout + b1.stderr)
                self.assertEqual((r1.returncode, r1.stdout), (r0.returncode, r0.stdout), r1.stderr)
                taken = {e['fn'] for e in entries if e['path'] == 'ir'}
                if copies == 'legacy':
                    # a field list of a struct local: left to the legacy emitter (value semantics there)
                    self.assertNotIn('main', taken)
                    continue
                self.assertIn('main', taken, [(e['fn'], e['reason']) for e in entries])
                if copies is not None:
                    got = sum((e.get('sharing') or {}).get('copies_inserted', 0) for e in entries
                              if e['fn'] == 'main')
                    self.assertEqual(got, copies, [e.get('sharing') for e in entries])

    def test_brace_programs_equal_the_legacy_build(self):
        for name, (text, copies) in BRACE.items():
            with self.subTest(name):
                self.check_program(name, text, copies)

    def test_copies_are_sanitizer_clean(self):
        # ASan + UBSan + LSan on the IR build: the copy keeps the destination's buffer when it fits
        # (double buffer), and frees nothing twice or not at all
        if not have_cc():
            self.skipTest('no gcc')
        env_run = dict(os.environ, ASAN_OPTIONS=ASAN_DETECT_LEAKS + ':abort_on_error=0',
                       UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
        for name in ('double_buffer', 'alias_mutate_read', 'alias_in_loop', 'swap_keep', 'field_store',
                     'field_to_field'):
            with self.subTest(name):
                text = BRACE[name][0]
                with tempfile.TemporaryDirectory() as directory:
                    source = Path(directory, name + '.ail')
                    source.write_text(text, encoding='utf-8')
                    built = subprocess.run(
                        [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'ail',
                         '-o', name + '.bin', '--debug-dir', name + '.d'], cwd=directory, capture_output=True,
                        text=True, timeout=600, env=dict(os.environ, AIL_IR='verify'))
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    plain = subprocess.run([str(Path(directory, name + '.bin'))], capture_output=True, text=True)
                    san = Path(directory, name + '.san')
                    cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                                         '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer', '-pthread',
                                         str(Path(directory, name + '.d', 'program.c')), '-lm', '-o', str(san)],
                                        capture_output=True, text=True)
                    self.assertEqual(cc.returncode, 0, cc.stderr[-1500:])
                    r = subprocess.run([str(san)], capture_output=True, text=True, timeout=120, env=env_run)
                    self.assertEqual((r.returncode, r.stdout), (0, plain.stdout), r.stderr[-1500:])
                    self.assertNotIn('Sanitizer', r.stderr)
                    self.assertNotIn('runtime error', r.stderr)

    def test_the_copy_is_reported_as_w_alias(self):
        text, _ = BRACE['double_buffer']
        with tempfile.TemporaryDirectory() as directory:
            built, ran, entries = compile_run(directory, 'wal', text, 'ir', 'ail', {'AIL_IR': '1'})
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            main = [e for e in entries if e['fn'] == 'main'][0]
            self.assertEqual(main['path'], 'ir', main['reason'])
            notes = main.get('walias') or []
            self.assertTrue(any(n['rule'] == 'copy' and n['differs'] and n['dst'] == 'ga' for n in notes), notes)

    def test_double_buffer_without_the_copy_would_be_wrong(self):
        # the same text as a def-syntax file shares (CPython's meaning) and prints something else: the
        # brace/def split is the whole point of option A
        text, _ = BRACE['double_buffer']
        with tempfile.TemporaryDirectory() as directory:
            _, brace_run, _ = compile_run(directory, 'db_brace', text, 'ir', 'ail', {'AIL_IR': '1'})
            _, def_run, _ = compile_run(directory, 'db_def', DEF['double_buffer'], 'ir', 'python', {'AIL_IR': '1'})
            self.assertNotEqual(brace_run.stdout, def_run.stdout)


class DefSharesLikeCPython(unittest.TestCase):
    def test_def_programs_equal_cpython_under_the_ir(self):
        for name, text in DEF.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, entries = compile_run(directory, name, text, 'ir', 'python', {'AIL_IR': 'verify'})
                    cpython = subprocess.run([sys.executable, str(Path(directory, name + '.ail'))],
                                             capture_output=True, text=True, timeout=60)
                    if name == 'copy_on_purpose':
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    if built.returncode == 0:
                        self.assertEqual((ran.returncode, ran.stdout), (cpython.returncode, cpython.stdout), ran.stderr)
                        sharing = [e.get('sharing') or {} for e in entries if e['fn'] == 'main']
                        self.assertTrue(all(s.get('copies_inserted', 0) == 0 for s in sharing), sharing)
                    else:
                        # not in the IR: the legacy path refuses by name, it never prints a different answer
                        self.assertIn('makes a second name for the same container', built.stdout + built.stderr)

    def test_def_programs_the_ir_takes_are_pinned(self):
        taken = {}
        for name in ('double_buffer', 'alias_mutate_read', 'alias_chain_loop', 'swap'):
            with tempfile.TemporaryDirectory() as directory:
                built, _, entries = compile_run(directory, name, DEF[name], 'ir', 'python', {'AIL_IR': '1'})
                taken[name] = built.returncode == 0
        self.assertTrue(taken['alias_mutate_read'], taken)
        self.assertTrue(taken['swap'], taken)

    def test_legacy_refuses_by_name_when_the_ir_is_off(self):
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = compile_run(directory, 'off', DEF['alias_mutate_read'], 'legacy', 'python',
                                      {'AIL_IR': '0', 'AIL_NO_GENERAL': '1'})
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn('makes a second name for the same container', built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
