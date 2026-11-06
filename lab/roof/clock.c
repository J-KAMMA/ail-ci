#define _POSIX_C_SOURCE 200809L
/* clock.c: the machine's measured clock and scalar/SIMD width, without a hardware PMU.
 *
 *   clock
 *
 * 1. dependent add chain: N dependent `add` instructions take N cycles (ALU latency 1), so
 *    clock = N / seconds. This is the effective core clock during a compute-bound loop.
 * 2. eight independent add chains: the scalar integer throughput, in adds per cycle at that clock.
 * 3. eight independent AVX2 double adds: 4 lanes per instruction; doubles per cycle at the clock.
 * Prints one "key value" line each.
 */
#include <immintrin.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

#define ITER 400000000ULL

static double dependent_ghz(void) {
    uint64_t x = 1;
    double t0 = now();
    for (uint64_t k = 0; k < ITER / 8; k++) {
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
        __asm__ volatile("add $1, %0" : "+r"(x));
    }
    double t1 = now();
    if (x == 0) puts("unreachable");
    return (double)ITER / (t1 - t0) / 1e9;
}

int main(void) {
    double ghz = dependent_ghz();
    printf("dependent_add_ghz %.3f\n", ghz);
    {
        uint64_t a = 1, b = 2, c = 3, d = 4, e = 5, f = 6, g = 7, h = 8;
        double t0 = now();
        for (uint64_t k = 0; k < ITER / 8; k++) {
            __asm__ volatile("add $1, %0" : "+r"(a));
            __asm__ volatile("add $1, %0" : "+r"(b));
            __asm__ volatile("add $1, %0" : "+r"(c));
            __asm__ volatile("add $1, %0" : "+r"(d));
            __asm__ volatile("add $1, %0" : "+r"(e));
            __asm__ volatile("add $1, %0" : "+r"(f));
            __asm__ volatile("add $1, %0" : "+r"(g));
            __asm__ volatile("add $1, %0" : "+r"(h));
        }
        double t1 = now();
        printf("scalar_add_per_cycle %.3f\n", (double)ITER / (t1 - t0) / 1e9 / ghz);
        if (a + b + c + d + e + f + g + h == 0) puts("unreachable");
    }
    {
        __m256d b = _mm256_set1_pd(2.0);
        __m256d a0 = _mm256_set1_pd(1.0), a1 = a0, a2 = a0, a3 = a0;
        __m256d a4 = a0, a5 = a0, a6 = a0, a7 = a0;
        double t0 = now();
        for (uint64_t k = 0; k < ITER / 8; k++) {
            a0 = _mm256_add_pd(a0, b); a1 = _mm256_add_pd(a1, b);
            a2 = _mm256_add_pd(a2, b); a3 = _mm256_add_pd(a3, b);
            a4 = _mm256_add_pd(a4, b); a5 = _mm256_add_pd(a5, b);
            a6 = _mm256_add_pd(a6, b); a7 = _mm256_add_pd(a7, b);
        }
        double t1 = now();
        printf("avx2_vector_add_per_cycle %.3f\n", (double)ITER / (t1 - t0) / 1e9 / ghz);
        printf("avx2_double_add_per_cycle %.3f\n", (double)ITER * 4.0 / (t1 - t0) / 1e9 / ghz);
        double r[4];
        _mm256_storeu_pd(r, _mm256_add_pd(_mm256_add_pd(_mm256_add_pd(a0, a1), _mm256_add_pd(a2, a3)),
                                          _mm256_add_pd(_mm256_add_pd(a4, a5), _mm256_add_pd(a6, a7))));
        if (r[0] == 0.0) puts("unreachable");
    }
    return 0;
}
