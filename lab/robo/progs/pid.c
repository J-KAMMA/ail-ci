/* 1 kHz control-loop jitter measurement, C reference.

   Absolute-deadline periodic loop with clock_nanosleep(CLOCK_MONOTONIC,
   TIMER_ABSTIME). Each iteration runs the same PID update as pid.py over 8
   state variables, then sleeps until the next absolute deadline, then records
   how late the wake-up was in a 1-microsecond histogram (bucket 20000 is
   "20000 us or more"; max is exact).

   usage: pid [iters] noalloc|alloc
*/
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define N 8
#define BUCKETS 20001
#define PERIOD_NS 1000000L

static const double SETPOINT[N] = {1.0, 0.5, 0.0, -0.5, -1.0, 0.25, 0.75, -0.25};

static void pid_step(double *state, double *integral, double *prev, int k) {
    double err = SETPOINT[k] - state[k];
    integral[k] += err * 0.005;
    double deriv = (err - prev[k]) / 0.005;
    prev[k] = err;
    double u = 0.85 * err + 0.12 * integral[k] + 0.04 * deriv;
    if (u > 2.0) u = 2.0;
    if (u < -2.0) u = -2.0;
    state[k] += (u - 0.3 * state[k]) * 0.005;
}

static int percentile(const unsigned *hist, int iters, int num, int den) {
    int want = (int)((long)iters * num / den);
    int cum = 0;
    for (int b = 0; b < BUCKETS; b++) {
        cum += (int)hist[b];
        if (cum > want) return b;
    }
    return BUCKETS - 1;
}

int main(int argc, char **argv) {
    int iters = argc > 1 ? atoi(argv[1]) : 20000;
    int allocating = argc > 2 && strcmp(argv[2], "alloc") == 0;
    if (iters <= 0) return 2;

    double state[N], integral[N], prev[N];
    for (int k = 0; k < N; k++) { state[k] = 0.0; integral[k] = 0.0; prev[k] = 0.0; }
    unsigned *hist = calloc(BUCKETS, sizeof(unsigned));
    if (!hist) return 3;

    struct timespec next;
    clock_gettime(CLOCK_MONOTONIC, &next);

    double max_miss = 0.0;
    int overruns = 0;
    for (int i = 0; i < iters; i++) {
        next.tv_nsec += PERIOD_NS;
        while (next.tv_nsec >= 1000000000L) { next.tv_nsec -= 1000000000L; next.tv_sec += 1; }

        for (int k = 0; k < N; k++) pid_step(state, integral, prev, k);

        if (allocating) {
            double *tmp = malloc(N * sizeof(double));
            if (!tmp) return 4;
            memcpy(tmp, state, N * sizeof(double));
            double sum = 0.0;
            for (int k = 0; k < N; k++) sum += tmp[k];
            state[0] += sum * 0.0;
            free(tmp);
        }

        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);

        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        double miss = ((double)(now.tv_sec - next.tv_sec) * 1e9 +
                       (double)(now.tv_nsec - next.tv_nsec)) / 1000.0;
        if (miss > max_miss) max_miss = miss;
        int b = (int)miss;
        if (b < 0) b = 0;
        if (b >= BUCKETS) b = BUCKETS - 1;
        hist[b]++;
        if (miss >= 1000.0) overruns++;
    }

    printf("iters %d\n", iters);
    printf("p50 %d\n", percentile(hist, iters, 50, 100));
    printf("p99 %d\n", percentile(hist, iters, 99, 100));
    printf("p999 %d\n", percentile(hist, iters, 999, 1000));
    printf("max %.3f\n", max_miss);
    printf("overruns %d\n", overruns);
    free(hist);
    return 0;
}
