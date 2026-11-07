/* fdarr3 step 1: native binary32 + - * / sqrt (and the double->float store) against the exact definition of
   prelude_ailarray.py: compute in binary64, round once with _ail_ta_r32 (Veltkamp split, transcribed below in pure
   double arithmetic). Every NaN result is canonical in the arrays, so two NaNs compare equal; everything else compares
   by bit pattern (signed zeros included).  Build: gcc -O2 -ffp-contract=off -o f32_identity tools/f32_identity.c -lm (no -ffast-math, x86-64 SSE2); run:
   ./f32_identity [pairs per operation, default 20M]. Used by AIL_CURRENT/test_ail_array_f32native.py (job fdarr3). */
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if FLT_EVAL_METHOD != 0
#error "this proof assumes FLT_EVAL_METHOD == 0"
#endif

static double r32(double x) {               /* _ail_ta_r32, line for line */
    if (x != x) return NAN;
    double y = fabs(x);
    if (y < 1.1754943508222875e-38) return copysign((y + 9.466330862652142e-30) - 9.466330862652142e-30, x);
    if (y >= 3.4028235677973366e+38) return copysign(INFINITY, x);
    double c = x * 536870913.0;
    return c - (c - x);
}
static double fdiv0(double x, double y) {   /* _ail_ta_fdiv0 */
    if (x != x || x == 0.0) return NAN;
    return copysign(INFINITY, copysign(1.0, x) * copysign(1.0, y));
}
static double ref(int op, float a, float b) {
    double x = a, y = b, v;
    switch (op) {
    case 0: v = x + y; break;
    case 1: v = x - y; break;
    case 2: v = x * y; break;
    case 3: v = (y == 0.0) ? fdiv0(x, y) : x / y; break;
    default: v = (x != x) ? NAN : (x < 0.0 ? NAN : sqrt(x)); break;   /* _ail_taf_fn which=0 */
    }
    return r32(v);
}
static float nat(int op, float a, float b) {
    switch (op) {
    case 0: return a + b;
    case 1: return a - b;
    case 2: return a * b;
    case 3: return a / b;
    default: return sqrtf(a);
    }
}
static uint32_t fb(float f) { uint32_t u; memcpy(&u, &f, 4); return u; }
static float bf(uint32_t u) { float f; memcpy(&f, &u, 4); return f; }
static uint64_t db(double d) { uint64_t u; memcpy(&u, &d, 8); return u; }
static int same(float n, double r) {
    if (n != n) return r != r;
    if (r != r) return 0;
    return db((double)n) == db(r);
}

static uint64_t s = 88172645463325252ull;
static uint64_t rnd(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }

static const uint32_t SPECIAL[] = {0x00000000, 0x80000000, 0x00000001, 0x80000001, 0x00000002, 0x007fffff, 0x807fffff,
    0x00800000, 0x80800000, 0x00800001, 0x7f7fffff, 0xff7fffff, 0x7f7ffffe, 0x7f800000, 0xff800000, 0x7fc00000,
    0x3f800000, 0xbf800000, 0x3f800001, 0x3f7fffff, 0x4b800000, 0x4b800001, 0x33800000, 0x34000000, 0x3dcccccd,
    0x5f800000, 0x1f800000, 0x0c000000, 0x72800000, 0x00400000, 0x40000000, 0x3fffffff};
#define NSPECIAL (sizeof SPECIAL / sizeof SPECIAL[0])

/* one operand drawn from a mix of classes: any pattern, normal near 1, subnormal, near overflow, special,
   or a neighbour of the other operand (cancellation and ties) */
static uint32_t pick(uint32_t other) {
    uint64_t r = rnd();
    uint32_t sign = (uint32_t)(r >> 63) << 31;
    switch ((r >> 56) & 7) {
    case 0: case 1: return (uint32_t)rnd();
    case 2: return sign | (uint32_t)((rnd() % 0x7f800000u));                    /* any finite */
    case 3: return sign | (uint32_t)(rnd() % 0x00800000u);                      /* subnormal or zero */
    case 4: return sign | (0x7f000000u + (uint32_t)(rnd() % 0x00800000u));    /* top binade */
    case 5: return SPECIAL[rnd() % NSPECIAL] ^ (uint32_t)(rnd() & 0x80000000u);
    case 6: return (other ^ (uint32_t)(rnd() & 0x80000000u)) + (uint32_t)(rnd() % 64) - 32;   /* neighbour */
    default: return sign | ((0x30000000u + (uint32_t)(rnd() % 0x1f000000u)) & 0x7f800000u) | (uint32_t)(rnd() & 0x7fu); /* few mantissa bits: exact ties */
    }
}

int main(int argc, char **argv) {
    long long per = argc > 1 ? atoll(argv[1]) : 20000000LL;
    const char *names[5] = {"add", "sub", "mul", "div", "sqrt"};
    long long bad_total = 0;
    for (int op = 0; op < 5; op++) {
        long long n = 0, bad = 0;
        /* every pair of specials */
        for (unsigned i = 0; i < NSPECIAL; i++)
            for (unsigned j = 0; j < NSPECIAL; j++) {
                float a = bf(SPECIAL[i]), b = bf(SPECIAL[j]);
                n++; if (!same(nat(op, a, b), ref(op, a, b))) { if (bad++ < 5) printf("BAD %s %08x %08x\n", names[op], SPECIAL[i], SPECIAL[j]); }
                a = -a; n++; if (!same(nat(op, a, b), ref(op, a, b))) { if (bad++ < 5) printf("BAD %s %08x %08x\n", names[op], fb(a), SPECIAL[j]); }
            }
        if (op == 4) {   /* sqrt: every binary32 pattern */
            for (uint64_t u = 0; u <= 0xffffffffull; u++) {
                float a = bf((uint32_t)u);
                n++; if (!same(nat(op, a, 0), ref(op, a, 0))) { if (bad++ < 5) printf("BAD sqrt %08x\n", (unsigned)u); }
            }
        } else {
            for (long long t = 0; t < per; t++) {
                uint32_t ua = pick((uint32_t)rnd());
                uint32_t ub = pick(ua);
                float a = bf(ua), b = bf(ub);
                n++; if (!same(nat(op, a, b), ref(op, a, b))) { if (bad++ < 5) printf("BAD %s %08x %08x\n", names[op], ua, ub); }
            }
        }
        printf("%-4s pairs %lld mismatches %lld\n", names[op], n, bad);
        bad_total += bad;
    }
    /* the store: (float)x for a binary64 x against r32(x), random doubles of every binade plus f32 midpoints */
    {
        long long n = 0, bad = 0;
        for (long long t = 0; t < per; t++) {
            uint64_t u = rnd();
            double x;
            if (t & 1) {
                memcpy(&x, &u, 8);
            } else {   /* a midpoint between two neighbouring f32 values, or one ulp of binary64 beside it */
                uint32_t f = (uint32_t)u & 0x7f7fffffu;
                double lo = bf(f), hi = bf(f + 1);
                x = lo + (hi - lo) / 2;
                int w = (int)((u >> 40) % 3);
                if (w == 1) x = nextafter(x, 0); else if (w == 2) x = nextafter(x, INFINITY);
                if (u >> 63) x = -x;
            }
            float nf = (float)x;
            n++;
            if (!same(nf, r32(x))) { if (bad++ < 5) printf("BAD store %016llx\n", (unsigned long long)db(x)); }
        }
        printf("store values %lld mismatches %lld\n", n, bad);
        bad_total += bad;
    }
    printf("TOTAL mismatches %lld\n", bad_total);
    return bad_total != 0;
}
