# -*- coding: utf-8 -*-
"""tint.py -- the tagged small-int type `ail_tint` of the general runtime (B2a).

`TINT` is inserted into `cruntime.OBJ2` beside the bigint runtime (bigint_core /
bigint_obj). A value is either an inline int64 (`b == NULL`) or a pointer to a
canonical heap `ail_bigobj`. The small fast path uses `__builtin_*_overflow`; a
result that does not fit calls the existing bigint routines, whose `ail_big_finish`
demotes an in-range result back to the inline form.
"""

TINT = r'''
/* ---- tagged small ints (tint.py) ------------------------------------------------------------------------- */
typedef struct ail_tint {
    int64_t i;          /* the inline payload; for a big value, clamped to int64 like AIL_T_BIG's .i */
    ail_bigobj *b;      /* NULL: small; otherwise the canonical heap bigint */
} ail_tint;

static AIL_BIGFN ail_st ail_tint__slow_divmod(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint b, int mod);
static AIL_BIGFN ail_st ail_tint__slow_shift(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint n, int left);
static inline ail_obj ail_tint_str(ail_ctx *cx, ail_tint a);
static inline ail_obj ail_tint_repr(ail_ctx *cx, ail_tint a);

static inline ail_tint ail_tint_from_int64(int64_t v) { ail_tint r; r.i = v; r.b = NULL; return r; }
static inline int ail_tint_is_small(ail_tint x) { return x.b == NULL; }
static inline int ail_tint_sign(ail_tint x) { return x.b ? x.b->sign : x.i < 0 ? -1 : x.i > 0; }
static inline int ail_tint_is_zero(ail_tint x) { return x.b ? x.b->sign == 0 : x.i == 0; }

/* a bigint magnitude that fits int64, without mutating it */
static inline int ail_tint__big_fits(const ail_bigobj *b, int64_t *out) {
    uint32_t n = b->n;
    while (n && b->d[n - 1] == 0) n--;
    if (!n) { *out = 0; return 1; }
    if (n <= 2) {
        uint64_t m = b->d[0] | (n > 1 ? (uint64_t)b->d[1] << 32 : 0);
        if (b->sign > 0 && m <= (uint64_t)INT64_MAX) { *out = (int64_t)m; return 1; }
        if (b->sign < 0 && m <= (uint64_t)INT64_MAX + 1u) { *out = (int64_t)(0 - m); return 1; }
    }
    return 0;
}

/* from an EIL int/bool/big boxed value; returns 0 when the value is not an int */
static inline int ail_tint_from_obj(ail_obj x, ail_tint *out) {
    if (x.tag == AIL_T_BIG) {
        ail_bigobj *b = AIL_BIG(x);
        int64_t v;
        if (ail_tint__big_fits(b, &v)) { out->i = v; out->b = NULL; }
        else { out->b = b; out->i = b->sign < 0 ? INT64_MIN : INT64_MAX; }
        return 1;
    }
    if (x.tag == AIL_T_INT || x.tag == AIL_T_BOOL) { out->i = x.i; out->b = NULL; return 1; }
    return 0;
}

/* to the canonical boxed form: INT when the value fits, BIG otherwise */
static inline ail_obj ail_tint_to_obj(ail_tint x) {
    if (x.b == NULL) return ail_box_int(x.i);
    int64_t v;
    if (ail_tint__big_fits(x.b, &v)) return ail_box_int(v);
    ail_obj o; memset(&o, 0, sizeof o);
    o.tag = AIL_T_BIG; o.sv.off = (int64_t)(uintptr_t)x.b;
    o.i = x.b->sign < 0 ? INT64_MIN : INT64_MAX;
    return o;
}

/* exact conversion to int64; returns 0 when the value does not fit */
static inline int ail_tint_to_int64(ail_tint x, int64_t *out) {
    if (x.b == NULL) { *out = x.i; return 1; }
    return ail_tint__big_fits(x.b, out);
}

/* ---- cold helpers: only reached when the inline path cannot answer ---- */
static AIL_BIGFN ail_tint ail_tint__slow_add(ail_ctx *cx, ail_tint a, ail_tint b) {
    ail_obj k[2]; k[0] = ail_tint_to_obj(a); k[1] = ail_tint_to_obj(b);
    AIL_ROOT_N(cx, fr, k, 2);
    ail_obj r = ail_big_addsub(cx, k[0], k[1], 0);
    ail_tint out; ail_tint_from_obj(r, &out);
    AIL_FRAME_LEAVE(cx, fr);
    return out;
}
static AIL_BIGFN ail_tint ail_tint__slow_sub(ail_ctx *cx, ail_tint a, ail_tint b) {
    ail_obj k[2]; k[0] = ail_tint_to_obj(a); k[1] = ail_tint_to_obj(b);
    AIL_ROOT_N(cx, fr, k, 2);
    ail_obj r = ail_big_addsub(cx, k[0], k[1], 1);
    ail_tint out; ail_tint_from_obj(r, &out);
    AIL_FRAME_LEAVE(cx, fr);
    return out;
}
static AIL_BIGFN ail_tint ail_tint__slow_mul(ail_ctx *cx, ail_tint a, ail_tint b) {
    ail_obj k[2]; k[0] = ail_tint_to_obj(a); k[1] = ail_tint_to_obj(b);
    AIL_ROOT_N(cx, fr, k, 2);
    ail_obj r = ail_big_mul(cx, k[0], k[1]);
    ail_tint out; ail_tint_from_obj(r, &out);
    AIL_FRAME_LEAVE(cx, fr);
    return out;
}
static AIL_BIGFN ail_tint ail_tint__slow_neg(ail_ctx *cx, ail_tint a) {
    ail_obj k[1]; k[0] = ail_tint_to_obj(a); AIL_ROOT1(cx, fr, k[0]);
    ail_obj r = ail_big_neg(cx, k[0]);
    ail_tint out; ail_tint_from_obj(r, &out);
    AIL_FRAME_LEAVE(cx, fr);
    return out;
}
/*P:bits<*/
static AIL_BIGFN ail_tint ail_tint__slow_bitop(ail_ctx *cx, ail_tint a, ail_tint b, char op) {
    ail_obj k[2]; k[0] = ail_tint_to_obj(a); k[1] = ail_tint_to_obj(b);
    AIL_ROOT_N(cx, fr, k, 2);
    ail_obj r = ail_big_bitop(cx, k[0], k[1], op);
    ail_tint out; ail_tint_from_obj(r, &out);
    AIL_FRAME_LEAVE(cx, fr);
    return out;
}
static inline ail_tint ail_tint_and(ail_ctx *cx, ail_tint a, ail_tint b) {
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1)) return ail_tint_from_int64(a.i & b.i);
    return ail_tint__slow_bitop(cx, a, b, '&');
}
static inline ail_tint ail_tint_or(ail_ctx *cx, ail_tint a, ail_tint b) {
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1)) return ail_tint_from_int64(a.i | b.i);
    return ail_tint__slow_bitop(cx, a, b, '|');
}
static inline ail_tint ail_tint_xor(ail_ctx *cx, ail_tint a, ail_tint b) {
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1)) return ail_tint_from_int64(a.i ^ b.i);
    return ail_tint__slow_bitop(cx, a, b, '^');
}
/*P|*/
/*P>*/
/*P:div<*/
static AIL_BIGFN ail_st ail_tint__slow_divmod(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint b, int mod) {
    if (ail_tint_is_zero(b))
        return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, mod ? "integer modulo by zero" : "integer division or modulo by zero");
    ail_obj k[2]; k[0] = ail_tint_to_obj(a); k[1] = ail_tint_to_obj(b);
    AIL_ROOT_N(cx, fr, k, 2);
    ail_obj q = ail_box_int(0), r = ail_box_int(0);
    ail_big_divmod(cx, mod ? NULL : &q, mod ? &r : NULL, k[0], k[1]);
    ail_tint_from_obj(mod ? r : q, out);
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/*P|*/
/*P>*/
/*P:shift<*/
static AIL_BIGFN ail_st ail_tint__slow_shift(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint n, int left) {
    if (ail_tint_sign(n) < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "negative shift count");
    if (ail_tint_is_zero(a)) { *out = ail_tint_from_int64(0); return AIL_OK; }
    ail_obj k[2]; k[0] = ail_tint_to_obj(a); k[1] = ail_tint_to_obj(n);
    AIL_ROOT_N(cx, fr, k, 2);
    ail_obj r = ail_box_int(0);
    ail_st st = ail__big_shift(cx, &r, k[0], k[1], left);
    if (st == AIL_OK) ail_tint_from_obj(r, out);
    AIL_FRAME_LEAVE(cx, fr);
    return st;
}
/*P|*/
/*P>*/

/* ---- inline operations ---- */
static inline ail_tint ail_tint_add(ail_ctx *cx, ail_tint a, ail_tint b) {
    int64_t r;
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1) && !__builtin_add_overflow(a.i, b.i, &r))
        return ail_tint_from_int64(r);
    return ail_tint__slow_add(cx, a, b);
}
static inline ail_tint ail_tint_sub(ail_ctx *cx, ail_tint a, ail_tint b) {
    int64_t r;
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1) && !__builtin_sub_overflow(a.i, b.i, &r))
        return ail_tint_from_int64(r);
    return ail_tint__slow_sub(cx, a, b);
}
static inline ail_tint ail_tint_mul(ail_ctx *cx, ail_tint a, ail_tint b) {
    int64_t r;
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1) && !__builtin_mul_overflow(a.i, b.i, &r))
        return ail_tint_from_int64(r);
    return ail_tint__slow_mul(cx, a, b);
}
static inline ail_tint ail_tint_neg(ail_ctx *cx, ail_tint a) {
    if (__builtin_expect(a.b == NULL && a.i != INT64_MIN, 1)) return ail_tint_from_int64(-a.i);
    return ail_tint__slow_neg(cx, a);
}
static inline ail_st ail_tint_floordiv(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint b) {
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1)) {
        if (__builtin_expect(b.i == 0, 0))
            return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "integer division or modulo by zero");
        if (!(a.i == INT64_MIN && b.i == -1)) {
            int64_t x = a.i, y = b.i, q = x / y, r = x % y;
            if (r != 0 && ((r < 0) != (y < 0))) q -= 1;
            *out = ail_tint_from_int64(q);
            return AIL_OK;
        }
    }
    return ail_tint__slow_divmod(cx, out, a, b, 0);
}
static inline ail_st ail_tint_mod(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint b) {
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1)) {
        if (__builtin_expect(b.i == 0, 0))
            return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "integer modulo by zero");
        if (!(a.i == INT64_MIN && b.i == -1)) {
            int64_t x = a.i, y = b.i, q = x / y, r = x % y;
            if (r != 0 && ((r < 0) != (y < 0))) { q -= 1; r += y; }
            *out = ail_tint_from_int64(r);
            return AIL_OK;
        }
    }
    return ail_tint__slow_divmod(cx, out, a, b, 1);
}
static inline ail_st ail_tint_lshift(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint n) {
    if (__builtin_expect(n.b == NULL, 1)) {
        int64_t sn = n.i;
        if (__builtin_expect(sn < 0, 0)) return ail_raise_c(cx, AIL_B_VALUEERROR, "negative shift count");
        if (__builtin_expect(a.b == NULL, 1)) {
            if (a.i == 0) { *out = ail_tint_from_int64(0); return AIL_OK; }
            if (sn < 63) {
                int64_t r;
                if (!__builtin_mul_overflow(a.i, (int64_t)((uint64_t)1 << sn), &r)) {
                    *out = ail_tint_from_int64(r);
                    return AIL_OK;
                }
            } else if (sn == 63 && a.i == -1) {
                *out = ail_tint_from_int64(INT64_MIN);
                return AIL_OK;
            }
        }
    } else if (__builtin_expect(n.b->sign < 0, 0)) {
        return ail_raise_c(cx, AIL_B_VALUEERROR, "negative shift count");
    }
    return ail_tint__slow_shift(cx, out, a, n, 1);
}
static inline ail_st ail_tint_rshift(ail_ctx *cx, ail_tint *out, ail_tint a, ail_tint n) {
    if (__builtin_expect(n.b == NULL, 1)) {
        int64_t sn = n.i;
        if (__builtin_expect(sn < 0, 0)) return ail_raise_c(cx, AIL_B_VALUEERROR, "negative shift count");
        if (__builtin_expect(a.b == NULL, 1)) {
            if (sn >= 63) { *out = ail_tint_from_int64(a.i < 0 ? -1 : 0); return AIL_OK; }
            *out = ail_tint_from_int64(a.i >> sn);
            return AIL_OK;
        }
    } else if (__builtin_expect(n.b->sign < 0, 0)) {
        return ail_raise_c(cx, AIL_B_VALUEERROR, "negative shift count");
    }
    return ail_tint__slow_shift(cx, out, a, n, 0);
}
static inline int ail_tint_cmp(ail_tint a, ail_tint b) {
    if (__builtin_expect(a.b == NULL && b.b == NULL, 1)) return a.i < b.i ? -1 : a.i > b.i ? 1 : 0;
    return ail_int_cmp(ail_tint_to_obj(a), ail_tint_to_obj(b));
}
static inline int ail_tint_eq(ail_tint a, ail_tint b) { return ail_tint_cmp(a, b) == 0; }
static inline int ail_tint_lt(ail_tint a, ail_tint b) { return ail_tint_cmp(a, b) < 0; }
static inline int ail_tint_le(ail_tint a, ail_tint b) { return ail_tint_cmp(a, b) <= 0; }

/*P:text<*/
static inline ail_obj ail_tint_str(ail_ctx *cx, ail_tint a) {
    if (a.b == NULL) return ail_str_of_int(cx, a.i);
    return ail_int_to_str(cx, ail_tint_to_obj(a));
}
/*P|*/
/*P>*/
/*P:text<*/
static inline ail_obj ail_tint_repr(ail_ctx *cx, ail_tint a) { return ail_tint_str(cx, a); }
/*P|*/
/*P>*/
'''
