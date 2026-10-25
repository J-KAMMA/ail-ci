# -*- coding: utf-8 -*-
"""bigint_core.py -- the arbitrary-precision integer core of the general runtime (docs/design/BIGINT.md).

`CORE` is plain C with no dependency on the object model: magnitudes are little-endian arrays of
base-2^32 limbs (`ail_limb`), every function takes explicit lengths and a caller-provided output of a
documented capacity, and the result lengths are normalised (no leading zero limb). The runtime
(`cruntime.OBJ2`) wraps it in heap objects and the sign rules; the differential test
(`test_ail_bigint.py`) also builds it alone as a shared library and checks it against CPython.

Nothing here allocates except Karatsuba's scratch, Knuth D's normalised copies and the decimal
conversion's working copy; each is freed before the function returns.
"""

CORE = r'''
/* every function of the big-integer code is cold (optimised for size, laid out away from the hot code) and not inlined into the
   operators: it runs only after an int64 overflow or on a big operand */
#define AIL_BIGFN __attribute__((cold, noinline))
/* ---- big integer core (bigint_core.py): magnitudes only, base 2^32 ---------------------------------------- */
typedef uint32_t ail_limb;
#define AIL_BN_KARATSUBA 40

static inline size_t ail_bn_norm(const ail_limb *d, size_t n) { while (n && d[n - 1] == 0) n--; return n; }

/* -1 / 0 / 1; both operands normalised */
static AIL_BIGFN int ail_bn_cmp(const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    if (na != nb) return na < nb ? -1 : 1;
    while (na) { na--; if (a[na] != b[na]) return a[na] < b[na] ? -1 : 1; }
    return 0;
}

/* o = a + b; capacity max(na,nb)+1; o may alias a or b */
static AIL_BIGFN size_t ail_bn_add(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    if (na < nb) { const ail_limb *t = a; a = b; b = t; size_t tn = na; na = nb; nb = tn; }
    uint64_t c = 0; size_t i = 0;
    for (; i < nb; i++) { c += (uint64_t)a[i] + b[i]; o[i] = (ail_limb)c; c >>= 32; }
    for (; i < na; i++) { c += a[i]; o[i] = (ail_limb)c; c >>= 32; }
    o[i] = (ail_limb)c;
    return ail_bn_norm(o, na + 1);
}

/* o = a - b, requires a >= b; capacity na; o may alias a or b */
static AIL_BIGFN size_t ail_bn_sub(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    int64_t br = 0; size_t i = 0;
    for (; i < nb; i++) { int64_t t = (int64_t)a[i] - b[i] - br; br = t < 0; o[i] = (ail_limb)t; }
    for (; i < na; i++) { int64_t t = (int64_t)a[i] - br; br = t < 0; o[i] = (ail_limb)t; }
    return ail_bn_norm(o, na);
}

/* o[0..na+nb) = a * b, schoolbook; o must not alias a or b */
static AIL_BIGFN void ail_bn_mul_school(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    memset(o, 0, (na + nb) * sizeof(ail_limb));
    for (size_t i = 0; i < na; i++) {
        uint64_t c = 0, ai = a[i];
        if (!ai) continue;
        for (size_t j = 0; j < nb; j++) { c += ai * b[j] + o[i + j]; o[i + j] = (ail_limb)c; c >>= 32; }
        o[i + nb] = (ail_limb)c;
    }
}

static AIL_BIGFN void ail_bn_mul_full(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb);

/* acc[0..) += x[0..nx), propagating the carry up to acc[cap) */
static AIL_BIGFN void ail_bn_acc(ail_limb *acc, size_t cap, const ail_limb *x, size_t nx) {
    uint64_t c = 0; size_t i = 0;
    for (; i < nx; i++) { c += (uint64_t)acc[i] + x[i]; acc[i] = (ail_limb)c; c >>= 32; }
    for (; c && i < cap; i++) { c += acc[i]; acc[i] = (ail_limb)c; c >>= 32; }
}
/* acc[0..) -= x[0..nx), the result known to be non-negative */
static AIL_BIGFN void ail_bn_dec(ail_limb *acc, size_t cap, const ail_limb *x, size_t nx) {
    int64_t br = 0; size_t i = 0;
    for (; i < nx; i++) { int64_t t = (int64_t)acc[i] - x[i] - br; br = t < 0; acc[i] = (ail_limb)t; }
    for (; br && i < cap; i++) { int64_t t = (int64_t)acc[i] - br; br = t < 0; acc[i] = (ail_limb)t; }
}

/* o[0..na+nb) = a * b for na >= nb (inputs need not be normalised). Karatsuba from AIL_BN_KARATSUBA limbs, and
   the larger operand cut into nb-limb chunks when it is more than twice the smaller. */
static AIL_BIGFN void ail_bn_mul_full(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    if (na < nb) { const ail_limb *t = a; a = b; b = t; size_t tn = na; na = nb; nb = tn; }
    if (nb < AIL_BN_KARATSUBA) { ail_bn_mul_school(o, a, na, b, nb); return; }
    if (2 * nb <= na) {
        ail_limb *t = (ail_limb *)malloc(2 * nb * sizeof(ail_limb));
        if (!t) ail_die("out of memory");
        memset(o, 0, (na + nb) * sizeof(ail_limb));
        for (size_t i = 0; i < na; i += nb) {
            size_t ch = na - i < nb ? na - i : nb;
            ail_bn_mul_full(t, a + i, ch, b, nb);
            ail_bn_acc(o + i, na + nb - i, t, ch + nb);
        }
        free(t);
        return;
    }
    size_t m = nb >> 1;                       /* a = a1*B^m + a0, b = b1*B^m + b0 */
    size_t ah = na - m, bh = nb - m;
    size_t sa_n = ah + 1, sb_n = bh + 1;
    ail_limb *sa = (ail_limb *)malloc((sa_n + sb_n + sa_n + sb_n) * sizeof(ail_limb));
    if (!sa) ail_die("out of memory");
    ail_limb *sb = sa + sa_n, *z1 = sb + sb_n;
    ail_bn_mul_full(o, a, m, b, m);           /* z0 -> o[0 .. 2m) */
    ail_bn_mul_full(o + 2 * m, a + m, ah, b + m, bh);   /* z2 -> o[2m .. na+nb) */
    { /* sa = a0 + a1, sb = b0 + b1 (a0, b0 have m limbs, a1, b1 more/less) */
        uint64_t c = 0; size_t i;
        for (i = 0; i < ah; i++) { c += (uint64_t)a[m + i] + (i < m ? a[i] : 0); sa[i] = (ail_limb)c; c >>= 32; }
        sa[ah] = (ail_limb)c;
        c = 0;
        for (i = 0; i < bh; i++) { c += (uint64_t)b[m + i] + (i < m ? b[i] : 0); sb[i] = (ail_limb)c; c >>= 32; }
        sb[bh] = (ail_limb)c;
    }
    ail_bn_mul_full(z1, sa, sa_n, sb, sb_n);
    size_t z1n = sa_n + sb_n;
    ail_bn_dec(z1, z1n, o, 2 * m);
    ail_bn_dec(z1, z1n, o + 2 * m, na + nb - 2 * m);
    z1n = ail_bn_norm(z1, z1n);
    ail_bn_acc(o + m, na + nb - m, z1, z1n);
    free(sa);
}

/* o = a * b; capacity na+nb; o must not alias a or b; returns the normalised length (0 for a zero operand) */
static AIL_BIGFN size_t ail_bn_mul(ail_limb *o, const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    if (!na || !nb) return 0;
    ail_bn_mul_full(o, a, na, b, nb);
    return ail_bn_norm(o, na + nb);
}

/* q = a / b, r = a % b (magnitudes), nb >= 1 normalised. q capacity na-nb+1 (or 1), r capacity nb.
   Knuth TAOCP 4.3.1 algorithm D with a 2^32 base. Either of q, r may be NULL. */
static AIL_BIGFN void ail_bn_divmod(ail_limb *q, size_t *qn, ail_limb *r, size_t *rn,
                          const ail_limb *a, size_t na, const ail_limb *b, size_t nb) {
    if (na < nb) {
        if (q) *qn = 0;
        if (r) { memcpy(r, a, na * sizeof(ail_limb)); *rn = na; }
        return;
    }
    if (nb == 1) {
        uint64_t rem = 0, d = b[0];
        for (size_t i = na; i-- > 0; ) {
            uint64_t cur = (rem << 32) | a[i];
            uint64_t qq = cur / d; rem = cur - qq * d;
            if (q) q[i] = (ail_limb)qq;
        }
        if (q) *qn = ail_bn_norm(q, na);
        if (r) { r[0] = (ail_limb)rem; *rn = rem ? 1 : 0; }
        return;
    }
    int s = __builtin_clz(b[nb - 1]);
    ail_limb *vn = (ail_limb *)malloc((nb + na + 1) * sizeof(ail_limb));
    if (!vn) ail_die("out of memory");
    ail_limb *un = vn + nb;
    for (size_t i = nb - 1; i > 0; i--) vn[i] = s ? (b[i] << s) | (b[i - 1] >> (32 - s)) : b[i];
    vn[0] = b[0] << s;
    un[na] = s ? a[na - 1] >> (32 - s) : 0;
    for (size_t i = na - 1; i > 0; i--) un[i] = s ? (a[i] << s) | (a[i - 1] >> (32 - s)) : a[i];
    un[0] = a[0] << s;
    const uint64_t B = (uint64_t)1 << 32;
    for (size_t j = na - nb + 1; j-- > 0; ) {
        uint64_t num = ((uint64_t)un[j + nb] << 32) | un[j + nb - 1];
        uint64_t qhat = num / vn[nb - 1], rhat = num - qhat * vn[nb - 1];
        while (qhat >= B || qhat * vn[nb - 2] > ((rhat << 32) | un[j + nb - 2])) {
            qhat--; rhat += vn[nb - 1];
            if (rhat >= B) break;
        }
        int64_t borrow = 0; uint64_t carry = 0;
        for (size_t i = 0; i < nb; i++) {
            uint64_t p = qhat * vn[i] + carry; carry = p >> 32;
            int64_t t = (int64_t)un[i + j] - borrow - (int64_t)(p & 0xffffffffu);
            un[i + j] = (ail_limb)t; borrow = t < 0;
        }
        int64_t t = (int64_t)un[j + nb] - borrow - (int64_t)carry;
        un[j + nb] = (ail_limb)t;
        if (t < 0) {                        /* qhat was one too large: add the divisor back */
            qhat--;
            uint64_t c = 0;
            for (size_t i = 0; i < nb; i++) { c += (uint64_t)un[i + j] + vn[i]; un[i + j] = (ail_limb)c; c >>= 32; }
            un[j + nb] += (ail_limb)c;
        }
        if (q) q[j] = (ail_limb)qhat;
    }
    if (q) *qn = ail_bn_norm(q, na - nb + 1);
    if (r) {
        for (size_t i = 0; i < nb; i++) r[i] = s ? (un[i] >> s) | ((ail_limb)((uint64_t)un[i + 1] << (32 - s))) : un[i];
        *rn = ail_bn_norm(r, nb);
    }
    free(vn);
}

/* o = a << bits; capacity na + bits/32 + 1 */
static AIL_BIGFN size_t ail_bn_shl(ail_limb *o, const ail_limb *a, size_t na, uint64_t bits) {
    size_t w = (size_t)(bits >> 5); int s = (int)(bits & 31);
    if (!na) return 0;
    if (s == 0) { memmove(o + w, a, na * sizeof(ail_limb)); memset(o, 0, w * sizeof(ail_limb)); return na + w; }
    ail_limb carry = 0;
    for (size_t i = 0; i < na; i++) { ail_limb x = a[i]; o[w + i] = (x << s) | carry; carry = x >> (32 - s); }
    o[w + na] = carry;
    memset(o, 0, w * sizeof(ail_limb));
    return ail_bn_norm(o, na + w + 1);
}
/* o = a >> bits (truncating); capacity na */
static AIL_BIGFN size_t ail_bn_shr(ail_limb *o, const ail_limb *a, size_t na, uint64_t bits) {
    uint64_t w64 = bits >> 5; int s = (int)(bits & 31);
    if (w64 >= na) return 0;
    size_t w = (size_t)w64, n = na - w;
    if (s == 0) { memmove(o, a + w, n * sizeof(ail_limb)); return ail_bn_norm(o, n); }
    for (size_t i = 0; i < n; i++) {
        ail_limb lo = a[w + i] >> s, hi = (w + i + 1 < na) ? a[w + i + 1] << (32 - s) : 0;
        o[i] = lo | hi;
    }
    return ail_bn_norm(o, n);
}
/* true when any of the low `bits` bits of a is set (what a floor shift of a negative number has to know) */
static AIL_BIGFN int ail_bn_low_bits(const ail_limb *a, size_t na, uint64_t bits) {
    uint64_t w = bits >> 5; int s = (int)(bits & 31);
    for (size_t i = 0; i < w && i < na; i++) if (a[i]) return 1;
    if (s && w < na && (a[w] & (((ail_limb)1 << s) - 1))) return 1;
    return 0;
}

static AIL_BIGFN uint64_t ail_bn_bitlen(const ail_limb *a, size_t na) {
    if (!na) return 0;
    return (uint64_t)(na - 1) * 32 + (32 - __builtin_clz(a[na - 1]));
}

/* in-place a = a * m + add (single limb), capacity na+1; returns the new length */
static inline size_t ail_bn_muladd1(ail_limb *a, size_t na, ail_limb m, ail_limb add) {
    uint64_t c = add;
    for (size_t i = 0; i < na; i++) { c += (uint64_t)a[i] * m; a[i] = (ail_limb)c; c >>= 32; }
    if (c) a[na++] = (ail_limb)c;
    return na;
}

/* decimal digits of a (a != 0, na >= 1) into buf (at least 10*na+1 bytes), most significant first; returns the
   count. Repeated division by 10^9 on a working copy (quadratic; the 4300-digit limit keeps it at ~450 limbs). */
static AIL_BIGFN size_t ail_bn_to_dec(char *buf, const ail_limb *a, size_t na) {
    ail_limb *t = (ail_limb *)malloc(na * sizeof(ail_limb));
    if (!t) ail_die("out of memory");
    memcpy(t, a, na * sizeof(ail_limb));
    size_t n = na, o = 0, cap = 10 * na + 1;
    char *tmp = (char *)malloc(cap);
    if (!tmp) ail_die("out of memory");
    while (n) {
        uint64_t rem = 0;
        for (size_t i = n; i-- > 0; ) { uint64_t cur = (rem << 32) | t[i]; t[i] = (ail_limb)(cur / 1000000000u); rem = cur % 1000000000u; }
        n = ail_bn_norm(t, n);
        for (int k = 0; k < 9; k++) { tmp[o++] = (char)('0' + (int)(rem % 10)); rem /= 10; if (!n && !rem) break; }
    }
    while (o > 1 && tmp[o - 1] == '0') o--;
    for (size_t i = 0; i < o; i++) buf[i] = tmp[o - 1 - i];
    free(t); free(tmp);
    return o;
}

/* a digit string (ASCII '0'..'9' only, nd >= 1) into o (capacity nd/9 + 2 limbs); returns the normalised length */
static AIL_BIGFN size_t ail_bn_from_dec(ail_limb *o, const char *s, size_t nd) {
    size_t n = 0;
    size_t first = nd % 9 ? nd % 9 : 9;
    size_t i = 0;
    while (i < nd) {
        size_t take = i == 0 ? first : 9;
        ail_limb v = 0, m = 1;
        for (size_t k = 0; k < take; k++) { v = v * 10 + (ail_limb)(s[i + k] - '0'); m *= 10; }
        n = ail_bn_muladd1(o, n, m, v);
        i += take;
    }
    return ail_bn_norm(o, n);
}

/* two's complement helpers for the bitwise operators: x = sign * |a| into `o` as L limbs (L > na) */
static AIL_BIGFN void ail_bn_to_twos(ail_limb *o, size_t L, const ail_limb *a, size_t na, int neg) {
    memcpy(o, a, na * sizeof(ail_limb));
    memset(o + na, 0, (L - na) * sizeof(ail_limb));
    if (neg) { uint64_t c = 1; for (size_t i = 0; i < L; i++) { c += (ail_limb)~o[i]; o[i] = (ail_limb)c; c >>= 32; } }
}
/* the reverse: o holds an L-limb two's complement value; returns the sign (-1/0/1) and leaves the magnitude */
static AIL_BIGFN int ail_bn_from_twos(ail_limb *o, size_t L, size_t *n) {
    int neg = (o[L - 1] >> 31) & 1;
    if (neg) { uint64_t c = 1; for (size_t i = 0; i < L; i++) { c += (ail_limb)~o[i]; o[i] = (ail_limb)c; c >>= 32; } }
    *n = ail_bn_norm(o, L);
    return *n == 0 ? 0 : (neg ? -1 : 1);
}

/* frexp / ldexp without libm: a program that never touches a float must not pull libm in (its load is ~30k start-up instructions) */
static AIL_BIGFN double ail__ldexp(double x, int e) {
    union { double d; uint64_t u; } k;
    while (e > 1000) { k.u = (uint64_t)(1000 + 1023) << 52; x *= k.d; e -= 1000; if (x == HUGE_VAL || x == -HUGE_VAL) return x; }
    while (e < -1000) { k.u = (uint64_t)(-1000 + 1023) << 52; x *= k.d; e += 1000; if (x == 0.0) return x; }
    k.u = (uint64_t)(e + 1023) << 52; return x * k.d;       /* one rounding in the last step (a subnormal result) */
}
static AIL_BIGFN double ail__frexp(double v, int *e) {
    union { double d; uint64_t u; } k; k.d = v;
    int ex = (int)((k.u >> 52) & 0x7ff), adj = 0;
    if (ex == 0x7ff || v == 0.0) { *e = 0; return v; }
    if (ex == 0) { k.d = v * 18014398509481984.0; ex = (int)((k.u >> 52) & 0x7ff); adj = -54; }
    *e = ex - 1022 + adj;
    k.u = (k.u & 0x800fffffffffffffULL) | ((uint64_t)1022 << 52);
    return k.d;
}
/* fmod without libm (exact, by shift and subtract; the algorithm of musl's fmod): the remainder of x / y with the sign of x. A zero or NaN y, an
   infinite or NaN x give NaN, an infinite y gives x, as libm does. */
static AIL_BIGFN double ail__fmod(double x, double y) {
    union { double f; uint64_t i; } ux, uy; ux.f = x; uy.f = y;
    int ex = (int)(ux.i >> 52 & 0x7ff), ey = (int)(uy.i >> 52 & 0x7ff);
    uint64_t sx = ux.i >> 63, i;
    if (uy.i << 1 == 0 || y != y || ex == 0x7ff) return (x * y) / (x * y);
    if (ux.i << 1 <= uy.i << 1) { if (ux.i << 1 == uy.i << 1) return 0 * x; return x; }
    if (!ex) { for (i = ux.i << 12; i >> 63 == 0; ex--, i <<= 1); ux.i <<= -ex + 1; }
    else { ux.i &= ~0ULL >> 12; ux.i |= 1ULL << 52; }
    if (!ey) { for (i = uy.i << 12; i >> 63 == 0; ey--, i <<= 1); uy.i <<= -ey + 1; }
    else { uy.i &= ~0ULL >> 12; uy.i |= 1ULL << 52; }
    for (; ex > ey; ex--) { i = ux.i - uy.i; if (i >> 63 == 0) { if (i == 0) return 0 * x; ux.i = i; } ux.i <<= 1; }
    i = ux.i - uy.i; if (i >> 63 == 0) { if (i == 0) return 0 * x; ux.i = i; }
    for (; ux.i >> 52 == 0; ux.i <<= 1, ex--);
    if (ex > 0) { ux.i -= 1ULL << 52; ux.i |= (uint64_t)ex << 52; } else { ux.i >>= -ex + 1; }
    ux.i |= sx << 63;
    return ux.f;
}
/* the nearest double to sign*a, ties to even; *ovf set when it does not fit a double */
static AIL_BIGFN double ail_bn_to_double(const ail_limb *a, size_t na, int neg, int *ovf) {
    *ovf = 0;
    if (!na) return 0.0;
    uint64_t bl = ail_bn_bitlen(a, na);
    double r;
    if (bl <= 64) {
        uint64_t v = a[0] | (na > 1 ? (uint64_t)a[1] << 32 : 0);
        r = (double)v;                         /* the hardware conversion rounds to nearest even */
    } else {
        if (bl > 1024) { *ovf = 1; return neg ? -HUGE_VAL : HUGE_VAL; }
        /* top 64 bits, sticky from everything below, then one rounding */
        uint64_t sh = bl - 64;
        uint64_t top = 0;
        for (int k = 0; k < 64; k++) {
            uint64_t bit = sh + (uint64_t)k;
            if ((a[bit >> 5] >> (bit & 31)) & 1) top |= (uint64_t)1 << k;
        }
        int sticky = ail_bn_low_bits(a, na, sh);
        /* round top (64 bits) to 53 bits: keep 11 low bits as the rounding information */
        uint64_t low = top & 0x7ffu; uint64_t hi = top >> 11;     /* hi has 53 bits, top bit set */
        if (low > 0x400u || (low == 0x400u && (sticky || (hi & 1)))) hi++;
        r = ail__ldexp((double)hi, (int)(sh + 11));
        if (isinf(r)) { *ovf = 1; return neg ? -HUGE_VAL : HUGE_VAL; }
    }
    return neg ? -r : r;
}

/* ---- end of the big integer core ------------------------------------------------------------------------- */
'''
