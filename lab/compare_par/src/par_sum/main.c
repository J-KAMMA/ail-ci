/* par_sum: sum over n in 1..N of steps(n) * (n % 7 - 3) on 4 pthreads with per-thread partial sums. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>

#define NTHREADS 4

typedef struct {
    int64_t lo, hi, sum;
} job;

static int64_t add64(int64_t a, int64_t b)
{
    int64_t r;
    if (__builtin_add_overflow(a, b, &r)) {
        fflush(stdout);
        fputs("OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)\n", stderr);
        exit(1);
    }
    return r;
}

static int64_t steps(int64_t n)
{
    int64_t c = 0;
    while (n != 1) {
        if (n & 1)
            n = 3 * n + 1;
        else
            n >>= 1;
        c++;
    }
    return c;
}

static void *worker(void *arg)
{
    job *j = arg;
    int64_t s = 0;
    for (int64_t n = j->lo; n <= j->hi; n++)
        s = add64(s, steps(n) * (n % 7 - 3));
    j->sum = s;
    return NULL;
}

int main(void)
{
    long long n;
    if (scanf("%lld", &n) != 1 || n < 0)
        return 1;
    if (n == 0) {
        puts("0");
        return 0;
    }
    int64_t threads = n < NTHREADS ? n : NTHREADS;
    int64_t chunk = (n + threads - 1) / threads;
    job *jobs = malloc((size_t)threads * sizeof *jobs);
    pthread_t *tids = malloc((size_t)threads * sizeof *tids);
    if (!jobs || !tids)
        return 1;
    int64_t started = 0;
    for (int64_t t = 0; t < threads; t++) {
        int64_t lo = t * chunk + 1, hi = lo + chunk - 1;
        if (lo > n)
            break;
        if (hi > n)
            hi = n;
        jobs[started].lo = lo;
        jobs[started].hi = hi;
        jobs[started].sum = 0;
        if (pthread_create(&tids[started], NULL, worker, &jobs[started]) != 0)
            return 1;
        started++;
    }
    int64_t total = 0;
    for (int64_t t = 0; t < started; t++)
        pthread_join(tids[t], NULL);
    for (int64_t t = 0; t < started; t++)
        total = add64(total, jobs[t].sum);
    printf("%lld\n", (long long)total);
    free(jobs);
    free(tids);
    return 0;
}
