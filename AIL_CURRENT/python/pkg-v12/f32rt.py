# -*- coding: utf-8 -*-
"""f32rt.py -- the native kernels of ail_array f32 arrays on the typed path (job fdarr3, docs/design/TYPED_ARRAY.md T3b).

An f32 array (`_AilTAS`, prelude_ailarray.py) keeps its elements as a `bytearray` of 4 bytes per element: the
little-endian binary32 pattern, every NaN the canonical 7fc00000. The prelude names a few primitives `_ail_tz_*` and
defines each of them in plain Python (binary64 arithmetic rounded once by `_ail_ta_r32`, the exact definition of the
f32 dtype): CPython and the general path run those definitions. The typed path drops the definitions
(`pyfunc._strip_tz_defs`) and calls the C below instead (`pyfunc._AIL_TZ`).

Why native binary32 arithmetic is the same definition. For + - * / and sqrt of binary32 operands, the binary64 result
rounded once to binary32 is the correctly rounded binary32 result, because 53 >= 2 * 24 + 2 (double rounding is
innocuous). C `float` arithmetic gives that correctly rounded result when every operation is rounded to binary32:
FLT_EVAL_METHOD == 0 (SSE2 on x86-64, every arm64), no -ffast-math, no contraction (the build passes
-ffp-contract=off; the kernels also keep each product and each sum in its own rounded `float`). Proof run:
tools/f32_identity.c (50M operand pairs per operation with every special class, every binary32 for sqrt, 50M stores).
A target with excess precision (FLT_EVAL_METHOD != 0, x87) rounds each result through a volatile float instead, which is
again the correctly rounded value (64 >= 2 * 24 + 2) -- and takes the scalar loops. The store of a binary64 value
`(float)x` is round-to-nearest-even with subnormals and overflow to +-inf: `_ail_ta_r32` exactly.

exp, log and tanh are not correctly rounded functions, so they stay on the binary64 path (prelude). The reductions
keep the order of design 3.5 exactly: blocks of 1024, sixteen lanes from -0.0, the 8-4-2-1 tree over the lanes, the
power-of-two tree over the blocks, a float add (and a float product for dot / matmul) at every step.

The vector loops (GCC / clang vector extensions, 4 lanes) apply the very same IEEE operation to each element as the
scalar loops; `-DAILZ_SCALAR` builds the scalar loops only (the tests build both).
"""

TYPED = r'''
/* ---- ail_array f32 kernels (f32rt.py, job fdarr3) ---- */
#include <float.h>
#include <string.h>
#include <math.h>
#if defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "ail_array f32 storage is little-endian"
#endif
#if defined(__FAST_MATH__)
#error "ail_array f32 kernels need IEEE arithmetic (no -ffast-math)"
#endif
#if defined(FLT_EVAL_METHOD) && FLT_EVAL_METHOD != 0
#define AILZ_EXCESS 1
static float ailz_fix(float x) { volatile float t = x; return t; }
#else
#define ailz_fix(x) (x)
#endif
#if !defined(AILZ_SCALAR) && !defined(AILZ_EXCESS) && (defined(__GNUC__) || defined(__clang__)) && !defined(__TINYC__) \
    && (defined(__SSE2__) || defined(__ARM_NEON) || defined(__aarch64__))
#define AILZ_VEC 1
typedef float ailz_v4f __attribute__((vector_size(16)));
typedef uint32_t ailz_v4u __attribute__((vector_size(16)));
static inline ailz_v4f ailz_vld(const unsigned char *p) { ailz_v4f v; memcpy(&v, p, 16); return v; }
static inline void ailz_vst(unsigned char *p, ailz_v4f v) {
    ailz_v4u u;
    memcpy(&u, &v, 16);
    ailz_v4u m = (ailz_v4u)((u & 0x7fffffffu) > 0x7f800000u);       /* NaN lanes: all ones */
    u = (u & ~m) | (m & 0x7fc00000u);
    memcpy(p, &u, 16);
}
#endif
static inline float ailz_ld(const unsigned char *p, int64_t k) { float f; memcpy(&f, p + 4 * k, 4); return f; }
static inline void ailz_st(unsigned char *p, int64_t k, float f) {
    uint32_t u;
    memcpy(&u, &f, 4);
    if ((u & 0x7fffffffu) > 0x7f800000u) u = 0x7fc00000u;
    memcpy(p + 4 * k, &u, 4);
}
static void ailz_chk(const ail_bytearray *B, int64_t n) {
    if (n < 0 || (uint64_t)n > (uint64_t)(B->n / 4)) ail_die("ail_array: f32 storage smaller than its length");
}
static double ailz_get(ail_bytearray *B, int64_t k) {
    if ((uint64_t)k >= (uint64_t)(B->n / 4)) ail_die("array index out of range");
    return (double)ailz_ld(B->p, k);
}
static int64_t ailz_put(ail_bytearray *B, int64_t k, double x) {
    if ((uint64_t)k >= (uint64_t)(B->n / 4)) ail_die("array index out of range");
    ailz_st(B->p, k, ailz_fix((float)x));
    return 0;
}
/* d = a op b, element by element (op 0 + 1 - 2 * 3 /); d may be a or b */
#define AILZ_AA(OP) do { \
        AILZ_AAV(OP) \
        for (; k < n; k++) ailz_st(d, k, ailz_fix(ailz_ld(a, k) OP ailz_ld(b, k))); \
    } while (0)
#ifdef AILZ_VEC
#define AILZ_AAV(OP) for (; k + 4 <= n; k += 4) ailz_vst(d + 4 * k, ailz_vld(a + 4 * k) OP ailz_vld(b + 4 * k));
#else
#define AILZ_AAV(OP)
#endif
static int64_t ailz_aa(ail_bytearray *D, ail_bytearray *A, ail_bytearray *B, int64_t n, int64_t op) {
    ailz_chk(D, n); ailz_chk(A, n); ailz_chk(B, n);
    if (n == 0) return 0;
    unsigned char *d = D->p;
    const unsigned char *a = A->p, *b = B->p;
    int64_t k = 0;
    if (op == 0) AILZ_AA(+);
    else if (op == 1) AILZ_AA(-);
    else if (op == 2) AILZ_AA(*);
    else AILZ_AA(/);
    return 0;
}
/* d = a op x, or x op a when refl (x is a binary64 value that is exactly f32) */
#ifdef AILZ_VEC
#define AILZ_ASV(EXPR) for (; k + 4 <= n; k += 4) { ailz_v4f v = ailz_vld(a + 4 * k); ailz_vst(d + 4 * k, EXPR); }
#else
#define AILZ_ASV(EXPR)
#endif
#define AILZ_AS(VEXPR, SEXPR) do { AILZ_ASV(VEXPR) for (; k < n; k++) { float v = ailz_ld(a, k); ailz_st(d, k, ailz_fix(SEXPR)); } } while (0)
static int64_t ailz_as(ail_bytearray *D, ail_bytearray *A, double xd, int64_t n, int64_t op, int64_t refl) {
    ailz_chk(D, n); ailz_chk(A, n);
    if (n == 0) return 0;
    unsigned char *d = D->p;
    const unsigned char *a = A->p;
    float x = (float)xd;
    int64_t k = 0;
#ifdef AILZ_VEC
    ailz_v4f xv = {x, x, x, x};
#endif
    if (op == 0) AILZ_AS(v + xv, v + x);
    else if (op == 1 && refl) AILZ_AS(xv - v, x - v);
    else if (op == 1) AILZ_AS(v - xv, v - x);
    else if (op == 2) AILZ_AS(v * xv, v * x);
    else if (refl) AILZ_AS(xv / v, x / v);
    else AILZ_AS(v / xv, v / x);
    return 0;
}
/* d = f(a): which 0 negation, 1 fabs, 2 sqrt (the NaN results canonical) */
static int64_t ailz_un(ail_bytearray *D, ail_bytearray *A, int64_t n, int64_t which) {
    ailz_chk(D, n); ailz_chk(A, n);
    if (n == 0) return 0;
    unsigned char *d = D->p;
    const unsigned char *a = A->p;
    for (int64_t k = 0; k < n; k++) {
        float v = ailz_ld(a, k);
        ailz_st(d, k, which == 0 ? -v : which == 1 ? fabsf(v) : ailz_fix(sqrtf(v)));
    }
    return 0;
}
/* the f32 sum of a[0..n) (prod 0) or of the products a[k] * e[k] (prod 1) in the order of design 3.5 */
static float ailz_tree(const float *blocks, int64_t lo, int64_t hi) {
    if (hi - lo == 1) return blocks[lo];
    int64_t p = 1;
    while (p * 2 < hi - lo) p = p * 2;
    return ailz_fix(ailz_tree(blocks, lo, lo + p) + ailz_tree(blocks, lo + p, hi));
}
static float ailz_block(const unsigned char *a, const unsigned char *e, int64_t s, int64_t t, int prod) {
    float l[16];
    for (int y = 0; y < 16; y++) l[y] = -0.0f;
    int64_t k = s;
#ifdef AILZ_VEC
    ailz_v4f L0 = {-0.0f, -0.0f, -0.0f, -0.0f}, L1 = L0, L2 = L0, L3 = L0;
    if (prod) {
        for (; k + 16 <= t; k += 16) {
            ailz_v4f p0 = ailz_vld(a + 4 * k) * ailz_vld(e + 4 * k);
            ailz_v4f p1 = ailz_vld(a + 4 * k + 16) * ailz_vld(e + 4 * k + 16);
            ailz_v4f p2 = ailz_vld(a + 4 * k + 32) * ailz_vld(e + 4 * k + 32);
            ailz_v4f p3 = ailz_vld(a + 4 * k + 48) * ailz_vld(e + 4 * k + 48);
            L0 = L0 + p0; L1 = L1 + p1; L2 = L2 + p2; L3 = L3 + p3;
        }
    } else {
        for (; k + 16 <= t; k += 16) {
            L0 = L0 + ailz_vld(a + 4 * k);
            L1 = L1 + ailz_vld(a + 4 * k + 16);
            L2 = L2 + ailz_vld(a + 4 * k + 32);
            L3 = L3 + ailz_vld(a + 4 * k + 48);
        }
    }
    memcpy(l, &L0, 16); memcpy(l + 4, &L1, 16); memcpy(l + 8, &L2, 16); memcpy(l + 12, &L3, 16);
#endif
    while (k < t) {
        /* one group of up to 16 elements; a lane the group does not reach adds -0.0, the identity */
        for (int y = 0; y < 16; y++) {
            float v = -0.0f;
            if (k + y < t) v = prod ? ailz_fix(ailz_ld(a, k + y) * ailz_ld(e, k + y)) : ailz_ld(a, k + y);
            l[y] = ailz_fix(l[y] + v);
        }
        k += 16;
    }
    for (int y = 0; y < 8; y++) l[y] = ailz_fix(l[y] + l[y + 8]);
    for (int y = 0; y < 4; y++) l[y] = ailz_fix(l[y] + l[y + 4]);
    l[0] = ailz_fix(l[0] + l[2]);
    l[1] = ailz_fix(l[1] + l[3]);
    return ailz_fix(l[0] + l[1]);
}
static float ailz_reduce(const unsigned char *a, const unsigned char *e, int64_t n, int prod, float *blocks) {
    int64_t nb = (n + 1023) / 1024;
    for (int64_t b = 0; b < nb; b++) {
        int64_t s = b * 1024, t = s + 1024;
        if (t > n) t = n;
        blocks[b] = ailz_block(a, e, s, t, prod);
    }
    return ailz_tree(blocks, 0, nb);
}
static float *ailz_blocks(int64_t n) {
    int64_t nb = (n + 1023) / 1024;
    float *blocks = (float *)malloc((size_t)(nb ? nb : 1) * sizeof(float));
    if (!blocks) ail_die("out of memory");
    return blocks;
}
static double ailz_fsum(ail_bytearray *A, ail_bytearray *E, int64_t n, int64_t prod) {
    ailz_chk(A, n); ailz_chk(E, n);
    if (n == 0) return 0.0;
    float *blocks = ailz_blocks(n);
    float r = ailz_reduce(A->p, E->p, n, prod != 0, blocks);
    free(blocks);
    if (r != r) return NAN;
    return (double)r;
}
/* out (m x n) = a (m x k) times b (k x n), row-major: element (i, j) is the f32 dot of row i of a and column j of b */
static int64_t ailz_mm(ail_bytearray *O, ail_bytearray *A, ail_bytearray *B, int64_t m, int64_t k, int64_t n) {
    if (m < 0 || k < 0 || n < 0 || (k && m > INT64_MAX / k) || (n && m > INT64_MAX / n) || (n && k > INT64_MAX / n / 4))
        ail_die("ail_array: matmul size");
    ailz_chk(O, m * n); ailz_chk(A, m * k); ailz_chk(B, k * n);
    if (k == 0 || m == 0 || n == 0) return 0;
    unsigned char *bt = (unsigned char *)malloc((size_t)(k * n) * 4);
    if (!bt) ail_die("out of memory");
    for (int64_t kk = 0; kk < k; kk++)
        for (int64_t jj = 0; jj < n; jj++) memcpy(bt + 4 * (jj * k + kk), B->p + 4 * (kk * n + jj), 4);
    float *blocks = ailz_blocks(k);
    for (int64_t i = 0; i < m; i++)
        for (int64_t j = 0; j < n; j++) {
            float r = ailz_reduce(A->p + 4 * (i * k), bt + 4 * (j * k), k, 1, blocks);
            ailz_st(O->p, i * n + j, r);
        }
    free(blocks);
    free(bt);
    return 0;
}
/* the index of the first NaN pattern other than 7fc00000 (sign or payload), or -1 */
static int64_t ailz_badnan(ail_bytearray *B, int64_t n) {
    ailz_chk(B, n);
    for (int64_t k = 0; k < n; k++) {
        uint32_t u;
        memcpy(&u, B->p + 4 * k, 4);
        if ((u & 0x7fffffffu) > 0x7f800000u && u != 0x7fc00000u) return k;
    }
    return -1;
}
'''


def register(ORDER, SOURCE, REQUIRES):
    """Add the F32K part to cruntime's tables (called once at the end of cruntime.py)."""
    ORDER.append('F32K')
    SOURCE['F32K'] = TYPED
    REQUIRES['F32K'] = ['TYPES', 'DIE', 'BYTEARRAY']
