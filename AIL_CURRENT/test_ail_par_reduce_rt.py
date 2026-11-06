"""fbred2: the reduction runtime part PARRED against the sequential checked loop, driven from C.

The harness below links cruntime's PARRED (with PAR, PARN and the DIE block they need) and hand-written
`fn` / `rerun` pairs for three shapes: `acc += v`, `acc -= v`, and two accumulators (`acc += v; neg -= w`).
Cases come from lab/race/reduce/model.py's generator. Every case runs twice, each run in its own forked
child (a stop is a loud `_Exit(1)`): once as the plain sequential checked loop, once through
`ail_par_reduce_run`. The accumulators and the iteration being run live in shared memory, so the
comparison key is (exit status, stdout + stderr text, acc after the run, the iteration where it stopped).

    python3 AIL_CURRENT/test_ail_par_reduce_rt.py                       # the unittest (small counts)
    python3 AIL_CURRENT/test_ail_par_reduce_rt.py diff [cases] [san]    # cases per thread count; san: tsan|asan
    python3 AIL_CURRENT/test_ail_par_reduce_rt.py cost [terms]          # instruction counts (lab/race/reduce/RT.md)
"""
import importlib.util
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
import cruntime  # noqa: E402

MODEL = ROOT.parent / "lab" / "race" / "reduce" / "model.py"
SEED = 20261106
THREADS = (1, 2, 4, 16)
CODES = {"ValueError": 1, "ZeroDivisionError": 2, "IndexError": 3}

PRELUDE = "#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n"

BODY = r"""
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#define ADD_TEXT "OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)"
#define SUB_TEXT "OverflowError: integer overflow in - (ints are 64-bit; --exact-int gives exact ints)"
typedef struct { int64_t acc[2]; int64_t at; } red_shared;
typedef struct { int kind; int64_t v, w; } red_item;          /* kind: 0 a value, else an exception code */
typedef struct { const red_item *it; int shape; int64_t delay; red_shared *sh; } red_args;
static void red_delay(int64_t d) { for (volatile int64_t k = 0; k < d; k++) {} }
/* The sequential checked loop: shape 0 `acc += v`, 1 `acc -= v`, 2 `acc += v; neg -= w`. */
static void red_rerun(void **args, int64_t lo, int64_t hi, int64_t *acc) {
    red_args *A = (red_args *)args[0];
    for (int64_t k = lo; k < hi; k++) {
        A->sh->at = k;
        if (A->delay) red_delay(A->delay);
        const red_item *x = &A->it[k];
        if (x->kind) ail_raise_named(x->kind);
        int64_t r;
        if (A->shape == 1) { if (__builtin_sub_overflow(acc[0], x->v, &r)) ail_die(SUB_TEXT); acc[0] = r; continue; }
        if (__builtin_add_overflow(acc[0], x->v, &r)) ail_die(ADD_TEXT);
        acc[0] = r;
        if (A->shape == 2) { if (__builtin_sub_overflow(acc[1], x->w, &r)) ail_die(SUB_TEXT); acc[1] = r; }
    }
}
/* fn, plain: every prefix in __int128. */
static void red_fn128(void **args, int64_t lo, int64_t hi, ail_red_part *parts) {
    red_args *A = (red_args *)args[0];
    __int128 s0 = 0, mx0 = 0, mn0 = 0, s1 = 0, mx1 = 0, mn1 = 0;
    for (int64_t k = lo; k < hi; k++) {
        if (A->delay) red_delay(A->delay);
        const red_item *x = &A->it[k];
        if (x->kind) ail_raise_named(x->kind);
        s0 += A->shape == 1 ? -(__int128)x->v : (__int128)x->v;
        if (s0 > mx0) mx0 = s0;
        if (s0 < mn0) mn0 = s0;
        if (A->shape == 2) { s1 -= x->w; if (s1 > mx1) mx1 = s1; if (s1 < mn1) mn1 = s1; }
    }
    parts[0] = (ail_red_part){s0, mx0, mn0};
    if (A->shape == 2) parts[1] = (ail_red_part){s1, mx1, mn1};
}
/* fn, fast: an int64 running sum while it fits, the __int128 loop from the first chunk-local overflow. */
static void red_fn64(void **args, int64_t lo, int64_t hi, ail_red_part *parts) {
    red_args *A = (red_args *)args[0];
    int64_t s0 = 0, mx0 = 0, mn0 = 0, s1 = 0, mx1 = 0, mn1 = 0, k = lo;
    for (; k < hi; k++) {
        if (A->delay) red_delay(A->delay);
        const red_item *x = &A->it[k];
        if (x->kind) ail_raise_named(x->kind);
        int64_t t, u = 0;
        if (A->shape == 1 ? __builtin_sub_overflow(s0, x->v, &t) : __builtin_add_overflow(s0, x->v, &t)) break;
        if (A->shape == 2 && __builtin_sub_overflow(s1, x->w, &u)) break;
        s0 = t; mx0 = t > mx0 ? t : mx0; mn0 = t < mn0 ? t : mn0;
        if (A->shape == 2) { s1 = u; mx1 = u > mx1 ? u : mx1; mn1 = u < mn1 ? u : mn1; }
    }
    __int128 S0 = s0, M0 = mx0, m0 = mn0, S1 = s1, M1 = mx1, m1 = mn1;
    for (; k < hi; k++) {      /* iteration k is re-done in full: its adds were not kept above */
        const red_item *x = &A->it[k];
        if (x->kind) ail_raise_named(x->kind);
        S0 += A->shape == 1 ? -(__int128)x->v : (__int128)x->v;
        if (S0 > M0) M0 = S0;
        if (S0 < m0) m0 = S0;
        if (A->shape == 2) { S1 -= x->w; if (S1 > M1) M1 = S1; if (S1 < m1) m1 = S1; }
    }
    parts[0] = (ail_red_part){S0, M0, m0};
    if (A->shape == 2) parts[1] = (ail_red_part){S1, M1, m1};
}
static red_shared *SH;
/* One run in a forked child; its stdout and stderr go to buf. */
static int red_child(int par, red_args *A, int64_t n, int64_t prefix, int64_t cap, int heavy, int fast,
                     const int64_t *start, char *buf, size_t cap_buf) {
    int fd[2];
    if (pipe(fd)) { perror("pipe"); exit(3); }
    fflush(stdout);
    pid_t pid = fork();
    if (pid < 0) { perror("fork"); exit(3); }
    if (!pid) {
        close(fd[0]); dup2(fd[1], 1); dup2(fd[1], 2); close(fd[1]);
        SH->acc[0] = start[0]; SH->acc[1] = start[1]; SH->at = -1;
        void *args[1] = {A};
        if (!par) red_rerun(args, 0, n, SH->acc);
        else {
            ail_par_site S = {0, heavy ? 1 : 0};
            red_rerun(args, 0, prefix, SH->acc);
            ail_par_reduce_run(fast ? red_fn64 : red_fn128, args, prefix, n, &S, cap, A->shape == 2 ? 2 : 1, SH->acc, red_rerun);
        }
        SH->at = n;
        fputs("ok\n", stdout);
        fflush(stdout);
        _Exit(0);
    }
    close(fd[1]);
    size_t got = 0;
    for (;;) {
        ssize_t r = read(fd[0], buf + got, cap_buf - 1 - got);
        if (r <= 0) break;
        got += (size_t)r;
        if (got >= cap_buf - 1) break;
    }
    buf[got] = 0;
    close(fd[0]);
    int st = 0;
    waitpid(pid, &st, 0);
    return WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st);
}
int main(void) {
    SH = (red_shared *)mmap(NULL, sizeof *SH, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    if (SH == MAP_FAILED) { perror("mmap"); return 3; }
    long cases = 0, bad = 0;
    int id, shape, heavy, fast;
    long long n, s0, s1, prefix, cap, delay;
    static red_item items[4096];
    static char out_s[4096], out_p[4096];
    while (scanf("%d %d %lld %lld %lld %lld %lld %lld %d %d", &id, &shape, &n, &s0, &s1, &prefix, &cap, &delay, &heavy, &fast) == 10) {
        if (n < 0 || n > 4096) return 3;
        for (long long k = 0; k < n; k++) {
            long long v, w; int kind;
            if (scanf("%d %lld %lld", &kind, &v, &w) != 3) return 3;
            items[k] = (red_item){kind, (int64_t)v, (int64_t)w};
        }
        red_args A = {items, shape, delay, SH};
        int64_t start[2] = {s0, s1};
        int st_s = red_child(0, &A, n, 0, 0, 0, 0, start, out_s, sizeof out_s);
        int64_t acc_s0 = SH->acc[0], acc_s1 = SH->acc[1], at_s = SH->at;
        int st_p = red_child(1, &A, n, prefix, cap, heavy, fast, start, out_p, sizeof out_p);
        cases++;
        if (st_s != st_p || strcmp(out_s, out_p) || acc_s0 != SH->acc[0] || acc_s1 != SH->acc[1] || at_s != SH->at) {
            if (bad++ < 5)
                printf("DIFF case=%d shape=%d n=%lld prefix=%lld cap=%lld heavy=%d fast=%d: seq (%d, %lld %lld at %lld, %s) par (%d, %lld %lld at %lld, %s)\n",
                       id, shape, n, prefix, cap, heavy, fast, st_s, (long long)acc_s0, (long long)acc_s1, (long long)at_s, out_s,
                       st_p, (long long)SH->acc[0], (long long)SH->acc[1], (long long)SH->at, out_p);
        }
    }
    printf("cases %ld differences %ld\n", cases, bad);
    return bad != 0;
}
"""

# The cost harness: `acc += term(i)` over [0, n), term(i) = i % 1000 (pure, cannot raise). seq: the
# sequential checked loop alone; par: ail_par_reduce_run with the fast fn. Prints acc.
COST = r"""
#define ADD_TEXT "OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)"
static inline int64_t term(int64_t i) { return i % 1000; }
static void c_rerun(void **args, int64_t lo, int64_t hi, int64_t *acc) {
    (void)args;
    int64_t a = acc[0];
    for (int64_t i = lo; i < hi; i++) {
        int64_t r;
        if (__builtin_add_overflow(a, term(i), &r)) { acc[0] = a; ail_die(ADD_TEXT); }
        a = r;
    }
    acc[0] = a;
}
static void c_fn(void **args, int64_t lo, int64_t hi, ail_red_part *parts) {
    (void)args;
    int64_t s = 0, mx = 0, mn = 0, i = lo;
    for (; i < hi; i++) {
        int64_t t;
        if (__builtin_add_overflow(s, term(i), &t)) break;
        s = t; mx = t > mx ? t : mx; mn = t < mn ? t : mn;
    }
    __int128 S = s, M = mx, m = mn;
    for (; i < hi; i++) { S += term(i); if (S > M) M = S; if (S < m) m = S; }
    parts[0] = (ail_red_part){S, M, m};
}
int main(int argc, char **argv) {
    int64_t n = argc > 2 ? atoll(argv[2]) : 10000000;
    int64_t acc[1] = {0};
    void *args[1] = {NULL};
    static ail_par_site site;
    if (argc > 1 && argv[1][0] == 'p') ail_par_reduce_run(c_fn, args, 0, n, &site, 0, 1, acc, c_rerun);
    else c_rerun(args, 0, n, acc);
    printf("%lld\n", (long long)acc[0]);
    return 0;
}
"""


def runtime_text():
    return PRELUDE + cruntime.emit(["PARRED"])


def load_model():
    spec = importlib.util.spec_from_file_location("reduce_model", MODEL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def case_text(count, seed=SEED):
    """`count` cases from model.py's generator, in the harness's input format."""
    model = load_model()
    rng = random.Random(seed)
    lines = []
    for cid in range(count):
        shape = rng.randrange(3)
        items, start, prefix, _chunks = model.rand_reduce_case(rng)
        n = len(items)
        second = model.make_items(rng, n, allow_exc=False)
        start1 = rng.choice(model.NEAR) if shape == 2 else 0
        cap = rng.choice((0, 0, 0, 2, 3, 5))
        heavy, delay = 1, 0
        if n >= 64 and rng.random() < 0.01:      # the runtime's own timed probe prefix, then wide
            heavy, delay, prefix = 0, 20000, 0
        lines.append("%d %d %d %d %d %d %d %d %d %d" % (cid, shape, n, start, start1, prefix, cap, delay, heavy,
                                                       rng.randrange(2)))
        for (kind, value), (_k2, w) in zip(items, second):
            lines.append("%d %d %d" % ((CODES[value], 0, w) if kind == "x" else (0, value, w)))
    return "\n".join(lines) + "\n"


def build(directory, body, san=None, opt="-O2"):
    src = Path(directory) / "h.c"
    exe = Path(directory) / ("h_" + (san or "plain"))
    src.write_text(runtime_text() + body)
    flags = {None: [], "tsan": ["-fsanitize=thread", "-g"],
             "asan": ["-fsanitize=address,undefined", "-fno-sanitize-recover=undefined", "-g"]}[san]
    r = subprocess.run(["cc", opt, "-w", "-pthread", *flags, "-o", str(exe), str(src)], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("cc failed:\n" + r.stderr[-3000:])
    return exe


def run_diff(exe, cases_in, threads):
    env = dict(os.environ, AIL_THREADS=str(threads))
    env.setdefault("TSAN_OPTIONS", "halt_on_error=1 exitcode=66")
    return subprocess.run([str(exe)], input=cases_in, capture_output=True, text=True, env=env, timeout=3000)


class ParReduceRuntimeTests(unittest.TestCase):
    def test_only_a_reduction_links_parred(self):
        self.assertNotIn("ail_par_reduce_run", cruntime.emit(["PARN"]))
        self.assertNotIn("ail_par_reduce_run", cruntime.emit(["PAR"]))
        text = cruntime.emit(["PARRED"])
        self.assertIn("ail_par_reduce_run", text)
        self.assertIn("ail_par_run_n", text)            # PARN came along

    def test_differential_small(self):
        cases_in = case_text(int(os.environ.get("AIL_RED_CASES", "300")))
        with tempfile.TemporaryDirectory() as d:
            exe = build(d, BODY)
            for t in THREADS:
                r = run_diff(exe, cases_in, t)
                self.assertEqual(r.returncode, 0, "AIL_THREADS=%d\n%s%s" % (t, r.stdout[-3000:], r.stderr[-2000:]))
                self.assertIn("differences 0", r.stdout)

    def test_hand_cases(self):
        big = 1 << 62
        # (shape, start, start1, prefix, items as (kind, v, w)): an overflow in the last chunk, an
        # exception before an overflow, a prefix that overflows while the total fits, two accumulators
        # where only the second stops.
        hand = [
            (0, 0, 0, 0, [(0, 1, 0)] * 40 + [(0, big, 0), (0, big, 0), (0, -big, 0)]),
            (0, 0, 0, 0, [(0, 5, 0)] * 30 + [(2, 0, 0)] + [(0, big, 0)] * 3),
            (0, 0, 0, 0, [(0, big, 0), (0, big, 0), (0, -big, 0), (0, -big, 0)] * 10),
            (1, -2, 0, 3, [(0, big, 0)] * 2 + [(0, 1, 0)] * 50),
            (2, 0, -5, 0, [(0, 1, big)] * 20 + [(0, 1, big)] * 20),
        ]
        lines = []
        for cid, (shape, s0, s1, prefix, items) in enumerate(hand):
            lines.append("%d %d %d %d %d %d 0 0 1 %d" % (cid, shape, len(items), s0, s1, prefix, cid % 2))
            lines += ["%d %d %d" % it for it in items]
        with tempfile.TemporaryDirectory() as d:
            exe = build(d, BODY)
            for t in THREADS:
                r = run_diff(exe, "\n".join(lines) + "\n", t)
                self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
                self.assertIn("cases %d differences 0" % len(hand), r.stdout)


def main_cli(argv):
    if argv[0] == "diff":
        count = int(argv[1]) if len(argv) > 1 else 20000
        san = argv[2] if len(argv) > 2 else None
        cases_in = case_text(count)
        with tempfile.TemporaryDirectory() as d:
            exe = build(d, BODY, san, "-O1" if san else "-O2")
            worst = 0
            for t in THREADS:
                r = run_diff(exe, cases_in, t)
                print("AIL_THREADS=%d exit %d: %s" % (t, r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""))
                if r.returncode:
                    print(r.stdout[-3000:], r.stderr[-4000:])
                    worst = 1
            return worst
    if argv[0] == "cost":
        n = argv[1] if len(argv) > 1 else "10000000"
        d = tempfile.mkdtemp(prefix="red_cost_")
        exe = build(d, COST)
        print(exe, n)
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("diff", "cost"):
        raise SystemExit(main_cli(sys.argv[1:]))
    unittest.main()
