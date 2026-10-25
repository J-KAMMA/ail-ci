# -*- coding: utf-8 -*-
"""bigint_obj.py -- the object layer of the big integers in the general runtime (docs/design/BIGINT.md).

EARLY goes into `cruntime.OBJ2` before the truthiness / equality / hashing section (the operators call it);
LATE goes after the builtins `abs` `round` `divmod` `pow` and the math functions (it builds tuples and uses
the string builders). Both rely on `bigint_core.CORE`, which is inserted ahead of them.

Every function takes operands that are INT, BOOL or BIG `ail_obj`s and returns a canonical result: an int64
is always the small form (`ail_big_finish`). The operands stay rooted by the caller, and a result is allocated
with its operands rooted as well (`ail_big_alloc`), the C84 discipline of the rest of the runtime.
"""

EARLY = r'''
/* ---- big integers: the object layer (bigint_obj.py) ------------------------------------------------------ */
typedef struct { ail_gcobj hdr; int32_t sign; uint32_t n; ail_limb d[1]; } ail_bigobj;
/* A BIG value keeps its heap object in the second word (`sv.off`) and, in the first word, where every int64 reader looks
   (`.i`), the value clamped to int64: code that reads `.i` without checking the tag (an index, a range bound, a size) then
   sees INT64_MAX / INT64_MIN, an out-of-range number, rather than an address. */
#define AIL_BIG(x) ((ail_bigobj *)(uintptr_t)(x).sv.off)
typedef struct { int sign; size_t n; const ail_limb *d; ail_limb tmp[2]; } ail_bv;   /* a view; do not copy */
static inline int ail__isint(uint8_t t) { return t == AIL_T_INT || t == AIL_T_BOOL || t == AIL_T_BIG; }
/* Prototypes of the pieces biggate.py may leave out: the definitions below are conditional, and an
   unused caller (a math helper the program never names) must still see the right return type. */
static AIL_BIGFN void ail_big_divmod(ail_ctx *cx, ail_obj *q, ail_obj *r, ail_obj a, ail_obj b);
static AIL_BIGFN ail_obj ail_big_shl(ail_ctx *cx, ail_obj a, int64_t n);
static AIL_BIGFN ail_obj ail_big_shr(ail_ctx *cx, ail_obj a, int64_t n);
static AIL_BIGFN ail_obj ail_big_bitop(ail_ctx *cx, ail_obj a, ail_obj b, char op);
static AIL_BIGFN ail_st ail__ov_floordiv(ail_ctx *cx, ail_obj *out);
static AIL_BIGFN ail_st ail__ov_shl(ail_ctx *cx, ail_obj *out, int64_t a, int64_t n);
static AIL_BIGFN ail_st ail__ov_pow(ail_ctx *cx, ail_obj *out, int64_t a, int64_t e);
static AIL_BIGFN ail_st ail__ov_truediv(ail_ctx *cx, ail_obj *out, int64_t a, int64_t b);
static inline void ail_int_divmod(ail_ctx *cx, ail_obj *q, ail_obj *r, ail_obj a, ail_obj b);
static AIL_BIGFN ail_st ail__int_pow(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b);
static AIL_BIGFN ail_st ail__int_truediv(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b);
static AIL_BIGFN int ail__big_floordiv(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st);
static AIL_BIGFN int ail__big_mod(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st);
static AIL_BIGFN int ail__big_truediv(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st);
static AIL_BIGFN int ail__big_pow(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st);
static AIL_BIGFN ail_st ail__big_shift(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, int left);
static AIL_BIGFN char *ail_big_dec(ail_obj a, size_t *len);
static AIL_BIGFN char *ail_big_radix(ail_obj a, int shift, size_t *len);
static AIL_BIGFN ail_obj ail_big_from_digits(ail_ctx *cx, const char *t, size_t n, int base, int neg);
static AIL_BIGFN ail_obj ail_int_to_str(ail_ctx *cx, ail_obj a);
static inline void ail_bv_of(ail_bv *v, ail_obj x) {
    if (x.tag == AIL_T_BIG) { ail_bigobj *b = AIL_BIG(x); v->sign = b->sign; v->n = b->n; v->d = b->d; return; }
    int64_t i = x.i;
    uint64_t m = i < 0 ? 0 - (uint64_t)i : (uint64_t)i;
    v->sign = i < 0 ? -1 : i > 0; v->tmp[0] = (ail_limb)m; v->tmp[1] = (ail_limb)(m >> 32);
    v->n = v->tmp[1] ? 2 : v->tmp[0] ? 1 : 0; v->d = v->tmp;
}
static inline ail_obj ail_big_alloc(ail_ctx *cx, size_t cap, ail_obj r1, ail_obj r2) {
    if (cap > ((size_t)1 << 31) / 4) { fputs("MemoryError: integer too large\n", stderr); fflush(stdout); _Exit(1); }
    ail_obj k[2]; k[0] = r1; k[1] = r2;
    AIL_ROOT_N(cx, fr, k, 2);
    ail_bigobj *b = (ail_bigobj *)ail_gc_alloc(cx, AIL_K_BIG, sizeof(ail_bigobj) + (cap ? cap - 1 : 0) * sizeof(ail_limb));
    AIL_FRAME_LEAVE(cx, fr);
    ail_obj r; memset(&r, 0, sizeof r); r.tag = AIL_T_BIG; r.sv.off = (int64_t)(uintptr_t)b; r.i = INT64_MAX; return r;
}
/* a big object that is static data (an int literal of the program) as a value */
static inline ail_obj ail_big_static(ail_bigobj *b) {
    ail_obj r; memset(&r, 0, sizeof r); r.tag = AIL_T_BIG; r.sv.off = (int64_t)(uintptr_t)b; r.i = b->sign < 0 ? INT64_MIN : INT64_MAX; return r;
}
/* set the sign and length of a freshly computed big object, and demote it when it fits int64 */
static inline ail_obj ail_big_finish(ail_obj o, int sign, size_t n) {
    ail_bigobj *b = AIL_BIG(o);
    n = ail_bn_norm(b->d, n);
    if (n == 0) return ail_box_int(0);
    if (n <= 2) {
        uint64_t m = b->d[0] | (n > 1 ? (uint64_t)b->d[1] << 32 : 0);
        if (sign > 0) { if (m <= (uint64_t)INT64_MAX) return ail_box_int((int64_t)m); }
        else if (m <= (uint64_t)INT64_MAX + 1u) return ail_box_int((int64_t)(0 - m));
    }
    b->sign = sign < 0 ? -1 : 1; b->n = (uint32_t)n;
    o.i = sign < 0 ? INT64_MIN : INT64_MAX;
    return o;
}
/* the same from a malloc'd / stack magnitude */
static AIL_BIGFN ail_obj ail_big_from_limbs(ail_ctx *cx, int sign, const ail_limb *d, size_t n, ail_obj r1, ail_obj r2) {
    n = ail_bn_norm(d, n);
    if (n == 0) return ail_box_int(0);
    if (n <= 2) {
        uint64_t m = d[0] | (n > 1 ? (uint64_t)d[1] << 32 : 0);
        if (sign > 0) { if (m <= (uint64_t)INT64_MAX) return ail_box_int((int64_t)m); }
        else if (m <= (uint64_t)INT64_MAX + 1u) return ail_box_int((int64_t)(0 - m));
    }
    ail_obj r = ail_big_alloc(cx, n, r1, r2);
    memcpy(AIL_BIG(r)->d, d, n * sizeof(ail_limb));
    AIL_BIG(r)->sign = sign < 0 ? -1 : 1; AIL_BIG(r)->n = (uint32_t)n;
    r.i = sign < 0 ? INT64_MIN : INT64_MAX;
    return r;
}
static inline ail_obj ail__int_plain(ail_obj a) { return a.tag == AIL_T_BOOL ? ail_box_int(a.i) : a; }

/* a + b, a - b */
static AIL_BIGFN ail_obj ail_big_addsub(ail_ctx *cx, ail_obj a, ail_obj b, int sub) {
    ail_bv x, y; ail_bv_of(&x, a); ail_bv_of(&y, b);
    if (sub) y.sign = -y.sign;
    size_t cap = (x.n > y.n ? x.n : y.n) + 1;
    ail_obj r = ail_big_alloc(cx, cap, a, b);
    ail_limb *o = AIL_BIG(r)->d; size_t n; int sign;
    if (x.sign == y.sign) { n = ail_bn_add(o, x.d, x.n, y.d, y.n); sign = x.sign; }
    else {
        int c = ail_bn_cmp(x.d, x.n, y.d, y.n);
        if (c == 0) { n = 0; sign = 0; }
        else if (c > 0) { n = ail_bn_sub(o, x.d, x.n, y.d, y.n); sign = x.sign; }
        else { n = ail_bn_sub(o, y.d, y.n, x.d, x.n); sign = y.sign; }
    }
    return ail_big_finish(r, sign, n);
}
static AIL_BIGFN ail_obj ail_big_mul(ail_ctx *cx, ail_obj a, ail_obj b) {
    ail_bv x, y; ail_bv_of(&x, a); ail_bv_of(&y, b);
    if (!x.sign || !y.sign) return ail_box_int(0);
    ail_obj r = ail_big_alloc(cx, x.n + y.n, a, b);
    size_t n = ail_bn_mul(AIL_BIG(r)->d, x.d, x.n, y.d, y.n);
    return ail_big_finish(r, x.sign * y.sign, n);
}
/* floor() without libm: a program that never needed libm must not load it (dynamic loading costs about 30k start-up instructions) */
static inline double ail__floor(double x) {
    if (!(fabs(x) < 4503599627370496.0)) return x;           /* 2**52 and beyond, inf, nan: already integral */
    double t = (double)(int64_t)x;
    if (t > x) t -= 1.0;
    return copysign(t, x);
}
/* floor division and modulo (b != 0): q and r are each optional (NULL) */
/*P:div<*/
static AIL_BIGFN void ail_big_divmod(ail_ctx *cx, ail_obj *q, ail_obj *r, ail_obj a, ail_obj b) {
    ail_bv x, y; ail_bv_of(&x, a); ail_bv_of(&y, b);
    size_t qcap = (x.n >= y.n ? x.n - y.n : 0) + 2, rcap = y.n + 1;
    ail_limb *qs = (ail_limb *)malloc((qcap + rcap) * sizeof(ail_limb)), *rs;
    if (!qs) ail_die("out of memory");
    rs = qs + qcap;
    size_t qn = 0, rn = 0;
    ail_bn_divmod(qs, &qn, rs, &rn, x.d, x.n, y.d, y.n);
    int diff = x.sign * y.sign < 0;
    if (diff && rn) {                        /* floor: |q| + 1, |r| = |b| - |r| */
        qn = ail_bn_add(qs, qs, qn, (const ail_limb[]){1}, 1);
        rn = ail_bn_sub(rs, y.d, y.n, rs, rn);
    }
    ail_obj qo = ail_box_int(0);
    if (q) {
        qo = ail_big_from_limbs(cx, diff ? -1 : 1, qs, qn, a, b);
        if (r) { AIL_ROOT1(cx, fr, qo); *r = ail_big_from_limbs(cx, y.sign, rs, rn, a, b); AIL_FRAME_LEAVE(cx, fr); }
        *q = qo;
    } else if (r) *r = ail_big_from_limbs(cx, y.sign, rs, rn, a, b);
    free(qs);
}
/*P|*/
/*P>*/
/* a << n, n >= 0 */
/*P:shift<*/
static AIL_BIGFN ail_obj ail_big_shl(ail_ctx *cx, ail_obj a, int64_t n) {
    ail_bv x; ail_bv_of(&x, a);
    if (!x.sign) return ail_box_int(0);
    if (n > ((int64_t)1 << 34)) { fputs("MemoryError: integer too large\n", stderr); fflush(stdout); _Exit(1); }
    ail_obj r = ail_big_alloc(cx, x.n + (size_t)(n >> 5) + 1, a, a);
    size_t k = ail_bn_shl(AIL_BIG(r)->d, x.d, x.n, (uint64_t)n);
    return ail_big_finish(r, x.sign, k);
}
/*P|*/
/*P>*/
/* a >> n (floor), n >= 0 */
/*P:shift<*/
static AIL_BIGFN ail_obj ail_big_shr(ail_ctx *cx, ail_obj a, int64_t n) {
    ail_bv x; ail_bv_of(&x, a);
    if (!x.sign) return ail_box_int(0);
    int lost = x.sign < 0 && ail_bn_low_bits(x.d, x.n, (uint64_t)n);
    ail_obj r = ail_big_alloc(cx, x.n + 1, a, a);
    ail_limb *o = AIL_BIG(r)->d;
    size_t k = ail_bn_shr(o, x.d, x.n, (uint64_t)n);
    if (lost) { o[k] = 0; k = ail_bn_add(o, o, k, (const ail_limb[]){1}, 1); }
    return ail_big_finish(r, x.sign, k);
}
/*P|*/
/*P>*/
static AIL_BIGFN ail_obj ail_big_neg(ail_ctx *cx, ail_obj a) {
    ail_bv x; ail_bv_of(&x, a);
    if (!x.sign) return ail_box_int(0);
    ail_obj r = ail_big_alloc(cx, x.n, a, a);
    memcpy(AIL_BIG(r)->d, x.d, x.n * sizeof(ail_limb));
    return ail_big_finish(r, -x.sign, x.n);
}
static AIL_BIGFN ail_obj ail_big_abs(ail_ctx *cx, ail_obj a) {
    ail_bv x; ail_bv_of(&x, a);
    if (x.sign >= 0) return ail__int_plain(a);
    return ail_big_neg(cx, a);
}
/* & | ^ with Python's infinite two's complement: op is '&', '|' or '^' */
/*P:bits<*/
static AIL_BIGFN ail_obj ail_big_bitop(ail_ctx *cx, ail_obj a, ail_obj b, char op) {
    ail_bv x, y; ail_bv_of(&x, a); ail_bv_of(&y, b);
    size_t L = (x.n > y.n ? x.n : y.n) + 1;
    ail_limb *t = (ail_limb *)malloc(2 * L * sizeof(ail_limb));
    if (!t) ail_die("out of memory");
    ail_bn_to_twos(t, L, x.d, x.n, x.sign < 0);
    ail_bn_to_twos(t + L, L, y.d, y.n, y.sign < 0);
    for (size_t i = 0; i < L; i++) t[i] = op == '&' ? (t[i] & t[L + i]) : op == '|' ? (t[i] | t[L + i]) : (t[i] ^ t[L + i]);
    size_t n; int sign = ail_bn_from_twos(t, L, &n);
    ail_obj r = ail_big_from_limbs(cx, sign, t, n, a, b);
    free(t);
    return r;
}
/*P|*/
/*P>*/

/* ---- comparison ---- */
static AIL_BIGFN int ail_int_cmp(ail_obj a, ail_obj b) {
    if (a.tag != AIL_T_BIG && b.tag != AIL_T_BIG) return a.i < b.i ? -1 : a.i > b.i ? 1 : 0;
    ail_bv x, y; ail_bv_of(&x, a); ail_bv_of(&y, b);
    if (x.sign != y.sign) return x.sign < y.sign ? -1 : 1;
    int c = ail_bn_cmp(x.d, x.n, y.d, y.n);
    return x.sign < 0 ? -c : c;
}
/* the exact magnitude of a double with |d| >= 2^63 (finite): limbs into o[40], returns the length */
static AIL_BIGFN size_t ail__dbl_mag(double d, ail_limb *o) {
    int e; double m = ail__frexp(fabs(d), &e);
    uint64_t mant = (uint64_t)ail__ldexp(m, 53);
    ail_limb mm[2]; mm[0] = (ail_limb)mant; mm[1] = (ail_limb)(mant >> 32);
    return ail_bn_shl(o, mm, 2, (uint64_t)(e - 53));
}
/* big (|a| >= 2^63) against a double: -1, 0, 1, or 2 for NaN */
static AIL_BIGFN int ail_big_cmp_double(ail_obj a, double d) {
    if (d != d) return 2;
    ail_bv x; ail_bv_of(&x, a);
    if (isinf(d)) return d > 0 ? -1 : 1;
    if (fabs(d) < 9223372036854775808.0) return x.sign;
    int ds = d < 0 ? -1 : 1;
    if (x.sign != ds) return x.sign < ds ? -1 : 1;
    ail_limb m[40]; size_t mn = ail__dbl_mag(d, m);
    int c = ail_bn_cmp(x.d, x.n, m, mn);
    return x.sign < 0 ? -c : c;
}
/* int/bool/big against double, with the sign of "a compared to d": -1, 0, 1, 2 (NaN) */
static inline int ail_int_cmp_double(ail_obj a, double d) {
    if (a.tag == AIL_T_BIG) return ail_big_cmp_double(a, d);
    return ail__cmp_int_float(a.i, d);
}
static inline double ail_big_to_double(ail_obj a, int *ovf) {
    ail_bv x; ail_bv_of(&x, a);
    return ail_bn_to_double(x.d, x.n, x.sign < 0, ovf);
}
/* the double of any int, infinities beyond range (the callers that must raise check with ail_big_to_double) */
static inline double ail_int_as_double(ail_obj a) {
    if (a.tag != AIL_T_BIG) return (double)a.i;
    int ovf; return ail_big_to_double(a, &ovf);
}
/* a finite double (already truncated to an integer or not: it is truncated here) as an int */
static AIL_BIGFN ail_obj ail_int_from_double(ail_ctx *cx, double d) {
    if (d >= -9223372036854775808.0 && d < 9223372036854775808.0) return ail_box_int((int64_t)d);   /* the cast truncates; beyond 2^63 every double is an integer */
    ail_limb m[40]; size_t mn = ail__dbl_mag(d, m);
    return ail_big_from_limbs(cx, d < 0 ? -1 : 1, m, mn, ail_box_none(), ail_box_none());
}

/* ---- hash: CPython's, x mod (2**61 - 1) with the sign applied ---- */
static AIL_BIGFN int64_t ail_int_pyhash(ail_obj a) {
    if (a.tag != AIL_T_BIG) {
        int64_t i = a.i;
        uint64_t m = i < 0 ? 0 - (uint64_t)i : (uint64_t)i;
        const uint64_t P = ((uint64_t)1 << 61) - 1;
        m = (m & P) + (m >> 61); m = (m & P) + (m >> 61); if (m == P) m = 0;   /* m < 2^64: two folds */
        int64_t h = (int64_t)m; if (i < 0) h = -h; return h == -1 ? -2 : h;
    }
    ail_bv x; ail_bv_of(&x, a);
    const uint64_t P = ((uint64_t)1 << 61) - 1;
    uint64_t r = 0;
    for (size_t i = x.n; i-- > 0; ) {
        /* r = (r * 2^32 + limb) mod P, r < 2^61 so r << 32 < 2^93: split off the bits above 2^61 */
        uint64_t hi = r >> 29, lo = (r & (((uint64_t)1 << 29) - 1)) << 32;     /* r*2^32 = hi*2^61 + lo, 2^61 = 1 mod P */
        uint64_t s = hi + lo + x.d[i];
        s = (s & P) + (s >> 61); if (s >= P) s -= P;
        r = s;
    }
    int64_t h = (int64_t)r; if (x.sign < 0) h = -h;
    return h == -1 ? -2 : h;
}
/* the container hash of a big int: the int64 mixer of the folded value (the same function as a small int's); a big value
   that is exactly a double (2**70) hashes as that double, so `2**70 == 2.0**70` finds the same dict slot */
static AIL_BIGFN uint64_t ail_big_hash(ail_obj a) {
    int ovf; double d = ail_big_to_double(a, &ovf);
    if (!ovf) {
        int cmp = ail_big_cmp_double(a, d);
        if (cmp == 0) { uint64_t h; memcpy(&h, &d, sizeof h); h ^= h >> 33; h *= 0xff51afd7ed558ccdULL; h ^= h >> 33; return h; }
    }
    ail_bv x; ail_bv_of(&x, a);
    uint64_t h = 0x9E3779B97F4A7C15ULL ^ (uint64_t)x.sign;
    for (size_t i = 0; i < x.n; i++) { h ^= x.d[i]; h *= 1099511628211ULL; h ^= h >> 29; }
    h ^= h >> 33; h *= 0xff51afd7ed558ccdULL; h ^= h >> 33;
    return h;
}

/* ---- text ---- */
#define AIL_INT_MAX_STR_DIGITS 4300
#define AIL_MSG_STR_LIMIT "Exceeds the limit (4300 digits) for integer string conversion; use sys.set_int_max_str_digits() to increase the limit"
#define AIL_MSG_BIGIDX "cannot fit 'int' into an index-sized integer"
/* [-]digits into a malloc'd buffer (len returned); NULL when the digit count is over the limit */
/*P:text<*/
static AIL_BIGFN char *ail_big_dec(ail_obj a, size_t *len) {
    ail_bv x; ail_bv_of(&x, a);
    /* 10**4300 is just above 2**14284: a value of 14286 bits or more has more than 4300 digits, no conversion needed */
    if (ail_bn_bitlen(x.d, x.n) >= 14286) return NULL;
    char *buf = (char *)malloc(10 * x.n + 3);
    if (!buf) ail_die("out of memory");
    size_t o = 0;
    if (x.sign < 0) buf[o++] = '-';
    size_t nd = ail_bn_to_dec(buf + o, x.d, x.n);
    if (nd > AIL_INT_MAX_STR_DIGITS) { free(buf); return NULL; }
    *len = o + nd; buf[*len] = 0;
    return buf;
}
/*P|*/
/*P>*/
/* hex/bin/oct digits of |a| (shift = 4, 1, 3): no limit, linear */
/*P:text<*/
static AIL_BIGFN char *ail_big_radix(ail_obj a, int shift, size_t *len) {
    ail_bv x; ail_bv_of(&x, a);
    uint64_t bl = ail_bn_bitlen(x.d, x.n);
    size_t nd = (size_t)((bl + shift - 1) / shift); if (!nd) nd = 1;
    char *buf = (char *)malloc(nd + 2);
    if (!buf) ail_die("out of memory");
    for (size_t k = 0; k < nd; k++) {
        unsigned v = 0;
        for (int b = 0; b < shift; b++) {
            uint64_t bit = (uint64_t)k * shift + b;
            if (bit < bl && ((x.d[bit >> 5] >> (bit & 31)) & 1)) v |= 1u << b;
        }
        buf[nd - 1 - k] = "0123456789abcdef"[v];
    }
    buf[nd] = 0; *len = nd;
    return buf;
}
/*P|*/
/*P>*/
/* parse the digits t[0..n) (digits of `base` only, no sign, no underscores) into |value|: base 2..36 */
/*P:text<*/
static AIL_BIGFN ail_obj ail_big_from_digits(ail_ctx *cx, const char *t, size_t n, int base, int neg) {
    size_t cap = n / 4 + 3;     /* >= n*log2(36)/32 limbs: 5.17 bits per digit < 8 */
    ail_limb *d = (ail_limb *)malloc(cap * sizeof(ail_limb));
    if (!d) ail_die("out of memory");
    size_t k = 0;
    if (base == 10) k = ail_bn_from_dec(d, t, n);
    else if ((base & (base - 1)) == 0) {
        int sh = __builtin_ctz(base);
        memset(d, 0, cap * sizeof(ail_limb));
        uint64_t bit = 0;
        for (size_t i = n; i-- > 0; ) {
            int c = (unsigned char)t[i], v = c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10;
            for (int b = 0; b < sh; b++, bit++) if ((v >> b) & 1) d[bit >> 5] |= (ail_limb)1 << (bit & 31);
        }
        k = ail_bn_norm(d, cap);
    } else {
        for (size_t i = 0; i < n; i++) {
            int c = (unsigned char)t[i], v = c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10;
            k = ail_bn_muladd1(d, k, (ail_limb)base, (ail_limb)v);
        }
        k = ail_bn_norm(d, k);
    }
    ail_obj r = ail_big_from_limbs(cx, neg ? -1 : 1, d, k, ail_box_none(), ail_box_none());
    free(d);
    return r;
}
/*P|*/
/*P>*/
/* the text form of any int as an AIL str; the oversized case sets cx->big_toolong and gives "" */
/*P:text<*/
static AIL_BIGFN ail_obj ail_int_to_str(ail_ctx *cx, ail_obj a) {
    size_t len;
    char *b = ail_big_dec(a, &len);
    if (!b) { cx->big_toolong = 1; return ail_str_from_cstr(cx, ""); }
    ail_strbuild sb = ail_str_buf1(cx, (int64_t)len, a);
    for (size_t i = 0; i < len; i++) sb.buf[i] = (unsigned char)b[i];
    free(b);
    return ail_str_buf_done(sb, (int64_t)len);
}
/*P|*/
/*P>*/

/* The cold half of the int fast path (docs/design/BIGINT.md section 2). The inline arms of `+ - * neg abs << // **` keep their
   `__builtin_*_overflow` test and, where it fires, TAIL-CALL one of these with the two int64 operands in registers: no frame, no
   struct copy and no code in the hot function beyond the call, exactly the shape of the stop that was there before. */
#define AIL_BIGCOLD AIL_BIGFN
static AIL_BIGCOLD ail_st ail__ov_add(ail_ctx *cx, ail_obj *out, int64_t a, int64_t b) { *out = ail_big_addsub(cx, ail_box_int(a), ail_box_int(b), 0); return AIL_OK; }
/* The add overflow arm passes the wrapped result and the second operand, not both operands: the hot path can then add in
   place (one instruction fewer) instead of keeping the first operand live for the call. a is recovered exactly, modulo 2**64. */
static AIL_BIGCOLD ail_st ail__ov_add1(ail_ctx *cx, ail_obj *out, int64_t b, int64_t r) {
    int64_t a = (int64_t)((uint64_t)r - (uint64_t)b);
    return ail__ov_add(cx, out, a, b);
}
static AIL_BIGCOLD ail_st ail__ov_sub(ail_ctx *cx, ail_obj *out, int64_t a, int64_t b) { *out = ail_big_addsub(cx, ail_box_int(a), ail_box_int(b), 1); return AIL_OK; }
static AIL_BIGCOLD ail_st ail__ov_mul(ail_ctx *cx, ail_obj *out, int64_t a, int64_t b) { *out = ail_big_mul(cx, ail_box_int(a), ail_box_int(b)); return AIL_OK; }
static AIL_BIGCOLD ail_st ail__ov_neg(ail_ctx *cx, ail_obj *out) { *out = ail_big_neg(cx, ail_box_int(INT64_MIN)); return AIL_OK; }
/*P:div<*/
static AIL_BIGCOLD ail_st ail__ov_floordiv(ail_ctx *cx, ail_obj *out) { *out = ail_big_neg(cx, ail_box_int(INT64_MIN)); return AIL_OK; }   /* INT64_MIN // -1 */
/*P|*/
/*P>*/
/*P:shift<*/
static AIL_BIGCOLD ail_st ail__ov_shl(ail_ctx *cx, ail_obj *out, int64_t a, int64_t n) { *out = ail_big_shl(cx, ail_box_int(a), n); return AIL_OK; }
/*P|*/
/*P>*/
static AIL_BIGCOLD ail_st ail__ov_pow(ail_ctx *cx, ail_obj *out, int64_t a, int64_t e);
static AIL_BIGCOLD ail_st ail__ov_truediv(ail_ctx *cx, ail_obj *out, int64_t a, int64_t b);
/* ---- generic int arithmetic (INT / BOOL / BIG operands) and the operators' big paths ---- */
static AIL_BIGFN void ail__big_memory_stop(void) { fflush(stdout); fputs("MemoryError\n", stderr); _Exit(1); }
static inline ail_obj ail_int_add(ail_ctx *cx, ail_obj a, ail_obj b) {
    int64_t r; if (a.tag != AIL_T_BIG && b.tag != AIL_T_BIG && !__builtin_add_overflow(a.i, b.i, &r)) return ail_box_int(r);
    return ail_big_addsub(cx, a, b, 0);
}
static inline ail_obj ail_int_sub(ail_ctx *cx, ail_obj a, ail_obj b) {
    int64_t r; if (a.tag != AIL_T_BIG && b.tag != AIL_T_BIG && !__builtin_sub_overflow(a.i, b.i, &r)) return ail_box_int(r);
    return ail_big_addsub(cx, a, b, 1);
}
static inline ail_obj ail_int_mul(ail_ctx *cx, ail_obj a, ail_obj b) {
    int64_t r; if (a.tag != AIL_T_BIG && b.tag != AIL_T_BIG && !__builtin_mul_overflow(a.i, b.i, &r)) return ail_box_int(r);
    return ail_big_mul(cx, a, b);
}
/* floor division / modulo of any ints, b != 0 */
static inline void ail_int_divmod(ail_ctx *cx, ail_obj *q, ail_obj *r, ail_obj a, ail_obj b) {
    if (a.tag != AIL_T_BIG && b.tag != AIL_T_BIG && !(a.i == INT64_MIN && b.i == -1)) {
        int64_t x = a.i, y = b.i, qq = x / y, rr = x % y;
        if (rr != 0 && ((rr < 0) != (y < 0))) { qq -= 1; rr += y; }
        if (q) *q = ail_box_int(qq);
        if (r) *r = ail_box_int(rr);
        return;
    }
    ail_big_divmod(cx, q, r, a, b);
}
static inline int ail_int_sign(ail_obj a) { return a.tag == AIL_T_BIG ? AIL_BIG(a)->sign : a.i < 0 ? -1 : a.i > 0; }

/* a ** e for ints, e >= 0 (a BIG exponent only for a in {0, 1, -1}) */
/*P:pow<*/
static AIL_BIGFN ail_st ail__int_pow(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {
    ail_bv x; ail_bv_of(&x, a);
    if (b.tag == AIL_T_BIG) {
        if (!x.sign) { *out = ail_box_int(0); return AIL_OK; }
        if (x.n == 1 && x.d[0] == 1) { *out = ail_box_int(x.sign > 0 ? 1 : (AIL_BIG(b)->d[0] & 1 ? -1 : 1)); return AIL_OK; }
        ail__big_memory_stop();
    }
    int64_t e = b.i;
    if (x.n && ail_bn_bitlen(x.d, x.n) > 1 && (double)ail_bn_bitlen(x.d, x.n) * (double)e > 17179869184.0) ail__big_memory_stop();
    ail_obj k[3]; k[0] = ail__int_plain(a); k[1] = ail_box_int(1); k[2] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, k, 3);
    while (e) {
        if (e & 1) { k[2] = ail_int_mul(cx, k[1], k[0]); k[1] = k[2]; }
        e >>= 1;
        if (e) { k[2] = ail_int_mul(cx, k[0], k[0]); k[0] = k[2]; }
    }
    *out = k[1];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/*P|*/
/*P>*/

/* int / int, correctly rounded (CPython's long_true_divide): the quotient is taken to 55 or 56 bits with a sticky
   remainder and rounded to 53 once */
/*P:div<*/
static AIL_BIGFN ail_st ail__int_truediv(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {
    ail_bv x, y; ail_bv_of(&x, a); ail_bv_of(&y, b);
    if (!y.sign) return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "division by zero");
    int sign = x.sign * y.sign;
    if (!x.sign) { *out = ail_box_float(cx, y.sign < 0 ? -0.0 : 0.0); return AIL_OK; }
    int64_t abl = (int64_t)ail_bn_bitlen(x.d, x.n), bbl = (int64_t)ail_bn_bitlen(y.d, y.n);
    int64_t shift = 55 - (abl - bbl);
    size_t xl = x.n + (shift > 0 ? (size_t)(shift >> 5) + 2 : 0), yl = y.n + (shift < 0 ? (size_t)((-shift) >> 5) + 2 : 0);
    ail_limb *num = (ail_limb *)malloc((xl + yl + (xl + 2) + (yl + 2)) * sizeof(ail_limb));
    if (!num) ail_die("out of memory");
    ail_limb *den = num + xl, *q = den + yl, *r = q + (xl + 2);
    size_t nn, dn, qn = 0, rn = 0;
    if (shift >= 0) { nn = ail_bn_shl(num, x.d, x.n, (uint64_t)shift); dn = y.n; memcpy(den, y.d, y.n * sizeof(ail_limb)); }
    else { nn = x.n; memcpy(num, x.d, x.n * sizeof(ail_limb)); dn = ail_bn_shl(den, y.d, y.n, (uint64_t)(-shift)); }
    ail_bn_divmod(q, &qn, r, &rn, num, nn, den, dn);
    uint64_t qv = (qn > 0 ? q[0] : 0) | (qn > 1 ? (uint64_t)q[1] << 32 : 0);
    int sticky = rn != 0;
    free(num);
    int qb = 64 - __builtin_clzll(qv), drop = qb - 53;
    uint64_t mant = qv >> drop, rem = qv & (((uint64_t)1 << drop) - 1), half = (uint64_t)1 << (drop - 1);
    if (rem > half || (rem == half && (sticky || (mant & 1)))) mant++;
    double res = ail__ldexp((double)mant, (int)(drop - shift));
    if (isinf(res)) return ail_raise_c(cx, AIL_B_OVERFLOWERROR, "integer division result too large for a float");
    *out = ail_box_float(cx, sign < 0 ? -res : res);
    return AIL_OK;
}
/*P|*/
/*P>*/

/*P:pow<*/
static AIL_BIGCOLD ail_st ail__ov_pow(ail_ctx *cx, ail_obj *out, int64_t a, int64_t e) { return ail__int_pow(cx, out, ail_box_int(a), ail_box_int(e)); }
/*P|*/
/*P>*/
/*P:div<*/
static AIL_BIGCOLD ail_st ail__ov_truediv(ail_ctx *cx, ail_obj *out, int64_t a, int64_t b) { return ail__int_truediv(cx, out, ail_box_int(a), ail_box_int(b)); }
/*P|*/
/*P>*/

/* The operators' paths when an operand is a BIG, one function per operator (so a program links only the operators it uses, and no
   function calls an operator back): int-with-int in the big code, a float operand through a float of the int (OverflowError when it
   does not fit). Each returns 1 when it handled the operands (*st is the status), 0 when they are not numbers: the operator then
   raises its own type error. */
/* CPython's float_floor_div: the remainder by fmod, the quotient from it, snapped; floor(x / y) is wrong near rounding
   boundaries (1 // 0.1 is 9.0, and a quotient that is not exact beyond 2**53) */
static inline double ail__ffloordiv(double vx, double wx) {
    double mod = ail__fmod(vx, wx);
    double div = (vx - mod) / wx;
    if (mod != 0.0 && ((wx < 0) != (mod < 0))) div -= 1.0;
    if (div != 0.0) { double fl = ail__floor(div); if (div - fl > 0.5) fl += 1.0; return fl; }
    return copysign(0.0, vx / wx);
}
static AIL_BIGFN int ail__big_flt(ail_ctx *cx, ail_obj a, ail_obj b, double *x, double *y, ail_st *st) {
    if (!ail__is_numb(a.tag) || !ail__is_numb(b.tag)) return 0;
    double d[2]; ail_obj o[2]; o[0] = a; o[1] = b;
    for (int i = 0; i < 2; i++) {
        if (o[i].tag == AIL_T_BIG) {
            int ovf; d[i] = ail_big_to_double(o[i], &ovf);
            if (ovf) { *st = ail_raise_c(cx, AIL_B_OVERFLOWERROR, "int too large to convert to float"); return -1; }
        } else d[i] = o[i].tag == AIL_T_FLOAT ? ail_float_val(o[i]) : (double)o[i].i;
    }
    *x = d[0]; *y = d[1];
    return 1;
}
static AIL_BIGFN int ail__big_add(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    *st = AIL_OK;
    if (ail__isint(a.tag) && ail__isint(b.tag)) { *out = ail_big_addsub(cx, a, b, 0); return 1; }
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) *out = ail_box_float(cx, x + y);
    return f != 0;
}
static AIL_BIGFN int ail__big_sub(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    *st = AIL_OK;
    if (ail__isint(a.tag) && ail__isint(b.tag)) { *out = ail_big_addsub(cx, a, b, 1); return 1; }
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) *out = ail_box_float(cx, x - y);
    return f != 0;
}
static AIL_BIGFN int ail__big_mul(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    *st = AIL_OK;
    int ai = ail__isint(a.tag), bi = ail__isint(b.tag);
    if (ai && bi) { *out = ail_big_mul(cx, a, b); return 1; }
    if ((ai && (b.tag == AIL_T_STR || b.tag == AIL_T_LIST || b.tag == AIL_T_TUPLE)) || (bi && (a.tag == AIL_T_STR || a.tag == AIL_T_LIST || a.tag == AIL_T_TUPLE))) {
        *st = ail_raise_c(cx, AIL_B_OVERFLOWERROR, "cannot fit 'int' into an index-sized integer"); return 1;
    }
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) *out = ail_box_float(cx, x * y);
    return f != 0;
}
/*P:div<*/
static AIL_BIGFN int ail__big_floordiv(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    *st = AIL_OK;
    if (ail__isint(a.tag) && ail__isint(b.tag)) {
        if (b.tag != AIL_T_BIG && b.i == 0) { *st = ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "integer division or modulo by zero"); return 1; }
        ail_big_divmod(cx, out, NULL, a, b); return 1;
    }
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) {
        if (y == 0.0) *st = ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float floor division by zero");
        else *out = ail_box_float(cx, ail__ffloordiv(x, y));
    }
    return f != 0;
}
/*P|*/
/*P>*/
/*P:div<*/
static AIL_BIGFN int ail__big_mod(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    *st = AIL_OK;
    if (ail__isint(a.tag) && ail__isint(b.tag)) {
        if (b.tag != AIL_T_BIG && b.i == 0) { *st = ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "integer modulo by zero"); return 1; }
        ail_big_divmod(cx, NULL, out, a, b); return 1;
    }
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) {
        if (y == 0.0) { *st = ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float modulo"); return 1; }
        double r = ail__fmod(x, y);
        if (r != 0.0) { if ((r < 0) != (y < 0)) r += y; } else r = copysign(0.0, y);
        *out = ail_box_float(cx, r);
    }
    return f != 0;
}
/*P|*/
/*P>*/
/*P:div<*/
static AIL_BIGFN int ail__big_truediv(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    if (ail__isint(a.tag) && ail__isint(b.tag)) { *st = ail__int_truediv(cx, out, a, b); return 1; }
    *st = AIL_OK;
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) {
        if (y == 0.0) *st = ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float division by zero");
        else *out = ail_box_float(cx, x / y);
    }
    return f != 0;
}
/*P|*/
/*P>*/
/*P:pow<*/
static AIL_BIGFN int ail__big_pow(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, ail_st *st) {
    *st = AIL_OK;
    if (ail__isint(a.tag) && ail__isint(b.tag) && ail_int_sign(b) >= 0) { *st = ail__int_pow(cx, out, a, b); return 1; }
    double x, y; int f = ail__big_flt(cx, a, b, &x, &y, st);
    if (f > 0) {
        double r = (pow)(x, y);
        if (!isfinite(r)) {      /* CPython float_pow, as ail_op_pow */
            if (isnan(r)) {
                if (!isnan(x) && !isnan(y)) { *st = ail_hit_limit(cx, "complex number: a negative number raised to a fractional power (Python has complex numbers, AIL does not)", "complex_pow"); return 1; }
            } else if (!isinf(x) && !isinf(y)) {
                if (x == 0.0) *st = ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "0.0 cannot be raised to a negative power");
                else *st = ail_raise_c(cx, AIL_B_OVERFLOWERROR, "(34, 'Numerical result out of range')");
                return 1;
            }
        }
        *out = ail_box_float(cx, r);
    }
    return f != 0;
}
/*P|*/
/*P>*/
/* a << b and a >> b with a BIG operand (both ints) */
/*P:shift<*/
static AIL_BIGFN ail_st ail__big_shift(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b, int left) {
    if (ail_int_sign(b) < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "negative shift count");
    if (left) {
        if (!ail_int_sign(a)) { *out = ail_box_int(0); return AIL_OK; }
        if (b.tag == AIL_T_BIG) return ail_raise_c(cx, AIL_B_OVERFLOWERROR, "too many digits in integer");
        *out = ail_big_shl(cx, a, b.i); return AIL_OK;
    }
    if (b.tag == AIL_T_BIG) { *out = ail_box_int(ail_int_sign(a) < 0 ? -1 : 0); return AIL_OK; }
    *out = ail_big_shr(cx, a, b.i); return AIL_OK;
}
/*P|*/
/*P>*/
/* ---- end of the object layer (early) --------------------------------------------------------------------- */
'''

RANGE = r"""
/* ---- a range with a bound beyond int64 (bigint): the struct is followed by three boxed ints (start, stop, step) and
   hdr.flags is 1; every other range keeps the int64 form and its speed ---- */
static inline ail_obj ail_range_new(ail_ctx *cx, int64_t start, int64_t stop, int64_t step);
static AIL_BIGFN ail_st ail__bigrange_make(ail_ctx *cx, ail_obj *out, ail_obj s, ail_obj e, ail_obj t) {
    if (ail_int_sign(t) == 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "range() arg 3 must not be zero");
    ail_obj k[3]; k[0] = s; k[1] = e; k[2] = t;
    AIL_ROOT_N(cx, fr, k, 3);
    ail_rangeobj *r = (ail_rangeobj *)ail_gc_alloc(cx, AIL_K_RANGE, sizeof *r + 3 * sizeof(ail_obj));
    AIL_FRAME_LEAVE(cx, fr);
    r->hdr.flags = 1;
    ail_obj *b = AIL_RANGE_BIGP(r);
    b[0] = k[0]; b[1] = k[1]; b[2] = k[2];
    ail_obj o; memset(&o, 0, sizeof o); o.tag = AIL_T_RANGE; o.o = (ail_gcobj *)r; *out = o;
    return AIL_OK;
}
static AIL_BIGFN ail_st ail__range_arg(ail_ctx *cx, ail_obj x) {
    if (x.tag == AIL_T_INT || x.tag == AIL_T_BOOL || x.tag == AIL_T_BIG) return AIL_OK;
    char buf[96]; snprintf(buf, sizeof buf, "'%s' object cannot be interpreted as an integer", ail_type_name(x.tag));
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
/* range(stop) / range(start, stop) / range(start, stop, step) over boxed arguments */
static inline ail_st ail_range_make(ail_ctx *cx, ail_obj *out, int n, ail_obj a, ail_obj b, ail_obj c) {
    ail_obj s = n == 1 ? ail_box_int(0) : a, e = n == 1 ? a : b, t = n == 3 ? c : ail_box_int(1);
    if (__builtin_expect(s.tag == AIL_T_INT && e.tag == AIL_T_INT && t.tag == AIL_T_INT, 1)) {
        if (__builtin_expect(t.i == 0, 0)) return ail_raise_c(cx, AIL_B_VALUEERROR, "range() arg 3 must not be zero");
        *out = ail_range_new(cx, s.i, e.i, t.i); return AIL_OK;
    }
    ail_st st;
    if ((st = ail__range_arg(cx, s)) != AIL_OK || (st = ail__range_arg(cx, e)) != AIL_OK || (st = ail__range_arg(cx, t)) != AIL_OK) return st;
    if (s.tag != AIL_T_BIG && e.tag != AIL_T_BIG && t.tag != AIL_T_BIG) {
        if (t.i == 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "range() arg 3 must not be zero");
        *out = ail_range_new(cx, s.i, e.i, t.i); return AIL_OK;
    }
    return ail__bigrange_make(cx, out, s, e, t);
}
/* the number of items, an int (small or big) */
/* a big range's own arithmetic (its end points are big ints already: these run only on a big range, so they are consumers for biggate.py) */
static AIL_BIGFN ail_obj ail__bigrange_add(ail_ctx *cx, ail_obj a, ail_obj b) { return ail_int_add(cx, a, b); }
static AIL_BIGFN ail_obj ail__bigrange_sub(ail_ctx *cx, ail_obj a, ail_obj b) { return ail_int_sub(cx, a, b); }
static AIL_BIGFN ail_obj ail__bigrange_count(ail_ctx *cx, const ail_rangeobj *r) {
    const ail_obj *b = AIL_RANGE_BIGP(r);
    int sg = ail_int_sign(b[2]);
    int c = ail_int_cmp(b[0], b[1]);
    if (sg > 0 ? c >= 0 : c <= 0) return ail_box_int(0);
    ail_obj t[4]; for (int i = 0; i < 4; i++) t[i] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, t, 4);
    t[0] = sg > 0 ? ail_int_sub(cx, b[1], b[0]) : ail_int_sub(cx, b[0], b[1]);
    t[1] = ail_int_sub(cx, t[0], ail_box_int(1));
    t[2] = sg > 0 ? b[2] : ail_big_neg(cx, b[2]);
    ail_int_divmod(cx, &t[3], &t[0], t[1], t[2]);
    ail_obj res = ail_int_add(cx, t[3], ail_box_int(1));
    AIL_FRAME_LEAVE(cx, fr);
    return res;
}
/* start + step * i for an int i */
static AIL_BIGFN ail_obj ail__bigrange_at(ail_ctx *cx, const ail_rangeobj *r, ail_obj i) {
    const ail_obj *b = AIL_RANGE_BIGP(r);
    ail_obj t[2]; t[0] = i; t[1] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, t, 2);
    t[1] = ail_int_mul(cx, b[2], t[0]);
    ail_obj res = ail_int_add(cx, b[0], t[1]);
    AIL_FRAME_LEAVE(cx, fr);
    return res;
}
static AIL_BIGFN int ail__bigrange_truthy(const ail_rangeobj *r) {
    const ail_obj *b = AIL_RANGE_BIGP(r);
    int c = ail_int_cmp(b[0], b[1]);
    return ail_int_sign(b[2]) > 0 ? c < 0 : c > 0;
}
static AIL_BIGFN ail_st ail__bigrange_getitem(ail_ctx *cx, ail_obj *out, ail_obj rng, ail_obj key) {
    const ail_rangeobj *r = (const ail_rangeobj *)rng.o;
    ail_st st = ail__range_arg(cx, key); if (st != AIL_OK) return st;
    ail_obj t[3]; t[0] = rng; t[1] = key; t[2] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, t, 3);
    ail_obj cnt = ail__bigrange_count(cx, r); t[2] = cnt;
    ail_obj i = key;
    if (ail_int_sign(i) < 0) { i = ail_int_add(cx, i, cnt); t[1] = i; }
    if (ail_int_sign(i) < 0 || ail_int_cmp(i, cnt) >= 0) { AIL_FRAME_LEAVE(cx, fr); return ail_raise_c(cx, AIL_B_INDEXERROR, "range object index out of range"); }
    *out = ail__bigrange_at(cx, r, i);
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/* v in range: arithmetic, for an int v of any size */
static AIL_BIGFN int ail__bigrange_has(ail_ctx *cx, const ail_rangeobj *r, ail_obj v) {
    const ail_obj *b = AIL_RANGE_BIGP(r);
    int sg = ail_int_sign(b[2]);
    if (sg > 0 ? (ail_int_cmp(v, b[0]) < 0 || ail_int_cmp(v, b[1]) >= 0) : (ail_int_cmp(v, b[0]) > 0 || ail_int_cmp(v, b[1]) <= 0)) return 0;
    ail_obj t[3]; t[0] = v; t[1] = ail_box_int(0); t[2] = ail_box_int(0);
    AIL_ROOT_N(cx, fr, t, 3);
    t[1] = sg > 0 ? ail_int_sub(cx, v, b[0]) : ail_int_sub(cx, b[0], v);
    ail_obj m = sg > 0 ? b[2] : ail_big_neg(cx, b[2]); t[2] = m;
    ail_obj rem; ail_int_divmod(cx, NULL, &rem, t[1], t[2]);
    AIL_FRAME_LEAVE(cx, fr);
    return ail_int_sign(rem) == 0;
}
"""

# (LATE is added with the builtins)
LATE = r'''
'''
