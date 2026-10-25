# -*- coding: utf-8 -*-
"""The tagged small-int runtime `ail_tint` (B2a), checked operation by operation against CPython.

The C harness is the real runtime (`cruntime.OBJ2`, with tint.py inserted beside bigint_obj.py)
followed by a `main` that builds the boundary values through the boxed int parser, converts
them with `ail_tint_from_obj`, and prints every operation's result.  The test compares those
lines with CPython's results for the same values.

Left shifts whose result has millions of bits cannot be printed.  For `2**31` the main harness
prints the bit length and checks `(a << n) >> n == a`; larger counts are run one case per
process, because the existing bigint shift stops the process with MemoryError once the count
exceeds 2**34.  Every `lshift` pair is therefore exercised: none is skipped by a private
cutoff or by a test-side `b > 100` rule.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

VALUES = [
    0,
    1, -1,
    2 ** 31, -(2 ** 31),
    2 ** 62, -(2 ** 62),
    2 ** 63 - 1, -(2 ** 63 - 1),
    -2 ** 63,
    2 ** 64 + 5,
    -2 ** 64 + 5,
    -(2 ** 64 + 5),
]

SHIFTS = [
    -70, -65, -64, -63, -1, 0, 1, 31, 62, 63, 64, 65, 70, 2 ** 31, 2 ** 63 - 1,
]

FROM64 = [
    -(2 ** 63), -(2 ** 63) + 1, -1, 0, 1, 2 ** 63 - 2, 2 ** 63 - 1,
]

OPERATIONS = ("add", "sub", "mul", "floordiv", "mod", "eq", "lt", "le")

# Results up to this many bits are printed in decimal.  A 2**31 shift is still checked in the
# main harness, but only by bit length and round trip; bigger counts are separate processes.
SMALL_SHIFT = 100
FEASIBLE_SHIFT = 2 ** 31
HUGE_SHIFTS = sorted({n for n in VALUES + SHIFTS if n > SMALL_SHIFT})


def _c_array(vs, name):
    digs = ",\n    ".join('"%d"' % abs(v) for v in vs)
    negs = ", ".join("1" if v < 0 else "0" for v in vs)
    return ('static const char *%s_dig[%d] = {\n    %s\n};\n'
            'static const int %s_neg[%d] = { %s };\n' % (name, len(vs), digs, name, len(vs), negs))


def _shift_expect(a, n):
    if n < 0:
        return "E"
    if a == 0:
        return "0"
    if n <= SMALL_SHIFT:
        return str(a << n)
    return None


def _huge_expect(a, n):
    if a == 0:
        return "zero"
    if n <= FEASIBLE_SHIFT:
        return "OK %d 1 %d" % (a.bit_length() + n, (a > 0) - (a < 0))
    if n <= 2 ** 63 - 1:
        return "MEMORY"
    # Pre-existing: the boxed runtime calls this an OverflowError where CPython allocates
    # until the allocator reports MemoryError.  Not introduced by ail_tint.
    return "ERR OverflowError"


def _expected():
    out = []
    for i, v in enumerate(VALUES):
        out.append("i64 %d %d %d" % (i, 1 if -(2 ** 63) <= v <= 2 ** 63 - 1 else 0, v)
                   if -(2 ** 63) <= v <= 2 ** 63 - 1 else "i64 %d 0" % i)
    for i, v in enumerate(VALUES):
        out.append("str %d %d" % (i, v))
        out.append("repr %d %d" % (i, v))
    for v in FROM64:
        out.append("from64 %d %d" % (v, v))
    out[:0] = [
        "err floordiv ZeroDivisionError",
        "err mod ZeroDivisionError",
        "err lshift ValueError",
        "err rshift ValueError",
    ]
    for i, a in enumerate(VALUES):
        for j, b in enumerate(VALUES):
            for name in OPERATIONS:
                if name == "add":
                    out.append("add %d %d %d" % (i, j, a + b))
                elif name == "sub":
                    out.append("sub %d %d %d" % (i, j, a - b))
                elif name == "mul":
                    out.append("mul %d %d %d" % (i, j, a * b))
                elif name == "floordiv":
                    out.append("floordiv %d %d %s" % (i, j, "E" if b == 0 else a // b))
                elif name == "mod":
                    out.append("mod %d %d %s" % (i, j, "E" if b == 0 else a % b))
                elif name == "eq":
                    out.append("eq %d %d %d" % (i, j, int(a == b)))
                elif name == "lt":
                    out.append("lt %d %d %d" % (i, j, int(a < b)))
                elif name == "le":
                    out.append("le %d %d %d" % (i, j, int(a <= b)))
            exp = _shift_expect(a, b)
            if exp is not None:
                out.append("lshift %d %d %s" % (i, j, exp))
            out.append("rshift %d %d %s" % (i, j, "E" if b < 0 else a >> b))
    for i, a in enumerate(VALUES):
        out.append("neg %d %d %d" % (i, i, -a))
    for i, a in enumerate(VALUES):
        for j, n in enumerate(SHIFTS):
            exp = _shift_expect(a, n)
            if exp is not None:
                out.append("lshiftS %d %d %s" % (i, j, exp))
            out.append("rshiftS %d %d %s" % (i, j, "E" if n < 0 else a >> n))
    return out


HARNESS = r'''
static const char *errname(ail_ctx *cx, ail_st st) {
    if (st == AIL_OK) return "OK";
    if (st == AIL_EXC) return ail_builtin_name(((ail_classobj *)cx->exc.cls.o)->builtin_id);
    return "LIMIT";
}
static void pobj(ail_obj s) { ail_str_write(ail_view_to_str(s), stdout); }
static void pval(ail_ctx *cx, ail_tint x) { pobj(ail_tint_str(cx, x)); }
static void one(ail_ctx *cx, const char *name, int op, int i, int j, ail_obj *vals) {
    ail_tint a, b, r; ail_tint_from_obj(vals[i], &a); ail_tint_from_obj(vals[j], &b);
    ail_obj keep[3]; keep[0] = vals[i]; keep[1] = vals[j]; keep[2] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, keep, 3);
    ail_st st = AIL_OK; int cmp = 0;
    r = ail_tint_from_int64(0);
    switch (op) {
        case 0: r = ail_tint_add(cx, a, b); break;
        case 1: r = ail_tint_sub(cx, a, b); break;
        case 2: r = ail_tint_mul(cx, a, b); break;
        case 3: st = ail_tint_floordiv(cx, &r, a, b); break;
        case 4: st = ail_tint_mod(cx, &r, a, b); break;
        case 5: cmp = ail_tint_eq(a, b); break;
        case 6: cmp = ail_tint_lt(a, b); break;
        case 7: cmp = ail_tint_le(a, b); break;
        case 8: st = ail_tint_lshift(cx, &r, a, b); break;
        case 9: st = ail_tint_rshift(cx, &r, a, b); break;
        default: break;
    }
    if (st != AIL_OK) printf("%s %d %d E\n", name, i, j);
    else if (op >= 5 && op <= 7) printf("%s %d %d %d\n", name, i, j, cmp);
    else {
        keep[2] = ail_tint_to_obj(r);
        printf("%s %d %d ", name, i, j); pval(cx, r); putchar('\n');
    }
    AIL_FRAME_LEAVE(cx, fr);
}
static void one_neg(ail_ctx *cx, int i, ail_obj *vals) {
    ail_tint a, r; ail_tint_from_obj(vals[i], &a);
    ail_obj keep[2]; keep[0] = vals[i]; keep[1] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, keep, 2);
    r = ail_tint_neg(cx, a);
    keep[1] = ail_tint_to_obj(r);
    printf("neg %d %d ", i, i); pval(cx, r); putchar('\n');
    AIL_FRAME_LEAVE(cx, fr);
}
static int shift_main(ail_tint a, ail_tint n) {
    int64_t sn;
    if (ail_tint_sign(n) < 0) return 1;             /* ValueError, printed by one() */
    if (ail_tint_is_zero(a)) return 1;              /* 0 << n is 0, even for a huge n */
    return ail_tint_to_int64(n, &sn) && sn <= 100;  /* bigger results: checked elsewhere */
}
static void check_errors(ail_ctx *cx) {
    ail_tint r;
    ail_st st = ail_tint_floordiv(cx, &r, ail_tint_from_int64(5), ail_tint_from_int64(0));
    printf("err floordiv %s\n", errname(cx, st));
    st = ail_tint_mod(cx, &r, ail_tint_from_int64(5), ail_tint_from_int64(0));
    printf("err mod %s\n", errname(cx, st));
    st = ail_tint_lshift(cx, &r, ail_tint_from_int64(1), ail_tint_from_int64(-1));
    printf("err lshift %s\n", errname(cx, st));
    st = ail_tint_rshift(cx, &r, ail_tint_from_int64(1), ail_tint_from_int64(-1));
    printf("err rshift %s\n", errname(cx, st));
}
int main(void) {
    ail_ctx cxs, *cx = &cxs; ail_ctx_init(cx);
    ail_obj vals[NVAL], shifts[NSHIFT];
    for (int i = 0; i < NVAL; i++) vals[i] = ail_box_none();
    for (int i = 0; i < NSHIFT; i++) shifts[i] = ail_box_none();
    AIL_ROOT_N(cx, f1, vals, NVAL);
    AIL_ROOT_N(cx, f2, shifts, NSHIFT);
    for (int i = 0; i < NVAL; i++) vals[i] = ail_big_from_digits(cx, vals_dig[i], strlen(vals_dig[i]), 10, vals_neg[i]);
    for (int i = 0; i < NSHIFT; i++) shifts[i] = ail_big_from_digits(cx, shifts_dig[i], strlen(shifts_dig[i]), 10, shifts_neg[i]);
    check_errors(cx);
    for (int i = 0; i < NVAL; i++) {
        ail_tint t; int64_t v; ail_tint_from_obj(vals[i], &t);
        int fits = ail_tint_to_int64(t, &v);
        if (fits) printf("i64 %d 1 %lld\n", i, (long long)v); else printf("i64 %d 0\n", i);
    }
    for (int i = 0; i < NVAL; i++) {
        ail_tint t; ail_tint_from_obj(vals[i], &t);
        printf("str %d ", i); pval(cx, t); putchar('\n');
        printf("repr %d ", i); pobj(ail_tint_repr(cx, t)); putchar('\n');
    }
    for (int i = 0; i < NFROM; i++) {
        ail_tint t = ail_tint_from_int64(from64[i]);
        printf("from64 %lld ", (long long)from64[i]); pval(cx, t); putchar('\n');
    }
    for (int i = 0; i < NVAL; i++) for (int j = 0; j < NVAL; j++) {
        one(cx, "add", 0, i, j, vals); one(cx, "sub", 1, i, j, vals); one(cx, "mul", 2, i, j, vals);
        one(cx, "floordiv", 3, i, j, vals); one(cx, "mod", 4, i, j, vals);
        one(cx, "eq", 5, i, j, vals); one(cx, "lt", 6, i, j, vals); one(cx, "le", 7, i, j, vals);
        ail_tint a, n; ail_tint_from_obj(vals[i], &a); ail_tint_from_obj(vals[j], &n);
        if (shift_main(a, n)) one(cx, "lshift", 8, i, j, vals);
        one(cx, "rshift", 9, i, j, vals);
    }
    for (int i = 0; i < NVAL; i++) one_neg(cx, i, vals);
    for (int i = 0; i < NVAL; i++) for (int j = 0; j < NSHIFT; j++) {
        ail_tint a, n; ail_tint_from_obj(vals[i], &a); ail_tint_from_obj(shifts[j], &n);
        if (shift_main(a, n)) {
            ail_obj pair[3]; pair[0] = vals[i]; pair[1] = shifts[j]; pair[2] = ail_box_int(0);
            AIL_ROOT_N(cx, fr, pair, 3);
            ail_tint r; ail_st st = ail_tint_lshift(cx, &r, a, n);
            if (st != AIL_OK) printf("lshiftS %d %d E\n", i, j);
            else { pair[2] = ail_tint_to_obj(r); printf("lshiftS %d %d ", i, j); pval(cx, r); putchar('\n'); }
            AIL_FRAME_LEAVE(cx, fr);
        }
        ail_obj pair[3]; pair[0] = vals[i]; pair[1] = shifts[j]; pair[2] = ail_box_int(0);
        AIL_ROOT_N(cx, fr, pair, 3);
        ail_tint r; ail_st st = ail_tint_rshift(cx, &r, a, n);
        if (st != AIL_OK) printf("rshiftS %d %d E\n", i, j);
        else { pair[2] = ail_tint_to_obj(r); printf("rshiftS %d %d ", i, j); pval(cx, r); putchar('\n'); }
        AIL_FRAME_LEAVE(cx, fr);
    }
    AIL_FRAME_LEAVE(cx, f2); AIL_FRAME_LEAVE(cx, f1);
    ail_ctx_destroy(cx);
    return 0;
}
'''

HUGE_HARNESS = r'''
static const char *errname(ail_ctx *cx, ail_st st) {
    if (st == AIL_OK) return "OK";
    if (st == AIL_EXC) return ail_builtin_name(((ail_classobj *)cx->exc.cls.o)->builtin_id);
    return "LIMIT";
}
static ail_obj parse(ail_ctx *cx, const char *s) {
    int neg = *s == '-';
    if (neg) s++;
    return ail_big_from_digits(cx, s, strlen(s), 10, neg);
}
static uint64_t tint_bitlen(ail_tint x) {
    if (x.b) return ail_bn_bitlen(x.b->d, x.b->n);
    uint64_t m = x.i < 0 ? (uint64_t)0 - (uint64_t)x.i : (uint64_t)x.i, n = 0;
    while (m) { n++; m >>= 1; }
    return n;
}
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    ail_ctx cxs, *cx = &cxs; ail_ctx_init(cx);
    ail_obj k[3]; k[0] = ail_box_none(); k[1] = ail_box_none(); k[2] = ail_box_none();
    AIL_ROOT_N(cx, fr, k, 3);
    k[0] = parse(cx, argv[1]); k[1] = parse(cx, argv[2]);
    ail_tint a, n, r; ail_tint_from_obj(k[0], &a); ail_tint_from_obj(k[1], &n);
    if (ail_tint_is_zero(a)) { printf("zero\n"); AIL_FRAME_LEAVE(cx, fr); ail_ctx_destroy(cx); return 0; }
    ail_st st = ail_tint_lshift(cx, &r, a, n);
    if (st != AIL_OK) printf("ERR %s\n", errname(cx, st));
    else {
        k[2] = ail_tint_to_obj(r);
        ail_tint back; ail_st st2 = ail_tint_rshift(cx, &back, r, n);
        int eq = st2 == AIL_OK && ail_tint_eq(back, a);
        printf("OK %llu %d %d\n", (unsigned long long)tint_bitlen(r), eq, ail_tint_sign(a));
    }
    AIL_FRAME_LEAVE(cx, fr);
    ail_ctx_destroy(cx);
    return 0;
}
'''


class TaggedIntRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CC:
            raise unittest.SkipTest("no C compiler")
        import cruntime
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-tint-")
        d = Path(cls.tmp.name)
        arrays = (_c_array(VALUES, "vals") + _c_array(SHIFTS, "shifts")
                  + "static const int64_t from64[%d] = { %s };\n"
                  % (len(FROM64), ", ".join("(-INT64_C(9223372036854775807) - 1)" if v == -(2 ** 63)
                                            else "%dLL" % v for v in FROM64))
                  + "#define NVAL %d\n#define NSHIFT %d\n#define NFROM %d\n"
                  % (len(VALUES), len(SHIFTS), len(FROM64)))
        runtime = cruntime.repr_runtime_for_host(cruntime.OBJ2)
        source = runtime + arrays + HARNESS
        (d / "t.c").write_text(source, encoding="utf-8")
        exe = d / "t"
        subprocess.run([CC, "-O2", "-w", "-o", str(exe), str(d / "t.c"), "-lm"], check=True)
        cls.result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
        cls.runtime_source = source

        (d / "huge.c").write_text(runtime + HUGE_HARNESS, encoding="utf-8")
        cls.huge_exe = d / "huge"
        subprocess.run([CC, "-O2", "-w", "-o", str(cls.huge_exe), str(d / "huge.c"), "-lm"], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_runtime_contains_tagged_int(self):
        self.assertIn("typedef struct ail_tint", self.runtime_source)
        self.assertIn("ail_tint_floordiv", self.runtime_source)

    def test_every_operation_matches_python(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr[-2000:])
        self.assertEqual(self.result.stderr, "")
        got = self.result.stdout.splitlines()
        want = _expected()
        self.assertEqual(len(got), len(want))
        for k, (g, w) in enumerate(zip(got, want)):
            if g != w:
                self.fail("line %d\n  CPython: %s\n  ail_tint: %s" % (k, w[:400], g[:400]))

    def test_every_huge_left_shift_matches_python(self):
        for a in VALUES:
            for n in HUGE_SHIFTS:
                if a == 0:
                    continue
                expect = _huge_expect(a, n)
                p = subprocess.run([str(self.huge_exe), str(a), str(n)],
                                   capture_output=True, text=True, timeout=300)
                if expect == "MEMORY":
                    self.assertNotEqual(p.returncode, 0, (a, n, p.stdout, p.stderr))
                    self.assertIn("MemoryError", p.stderr, (a, n, p.stderr))
                    continue
                self.assertEqual(p.returncode, 0, (a, n, p.stderr[-2000:]))
                self.assertEqual(p.stderr, "", (a, n))
                self.assertEqual(p.stdout.strip(), expect, "a=%d n=%d" % (a, n))


if __name__ == "__main__":
    unittest.main()
