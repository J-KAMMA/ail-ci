# -*- coding: utf-8 -*-
"""rebrt.py -- relib.py's Pike VM and byte DFA on the general (boxed) path, in C (fragment 'rex' of safetyrt.py).

`import re` with literal patterns (relib.py) adds a matcher written in the Python subset to the program: a table per
pattern (a list of ints) and the engine's functions. The typed path compiles that text to plain C; the general path
ran it on boxed values (every `p[opo + pc]` an object access, every `cps[pos]` a call of bytes.__getitem__), and the
profile of the gdev programs that use re put 40-50% of their instructions into _ail_re_addY, _ail_re_runY and
_ail_re_dp. pyboxed2._native_re replaces

* _ail_re_run / _ail_re_runY (the Pike VM with _ail_re_add, _ail_re_assert, _ail_re_look under it) by a call of the
  primitive _ail_rx_run, which is those five functions in C, step for step;
* _ail_re_dp / _ail_re_ds / _ail_re_dm (the byte DFA) by the primitives _ail_rx_dp / _ail_rx_ds / _ail_rx_dm.

The original Python functions stay in the program under the names `...P` and run when the C one gives up: the
subject is not a bytes object the primitive can read (a bytearray), or the match needs a Unicode predicate for a code
point above 127 (\\w, \\d, \\s or a class on text that is not ASCII): the C returns -1 and the Python code answers, so
the results are the ones the Python text always gave. The tables, the Match objects and the glue are unchanged. A
program that does not use re gets the C it always had.
"""

PRIMS = {
    '_ail_rx_run': ('ail2x_run_p(cx, &{t}, {a0}, {a1}, {a2}, {a3}, {a4}, {a5}, {a6}, {a7}, {a8})', 9),
    '_ail_rx_dp': ('ail2x_dp_p(cx, &{t}, {a0}, {a1}, {a2}, {a3}, {a4})', 5),
    '_ail_rx_ds': ('ail2x_ds_p(cx, &{t}, {a0}, {a1}, {a2}, {a3}, {a4})', 5),
    '_ail_rx_dm': ('ail2x_dm_p(cx, &{t}, {a0}, {a1}, {a2})', 3),
}

# name of the engine function -> the wrapper that takes its place (the original is kept as NAME + 'P')
_WRAP = {
    '_ail_re_run': '''
def _ail_re_run(vm, p, cps, n, start, mode, mustadv, pc0, mustend):
    r = _ail_rx_run(vm.res, p, cps, n, start, mode, mustadv, pc0, mustend)
    if r >= 0:
        return r == 1
    full = _ail_re_newP(p)
    ok = _ail_re_runP(full, p, cps, n, start, mode, mustadv, pc0, mustend)
    for k in range(p[0]):
        vm.res[k] = full.res[k]
    return ok
''',
    '_ail_re_new': '''
class _ail_re_Vx:
    def __init__(self, res):
        self.res = res


def _ail_re_new(p):
    return _ail_re_Vx([0] * p[0])
''',
    '_ail_re_runY': '''
def _ail_re_runY(vm, p, cps, n, start, mode, mustadv, pc0, mustend):
    if isinstance(cps, bytes):
        r = _ail_rx_run(vm.res, p, cps._s, n, start, mode, mustadv, pc0, mustend)
        if r >= 0:
            return r == 1
    full = _ail_re_newP(p)
    ok = _ail_re_runYP(full, p, cps, n, start, mode, mustadv, pc0, mustend)
    for k in range(p[0]):
        vm.res[k] = full.res[k]
    return ok
''',
    '_ail_re_dp': '''
def _ail_re_dp(p, sb, n, s, wk):
    if isinstance(sb, bytes):
        return _ail_rx_dp(p, sb._s, n, s, wk.v)
    return _ail_re_dpP(p, sb, n, s, wk)
''',
    '_ail_re_ds': '''
def _ail_re_ds(p, sb, n, pos, wk):
    if isinstance(sb, bytes):
        return _ail_rx_ds(p, sb._s, n, pos, wk.v)
    return _ail_re_dsP(p, sb, n, pos, wk)
''',
    '_ail_re_dm': '''
def _ail_re_dm(p, sb, n):
    if isinstance(sb, bytes):
        return _ail_rx_dm(p, sb._s, n)
    return _ail_re_dmP(p, sb, n)
''',
}

REX = r'''
/* ---- re on the general path (rebrt.py): relib.py's Pike VM and byte DFA, step for step ---- */
typedef struct {
    const ail_obj *P;               /* the pattern table */
    int64_t ncap, nprog, opo, xo, asc;
    const uint16_t *sp;             /* the subject as units (a bytes object's str) ... */
    const ail_obj *lp;              /* ... or as a list of code points */
    int64_t n;
    int fb;                         /* a Unicode predicate was needed: the caller falls back to the Python text */
} ail2x_t;
typedef struct {
    int64_t *pcs, *caps, *mark, *work, *stack;
    int64_t cnt[2], gens[2];
} ail2x_vm;
static inline int64_t ail2x_cp(const ail2x_t *R, int64_t i) { return R->sp ? (int64_t)R->sp[i] : R->lp[i].i; }
static inline int ail2x_isw(ail2x_t *R, int64_t c) {
    if (c < 0) return 0;
    if (c < 128) return (c >= 48 && c <= 57) || (c >= 65 && c <= 90) || c == 95 || (c >= 97 && c <= 122);
    if (R->asc == 1) return 0;
    R->fb = 1;
    return 0;
}
static int ail2x_assert(ail2x_t *R, int64_t kind, int64_t pos) {
    int64_t n = R->n;
    if (kind == 0 || kind == 4) return pos == 0;
    if (kind == 1) return pos == 0 || ail2x_cp(R, pos - 1) == 10;
    if (kind == 2) return pos == n || (pos == n - 1 && ail2x_cp(R, pos) == 10);
    if (kind == 3) return pos == n || ail2x_cp(R, pos) == 10;
    if (kind == 5) return pos == n;
    if (n == 0) return 0;
    int before = 0, after = 0;
    if (pos > 0) before = ail2x_isw(R, ail2x_cp(R, pos - 1));
    if (pos < n) after = ail2x_isw(R, ail2x_cp(R, pos));
    if (kind == 6) return before != after;
    return before == after;
}
static int ail2x_nonascii(ail2x_t *R, int64_t off, int64_t c) {
    int64_t i = off;
    while (R->P[i].i != -100) {
        int64_t lo = R->P[i].i;
        if (lo >= 0) { if (lo <= c && c <= R->P[i + 1].i) return 1; }
        else { R->fb = 1; return 0; }
        i += 2;
    }
    return 0;
}
static int ail2x_run(ail2x_t *R, int64_t start, int mode, int mustadv, int64_t pc0, int64_t mustend, int64_t *res);
/* _ail_re_add: the epsilon closure of pc0 at pos into buffer buf; src is the caps row to start from, or -1 */
static int ail2x_add(ail2x_t *R, ail2x_vm *vm, int buf, int64_t pc0, int64_t pos, int64_t src) {
    const ail_obj *P = R->P;
    int64_t ncap = R->ncap, nprog = R->nprog, opo = R->opo, xo = R->xo, yo = P[7].i;
    if (src < 0) { for (int64_t k = 0; k < ncap; k++) vm->work[k] = -1; }
    else { for (int64_t k = 0; k < ncap; k++) vm->work[k] = vm->caps[src + k]; }
    int64_t gen = vm->gens[buf], base = buf * nprog;
    vm->stack[0] = pc0; vm->stack[1] = 0;
    int64_t sp = 2;
    while (sp > 0) {
        sp -= 2;
        int64_t a = vm->stack[sp];
        if (vm->stack[sp + 1] == 1) { vm->work[a % 1024] = a / 1024 - 1; continue; }
        int64_t pc = a;
        for (;;) {
            if (vm->mark[base + pc] == gen) break;
            vm->mark[base + pc] = gen;
            int64_t op = P[opo + pc].i;
            if (op == 6) pc = P[xo + pc].i;
            else if (op == 5) {
                vm->stack[sp] = P[yo + pc].i; vm->stack[sp + 1] = 0; sp += 2;
                pc = P[xo + pc].i;
            } else if (op == 7) {
                int64_t slot = P[xo + pc].i;
                vm->stack[sp] = (vm->work[slot] + 1) * 1024 + slot; vm->stack[sp + 1] = 1; sp += 2;
                vm->work[slot] = pos;
                pc += 1;
            } else if (op == 8) {
                int ok = ail2x_assert(R, P[xo + pc].i, pos);
                if (R->fb) return -1;
                if (ok) pc += 1; else break;
            } else if (op == 10) {
                /* _ail_re_look: a sub-run of the lookaround body */
                int64_t y = P[P[7].i + pc].i, found = 0;
                int64_t sub = P[xo + pc].i;
                if ((y / 2) % 2 == 1) {
                    int64_t width = y / 4;
                    if (pos >= width) found = ail2x_run(R, pos - width, 0, 0, sub, pos, NULL);
                } else found = ail2x_run(R, pos, 0, 0, sub, -1, NULL);
                if (R->fb) return -1;
                int ok = (y % 2 == 1) ? found == 0 : found == 1;
                if (ok) pc += 1; else break;
            } else {
                int64_t idx = vm->cnt[buf];
                vm->pcs[base + idx] = pc;
                int64_t dst = (base + idx) * ncap;
                for (int64_t k = 0; k < ncap; k++) vm->caps[dst + k] = vm->work[k];
                vm->cnt[buf] = idx + 1;
                break;
            }
        }
    }
    return 0;
}
/* _ail_re_run: 1 matched, 0 not, -1 when R->fb says the Python text has to answer. res (ncap ints) gets the groups. */
static int ail2x_run(ail2x_t *R, int64_t start, int mode, int mustadv, int64_t pc0, int64_t mustend, int64_t *res) {
    const ail_obj *P = R->P;
    int64_t ncap = R->ncap, nprog = R->nprog, opo = R->opo, xo = R->xo, n = R->n;
    int64_t offasc = P[8].i, offcl = P[9].i;
    int64_t total = 2 * nprog + 2 * nprog * ncap + 2 * nprog + ncap + 2 * nprog + 8 + ncap;
    int64_t *mem = (int64_t *)calloc((size_t)total, sizeof(int64_t));
    if (!mem) { R->fb = 1; return -1; }
    ail2x_vm vm; int64_t *q = mem;
    vm.pcs = q; q += 2 * nprog;
    vm.caps = q; q += 2 * nprog * ncap;
    vm.mark = q; q += 2 * nprog;
    vm.work = q; q += ncap;
    vm.stack = q; q += 2 * nprog + 8;
    int64_t *lres = res ? res : q;
    vm.cnt[0] = vm.cnt[1] = 0; vm.gens[0] = vm.gens[1] = 0;
    int skip = (mode == 2 && P[11].i == 0 && pc0 == 0);
    int cb = 0, matched = 0;
    vm.gens[0] += 1;
    int64_t pos = start;
    for (;;) {
        if (skip && !matched && vm.cnt[cb] == 0) {
            while (pos < n) {
                int64_t c = ail2x_cp(R, pos);
                if (c < 128) { if (P[P[13].i + c].i != 0) break; }
                else if (P[12].i != 0) break;
                pos++;
            }
            if (pos >= n) break;
            vm.gens[cb] += 1;
        }
        if (!matched && (mode == 2 || pos == start)) {
            if (ail2x_add(R, &vm, cb, pc0, pos, -1) < 0) { free(mem); return -1; }
        }
        if (vm.cnt[cb] == 0) {
            if (matched || mode != 2 || pos >= n) break;
            pos++;
            vm.gens[cb] += 1;
            continue;
        }
        int nb = 1 - cb;
        vm.cnt[nb] = 0;
        vm.gens[nb] += 1;
        int64_t c = -1;
        if (pos < n) c = ail2x_cp(R, pos);
        int64_t cnt = vm.cnt[cb];
        for (int64_t i = 0; i < cnt; i++) {
            int64_t idx = cb * nprog + i;
            int64_t pc = vm.pcs[idx];
            int64_t op = P[opo + pc].i;
            int ok = 0;
            if (op == 0) { if (c == P[xo + pc].i) ok = 1; }
            else if (op == 3 || op == 4) {
                if (c >= 0) {
                    int64_t k = P[xo + pc].i;
                    if (c < 128) ok = P[offasc + k * 128 + c].i != 0;
                    else {
                        ok = ail2x_nonascii(R, P[offcl + k].i, c);
                        if (R->fb) { free(mem); return -1; }
                        if (op == 4) ok = 1 - ok;
                    }
                }
            } else if (op == 1) { if (c >= 0 && c != 10) ok = 1; }
            else if (op == 2) { if (c >= 0) ok = 1; }
            else {
                if ((mustend >= 0 && pos != mustend) || (mustadv != 0 && pos == start)) ok = 0;
                else {
                    for (int64_t k = 0; k < ncap; k++) lres[k] = vm.caps[idx * ncap + k];
                    matched = 1;
                    break;
                }
            }
            if (ok) {
                int64_t tpc = pc + 1;
                int64_t top = P[opo + tpc].i;
                if (top <= 4 || top == 9 || top == 11) {
                    if (vm.mark[nb * nprog + tpc] != vm.gens[nb]) {
                        vm.mark[nb * nprog + tpc] = vm.gens[nb];
                        int64_t j = vm.cnt[nb];
                        vm.pcs[nb * nprog + j] = tpc;
                        int64_t srcr = idx * ncap, dst = (nb * nprog + j) * ncap;
                        for (int64_t k = 0; k < ncap; k++) vm.caps[dst + k] = vm.caps[srcr + k];
                        vm.cnt[nb] = j + 1;
                    }
                } else if (ail2x_add(R, &vm, nb, tpc, pos + 1, idx * ncap) < 0) { free(mem); return -1; }
            }
        }
        cb = nb;
        if (pos >= n) break;
        pos++;
    }
    if (res == NULL && matched) { /* nothing to copy: a lookaround only asks whether */ }
    free(mem);
    return matched;
}
static ail_st ail2x_setup(ail_ctx *cx, ail2x_t *R, ail_obj p, ail_obj subj, ail_obj no, int *usable) {
    *usable = 0;
    if (p.tag != AIL_T_LIST || (no.tag != AIL_T_INT)) return AIL_OK;
    const ail_vecobj *pv = (const ail_vecobj *)p.o;
    if (pv->n < 17) return AIL_OK;
    R->P = pv->p; R->ncap = pv->p[0].i; R->nprog = pv->p[1].i; R->opo = pv->p[5].i; R->xo = pv->p[6].i; R->asc = pv->p[10].i;
    R->fb = 0; R->n = no.i; R->sp = NULL; R->lp = NULL;
    if (subj.tag == AIL_T_STR) {
        ail_str s = ail_view_to_str(subj);
        if (R->n > s.n || R->n < 0) return AIL_OK;
        R->sp = s.p;
    } else if (subj.tag == AIL_T_LIST) {
        const ail_vecobj *sv = (const ail_vecobj *)subj.o;
        if (R->n > sv->n || R->n < 0) return AIL_OK;
        R->lp = sv->p;
    } else return AIL_OK;
    *usable = 1;
    (void)cx;
    return AIL_OK;
}
/* _ail_rx_run(res, p, subject, n, start, mode, mustadv, pc0, mustend) -> 1, 0 or -1 (the Python text answers) */
static ail_st ail2x_run_p(ail_ctx *cx, ail_obj *out, ail_obj res, ail_obj p, ail_obj subj, ail_obj no, ail_obj start,
                          ail_obj mode, ail_obj mustadv, ail_obj pc0, ail_obj mustend) {
    ail2x_t R; int usable;
    ail_st st = ail2x_setup(cx, &R, p, subj, no, &usable); if (st != AIL_OK) return st;
    if (!usable || res.tag != AIL_T_LIST || start.tag != AIL_T_INT || mode.tag != AIL_T_INT || mustadv.tag != AIL_T_INT
        || pc0.tag != AIL_T_INT || mustend.tag != AIL_T_INT || ((ail_vecobj *)res.o)->n < R.ncap
        || start.i < 0 || start.i > R.n || R.ncap < 2 || R.nprog < 1) { *out = ail_box_int(-1); return AIL_OK; }
    int64_t *lres = (int64_t *)malloc((size_t)R.ncap * sizeof(int64_t));
    if (!lres) { *out = ail_box_int(-1); return AIL_OK; }
    int r = ail2x_run(&R, start.i, (int)mode.i, (int)mustadv.i, pc0.i, mustend.i, lres);
    if (r == 1) {
        ail_obj *rv = ((ail_vecobj *)res.o)->p;
        for (int64_t k = 0; k < R.ncap; k++) rv[k] = ail_box_int(lres[k]);
    }
    free(lres);
    *out = ail_box_int(r);
    return AIL_OK;
}
/* the byte DFA: _ail_re_dp, _ail_re_ds, _ail_re_dm */
static int64_t ail2x_dp(const ail_obj *P, const uint16_t *sb, int64_t n, int64_t s, ail_obj *W) {
    int64_t d = P[14].i, ncls = P[d].i, co = P[d + 3].i, tb = P[d + 4].i, ib = P[d + 6].i;
    int64_t st = P[ib + ncls].i;
    if (s > 0) st = P[ib + P[co + sb[s - 1]].i].i;
    int64_t last = -1, pos = s;
    while (pos < n) {
        int64_t v = P[tb + st + P[co + sb[pos]].i].i;
        if ((v & 1) == 1) last = pos;
        st = v >> 1;
        if (st == 0) { W[3] = ail_box_int(pos + 1 - s); return last; }
        pos++;
    }
    if ((P[tb + st + ncls].i & 1) == 1) last = n;
    W[3] = ail_box_int(pos - s);
    return last;
}
static int64_t ail2x_ds(const ail_obj *P, const uint16_t *sb, int64_t n, int64_t pos, ail_obj *W) {
    int64_t d = P[14].i, co = P[d + 3].i, k = P[d + 2].i, qo = P[d + 8].i, ncls = P[d].i;
    int64_t s = pos;
    while (s <= n) {
        if (k > 0) {
            if (qo > 0) {
                if (s == 0 && n > 0) { if (P[qo + ncls * ncls + P[co + sb[0]].i].i == 0) s = 1; }
                while (s > 0 && s < n && P[qo + P[co + sb[s - 1]].i * ncls + P[co + sb[s]].i].i == 0) s++;
            } else {
                while (s < n && P[co + sb[s]].i < k) s++;
            }
            if (s >= n) return -1;
        }
        int64_t e = ail2x_dp(P, sb, n, s, W);
        if (e >= 0) {
            W[1] = ail_box_int(e);
            W[2] = ail_box_int(W[2].i - (W[3].i - (e - s)));
            return s;
        }
        W[2] = ail_box_int(W[2].i - W[3].i);
        if (W[2].i < 0) { W[0] = ail_box_int(s + 1); return -2; }
        s++;
    }
    return -1;
}
static int ail2x_dm(const ail_obj *P, const uint16_t *sb, int64_t n) {
    int64_t d = P[14].i, ncls = P[d].i, co = P[d + 3].i, tb = P[d + 5].i;
    int64_t st = P[P[d + 7].i + ncls].i, pos = 0;
    while (pos < n) {
        st = P[tb + st + P[co + sb[pos]].i].i >> 1;
        if (st == 0) return 0;
        pos++;
    }
    return (P[tb + st + ncls].i & 1) == 1;
}
/* a table and a text the DFA primitives can read without going out of range (they are what relib.py built) */
static int ail2x_dfa_ok(ail_obj p, ail_obj s, ail_obj no, ail_obj w, const ail_obj **P, const uint16_t **sb, int64_t *n,
                        ail_obj **W) {
    if (p.tag != AIL_T_LIST || s.tag != AIL_T_STR || no.tag != AIL_T_INT) return 0;
    const ail_vecobj *pv = (const ail_vecobj *)p.o;
    ail_str st = ail_view_to_str(s);
    if (pv->n < 17 || no.i < 0 || no.i > st.n) return 0;
    if (w.tag != AIL_T_LIST || ((ail_vecobj *)w.o)->n < 4) { if (w.tag != AIL_T_NONE) return 0; }
    *P = pv->p; *sb = st.p; *n = no.i; *W = w.tag == AIL_T_LIST ? ((ail_vecobj *)w.o)->p : NULL;
    return 1;
}
static ail_st ail2x_dp_p(ail_ctx *cx, ail_obj *out, ail_obj p, ail_obj s, ail_obj no, ail_obj s0, ail_obj w) {
    const ail_obj *P; const uint16_t *sb; int64_t n; ail_obj *W;
    if (!ail2x_dfa_ok(p, s, no, w, &P, &sb, &n, &W) || !W || s0.tag != AIL_T_INT || s0.i < 0 || s0.i > n)
        return ail_raise_c(cx, AIL_B_VALUEERROR, "re: the DFA primitive got a table or text it cannot read");
    *out = ail_box_int(ail2x_dp(P, sb, n, s0.i, W));
    return AIL_OK;
}
static ail_st ail2x_ds_p(ail_ctx *cx, ail_obj *out, ail_obj p, ail_obj s, ail_obj no, ail_obj pos, ail_obj w) {
    const ail_obj *P; const uint16_t *sb; int64_t n; ail_obj *W;
    if (!ail2x_dfa_ok(p, s, no, w, &P, &sb, &n, &W) || !W || pos.tag != AIL_T_INT || pos.i < 0
        || W[2].tag != AIL_T_INT)
        return ail_raise_c(cx, AIL_B_VALUEERROR, "re: the DFA primitive got a table or text it cannot read");
    *out = ail_box_int(ail2x_ds(P, sb, n, pos.i, W));
    return AIL_OK;
}
static ail_st ail2x_dm_p(ail_ctx *cx, ail_obj *out, ail_obj p, ail_obj s, ail_obj no) {
    const ail_obj *P; const uint16_t *sb; int64_t n; ail_obj *W;
    if (!ail2x_dfa_ok(p, s, no, (ail_obj){.tag = AIL_T_NONE}, &P, &sb, &n, &W))
        return ail_raise_c(cx, AIL_B_VALUEERROR, "re: the DFA primitive got a table or text it cannot read");
    *out = ail_box_bool(ail2x_dm(P, sb, n));
    return AIL_OK;
}
'''
