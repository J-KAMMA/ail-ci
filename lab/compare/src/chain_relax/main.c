#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

static int parse(const char *s, uint64_t max, uint64_t *out) {
    if (!*s) return 0;
    uint64_t v = 0;
    for (; *s; s++) {
        if (*s < '0' || *s > '9') return 0;
        unsigned d = (unsigned)(*s - '0');
        if (v > (UINT64_MAX - d) / 10) return 0;
        v = v * 10 + d;
        if (v > max) return 0;
    }
    *out = v;
    return 1;
}

static void pr(const char *name, double v) {
    char buf[512];
    snprintf(buf, sizeof buf, "%.9f", v);
    char *p = buf;
    if (p[0] == '-') {
        int zero = 1;
        for (char *q = p + 1; *q; q++)
            if (*q != '0' && *q != '.') { zero = 0; break; }
        if (zero) p++;
    }
    printf("%s %s\n", name, p);
}

#define STEP(L, R, C, OUT) do { \
    double d_ = ((L) + (R)) - ((C) + (C)); \
    double g_ = d_ / (1.0 + sqrt(d_ * d_ + 0.0625)); \
    (OUT) = (C) + 0.375 * g_; } while (0)

int main(int argc, char **argv) {
    if (argc != 4) return 1;
    uint64_t N, T, SEED;
    if (!parse(argv[1], 10000000, &N) || N < 1) return 1;
    if (!parse(argv[2], 1000000, &T)) return 1;
    if (!parse(argv[3], UINT64_MAX, &SEED)) return 1;
    double *h = malloc(N * sizeof(double));
    if (!h) return 1;
    uint64_t x = SEED;
    for (uint64_t i = 0; i < N; i++) {
        x = x * 6364136223846793005ULL + 1442695040888963407ULL;
        h[i] = (double)((int64_t)((x >> 33) % 2001) - 1000) / 64.0;
    }
    for (uint64_t s = 1; s <= T; s++) {
        if (s & 1) {
            double l = h[N - 1];
            for (uint64_t i = 0; i < N; i++) {
                double c = h[i];
                double r = h[i + 1 == N ? 0 : i + 1];
                double nv;
                STEP(l, r, c, nv);
                h[i] = nv;
                l = nv;
            }
        } else {
            double r = h[0];
            for (uint64_t i = N; i-- > 0;) {
                double c = h[i];
                double l = h[i == 0 ? N - 1 : i - 1];
                double nv;
                STEP(l, r, c, nv);
                h[i] = nv;
                r = nv;
            }
        }
    }
    double sum = 0.0, energy = 0.0, mn = h[0], mx = h[0];
    for (uint64_t i = 0; i < N; i++) {
        sum = sum + h[i];
        double t = h[i + 1 == N ? 0 : i + 1] - h[i];
        energy = energy + t * t;
        if (h[i] < mn) mn = h[i];
        if (h[i] > mx) mx = h[i];
    }
    pr("sum", sum);
    pr("energy", energy);
    pr("min", mn);
    pr("max", mx);
    pr("first", h[0]);
    pr("middle", h[N / 2]);
    pr("last", h[N - 1]);
    return 0;
}
