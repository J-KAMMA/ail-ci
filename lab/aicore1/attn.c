/* Plain C version of bench_attn.py: the same inputs, naive loops (sequential sums, not the fixed order), float, expf.
   gcc -O2 -o attn_c lab/aicore1/attn.c -lm */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define N 128
#define D 64
#define REPS 101

static float q[N][D], k[N][D], v[N][D], s[N][N], o[N][D];

static uint64_t fill(float *m, int n, uint64_t st, double scale) {
    for (int t = 0; t < n; t++) {
        st = (1664525 * st + 1013904223) % 4294967296ULL;
        m[t] = (float)(((double)st / 4294967296.0 - 0.5) * scale);
    }
    return st;
}

static void attn(void) {
    const float scale = (float)(1.0 / sqrt((double)D));
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            float acc = 0.0f;
            for (int t = 0; t < D; t++) acc += q[i][t] * k[j][t];
            s[i][j] = acc * scale;
        }
    for (int i = 0; i < N; i++) {
        float m = s[i][0];
        for (int j = 1; j < N; j++) m = s[i][j] > m ? s[i][j] : m;
        float sum = 0.0f;
        for (int j = 0; j < N; j++) {
            s[i][j] = expf(s[i][j] - m);
            sum += s[i][j];
        }
        for (int j = 0; j < N; j++) s[i][j] = s[i][j] / sum;
    }
    for (int i = 0; i < N; i++)
        for (int j = 0; j < D; j++) {
            float acc = 0.0f;
            for (int t = 0; t < N; t++) acc += s[i][t] * v[t][j];
            o[i][j] = acc;
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
    uint64_t st = fill(&q[0][0], N * D, 7, 2.0);
    st = fill(&k[0][0], N * D, st, 2.0);
    fill(&v[0][0], N * D, st, 2.0);
    double ts[REPS];
    attn();
    for (int r = 0; r < REPS; r++) {
        double t0 = now();
        attn();
        ts[r] = now() - t0;
    }
    double total = 0.0;
    for (int i = 0; i < N; i++)
        for (int j = 0; j < D; j++) total += o[i][j];
    printf("%.17g\n", total);
    qsort(ts, REPS, sizeof(double), cmp);
    printf("forward median us %.1f\n", ts[REPS / 2] * 1e6);
    return 0;
}
