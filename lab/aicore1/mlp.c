/* Plain C version of bench_mlp.py: the same weights, naive loops (sequential sums, not the fixed order), float.
   gcc -O2 -o mlp_c lab/aicore1/mlp.c */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define B 64
#define I 784
#define H 512
#define O 10
#define REPS 21

static float x[B][I], w1[I][H], b1[H], w2[H][O], b2[O], h[B][H], y[B][O];

static uint64_t fill(float *m, int n, uint64_t s, double scale) {
    for (int k = 0; k < n; k++) {
        s = (1664525 * s + 1013904223) % 4294967296ULL;
        m[k] = (float)(((double)s / 4294967296.0 - 0.5) * scale);
    }
    return s;
}

static void forward(void) {
    for (int i = 0; i < B; i++)
        for (int j = 0; j < H; j++) {
            float acc = 0.0f;
            for (int k = 0; k < I; k++) acc += x[i][k] * w1[k][j];
            acc += b1[j];
            h[i][j] = acc > 0.0f ? acc : 0.0f;
        }
    for (int i = 0; i < B; i++)
        for (int j = 0; j < O; j++) {
            float acc = 0.0f;
            for (int k = 0; k < H; k++) acc += h[i][k] * w2[k][j];
            y[i][j] = acc + b2[j];
        }
}

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

static int cmp(const void *a, const void *b) {
    double d = *(const double *)a - *(const double *)b;
    return (d > 0) - (d < 0);
}

int main(void) {
    uint64_t s = fill(&x[0][0], B * I, 1, 2.0);
    s = fill(&w1[0][0], I * H, s, 0.1);
    s = fill(b1, H, s, 0.1);
    s = fill(&w2[0][0], H * O, s, 0.1);
    fill(b2, O, s, 0.1);
    double ts[REPS];
    forward();
    for (int r = 0; r < REPS; r++) {
        double t0 = now();
        forward();
        ts[r] = now() - t0;
    }
    double total = 0.0;
    for (int i = 0; i < B; i++)
        for (int j = 0; j < O; j++) total += y[i][j];
    printf("%.17g\n", total);
    qsort(ts, REPS, sizeof(double), cmp);
    printf("forward median us %.1f\n", ts[REPS / 2] * 1e6);
    return 0;
}
