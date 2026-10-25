# -*- coding: utf-8 -*-
"""statbrt.py -- the numeric loops of prelude_genlib.py's statistics on the general (boxed) path, in C (fragment 'sta'
of safetyrt.py).

statistics.mean / variance / stdev ... on the general path are Python source that sums exactly with the partials of
math.fsum and keeps the squares in two doubles; every step of those loops was a chain of boxed float operations (a
boxed float is a heap object), and the profile of the gdev programs that use statistics put 20-40% of their
instructions there. The loops are primitives here, the same IEEE double operations in the same order (the pragma
below keeps a compiler that has fused multiply-add from contracting them), so the doubles that come out are the bits
the Python source gives:

* _ail_st_finite(xs)           -> every x - x == 0.0
* _ail_st_partials(xs)         -> the list of non-overlapping partials (math.fsum's recipe)
* _ail_st_ssd_dd(xs, ch, cl)   -> (hi, lo): the sum of (x - c)**2 as two doubles
* _ail_st_ints_sums(xs)        -> (sum, sum of squares) of ints that fit, else None
* _ail_st_isint(xs)            -> every element is an int
* _ail_st_badat(xs)            -> the index of the first element that is neither int nor float, else -1

A program that does not use statistics gets the C it always had.
"""

PRIMS = {
    '_ail_st_finite': ('ail2q_finite(cx, &{t}, {a0})', 1),
    '_ail_st_partials': ('ail2q_partials(cx, &{t}, {a0})', 1),
    '_ail_st_ssd_dd': ('ail2q_ssd(cx, &{t}, {a0}, {a1}, {a2})', 3),
    '_ail_st_ints_sums': ('ail2q_ints_sums(cx, &{t}, {a0})', 1),
    '_ail_st_isint': ('ail2q_isint(cx, &{t}, {a0})', 1),
    '_ail_st_badat': ('ail2q_badat(cx, &{t}, {a0})', 1),
}

# the Python functions the primitives replace (genlib._native_source takes them out of the prelude)
NATIVE = ('_ail_st_finite', '_ail_st_partials', '_ail_st_ssd_dd', '_ail_st_ints_sums', '_ail_st_isint', '_ail_st_data')

WRAPPERS = '''
def _ail_st_data(data):
    xs = list(data)
    k = _ail_st_badat(xs)
    if k >= 0:
        raise TypeError("can't convert type '" + type(xs[k]).__name__ + "' to numerator/denominator")
    return xs
'''

STA = r'''
/* ---- statistics on the general path (statbrt.py) ---- */
#ifndef AIL2Z_PAUSE
#define AIL2Z_PAUSE(cx) size_t ail2z_saved_ = (cx)->gc_threshold; (cx)->gc_threshold = (size_t)-1 >> 1
#define AIL2Z_RESUME(cx) (cx)->gc_threshold = ail2z_saved_
#endif
#include <math.h>
#pragma GCC push_options
#pragma GCC optimize ("fp-contract=off")
static ail_st ail2q_vec(ail_ctx *cx, ail_obj x, ail_vecobj **v) {
    if (x.tag != AIL_T_LIST && x.tag != AIL_T_TUPLE) {
        char buf[96]; snprintf(buf, sizeof buf, "statistics: expected a list, not %s", ail_type_name(x.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
    }
    *v = (ail_vecobj *)x.o;
    return AIL_OK;
}
/* the element as a double (float(v)); 0 when it is no number */
static inline int ail2q_dbl(ail_obj x, double *d) {
    if (x.tag == AIL_T_FLOAT) { *d = ail_float_val(x); return 1; }
    if (x.tag == AIL_T_INT || x.tag == AIL_T_BOOL) { *d = (double)x.i; return 1; }
    return 0;
}
static ail_st ail2q_nonum(ail_ctx *cx, ail_obj x) {
    char buf[128]; snprintf(buf, sizeof buf, "float() argument must be a string or a real number, not '%s'", ail_type_name(x.tag));
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
static ail_st ail2q_finite(ail_ctx *cx, ail_obj *out, ail_obj xs) {
    ail_vecobj *v; ail_st st = ail2q_vec(cx, xs, &v); if (st != AIL_OK) return st;
    for (int64_t i = 0; i < v->n; i++) {
        ail_obj x = v->p[i];
        if (x.tag == AIL_T_FLOAT) {
            double d = ail_float_val(x);
            if (d - d != 0.0) { *out = ail_box_bool(0); return AIL_OK; }
        } else if (x.tag != AIL_T_INT && x.tag != AIL_T_BOOL) {
            char buf[128]; snprintf(buf, sizeof buf, "unsupported operand type(s) for -: '%s' and '%s'", ail_type_name(x.tag), ail_type_name(x.tag));
            return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
        }
    }
    *out = ail_box_bool(1);
    return AIL_OK;
}
static ail_st ail2q_isint(ail_ctx *cx, ail_obj *out, ail_obj xs) {
    ail_vecobj *v; ail_st st = ail2q_vec(cx, xs, &v); if (st != AIL_OK) return st;
    for (int64_t i = 0; i < v->n; i++)
        if (v->p[i].tag != AIL_T_INT && v->p[i].tag != AIL_T_BOOL) { *out = ail_box_bool(0); return AIL_OK; }
    *out = ail_box_bool(1);
    return AIL_OK;
}
static ail_st ail2q_badat(ail_ctx *cx, ail_obj *out, ail_obj xs) {
    ail_vecobj *v; ail_st st = ail2q_vec(cx, xs, &v); if (st != AIL_OK) return st;
    for (int64_t i = 0; i < v->n; i++) {
        uint8_t t = v->p[i].tag;
        if (t != AIL_T_INT && t != AIL_T_BOOL && t != AIL_T_FLOAT) { *out = ail_box_int(i); return AIL_OK; }
    }
    *out = ail_box_int(-1);
    return AIL_OK;
}
static ail_st ail2q_partials(ail_ctx *cx, ail_obj *out, ail_obj xs) {
    ail_vecobj *v; ail_st st = ail2q_vec(cx, xs, &v); if (st != AIL_OK) return st;
    int64_t cap = 16, np = 0;
    double *pt = (double *)ail_xmalloc((size_t)cap * sizeof(double));
    for (int64_t j = 0; j < v->n; j++) {
        double x;
        if (!ail2q_dbl(v->p[j], &x)) { free(pt); return ail2q_nonum(cx, v->p[j]); }
        int64_t k = 0;
        for (int64_t i = 0; i < np; i++) {
            double y = pt[i];
            if (fabs(x) < fabs(y)) { double t = x; x = y; y = t; }
            double hi = x + y;
            double lo = y - (hi - x);
            if (lo != 0.0) pt[k++] = lo;
            x = hi;
        }
        if (k >= cap) { cap *= 2; pt = (double *)realloc(pt, (size_t)cap * sizeof(double)); if (!pt) return ail_raise_c(cx, AIL_B_RUNTIMEERROR, "out of memory"); }
        if (x != 0.0) pt[k++] = x;      /* math.fsum drops a zero: fsum([-0.0]) is 0.0 */
        np = k;
    }
    AIL2Z_PAUSE(cx);
    ail_obj lst = ail_list_new(cx);
    AIL_ROOT1(cx, fr, lst);
    ail_vecobj *r = (ail_vecobj *)lst.o;
    ail_vec_reserve(cx, r, np ? np : 1);
    for (int64_t i = 0; i < np; i++) r->p[r->n++] = ail_box_float(cx, pt[i]);
    AIL_FRAME_LEAVE(cx, fr);
    AIL2Z_RESUME(cx);
    free(pt);
    *out = lst;
    return AIL_OK;
}
static inline void ail2q_twosum(double a, double b, double *s, double *e) {
    double sum = a + b;
    double bb = sum - a;
    *e = (a - (sum - bb)) + (b - bb);
    *s = sum;
}
static inline void ail2q_twoprod(double a, double b, double *p, double *e) {
    double pr = a * b;
    double c = 134217729.0 * a;
    double ah = c - (c - a);
    double al = a - ah;
    c = 134217729.0 * b;
    double bh = c - (c - b);
    double bl = b - bh;
    *e = ((ah * bh - pr) + ah * bl + al * bh) + al * bl;
    *p = pr;
}
static ail_st ail2q_ssd(ail_ctx *cx, ail_obj *out, ail_obj xs, ail_obj cho, ail_obj clo) {
    ail_vecobj *v; ail_st st = ail2q_vec(cx, xs, &v); if (st != AIL_OK) return st;
    double ch, cl;
    if (!ail2q_dbl(cho, &ch)) return ail2q_nonum(cx, cho);
    if (!ail2q_dbl(clo, &cl)) return ail2q_nonum(cx, clo);
    double ah = 0.0, al = 0.0;
    for (int64_t i = 0; i < v->n; i++) {
        double x;
        if (!ail2q_dbl(v->p[i], &x)) return ail2q_nonum(cx, v->p[i]);
        double dh, t1;
        ail2q_twosum(x, -ch, &dh, &t1);
        double dl = t1 - cl;
        double s0, s1;
        ail2q_twosum(dh, dl, &s0, &s1);
        dh = s0; dl = s1;
        double p, pe;
        ail2q_twoprod(dh, dh, &p, &pe);
        double e = pe + 2.0 * dh * dl;
        double u0, u1;
        ail2q_twosum(ah, p, &u0, &u1);
        double w = u1 + (al + e);
        double z0, z1;
        ail2q_twosum(u0, w, &z0, &z1);
        ah = z0; al = z1;
    }
    AIL2Z_PAUSE(cx);
    ail_obj it[2] = { ail_box_none(), ail_box_none() };
    AIL_ROOT_N(cx, fr, it, 2);
    it[0] = ail_box_float(cx, ah);
    it[1] = ail_box_float(cx, al);
    *out = ail_tuple_new(cx, it, 2);
    AIL_FRAME_LEAVE(cx, fr);
    AIL2Z_RESUME(cx);
    return AIL_OK;
}
static ail_st ail2q_ints_sums(ail_ctx *cx, ail_obj *out, ail_obj xs) {
    ail_vecobj *v; ail_st st = ail2q_vec(cx, xs, &v); if (st != AIL_OK) return st;
    int64_t n = v->n, big = 0;
    for (int64_t i = 0; i < n; i++) {
        ail_obj x = v->p[i];
        if (x.tag != AIL_T_INT && x.tag != AIL_T_BOOL) return ail2q_nonum(cx, x);
        int64_t a = x.i < 0 ? -x.i : x.i;
        if (x.i == INT64_MIN) a = INT64_MAX;
        if (a > big) big = a;
    }
    if (big > 1000000000 || n > 1000000000 || (__int128)big * n > 3000000000) { *out = ail_box_none(); return AIL_OK; }
    int64_t s = 0, q = 0;
    for (int64_t i = 0; i < n; i++) { int64_t x = v->p[i].i; s += x; q += x * x; }
    ail_obj it[2]; it[0] = ail_box_int(s); it[1] = ail_box_int(q);
    *out = ail_tuple_new(cx, it, 2);
    return AIL_OK;
}
#pragma GCC pop_options
'''
