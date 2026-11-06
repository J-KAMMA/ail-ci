/* par_collatz: Collatz step counts for 1..N on W pthreads with contiguous chunks (see spec.md). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>

typedef struct {
    int64_t lo, hi;
    int32_t *res;
} job;

static void *worker(void *arg)
{
    job *j = arg;
    for (int64_t n = j->lo; n <= j->hi; n++) {
        int64_t m = n;
        int32_t c = 0;
        while (m != 1) {
            if (m & 1)
                m = 3 * m + 1;
            else
                m >>= 1;
            c++;
        }
        j->res[n - 1] = c;
    }
    return NULL;
}

int main(void)
{
    long long n, w;
    if (scanf("%lld %lld", &n, &w) != 2 || n < 1 || w < 1)
        return 1;
    long long threads = w < n ? w : n;
    int32_t *res = malloc((size_t)n * sizeof *res);
    job *jobs = malloc((size_t)threads * sizeof *jobs);
    pthread_t *tids = malloc((size_t)threads * sizeof *tids);
    if (!res || !jobs || !tids)
        return 1;
    int64_t chunk = (n + threads - 1) / threads, started = 0;
    for (int64_t t = 0; t < threads; t++) {
        int64_t lo = t * chunk + 1, hi = lo + chunk - 1;
        if (lo > n)
            break;
        if (hi > n)
            hi = n;
        jobs[started].lo = lo;
        jobs[started].hi = hi;
        jobs[started].res = res;
        if (pthread_create(&tids[started], NULL, worker, &jobs[started]) != 0)
            return 1;
        started++;
    }
    for (int64_t t = 0; t < started; t++)
        pthread_join(tids[t], NULL);

    int64_t best = -1, bestn = 0, total = 0;
    for (int64_t i = 0; i < n; i++) {
        int64_t v = res[i];
        total += v;
        if (v > best) {
            best = v;
            bestn = i + 1;
        }
    }
    printf("%lld %lld %lld\n", (long long)best, (long long)bestn, (long long)total);
    free(res);
    free(jobs);
    free(tids);
    return 0;
}
