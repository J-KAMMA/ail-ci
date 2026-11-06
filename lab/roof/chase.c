#define _POSIX_C_SOURCE 200809L
/* chase.c: random pointer chase, the roof for latency-bound (pointer-chasing) programs.
 *
 *   chase [clock_ghz]
 *
 * Builds a random single-cycle permutation over 2^k uint64 indices and walks it for a fixed number
 * of steps, so every load depends on the previous one. Prints, per working-set size,
 * "entries bytes ns_per_load cycles_per_load" (cycles need the measured clock, arg 1).
 *
 * Sizes: 4K (32 KiB, L1), 64K (512 KiB, L2), 1M (8 MiB, L3), 32M (256 MiB, DRAM).
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define _POSIX_C_SOURCE 200809L
#include <time.h>

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

static uint64_t *perm(size_t n, uint64_t seed) {
    uint64_t *p = malloc(n * sizeof *p);
    if (!p) exit(1);
    for (size_t i = 0; i < n; i++) p[i] = i;
    for (size_t i = n - 1; i > 0; i--) {          /* Sattolo: one cycle, no fixed points */
        seed = seed * 6364136223846793005ULL + 1442695040888963407ULL;
        size_t j = (size_t)((seed >> 33) % i);
        uint64_t t = p[i]; p[i] = p[j]; p[j] = t;
    }
    return p;
}

static double chase(size_t n, uint64_t *p, size_t steps, double clock_ghz, double *cpl) {
    size_t best = ~(size_t)0, reps = 5;
    double best_s = 1e30;
    volatile uint64_t sink;
    for (size_t r = 0; r < reps; r++) {
        size_t i = 0;
        double t0 = now();
        for (size_t k = 0; k < steps; k++) i = p[i];
        double t1 = now();
        sink = i; (void)sink;
        if (t1 - t0 < best_s) { best_s = t1 - t0; best = steps; }
    }
    double ns = best_s / (double)best * 1e9;
    *cpl = ns * clock_ghz;
    return ns;
}

int main(int argc, char **argv) {
    double clock_ghz = argc > 1 ? atof(argv[1]) : 0.0;
    size_t entries[] = {1u << 12, 1u << 16, 1u << 20, 1u << 25};
    size_t steps[] = {20000000, 20000000, 10000000, 3000000};
    printf("# entries bytes ns_per_load cycles_per_load\n");
    for (int i = 0; i < 4; i++) {
        uint64_t *p = perm(entries[i], 12345 + i);
        double cpl = 0.0;
        double ns = chase(entries[i], p, steps[i], clock_ghz, &cpl);
        printf("%zu %zu %.3f %.3f\n", entries[i], entries[i] * sizeof(uint64_t), ns, cpl);
        free(p);
    }
    return 0;
}
