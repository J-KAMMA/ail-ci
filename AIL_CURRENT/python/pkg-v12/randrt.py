# -*- coding: utf-8 -*-
"""randrt.py -- `random.Random` on the general (boxed) path, in C (fragment 'rng' of safetyrt.py).

prelude_random.py is plain Python: on the general path every draw ran the Mersenne Twister word by word through boxed
integer operations (a refill alone is ~1250 of them), which was most of the instructions of a program that draws a
few hundred thousand numbers. prelude_random_boxed.py is the same class with the work done by the primitives below:
CPython 3.12's MT19937, its init_by_array seeding for an int seed, random(), getrandbits, _randbelow by rejection,
randrange / randint, choice, shuffle, sample (the pool and the selected-set variants, switched at CPython's size),
uniform, gauss (the cached pair), expovariate and triangular, bit for bit (the same algorithms as the typed
path's cruntime.RANDOM, which keeps one generator in static storage; here every Random object has its own).

The state is one list of 627 ints held in the object's `mt` field: the 624 words, the position, whether a second
gauss value is cached, and that value's bits. (A list, because the boxed runtime has no opaque value; the collector
already knows how to hold it.) A program that does not use the class gets the C it always had.
"""

# name -> (C call, argument count): safetyrt.PRIMS takes these with the fragment name 'rng'
PRIMS = {
    '_ail_rg_new': ('ail2r_new(cx, &{t}, {a0})', 1),
    '_ail_rg_seed': ('ail2r_seed(cx, &{t}, {a0}, {a1})', 2),
    '_ail_rg_random': ('ail2r_random(cx, &{t}, {a0})', 1),
    '_ail_rg_bits': ('ail2r_bits(cx, &{t}, {a0}, {a1})', 2),
    '_ail_rg_below': ('ail2r_below(cx, &{t}, {a0}, {a1})', 2),
    '_ail_rg_range': ('ail2r_range(cx, &{t}, {a0}, {a1}, {a2}, {a3}, {a4})', 5),
    '_ail_rg_choice': ('ail2r_choice(cx, &{t}, {a0}, {a1})', 2),
    '_ail_rg_shuffle': ('ail2r_shuffle(cx, &{t}, {a0}, {a1})', 2),
    '_ail_rg_sample': ('ail2r_sample(cx, &{t}, {a0}, {a1}, {a2})', 3),
    '_ail_rg_uniform': ('ail2r_uniform(cx, &{t}, {a0}, {a1}, {a2})', 3),
    '_ail_rg_gauss': ('ail2r_gauss(cx, &{t}, {a0}, {a1}, {a2})', 3),
    '_ail_rg_expo': ('ail2r_expo(cx, &{t}, {a0}, {a1})', 2),
    '_ail_rg_tri': ('ail2r_tri(cx, &{t}, {a0}, {a1}, {a2}, {a3})', 4),
}

RNG = r'''
/* ---- random.Random on the general path (randrt.py): MT19937 as CPython 3.12 runs it ---- */
#include <math.h>
#define AIL2R_MTI 624
#define AIL2R_HAVE 625
#define AIL2R_NEXT 626
#define AIL2R_LEN 627
static inline ail_st ail2r_state(ail_ctx *cx, ail_obj L, ail_obj **p) {
    if (L.tag != AIL_T_LIST || ((ail_vecobj *)L.o)->n != AIL2R_LEN)
        return ail_raise_c(cx, AIL_B_TYPEERROR, "random: the generator state is not the list Random made");
    *p = ((ail_vecobj *)L.o)->p;
    return AIL_OK;
}
static inline int ail2r_isint(ail_obj x) { return x.tag == AIL_T_INT || x.tag == AIL_T_BOOL; }
static ail_st ail2r_need_int(ail_ctx *cx, ail_obj x) {
    if (ail2r_isint(x)) return AIL_OK;
    char buf[96]; snprintf(buf, sizeof buf, "'%s' object cannot be interpreted as an integer", ail_type_name(x.tag));
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
/* x as a double; 0 when it is not a number */
static inline int ail2r_num(ail_obj x, double *d) {
    if (x.tag == AIL_T_FLOAT) { *d = ail_float_val(x); return 1; }
    if (ail2r_isint(x)) { *d = (double)x.i; return 1; }
    return 0;
}
static ail_st ail2r_need_num(ail_ctx *cx, ail_obj x, double *d) {
    if (ail2r_num(x, d)) return AIL_OK;
    char buf[96]; snprintf(buf, sizeof buf, "unsupported operand type(s): '%s' is not a number", ail_type_name(x.tag));
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
/* a - b as Python computes it before the float multiply: exact for two ints, then converted */
static inline double ail2r_diff(ail_obj a, ail_obj b) {
    if (ail2r_isint(a) && ail2r_isint(b)) return (double)((__int128)a.i - (__int128)b.i);
    return ail__as_double(a) - ail__as_double(b);
}

static void ail2r_init_by_array(ail_obj *p, const uint32_t *key, int len) {
    uint32_t mt[624];
    mt[0] = 19650218U;
    for (int i = 1; i < 624; i++) mt[i] = 1812433253U * (mt[i - 1] ^ (mt[i - 1] >> 30)) + (uint32_t)i;
    int i = 1, j = 0, k = 624 > len ? 624 : len;
    for (; k; k--) {
        mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525U)) + key[j] + (uint32_t)j;
        i++; j++;
        if (i >= 624) { mt[0] = mt[623]; i = 1; }
        if (j >= len) j = 0;
    }
    for (k = 623; k; k--) {
        mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941U)) - (uint32_t)i;
        i++;
        if (i >= 624) { mt[0] = mt[623]; i = 1; }
    }
    mt[0] = 0x80000000U;
    for (int n = 0; n < 624; n++) p[n] = ail_box_int((int64_t)mt[n]);
    p[AIL2R_MTI] = ail_box_int(624);
    p[AIL2R_HAVE] = ail_box_int(0);
    p[AIL2R_NEXT] = ail_box_int(0);
}
static void ail2r_seed_int(ail_obj *p, int64_t a) {
    uint64_t n = a < 0 ? (uint64_t)0 - (uint64_t)a : (uint64_t)a;
    uint32_t key[2];
    key[0] = (uint32_t)(n & 0xffffffffU); key[1] = (uint32_t)(n >> 32);
    ail2r_init_by_array(p, key, key[1] ? 2 : 1);
}
static inline ail_st ail2r_new(ail_ctx *cx, ail_obj *out, ail_obj seed) {
    ail_st st = ail2r_need_int(cx, seed); if (st != AIL_OK) return st;
    ail_vecobj *v = ail_vec_new(cx);
    ail_obj listobj; listobj.tag = AIL_T_LIST; listobj.o = (ail_gcobj *)v;
    ail_vec_reserve(cx, v, AIL2R_LEN);
    v->n = AIL2R_LEN;
    ail2r_seed_int(v->p, seed.i);
    *out = listobj;
    return AIL_OK;
}
static inline ail_st ail2r_seed(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj seed) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    if ((st = ail2r_need_int(cx, seed)) != AIL_OK) return st;
    ail2r_seed_int(p, seed.i);
    *out = ail_box_none();
    return AIL_OK;
}
static void ail2r_refill(ail_obj *p) {
    uint32_t y;
    int kk;
#define AIL2R_W(k) ((uint32_t)p[k].i)
    for (kk = 0; kk < 624 - 397; kk++) {
        y = (AIL2R_W(kk) & 0x80000000U) | (AIL2R_W(kk + 1) & 0x7fffffffU);
        p[kk].i = (int64_t)(AIL2R_W(kk + 397) ^ (y >> 1) ^ ((y & 1U) ? 0x9908b0dfU : 0U));
    }
    for (; kk < 623; kk++) {
        y = (AIL2R_W(kk) & 0x80000000U) | (AIL2R_W(kk + 1) & 0x7fffffffU);
        p[kk].i = (int64_t)(AIL2R_W(kk - 227) ^ (y >> 1) ^ ((y & 1U) ? 0x9908b0dfU : 0U));
    }
    y = (AIL2R_W(623) & 0x80000000U) | (AIL2R_W(0) & 0x7fffffffU);
    p[623].i = (int64_t)(AIL2R_W(396) ^ (y >> 1) ^ ((y & 1U) ? 0x9908b0dfU : 0U));
#undef AIL2R_W
    p[AIL2R_MTI].i = 0;
}
static inline uint32_t ail2r_u32(ail_obj *p) {
    if (p[AIL2R_MTI].i >= 624) ail2r_refill(p);
    uint32_t y = (uint32_t)p[p[AIL2R_MTI].i++].i;
    y ^= (y >> 11);
    y ^= (y << 7) & 0x9d2c5680U;
    y ^= (y << 15) & 0xefc60000U;
    y ^= (y >> 18);
    return y;
}
static inline double ail2r_rand(ail_obj *p) {
    uint32_t a = ail2r_u32(p) >> 5, b = ail2r_u32(p) >> 6;
    return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0);
}
/* getrandbits(k), 1 <= k <= 63: the first word is the low 32 bits */
static inline uint64_t ail2r_getbits(ail_obj *p, int k) {
    if (k <= 32) return (uint64_t)(ail2r_u32(p) >> (32 - k));
    uint64_t low = ail2r_u32(p);
    uint64_t high = ail2r_u32(p) >> (64 - k);
    return low | (high << 32);
}
static inline uint64_t ail2r_belowu(ail_obj *p, uint64_t n) {
    int k = 64 - __builtin_clzll(n);
    uint64_t r = ail2r_getbits(p, k);
    while (r >= n) r = ail2r_getbits(p, k);
    return r;
}
static inline ail_st ail2r_random(ail_ctx *cx, ail_obj *out, ail_obj L) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    *out = ail_box_float(cx, ail2r_rand(p));
    return AIL_OK;
}
static inline ail_st ail2r_bits(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj k) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    if ((st = ail2r_need_int(cx, k)) != AIL_OK) return st;
    if (k.i < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "number of bits must be non-negative");
    if (k.i == 0) { *out = ail_box_int(0); return AIL_OK; }
    if (k.i > 63) return ail_raise_c(cx, AIL_B_RUNTIMEERROR, "getrandbits: more than 63 bits needs integers beyond 64 bits");
    *out = ail_box_int((int64_t)ail2r_getbits(p, (int)k.i));
    return AIL_OK;
}
/* _randbelow(n): 0 for n <= 0, as prelude_random.py */
static inline ail_st ail2r_below(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj n) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    if ((st = ail2r_need_int(cx, n)) != AIL_OK) return st;
    *out = ail_box_int(n.i <= 0 ? 0 : (int64_t)ail2r_belowu(p, (uint64_t)n.i));
    return AIL_OK;
}
static inline __int128 ail2r_floordiv(__int128 a, __int128 b) {
    __int128 q = a / b;
    if ((a % b != 0) && ((a < 0) != (b < 0))) q -= 1;
    return q;
}
/* randrange(start[, stop[, step]]) (inclusive 0) and randint(start, stop) (inclusive 1, step 1) */
static ail_st ail2r_range(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj start, ail_obj stop, ail_obj step, ail_obj inclusive) {
    typedef __int128 i128;
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    char text[160];
    if ((st = ail2r_need_int(cx, start)) != AIL_OK) return st;
    if (stop.tag == AIL_T_NONE) {
        if (start.i > 0) { *out = ail_box_int((int64_t)ail2r_belowu(p, (uint64_t)start.i)); return AIL_OK; }
        return ail_raise_c(cx, AIL_B_VALUEERROR, "empty range for randrange()");
    }
    if ((st = ail2r_need_int(cx, stop)) != AIL_OK) return st;
    if ((st = ail2r_need_int(cx, step)) != AIL_OK) return st;
    i128 istart = start.i, istop = (inclusive.i ? (i128)stop.i + 1 : (i128)stop.i), width = istop - istart, n;
    int64_t st_ = inclusive.i ? 1 : step.i;
    if (st_ == 1) {
        if (width > 0) {
            *out = ail_box_int((int64_t)((uint64_t)start.i + ail2r_belowu(p, (uint64_t)width)));
            return AIL_OK;
        }
        snprintf(text, sizeof text, "empty range in randrange(%lld, %lld)", (long long)start.i, (long long)istop);
        return ail_raise_c(cx, AIL_B_VALUEERROR, text);
    }
    if (st_ > 0) n = ail2r_floordiv(width + st_ - 1, st_);
    else if (st_ < 0) n = ail2r_floordiv(width + st_ + 1, st_);
    else return ail_raise_c(cx, AIL_B_VALUEERROR, "zero step for randrange()");
    if (n <= 0) {
        snprintf(text, sizeof text, "empty range in randrange(%lld, %lld, %lld)", (long long)start.i, (long long)stop.i, (long long)st_);
        return ail_raise_c(cx, AIL_B_VALUEERROR, text);
    }
    i128 pick = (i128)ail2r_belowu(p, (uint64_t)n);
    *out = ail_box_int((int64_t)(istart + (i128)st_ * pick));
    return AIL_OK;
}
static inline ail_st ail2r_choice(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj seq) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    if (seq.tag != AIL_T_LIST) return ail_raise_c(cx, AIL_B_TYPEERROR, "random.choice: a list is expected");
    ail_vecobj *v = (ail_vecobj *)seq.o;
    if (v->n <= 0) return ail_raise_c(cx, AIL_B_INDEXERROR, "Cannot choose from an empty sequence");
    *out = v->p[ail2r_belowu(p, (uint64_t)v->n)];
    return AIL_OK;
}
static inline ail_st ail2r_shuffle(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj x) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    if (x.tag != AIL_T_LIST) return ail_raise_c(cx, AIL_B_TYPEERROR, "random.shuffle: a list is expected");
    ail_vecobj *v = (ail_vecobj *)x.o;
    for (int64_t i = v->n - 1; i >= 1; i--) {
        int64_t j = (int64_t)ail2r_belowu(p, (uint64_t)(i + 1));
        ail_obj t = v->p[i]; v->p[i] = v->p[j]; v->p[j] = t;
    }
    *out = ail_box_none();
    return AIL_OK;
}
/* sample(population, k) for a list: CPython's pool method for small populations, the selected-set method else */
static ail_st ail2r_sample(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj pop, ail_obj kk) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    if (pop.tag != AIL_T_LIST) return ail_raise_c(cx, AIL_B_TYPEERROR, "random.sample: a list is expected");
    if ((st = ail2r_need_int(cx, kk)) != AIL_OK) return st;
    ail_vecobj *src = (ail_vecobj *)pop.o;
    int64_t n = src->n, k = kk.i;
    if (k < 0 || k > n) return ail_raise_c(cx, AIL_B_VALUEERROR, "Sample larger than population or is negative");
    uint64_t setsize = 21;
    if (k > 5) {
        int m = 0; uint64_t pw = 1;
        while (pw < (uint64_t)k * 3) { pw *= 4; m++; }
        setsize += m > 30 ? ((uint64_t)1 << 62) : ((uint64_t)1 << (2 * m));
    }
    ail_vecobj *res = ail_vec_new(cx);
    ail_obj listobj; listobj.tag = AIL_T_LIST; listobj.o = (ail_gcobj *)res;
    if (k) ail_vec_reserve(cx, res, k);
    if ((uint64_t)n <= setsize) {
        ail_obj *pool = (ail_obj *)ail_xmalloc((size_t)(n ? n : 1) * sizeof(ail_obj));
        if (n) memcpy(pool, src->p, (size_t)n * sizeof(ail_obj)); /* an empty list has no array */
        for (int64_t i = 0; i < k; i++) {
            int64_t j = (int64_t)ail2r_belowu(p, (uint64_t)(n - i));
            res->p[res->n++] = pool[j];
            pool[j] = pool[n - i - 1];
        }
        free(pool);
    } else {
        uint64_t cap = 8;
        while (cap < (uint64_t)k * 2 + 2) cap <<= 1;
        int64_t *tab = (int64_t *)ail_xmalloc((size_t)cap * sizeof(int64_t));
        for (uint64_t i = 0; i < cap; i++) tab[i] = -1;
        for (int64_t i = 0; i < k; i++) {
            int64_t j;
            for (;;) {
                j = (int64_t)ail2r_belowu(p, (uint64_t)n);
                uint64_t h = ((uint64_t)j * 0x9E3779B97F4A7C15ULL) >> 20 & (cap - 1);
                while (tab[h] != -1 && tab[h] != j) h = (h + 1) & (cap - 1);
                if (tab[h] == -1) { tab[h] = j; break; }
            }
            res->p[res->n++] = src->p[j];
        }
        free(tab);
    }
    *out = listobj;
    return AIL_OK;
}
static inline ail_st ail2r_uniform(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj a, ail_obj b) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    double da, db;
    if ((st = ail2r_need_num(cx, a, &da)) != AIL_OK) return st;
    if ((st = ail2r_need_num(cx, b, &db)) != AIL_OK) return st;
    double r = ail2r_rand(p);
    volatile double scaled = ail2r_diff(b, a) * r;      /* rounded before the sum, as the two Python operations are */
    *out = ail_box_float(cx, da + scaled);
    return AIL_OK;
}
static inline ail_st ail2r_gauss(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj mu, ail_obj sigma) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    double dm, ds, z;
    if ((st = ail2r_need_num(cx, mu, &dm)) != AIL_OK) return st;
    if ((st = ail2r_need_num(cx, sigma, &ds)) != AIL_OK) return st;
    if (p[AIL2R_HAVE].i) {
        memcpy(&z, &p[AIL2R_NEXT].i, sizeof z);
        p[AIL2R_HAVE].i = 0;
    } else {
        double x2pi = ail2r_rand(p) * 6.283185307179586;
        double g2rad = sqrt(-2.0 * log(1.0 - ail2r_rand(p)));
        volatile double x_cos = x2pi, x_sin = x2pi;      /* cos and sin of one argument stay two libm calls */
        z = cos(x_cos) * g2rad;
        double nx = sin(x_sin) * g2rad;
        memcpy(&p[AIL2R_NEXT].i, &nx, sizeof nx);
        p[AIL2R_HAVE].i = 1;
    }
    volatile double scaled = z * ds;
    *out = ail_box_float(cx, dm + scaled);
    return AIL_OK;
}
static inline ail_st ail2r_expo(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj lambd) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    double dl;
    if ((st = ail2r_need_num(cx, lambd, &dl)) != AIL_OK) return st;
    double v = -log(1.0 - ail2r_rand(p));
    if (dl == 0.0) return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float division by zero");
    *out = ail_box_float(cx, v / dl);
    return AIL_OK;
}
static inline ail_st ail2r_tri(ail_ctx *cx, ail_obj *out, ail_obj L, ail_obj low, ail_obj high, ail_obj mode) {
    ail_obj *p; ail_st st = ail2r_state(cx, L, &p); if (st != AIL_OK) return st;
    double lo, hi, md = 0.0;
    if ((st = ail2r_need_num(cx, low, &lo)) != AIL_OK) return st;
    if ((st = ail2r_need_num(cx, high, &hi)) != AIL_OK) return st;
    if (mode.tag != AIL_T_NONE && (st = ail2r_need_num(cx, mode, &md)) != AIL_OK) return st;
    double u = ail2r_rand(p), c = 0.5;
    if (hi == lo) { *out = low; return AIL_OK; }
    double d = ail2r_diff(high, low);
    if (mode.tag != AIL_T_NONE) c = ail2r_diff(mode, low) / d;
    double base = lo;
    if (u > c) { u = 1.0 - u; c = 1.0 - c; base = hi; d = -d; }
    volatile double scaled = d * sqrt(u * c);
    *out = ail_box_float(cx, base + scaled);
    return AIL_OK;
}
'''

# AIL_UNIFIED=1 (unified.py): the float draws with an unboxed result, for a call whose value lands in a C double.
# The same arithmetic as ail2r_expo / _uniform / _gauss above (the checks of the arguments and of the state are
# emitted at the call, in the order those functions make them). Only a program built with the flag gets this.
RNG_U = r'''
/* ---- unboxed results of random.Random's float draws (unified.py, AIL_UNIFIED=1) ---- */
static inline ail_st ail2r_expo_u(ail_ctx *cx, double *out, ail_obj *p, double dl) {
    double v = -log(1.0 - ail2r_rand(p));
    if (dl == 0.0) return ail_raise_c(cx, AIL_B_ZERODIVISIONERROR, "float division by zero");
    *out = v / dl;
    return AIL_OK;
}
static inline double ail2r_uniform_u(ail_obj *p, double da, double diff) {
    double r = ail2r_rand(p);
    volatile double scaled = diff * r;
    return da + scaled;
}
static inline double ail2r_gauss_u(ail_obj *p, double dm, double ds) {
    double z;
    if (p[AIL2R_HAVE].i) {
        memcpy(&z, &p[AIL2R_NEXT].i, sizeof z);
        p[AIL2R_HAVE].i = 0;
    } else {
        double x2pi = ail2r_rand(p) * 6.283185307179586;
        double g2rad = sqrt(-2.0 * log(1.0 - ail2r_rand(p)));
        volatile double x_cos = x2pi, x_sin = x2pi;
        z = cos(x_cos) * g2rad;
        double nx = sin(x_sin) * g2rad;
        memcpy(&p[AIL2R_NEXT].i, &nx, sizeof nx);
        p[AIL2R_HAVE].i = 1;
    }
    volatile double scaled = z * ds;
    return dm + scaled;
}
'''
