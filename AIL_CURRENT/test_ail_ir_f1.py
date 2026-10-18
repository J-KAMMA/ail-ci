"""IR stage F1: list[str] struct fields held packed (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 21,
python/pkg-v12/cruntime.py PSLIST and SFIELDMUT).

A `list[str]` field of a struct was an `ail_slist` block: a 24-byte `ail_str` per element, the text behind it, repacked
(every string copied) whenever it grew, and copied string by string again at every whole-field store. It is now an
`ail_pslist`: in the dense mode all the text back to back and an 8-byte end offset per element (an append is a copy of its
text and one store; a whole-field store `o.f = xs` is two passes over `xs` and two allocations); any change that needs
per-element ranges (an element store, a delete in the middle, a slice, a reverse or a sort, or a read-only parameter
lent the field) turns the field into the wide mode, which is the legacy block with the legacy code. What this module pins:

* a long random operation stream over a struct with a `list[str]` field (appends, bulk growth, whole-field rebuilds from a
  local, pops, element stores, whole stores of a new list, copies, sort, reverse, `count`, `in`, a read-only function
  parameter, `extend`, `clear`, slices, negative indexes, IndexError, non-ASCII strings) prints what CPython prints, in the
  legacy build and both IR modes, and is clean under ASan+UBSan+LSan;
* the runtime's packed list against a plain model under a deterministic operation sequence in C, with values that view the
  field's own text (aliasing appends across a growth, a store of its own views), under the sanitizers;
* the generated C holds the field as an `ail_pslist` and stores a local list into it with one `ail_pslist_assign`;
* programs without a list[str] field get the same C as before (the part is not included).
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]

from ir import ir as I                       # noqa: E402
from ir import effects as E                  # noqa: E402
from ir import emit_c, text, verify          # noqa: E402
from test_ail_ir_s3 import Built, compile_program, cpython_run, run, HAVE_CC     # noqa: E402

PLIST_FN = '''func @pl(%t: obj<T>, %i: i64, %s: strv) -> (i64) attrs {linkage = "extern", names = ["t", "i", "s"], sym = "pl"} {
  %p = field.plist %t {cls = "T", name = "nm"} : obj<plist<strv>>
  %n = plist.len %p : i64
  %v = plist.get %p, %i {mode = "ck"} : strv
  %h = plist.has %p, %s : i1
  %e = rt %v, %s {callee = "str_eq"} : i1
  %a = zext %h : i64
  %b = zext %e : i64
  %c = add %a, %b {mode = "ck"} : i64
  %d = add %c, %n {mode = "ck"} : i64
  return %d
}
'''


def fn_of(src):
    fn = text.parse_function(src)
    program = I.Program({fn.sym: fn})
    E.summarize_program(program)
    return fn, program


class OpTests(unittest.TestCase):
    def errors(self, src):
        fn = text.parse_function(src)
        return verify.verify_function(fn, I.Program({fn.sym: fn}))

    def test_round_trip_and_verify(self):
        fn, program = fn_of(PLIST_FN)
        verify.check(fn, program)
        printed = text.print_function(fn)
        self.assertEqual(text.print_function(text.parse_function(printed)), printed)

    def test_malformed_uses_are_rejected_by_name(self):
        for src, fragment in (
                (PLIST_FN.replace('%p = field.plist %t', '%p = field.plist %i'), 'field.plist of a non-object'),
                (PLIST_FN.replace('plist.len %p', 'plist.len %i'), 'plist.len takes a plist'),
                (PLIST_FN.replace('plist.get %p, %i', 'plist.get %p, %s'), 'plist.get takes (plist, i64)'),
                (PLIST_FN.replace('plist.has %p, %s', 'plist.has %p, %i'), 'plist.has takes (plist, str)'),
                (PLIST_FN.replace('{mode = "ck"} : strv', '{mode = "maybe"} : strv'), 'index mode must be one of')):
            errs = self.errors(src)
            self.assertTrue(any(fragment in e for e in errs), (fragment, errs))

    def test_the_c_reads_the_packed_field(self):
        fn, program = fn_of(PLIST_FN)
        _, c, needs = emit_c.emit_function(fn)
        self.assertIn('(&(v_t)->f_nm)', c)
        self.assertIn('ail_pslist_get(', c)
        self.assertIn('ail_pslist_has(', c)
        self.assertLessEqual({'SLIST', 'PSLIST'}, needs['parts'])

    def test_the_effects_name_the_field_and_the_read_can_raise(self):
        fn, program = fn_of(PLIST_FN)
        get = [i for i in I.walk(fn.body) if i.op == 'plist.get'][0]
        eff = E.instr_effects(get, fn, program)
        self.assertIn('Field(T,nm)' and 'Elem(Field(T,nm))', eff.reads)
        self.assertIn(E.INDEX, eff.raises)

PROGRAM = '''import sys


class Rng:
    def __init__(self, s: int):
        self.s = s

    def next(self, m: int) -> int:
        self.s = (self.s * 1103515245 + 12345) % 2147483648
        return (self.s >> 8) % m


class T:
    def __init__(self, nm: list[str], w: list[int]):
        self.nm = nm
        self.w = w


def word(r: Rng, k: int) -> str:
    n = r.next(k)
    kind = r.next(9)
    parts: list[str] = []
    for i in range(n):
        if kind == 0:
            parts.append(chr(233))
        elif kind == 1:
            parts.append(chr(26085))
        elif kind == 2:
            parts.append(chr(128512))
        else:
            parts.append(chr(97 + r.next(26)))
    return "".join(parts)


def total_len(xs: list[str]) -> int:
    s = 0
    for x in xs:
        s += len(x)
    return s + len(xs)


def first_or(xs: list[str], d: str) -> str:
    if len(xs) > 0:
        return xs[0]
    return d


def rebuild(t: T, r: Rng) -> None:
    nm: list[str] = []
    for i in range(len(t.nm)):
        if r.next(4) != 0:
            nm.append(t.nm[i])
    t.nm = nm


def reverse_copy(t: T) -> None:
    nm: list[str] = []
    i = len(t.nm) - 1
    while i >= 0:
        nm.append(t.nm[i])
        i -= 1
    t.nm = nm


def grow(t: T, r: Rng, k: int) -> None:
    for i in range(k):
        t.nm.append(word(r, 12))
        t.w.append(i)


def dump(t: T, tag: str) -> None:
    print(tag, len(t.nm), ",".join(t.nm), total_len(t.nm), first_or(t.nm, "-"))


def main() -> int:
    r = Rng(int(sys.argv[1]))
    t = T([], [])
    kept: list[str] = []
    errors = 0
    for step in range(int(sys.argv[2])):
        op = r.next(24)
        n = len(t.nm)
        if op < 6:
            t.nm.append(word(r, 10))
        elif op == 6:
            grow(t, r, 1 + r.next(300))
        elif op == 7:
            rebuild(t, r)
        elif op == 8:
            reverse_copy(t)
        elif op == 9 and n > 0:
            kept.append(t.nm.pop())
        elif op == 10 and n > 0:
            del t.nm[-1]
        elif op == 11 and n > 0:
            t.nm[r.next(n)] = word(r, 30)
        elif op == 12:
            t.nm = [word(r, 5), "", word(r, 5)]
        elif op == 13:
            c = t.nm.copy()
            c.append("copy")
            kept.append(c[-1])
            if len(c) > 1:
                kept.append(c[0])
        elif op == 14:
            kept.append(str(total_len(t.nm)))
        elif op == 15 and n > 1:
            t.nm.sort()
        elif op == 16 and n > 1:
            t.nm.reverse()
        elif op == 17 and n > 0:
            w = t.nm[r.next(n)]
            kept.append(str(t.nm.count(w)))
            kept.append("in" if w in t.nm else "out")
            kept.append("in" if (w + "!") in t.nm else "out")
        elif op == 18 and n > 0:
            t.nm.append(t.nm[r.next(n)])
        elif op == 19:
            try:
                kept.append(t.nm[n + r.next(3)])
            except IndexError:
                errors += 1
        elif op == 20 and n > 0:
            kept.append(t.nm[-1 - r.next(n)])
        elif op == 21:
            t.nm.extend([word(r, 4), "", word(r, 40)])
        elif op == 22 and n > 70:
            t.nm.clear()
        elif op == 23 and n > 60:
            t.nm = t.nm[r.next(30):]
        if step % 41 == 0:
            dump(t, "step %d" % step)
        if len(t.nm) > 3000:
            t.nm = t.nm[1500:]
    dump(t, "final")
    print("kept", len(kept), "|".join(kept))
    print("errors", errors)
    return 0


sys.exit(main())
'''

# a field that is only appended to and replaced as a whole: it never leaves the dense mode
DENSE = '''import sys


class T:
    def __init__(self, nm: list[str], w: list[int]):
        self.nm = nm
        self.w = w


def build(t: T, n: int) -> None:
    for i in range(n):
        t.nm.append("n" + str(i))
        t.w.append(i)


def shuffle(t: T, step: int) -> None:
    nm: list[str] = []
    n = len(t.nm)
    for i in range(n):
        nm.append(t.nm[(i * step) % n])
    t.nm = nm


def main() -> int:
    t = T([], [])
    n = int(sys.argv[1])
    build(t, n)
    for round in range(6):
        shuffle(t, 7 + round * 2)
    acc = 0
    for i in range(len(t.nm)):
        acc = (acc * 31 + len(t.nm[i]) + ord(t.nm[i][1])) % 1000003
    print(len(t.nm), acc, t.nm[0], t.nm[-1])
    return 0


sys.exit(main())
'''

READS = '''import sys


class T:
    def __init__(self, nm: list[str], w: list[int]):
        self.nm = nm
        self.w = w


def count_eq(t: T, name: str) -> int:
    c = 0
    for i in range(len(t.nm)):
        if t.nm[i] == name:
            c += 1
    return c


def first_index(t: T, name: str) -> int:
    n = len(t.nm)
    for i in range(n):
        if t.nm[i] == name:
            return i
    return -1


def has(t: T, name: str) -> int:
    if name in t.nm:
        return 1
    if name + "x" not in t.nm:
        return 2
    return 0


def lens(t: T) -> int:
    s = 0
    for i in range(len(t.nm)):
        s += len(t.nm[i]) + t.w[i]
    return s


def pick(t: T, i: int) -> str:
    return t.nm[i]


def main() -> int:
    t = T(["a", "bb", "ccc", "bb"], [1, 2, 3, 4])
    print(count_eq(t, "bb"), first_index(t, "ccc"), has(t, "a"), has(t, "q"), lens(t), pick(t, 2), pick(t, -1))
    t.nm.append("dddd")
    t.w.append(5)
    print(count_eq(t, "dddd"), first_index(t, "zz"), has(t, "a"), lens(t), len(t.nm))
    try:
        print(pick(t, 9))
    except IndexError:
        print("index")
    return 0


sys.exit(main())
'''

VIEWS = '''import sys


class T:
    def __init__(self, nm: list[str], w: list[int]):
        self.nm = nm
        self.w = w


def bump(t: T) -> str:
    t.nm[0] = "zzzz-longer-than-before"
    t.nm.reverse()
    return "!"


def label(t: T, i: int) -> str:
    return t.nm[i] + ":" + str(t.w[i]) + "/" + str(len(t.nm))


def label_after_call(t: T, i: int) -> str:
    return t.nm[i] + bump(t)


def order(t: T) -> int:
    ch: list[int] = []
    for i in range(len(t.nm)):
        ch.append(i)
    ch.sort(key=lambda i: (-t.w[i], t.nm[i]))
    acc = 0
    for k in ch:
        acc = acc * 7 + k
    return acc


def main() -> int:
    t = T(["pear", "apple", "fig", "apple", "kiwi"], [2, 3, 2, 3, 1])
    for i in range(len(t.nm)):
        print(label(t, i))
    print(order(t))
    print(label_after_call(t, 1), t.nm[0], len(t.nm))
    print(order(t))
    return 0


sys.exit(main())
'''


PLAIN = '''import sys


def main() -> int:
    xs: list[str] = []
    for i in range(int(sys.argv[1])):
        xs.append("k" + str(i))
    print(len(xs), ",".join(xs))
    return 0


sys.exit(main())
'''

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
%(runtime)s
static uint64_t rng = 88172645463325252ULL;
static uint64_t rnd(uint64_t m) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng %% m; }
/* the model: independent copies, one malloc each */
static ail_slist model;
static void model_push(ail_str s) {
    uint8_t *q = malloc(s.n ? (size_t)s.n : 1);
    if (s.n) memcpy(q, s.p, (size_t)s.n);
    ail_slist_push(&model, (ail_str){q, s.n, s.bytes});
}
static void model_free_elem(int64_t i) { free((void *)model.p[i].p); }
static ail_str word(char *buf, int k) {
    int n = (int)rnd((uint64_t)k);
    int nonascii = rnd(7) == 0;
    int o = 0;
    for (int i = 0; i < n; i++) {
        if (nonascii && rnd(3) == 0) { buf[o++] = (char)0xC3; buf[o++] = (char)0xA9; }
        else buf[o++] = (char)('a' + rnd(26));
    }
    return (ail_str){(const uint8_t *)buf, o, !nonascii};
}
static int same(const ail_pslist *L) {
    if (L->n != model.n) return 0;
    for (int64_t i = 0; i < L->n; i++) {
        ail_str a = ail_pslist_get(L, i), b = model.p[i];
        if (a.n != b.n || (a.n && memcmp(a.p, b.p, (size_t)a.n))) return 0;
    }
    return 1;
}
int main(void) {
    ail_pslist L = {0};
    char buf[256];
    ail_sarena A = {0};
    for (int step = 0; step < 30000; step++) {
        int op = (int)rnd(20);
        int64_t n = L.n;
        if (op < 8) {                                   /* append a new word */
            ail_str w = word(buf, 40);
            ail_sfield_append(&L, w); model_push(w);
        } else if (op == 8 && n > 0) {                  /* append a view of the field's own element: growth must not break it */
            int64_t i = (int64_t)rnd((uint64_t)n);
            ail_sfield_append(&L, ail_pslist_get(&L, i)); model_push(model.p[i]);
        } else if (op == 9 && n > 0) {
            int64_t i = (int64_t)rnd((uint64_t)n);
            ail_str w = word(buf, 60);
            ail_sfield_set(&L, i, w);
            model_free_elem(i);
            uint8_t *q = malloc(w.n ? (size_t)w.n : 1); if (w.n) memcpy(q, w.p, (size_t)w.n);
            model.p[i] = (ail_str){q, w.n, w.bytes};
        } else if (op == 10 && n > 0) {                 /* pop the last (dense stays dense) or another */
            int64_t i = rnd(2) ? -1 : (int64_t)rnd((uint64_t)n);
            ail_str v = ail_sfield_pop(&L, i);
            int64_t j = i < 0 ? i + n : i;
            if (v.n != model.p[j].n || (v.n && memcmp(v.p, model.p[j].p, (size_t)v.n))) { puts("pop differs"); return 1; }
            free((void *)v.p);
            model_free_elem(j);
            for (int64_t k = j; k + 1 < n; k++) model.p[k] = model.p[k + 1];
            model.n--;
        } else if (op == 11 && n > 0) {
            int64_t i = rnd(2) ? -1 : (int64_t)rnd((uint64_t)n);
            ail_sfield_delete(&L, i);
            int64_t j = i < 0 ? i + n : i;
            model_free_elem(j);
            for (int64_t k = j; k + 1 < n; k++) model.p[k] = model.p[k + 1];
            model.n--;
        } else if (op == 12) {                          /* a whole store built from the field's own views */
            ail_slist V = {0};
            ail_slist next = {0};
            for (int64_t i = 0; i < n; i++) if (rnd(4) != 0) {
                ail_slist_push(&V, ail_pslist_get(&L, i));
                uint8_t *q = malloc(model.p[i].n ? (size_t)model.p[i].n : 1);
                if (model.p[i].n) memcpy(q, model.p[i].p, (size_t)model.p[i].n);
                ail_slist_push(&next, (ail_str){q, model.p[i].n, model.p[i].bytes});
            }
            ail_pslist_assign(&L, V);
            ail_slist_free(&V);
            for (int64_t i = 0; i < model.n; i++) model_free_elem(i);
            ail_slist_free(&model);
            model = next;
        } else if (op == 13) {                          /* extend from an independent list */
            ail_slist V = {0};
            for (int k = (int)rnd(5); k > 0; k--) { ail_str w = word(buf, 20); ail_str c = ail_str_return_owned(w); ail_slist_push(&V, c); model_push(w); }
            ail_sfield_extend(&L, &V);
            for (int64_t i = 0; i < V.n; i++) free((void *)V.p[i].p);
            ail_slist_free(&V);
        } else if (op == 14 && n > 1) {
            ail_sfield_reverse(&L);
            ail_slist_reverse(&model);
        } else if (op == 15 && n > 1) {
            ail_sfield_sort(&L);
            ail_slist_sort(&model);
        } else if (op == 16) {                          /* a snapshot is independent of the field */
            ail_slist S = ail_slist_snapshot(&A, L);
            if (S.n != model.n) { puts("snapshot length"); return 1; }
            ail_sfield_append(&L, (ail_str){(const uint8_t *)"z", 1, 1}); model_push((ail_str){(const uint8_t *)"z", 1, 1});
            for (int64_t i = 0; i < S.n; i++)
                if (S.p[i].n != model.p[i].n || (S.p[i].n && memcmp(S.p[i].p, model.p[i].p, (size_t)S.p[i].n))) { puts("snapshot differs"); return 1; }
            ail_slist_free(&S);
            ail_sarena_free(&A);
        } else if (op == 17 && n > 0) {
            ail_str w = ail_pslist_get(&L, (int64_t)rnd((uint64_t)n));
            int64_t c = 0;
            for (int64_t i = 0; i < model.n; i++) c += ail_str_eq(model.p[i], w) != 0;
            if (ail_pslist_count(&L, w) != c || !ail_pslist_has(&L, w)) { puts("count/has"); return 1; }
        } else if (op == 18 && n > 40) {
            ail_sfield_clear(&L);
            for (int64_t i = 0; i < model.n; i++) model_free_elem(i);
            model.n = 0;
        } else if (op == 19 && n > 2) {                 /* a read-only parameter lent the field */
            ail_slist B = ail_pslist_borrow(&L);
            if (B.n != model.n) { puts("borrow length"); return 1; }
        }
        if (!same(&L)) { printf("differs after step %%d op %%d\n", step, op); return 1; }
    }
    for (int64_t i = 0; i < model.n; i++) model_free_elem(i);
    ail_slist_free(&model);
    ail_pslist_free(&L);
    puts("ok");
    return 0;
}
'''


def cc_san(src, exe):
    return subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                           '-fno-omit-frame-pointer', '-pthread', '-Wall', '-Wno-unused-function', '-Werror=incompatible-pointer-types',
                           str(src), '-lm', '-o', str(exe)], capture_output=True, text=True)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class FieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-f1-')
        cls.built = Built(cls.dir.name, 'f1', PROGRAM, debug=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_operation_streams_match_cpython_in_every_mode(self):
        for seed, steps in ((1, 2500), (2, 2500), (3, 2500), (4, 4000), (11, 1200), (2026, 3000)):
            expected = cpython_run(self.dir.name, 'f1_cpython', PROGRAM, (seed, steps))
            self.assertEqual(expected[0], 0, expected[2])
            self.assertIn('final', expected[1])
            for tag, exe in self.built.exe.items():
                got = run(exe, (seed, steps))
                self.assertEqual(got[0], 0, (tag, seed, got[2]))
                self.assertEqual(got[1], expected[1], (tag, seed))

    def test_the_field_is_packed_and_stored_whole(self):
        c = Path(self.dir.name, 'f1.legacy.d', 'program.c').read_text()
        self.assertRegex(c, r'ail_pslist f_nm;')
        self.assertIn('ail_pslist_assign(slot, value)', c)
        self.assertIn('ail_obj_field_slist(&', c)
        self.assertNotIn('ail_slist f_nm', c)
        self.assertNotIn('ail_slist_return_owned(value)', c.split('static void ail_obj_field_slist')[1].split('}')[0])

    def test_sanitizers_report_nothing(self):
        for tag in ('legacy', 'ir'):
            san = Path(self.dir.name, 'f1.%s.san' % tag)
            cc = cc_san(Path(self.dir.name, 'f1.%s.d' % tag, 'program.c'), san)
            self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
            for seed in (1, 2, 3):
                r = subprocess.run([str(san), str(seed), '2500'], capture_output=True, timeout=300,
                                   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                                            UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1'))
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-800:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)
                expected = cpython_run(self.dir.name, 'f1_cpython', PROGRAM, (seed, 2500))
                self.assertEqual(r.stdout.decode(), expected[1])


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class RuntimeTests(unittest.TestCase):
    def test_the_packed_list_agrees_with_a_plain_model_under_the_sanitizers(self):
        import cruntime
        runtime = cruntime.emit({'SLIST', 'PSLIST', 'SFIELDMUT', 'DIE'})
        with tempfile.TemporaryDirectory(prefix='ail-f1c-') as tmp:
            src = Path(tmp, 'h.c')
            src.write_text(HARNESS % {'runtime': runtime})
            exe = Path(tmp, 'h')
            cc = cc_san(src, exe)
            self.assertEqual(cc.returncode, 0, cc.stderr[-3000:])
            r = subprocess.run([str(exe)], capture_output=True, timeout=300,
                               env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0',
                                        UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1'))
            self.assertEqual(r.stdout.decode(), 'ok\n', r.stderr.decode(errors='replace')[-1500:])
            self.assertEqual(r.returncode, 0, r.stderr.decode(errors='replace')[-1500:])


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ReadTests(unittest.TestCase):
    def test_reads_of_the_field_enter_the_ir_and_agree_with_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-f1r-') as tmp:
            built = Built(tmp, 'reads', READS, debug=True)
            self.assertLessEqual({'count_eq', 'first_index', 'has', 'lens', 'pick'}, built.ir['ir'])
            self.assertNotIn('count_eq', built.ir['legacy'])
            expected = cpython_run(tmp, 'reads_cpython', READS)
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in built.exe.items():
                got = run(exe)
                self.assertEqual(got[:2], expected[:2], tag)
            c = Path(tmp, 'reads.ir.d', 'program.c').read_text()

            def body(name):
                m = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, c)
                return c[m.end():c.index('\n}\n', m.end())]
            # a comparison is done with the element before anything can change the field: a view, no copy
            self.assertIn('ail_pslist_get(', body('count_eq'))
            self.assertNotIn('ail_str_adopt', body('count_eq'))
            self.assertNotIn('ail_str_adopt', body('first_index'))
            # an element that outlives the read is copied into the arena, as the legacy build copies it
            self.assertIn('ail_str_adopt', body('pick'))

    def test_a_bad_index_fails_like_the_legacy_build(self):
        src = READS.replace('print(pick(t, 9))', 'print(pick(t, 9) + "!")')
        with tempfile.TemporaryDirectory(prefix='ail-f1r-') as tmp:
            built = Built(tmp, 'reads2', src)
            outs = {tag: run(exe) for tag, exe in built.exe.items()}
            self.assertEqual(len({o[:2] for o in outs.values()}), 1, outs)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ViewTests(unittest.TestCase):
    def test_chain_parts_and_sort_key_columns_read_the_field_in_place(self):
        with tempfile.TemporaryDirectory(prefix='ail-f1v-') as tmp:
            built = Built(tmp, 'views', VIEWS, debug=True)
            self.assertLessEqual({'label', 'order'}, built.ir['ir'])
            expected = cpython_run(tmp, 'views_cpython', VIEWS)
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in built.exe.items():
                self.assertEqual(run(exe)[:2], expected[:2], tag)
            c = Path(tmp, 'views.ir.d', 'program.c').read_text()

            def body(name):
                m = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, c)
                return c[m.end():c.index('\n}\n', m.end())]
            # a `+` chain copies every part at once and runs no code that could change the field: a view, no copy
            self.assertIn('ail_pslist_get(', body('label'))
            self.assertNotIn("ail_str_adopt", body("label"))
            # the sort key column is read by the permutation sort only: views
            self.assertIn('ail_pslist_get(', body('order'))
            self.assertNotIn("ail_str_adopt", body("order"))


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class DenseTests(unittest.TestCase):
    def test_an_appended_and_rebuilt_field_stays_dense_and_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-f1d-') as tmp:
            built = Built(tmp, 'dense', DENSE, debug=True)
            for n in (1, 2, 9, 10, 1000, 70001):
                expected = cpython_run(tmp, 'dense_cpython', DENSE, (n,))
                for tag, exe in built.exe.items():
                    self.assertEqual(run(exe, (n,))[1], expected[1], (tag, n))
            c = Path(tmp, 'dense.legacy.d', 'program.c').read_text()
            self.assertIn('ail_pslist_assign(slot, value)', c)
            self.assertIn('ail_obj_field_slist(&', c)
            self.assertIn('ail_sfield_append(&(v_t)->f_nm', c)

    def test_a_program_without_a_string_field_does_not_include_the_part(self):
        with tempfile.TemporaryDirectory(prefix='ail-f1p-') as tmp:
            built = Built(tmp, 'plain', PLAIN, debug=True)
            c = Path(tmp, 'plain.legacy.d', 'program.c').read_text()
            self.assertNotIn('ail_pslist', c)
            expected = cpython_run(tmp, 'plain_cpython', PLAIN, (50,))
            self.assertEqual(run(built.exe['legacy'], (50,))[1], expected[1])


if __name__ == '__main__':
    unittest.main()
