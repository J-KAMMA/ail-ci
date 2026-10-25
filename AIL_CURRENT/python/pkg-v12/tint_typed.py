# -*- coding: utf-8 -*-
"""tint_typed.py -- the tagged small int `ail_tint` for the typed (int64) path (B2b).

The typed runtime has no GC: a big value is a malloc'd magnitude, freed only by the process exit.
The inline form is the common case and never allocates.  `add/sub/mul/floordiv/mod/shift/neg` use
the `__builtin_*_overflow` fast path and fall back to the shared bigint core (`bigint_core.CORE`).
A result that fits int64 is demoted back to the inline form, so `x - x` is a plain small int.
"""

TINT = r'''
/* ---- tagged small ints for the typed path (tint_typed.py) ------------------------------------------------ */
typedef struct { int32_t sign; uint32_t n; ail_limb d[1]; } ail_tbig;
typedef struct ail_tint { int64_t i; ail_tbig *b; } ail_tint;
static inline int ail_tint_to_int64(ail_tint x, int64_t *out);

static inline ail_tint ail_tint_from_int64(int64_t v) { ail_tint r; r.i = v; r.b = NULL; return r; }
static inline int ail_tint_is_small(ail_tint x) { return x.b == NULL; }
static inline int ail_tint_sign(ail_tint x) { return x.b ? x.b->sign : x.i < 0 ? -1 : x.i > 0; }
static inline int ail_tint_is_zero(ail_tint x) { return x.b ? x.b->sign == 0 : x.i == 0; }

static inline int ail_tint__fits(const ail_tbig *b, int64_t *out) {
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
static inline ail_tint ail_tint_from_big(ail_tbig *b) {
    ail_tint r; r.b = b; r.i = b->sign < 0 ? INT64_MIN : INT64_MAX; return r;
}
static inline ail_tint ail_tint_demote(ail_tbig *b, int sign) {
    b->n = (uint32_t)ail_bn_norm(b->d, b->n);
    if (b->n == 0) { free(b); return ail_tint_from_int64(0); }
    b->sign = sign < 0 ? -1 : 1;
    int64_t v;
    if (ail_tint__fits(b, &v)) { free(b); return ail_tint_from_int64(v); }
    return ail_tint_from_big(b);
}
static ail_tbig *ail_tint__new(size_t cap) {
    if (cap > ((size_t)1 << 29)) ail_die("MemoryError: integer too large");
    ail_tbig *b = (ail_tbig *)malloc(sizeof(ail_tbig) + (cap ? cap - 1 : 0) * sizeof(ail_limb));
    if (!b) ail_die("out of memory");
    return b;
}
typedef struct { int sign; size_t n; const ail_limb *d; ail_limb tmp[2]; } ail_tbv;
static inline void ail_tbv_of(ail_tbv *v, ail_tint x) {
    if (x.b) { v->sign = x.b->sign; v->n = x.b->n; v->d = x.b->d; return; }
    int64_t i = x.i;
    uint64_t m = i < 0 ? 0 - (uint64_t)i : (uint64_t)i;
    v->sign = i < 0 ? -1 : i > 0; v->tmp[0] = (ail_limb)m; v->tmp[1] = (ail_limb)(m >> 32);
    v->n = v->tmp[1] ? 2 : v->tmp[0] ? 1 : 0; v->d = v->tmp;
}
static AIL_BIGFN ail_tint ail_tint__slow_add(ail_tint a, ail_tint b) {
    ail_tbv x, y; ail_tbv_of(&x, a); ail_tbv_of(&y, b);
    size_t cap = (x.n > y.n ? x.n : y.n) + 1, n; int sign;
    ail_tbig *r = ail_tint__new(cap); ail_limb *o = r->d;
    if (x.sign == y.sign) { n = ail_bn_add(o, x.d, x.n, y.d, y.n); sign = x.sign; }
    else {
        int c = ail_bn_cmp(x.d, x.n, y.d, y.n);
        if (c == 0) { n = 0; sign = 0; }
        else if (c > 0) { n = ail_bn_sub(o, x.d, x.n, y.d, y.n); sign = x.sign; }
        else { n = ail_bn_sub(o, y.d, y.n, x.d, x.n); sign = y.sign; }
    }
    r->n = (uint32_t)n;
    return ail_tint_demote(r, sign);
}
static AIL_BIGFN ail_tint ail_tint__slow_sub(ail_tint a, ail_tint b) {
    ail_tbv x, y; ail_tbv_of(&x, a); ail_tbv_of(&y, b); y.sign = -y.sign;
    size_t cap = (x.n > y.n ? x.n : y.n) + 1, n; int sign;
    ail_tbig *r = ail_tint__new(cap); ail_limb *o = r->d;
    if (x.sign == y.sign) { n = ail_bn_add(o, x.d, x.n, y.d, y.n); sign = x.sign; }
    else {
        int c = ail_bn_cmp(x.d, x.n, y.d, y.n);
        if (c == 0) { n = 0; sign = 0; }
        else if (c > 0) { n = ail_bn_sub(o, x.d, x.n, y.d, y.n); sign = x.sign; }
        else { n = ail_bn_sub(o, y.d, y.n, x.d, x.n); sign = y.sign; }
    }
    r->n = (uint32_t)n;
    return ail_tint_demote(r, sign);
}
static AIL_BIGFN ail_tint ail_tint__slow_mul(ail_tint a, ail_tint b) {
    ail_tbv x, y; ail_tbv_of(&x, a); ail_tbv_of(&y, b);
    if (!x.sign || !y.sign) return ail_tint_from_int64(0);
    ail_tbig *r = ail_tint__new(x.n + y.n);
    size_t n = ail_bn_mul(r->d, x.d, x.n, y.d, y.n);
    r->n = (uint32_t)n;
    return ail_tint_demote(r, x.sign * y.sign);
}
static AIL_BIGFN ail_tint ail_tint__slow_neg(ail_tint a) {
    if (!a.b) { if (a.i == INT64_MIN) { /* fall through */ } else return ail_tint_from_int64(-a.i); }
    ail_tbv x; ail_tbv_of(&x, a);
    ail_tbig *r = ail_tint__new(x.n ? x.n : 1);
    memcpy(r->d, x.d, x.n * sizeof(ail_limb));
    r->n = (uint32_t)x.n;
    return ail_tint_demote(r, -x.sign);
}
static AIL_BIGFN int ail_tint__divmod(ail_tint *qo, ail_tint *ro, ail_tint a, ail_tint b, int mod) {
    if (ail_tint_is_zero(b)) ail_die(mod ? "integer modulo by zero" : "integer division or modulo by zero");
    ail_tbv x, y; ail_tbv_of(&x, a); ail_tbv_of(&y, b);
    size_t qcap = (x.n >= y.n ? x.n - y.n : 0) + 2, rcap = y.n + 1;
    ail_limb *qs = (ail_limb *)malloc((qcap + rcap) * sizeof(ail_limb));
    if (!qs) ail_die("out of memory");
    ail_limb *rs = qs + qcap;
    size_t qn = 0, rn = 0;
    ail_bn_divmod(qs, &qn, rs, &rn, x.d, x.n, y.d, y.n);
    int diff = x.sign * y.sign < 0;
    if (diff && rn) {
        qn = ail_bn_add(qs, qs, qn, (const ail_limb[]){1}, 1);
        rn = ail_bn_sub(rs, y.d, y.n, rs, rn);
    }
    if (!mod) {
        ail_tbig *r = ail_tint__new(qn ? qn : 1);
        memcpy(r->d, qs, qn * sizeof(ail_limb)); r->n = (uint32_t)qn;
        *qo = ail_tint_demote(r, diff ? -1 : 1);
    } else {
        ail_tbig *r = ail_tint__new(rn ? rn : 1);
        if (rn) memcpy(r->d, rs, rn * sizeof(ail_limb));
        r->n = (uint32_t)rn;
        *ro = ail_tint_demote(r, y.sign);
    }
    free(qs);
    return 1;
}
static AIL_BIGFN int ail_tint__shift(ail_tint *out, ail_tint a, ail_tint n, int left) {
    if (ail_tint_sign(n) < 0) ail_die("negative shift count");
    int64_t sn;
    if (!ail_tint_to_int64(n, &sn)) {
        /* a right shift by a count beyond int64 keeps only the sign: 1 >> 2**70 is 0, -1 >> 2**70 is -1 */
        if (!left) { *out = ail_tint_from_int64(ail_tint_sign(a) < 0 ? -1 : 0); return 1; }
        ail_die("OverflowError: too many digits in integer");
    }
    if (ail_tint_is_zero(a)) { *out = ail_tint_from_int64(0); return 1; }
    ail_tbv x; ail_tbv_of(&x, a);
    if (left) {
        size_t cap = x.n + (size_t)(sn >> 5) + 1;
        ail_tbig *r = ail_tint__new(cap);
        size_t nn = ail_bn_shl(r->d, x.d, x.n, (uint64_t)sn);
        r->n = (uint32_t)nn;
        *out = ail_tint_demote(r, x.sign);
    } else {
        ail_tbig *r = ail_tint__new(x.n + 1);
        size_t nn = ail_bn_shr(r->d, x.d, x.n, (uint64_t)sn);
        r->n = (uint32_t)nn;
        if (x.sign < 0) {
            /* Python floors: a negative value shifted right rounds toward -infinity, so add one to the
               magnitude when any bit below the shift was dropped. */
            size_t w = (size_t)((uint64_t)sn >> 5), b = (size_t)((uint64_t)sn & 31);
            int gone = 0;
            for (size_t i = 0; i < w && i < x.n; i++) if (x.d[i]) { gone = 1; break; }
            if (!gone && b && w < x.n) gone = (x.d[w] & ((1u << b) - 1u)) != 0;
            if (gone) {
                nn = ail_bn_add(r->d, r->d, nn, (const ail_limb[]){1}, 1);
                r->n = (uint32_t)nn;
            }
        }
        *out = ail_tint_demote(r, x.sign);
    }
    return 1;
}
static inline ail_tint ail_tint_add(ail_tint a, ail_tint b) {
    int64_t r;
    if (__builtin_expect(!a.b && !b.b, 1) && !__builtin_add_overflow(a.i, b.i, &r)) return ail_tint_from_int64(r);
    return ail_tint__slow_add(a, b);
}
static inline ail_tint ail_tint_sub(ail_tint a, ail_tint b) {
    int64_t r;
    if (__builtin_expect(!a.b && !b.b, 1) && !__builtin_sub_overflow(a.i, b.i, &r)) return ail_tint_from_int64(r);
    return ail_tint__slow_sub(a, b);
}
static inline ail_tint ail_tint_mul(ail_tint a, ail_tint b) {
    int64_t r;
    if (__builtin_expect(!a.b && !b.b, 1) && !__builtin_mul_overflow(a.i, b.i, &r)) return ail_tint_from_int64(r);
    return ail_tint__slow_mul(a, b);
}
static inline ail_tint ail_tint_neg(ail_tint a) {
    if (__builtin_expect(!a.b && a.i != INT64_MIN, 1)) return ail_tint_from_int64(-a.i);
    return ail_tint__slow_neg(a);
}
static inline ail_tint ail_tint_floordiv(ail_tint a, ail_tint b) {
    if (__builtin_expect(!a.b && !b.b, 1)) {
        if (__builtin_expect(b.i == 0, 0)) ail_die("integer division or modulo by zero");
        if (!(a.i == INT64_MIN && b.i == -1)) {
            int64_t x = a.i, y = b.i, q = x / y, r = x % y;
            if (r != 0 && ((r < 0) != (y < 0))) q -= 1;
            return ail_tint_from_int64(q);
        }
    }
    ail_tint o; ail_tint__divmod(&o, NULL, a, b, 0); return o;
}
static inline ail_tint ail_tint_mod(ail_tint a, ail_tint b) {
    if (__builtin_expect(!a.b && !b.b, 1)) {
        if (__builtin_expect(b.i == 0, 0)) ail_die("integer modulo by zero");
        if (!(a.i == INT64_MIN && b.i == -1)) {
            int64_t x = a.i, y = b.i, q = x / y, r = x % y;
            if (r != 0 && ((r < 0) != (y < 0))) { q -= 1; r += y; }
            return ail_tint_from_int64(r);
        }
    }
    ail_tint o; ail_tint__divmod(NULL, &o, a, b, 1); return o;
}
static inline ail_tint ail_tint_mod_pos_i64(ail_tint a, int64_t b) {
    if (__builtin_expect(!a.b, 1)) {
        if (__builtin_expect(b == 0, 0)) ail_die("integer modulo by zero");
        return ail_tint_from_int64(a.i % b);
    }
    return ail_tint_mod(a, ail_tint_from_int64(b));
}
static inline int64_t ail_tint_mod_pos_i64_i64(ail_tint a, int64_t b) {
    if (__builtin_expect(!a.b, 1)) {
        if (__builtin_expect(b == 0, 0)) ail_die("integer modulo by zero");
        return a.i % b;
    }
    ail_tint m = ail_tint_mod(a, ail_tint_from_int64(b));
    int64_t v;
    if (!ail_tint_to_int64(m, &v)) ail_die("integer overflow");
    return v;
}
static inline int64_t ail_tint_mod_i64_i64(ail_tint a, int64_t b) {
    if (__builtin_expect(!a.b, 1)) {
        if (__builtin_expect(b == 0, 0)) ail_die("integer modulo by zero");
        if (b > 0) {
            int64_t r = a.i % b;
            if (r < 0) r += b;
            return r;
        }
        if (!(a.i == INT64_MIN && b == -1)) {
            int64_t r = a.i % b;
            if (r != 0 && ((r < 0) != (b < 0))) r += b;
            return r;
        }
    }
    ail_tint m = ail_tint_mod(a, ail_tint_from_int64(b));
    int64_t v;
    if (!ail_tint_to_int64(m, &v)) ail_die("integer overflow");
    return v;
}
static inline ail_tint ail_tint_add_i64(ail_tint a, int64_t b) {
    int64_t r;
    if (__builtin_expect(!a.b, 1) && !__builtin_add_overflow(a.i, b, &r)) return ail_tint_from_int64(r);
    return ail_tint__slow_add(a, ail_tint_from_int64(b));
}
static inline ail_tint ail_tint_sub_i64(ail_tint a, int64_t b) {
    int64_t r;
    if (__builtin_expect(!a.b, 1) && !__builtin_sub_overflow(a.i, b, &r)) return ail_tint_from_int64(r);
    return ail_tint__slow_sub(a, ail_tint_from_int64(b));
}
static inline ail_tint ail_tint_mul_i64(ail_tint a, int64_t b) {
    int64_t r;
    if (__builtin_expect(!a.b, 1) && !__builtin_mul_overflow(a.i, b, &r)) return ail_tint_from_int64(r);
    return ail_tint__slow_mul(a, ail_tint_from_int64(b));
}
static inline ail_tint ail_tint_floordiv_i64(ail_tint a, int64_t b) {
    if (__builtin_expect(!a.b, 1)) {
        if (__builtin_expect(b == 0, 0)) ail_die("integer division or modulo by zero");
        if (b > 0) {
            int64_t q = a.i / b;
            if (a.i % b < 0) q -= 1;
            return ail_tint_from_int64(q);
        }
        if (!(a.i == INT64_MIN && b == -1)) {
            int64_t q = a.i / b, r = a.i % b;
            if (r != 0 && ((r < 0) != (b < 0))) q -= 1;
            return ail_tint_from_int64(q);
        }
    }
    return ail_tint_floordiv(a, ail_tint_from_int64(b));
}
static inline ail_tint ail_tint_mod_i64(ail_tint a, int64_t b) {
    if (__builtin_expect(!a.b, 1)) {
        if (__builtin_expect(b == 0, 0)) ail_die("integer modulo by zero");
        if (b > 0) {
            int64_t r = a.i % b;
            if (r < 0) r += b;
            return ail_tint_from_int64(r);
        }
        if (!(a.i == INT64_MIN && b == -1)) {
            int64_t r = a.i % b;
            if (r != 0 && ((r < 0) != (b < 0))) r += b;
            return ail_tint_from_int64(r);
        }
    }
    return ail_tint_mod(a, ail_tint_from_int64(b));
}
static inline ail_tint ail_tint_lshift(ail_tint a, ail_tint n) {
    int64_t r;
    if (__builtin_expect(!a.b && !n.b, 1)) {
        if (__builtin_expect(n.i < 0, 0)) ail_die("negative shift count");
        if (n.i < 63 && !__builtin_mul_overflow(a.i, (int64_t)((uint64_t)1 << n.i), &r))
            return ail_tint_from_int64(r);
    }
    ail_tint o; ail_tint__shift(&o, a, n, 1); return o;
}
static inline ail_tint ail_tint_rshift(ail_tint a, ail_tint n) {
    if (__builtin_expect(!a.b && !n.b, 1)) {
        if (__builtin_expect(n.i < 0, 0)) ail_die("negative shift count");
        if (n.i < 63) return ail_tint_from_int64(a.i >> n.i);
        return ail_tint_from_int64(a.i < 0 ? -1 : 0);
    }
    ail_tint o; ail_tint__shift(&o, a, n, 0); return o;
}
static inline ail_tint ail_tint_mod2(ail_tint a) {
    return ail_tint_from_int64(a.b ? (int64_t)(a.b->d[0] & 1u) : (a.i & 1));
}

/* `a ** n` for a non-negative int exponent. Exponentiation by squaring through ail_tint_mul, so
   a module variable in tint storage can grow past int64 (the IR's `tint.pow`). A negative
   exponent is not an int power (Python returns a float); the typed path's caller only emits this
   for a non-negative constant exponent. */
static AIL_BIGFN ail_tint ail_tint_pow(ail_tint a, ail_tint n) {
    int64_t e;
    if (!ail_tint_to_int64(n, &e) || e < 0) ail_die("integer overflow");
    ail_tint r = ail_tint_from_int64(1), b = a;
    while (e) {
        if (e & 1) r = ail_tint_mul(r, b);
        e >>= 1;
        if (e) b = ail_tint_mul(b, b);
    }
    return r;
}

static inline int ail_tint_cmp(ail_tint a, ail_tint b) {
    if (__builtin_expect(!a.b && !b.b, 1)) return a.i < b.i ? -1 : a.i > b.i ? 1 : 0;
    ail_tbv x, y; ail_tbv_of(&x, a); ail_tbv_of(&y, b);
    if (x.sign != y.sign) return x.sign < y.sign ? -1 : 1;
    int c = ail_bn_cmp(x.d, x.n, y.d, y.n);
    return x.sign < 0 ? -c : c;
}
static inline int ail_tint_eq_i64(ail_tint a, int64_t c) { return !a.b && a.i == c; }
static inline int ail_tint_ne_i64(ail_tint a, int64_t c) { return a.b || a.i != c; }
static inline int ail_tint_lt_i64(ail_tint a, int64_t c) { return a.b ? a.b->sign < 0 : a.i < c; }
static inline int ail_tint_le_i64(ail_tint a, int64_t c) { return a.b ? a.b->sign < 0 : a.i <= c; }
static inline int ail_tint_eq(ail_tint a, ail_tint b) { return ail_tint_cmp(a, b) == 0; }
static inline int ail_tint_lt(ail_tint a, ail_tint b) { return ail_tint_cmp(a, b) < 0; }
static inline int ail_tint_le(ail_tint a, ail_tint b) { return ail_tint_cmp(a, b) <= 0; }
static inline int ail_tint_to_int64(ail_tint x, int64_t *out) {
    if (!x.b) { *out = x.i; return 1; }
    return ail_tint__fits(x.b, out);
}
static inline int64_t ail_tint_i64(ail_tint x) {
    int64_t v;
    if (!ail_tint_to_int64(x, &v)) ail_die("integer overflow");
    return v;
}
static inline int64_t ail_tint_i64_sat(ail_tint x) {
    int64_t v;
    if (ail_tint_to_int64(x, &v)) return v;
    return x.b->sign < 0 ? INT64_MIN : INT64_MAX;
}
static inline double ail_tint_double(ail_tint x) {
    if (!x.b) return (double)x.i;
    int ovf;
    return ail_bn_to_double(x.b->d, x.b->n, x.b->sign < 0, &ovf);
}
static AIL_BIGFN ail_str ail_tint_base_str(ail_sarena *A, ail_tint x, int sh, const char *pfx) {
    ail_tbv v; ail_tbv_of(&v, x);
    int neg = v.sign < 0;
    size_t bits = v.n ? (size_t)(v.n - 1) * 32 + (size_t)(32 - __builtin_clz(v.d[v.n - 1])) : 0;
    size_t nd = bits ? (bits + (size_t)sh - 1) / (size_t)sh : 1;
    size_t len = (size_t)(neg ? 1 : 0) + 2 + nd;
    uint8_t *q = ail_sarena_alloc(A, (int64_t)len);
    size_t k = 0;
    if (neg) q[k++] = '-';
    q[k++] = (uint8_t)pfx[0];
    q[k++] = (uint8_t)pfx[1];
    const char *digits = "0123456789abcdef";
    uint32_t mask = (uint32_t)((1u << sh) - 1u);
    for (size_t i = 0; i < nd; i++) {
        size_t bp = (nd - 1 - i) * (size_t)sh;
        size_t w = bp >> 5, off = bp & 31;
        uint64_t word = w < v.n ? v.d[w] : 0;
        if (w + 1 < v.n) word |= (uint64_t)v.d[w + 1] << 32;
        q[k++] = (uint8_t)digits[(word >> off) & mask];
    }
    return (ail_str){q, (int64_t)len, 0};
}
static AIL_BIGFN ail_str ail_tint_bin(ail_sarena *A, ail_tint x) { return ail_tint_base_str(A, x, 1, "0b"); }
static AIL_BIGFN ail_str ail_tint_oct(ail_sarena *A, ail_tint x) { return ail_tint_base_str(A, x, 3, "0o"); }
static AIL_BIGFN ail_str ail_tint_hex(ail_sarena *A, ail_tint x) { return ail_tint_base_str(A, x, 4, "0x"); }

static inline ail_str ail_tint_str(ail_sarena *A, ail_tint x) {
    if (!x.b) return ail_str_from_int(A, x.i);
    size_t cap = 10 * (size_t)x.b->n + 3;
    char *buf = (char *)malloc(cap);
    if (!buf) ail_die("out of memory");
    size_t nd = ail_bn_to_dec(buf, x.b->d, x.b->n);
    int64_t n = (int64_t)nd + (x.b->sign < 0 ? 1 : 0);
    uint8_t *q = ail_sarena_alloc(A, n);
    int64_t k = 0;
    if (x.b->sign < 0) q[k++] = '-';
    for (size_t i = 0; i < nd; i++) q[k++] = (uint8_t)buf[i];
    free(buf);
    return (ail_str){q, n, 0};
}
'''
