#define _POSIX_C_SOURCE 200809L
/* stream.c: STREAM triad (c = a + s*b) at four working-set sizes, the roof for memory-bound programs.
 *
 *   stream            run every size, print "working_set_bytes best_GBs median_GBs" per size
 *
 * Each size runs RUNS times; the median bandwidth is printed. The footprint of a size is
 * 3 * n * 8 bytes, so the four sizes span L2 (512 KiB), L3 (32 MiB) and DRAM.
 */
#include <stdio.h>
#include <stdlib.h>
#define _POSIX_C_SOURCE 200809L
#include <time.h>

#define RUNS 5

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + 1e-9 * t.tv_nsec;
}

static int cmp(const void *x, const void *y) {
    double a = *(const double *)x, b = *(const double *)y;
    return (a > b) - (a < b);
}

static double triad(size_t n, double *best) {
    double *a = aligned_alloc(64, n * sizeof *a);
    double *b = aligned_alloc(64, n * sizeof *b);
    double *c = aligned_alloc(64, n * sizeof *c);
    if (!a || !b || !c) { fprintf(stderr, "alloc failed\n"); exit(1); }
    for (size_t i = 0; i < n; i++) { a[i] = 1.0; b[i] = 2.0; c[i] = 0.0; }
    const double s = 3.0;
    double t[RUNS];
    for (int r = 0; r < RUNS; r++) {
        double t0 = now();
        for (size_t i = 0; i < n; i++) c[i] = a[i] + s * b[i];
        double t1 = now();
        t[r] = 3.0 * (double)n * sizeof(double) / (t1 - t0) / 1e9;
    }
    qsort(t, RUNS, sizeof t[0], cmp);
    *best = t[RUNS - 1];
    double med = t[RUNS / 2];
    volatile double touch = c[n / 2];
    (void)touch;
    free(a); free(b); free(c);
    return med;
}

int main(void) {
    size_t sizes[] = {1u << 16, 1u << 19, 1u << 22, 1u << 24};   /* 64K .. 16M doubles */
    printf("# working_set_bytes best_GBs median_GBs\n");
    for (int i = 0; i < 4; i++) {
        double best;
        double med = triad(sizes[i], &best);
        printf("%zu %.3f %.3f\n", 3 * sizes[i] * sizeof(double), best, med);
    }
    return 0;
}
