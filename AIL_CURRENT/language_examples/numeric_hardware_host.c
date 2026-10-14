/* Empirical capacity harness. Compile without fastmath; optional runtime precedes this file. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <stddef.h>
#include <string.h>
#include <float.h>
#include <time.h>
#include <sys/types.h>
#include <sys/resource.h>
#include <pthread.h>

_Static_assert(sizeof(double) == 8 && FLT_RADIX == 2 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
               "IEEE binary64 required");
static uint64_t hardware_now(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) || value.tv_sec < 0 || value.tv_nsec < 0 ||
            value.tv_nsec >= 1000000000 ||
            (uintmax_t)value.tv_sec > (UINT64_MAX - (uint64_t)value.tv_nsec) / UINT64_C(1000000000)) exit(1);
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}
static void hardware_interval(uint64_t *sum, uint64_t begin, uint64_t end) {
    if (end < begin || end - begin > UINT64_MAX - *sum) exit(1);
    *sum += end - begin;
}
static int hardware_decimal(const char *text, unsigned limit, unsigned *result) {
    if (!*text) return 0;
    unsigned value = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p < '0' || *p > '9') return 0;
        unsigned digit = *p - '0';
        if (value > limit / 10 || (value == limit / 10 && digit > limit % 10)) return 0;
        value = value * 10 + digit;
    }
    *result = value;
    return 1;
}
static int hardware_invalid(void) {
    fputs("invalid arguments\n", stderr);
    return 2;
}
static unsigned char *hardware_read(const char *path, size_t *bytes) {
    FILE *file = fopen(path, "rb");
    if (!file) return NULL;
    unsigned char *data = NULL;
    if (fseeko(file, 0, SEEK_END)) goto done;
    off_t length = ftello(file);
    if (length < 0 || (uintmax_t)length > UINT64_C(8388609) * 8 ||
            (uintmax_t)length > SIZE_MAX || (uintmax_t)length > PTRDIFF_MAX ||
            (uintmax_t)length > INT64_MAX || length % 8 || fseeko(file, 0, SEEK_SET)) goto done;
    data = malloc(length ? (size_t)length : 1);
    if (!data) goto done;
    if (fread(data, 1, (size_t)length, file) != (size_t)length || fgetc(file) != EOF || ferror(file)) {
        free(data); data = NULL;
    } else *bytes = (size_t)length;
done:
    if (fclose(file)) { free(data); data = NULL; }
    return data;
}
static uint64_t hardware_swap(uint64_t value) {
    value = ((value & UINT64_C(0x00ff00ff00ff00ff)) << 8) |
            ((value & UINT64_C(0xff00ff00ff00ff00)) >> 8);
    value = ((value & UINT64_C(0x0000ffff0000ffff)) << 16) |
            ((value & UINT64_C(0xffff0000ffff0000)) >> 16);
    return (value << 32) | (value >> 32);
}
static void hardware_kernel(const unsigned char *src, unsigned char *dst, size_t lo, size_t hi,
                            int copy, int swapped) {
    if (copy) {
        memcpy(dst + lo * 8, src + lo * 8, (hi - lo) * 8);
    } else if (!swapped) {
        for (size_t index = lo; index < hi; ++index) {
            double value;
            memcpy(&value, src + index * 8, 8);
            value = value * 0.5;
            memcpy(dst + index * 8, &value, 8);
        }
    } else {
        for (size_t index = lo; index < hi; ++index) {
            uint64_t bits;
            double value;
            memcpy(&bits, src + index * 8, 8);
            bits = hardware_swap(bits);
            memcpy(&value, &bits, 8);
            value = value * 0.5;
            memcpy(&bits, &value, 8);
            bits = hardware_swap(bits);
            memcpy(dst + index * 8, &bits, 8);
        }
    }
}
typedef struct hardware_pool hardware_pool;
typedef struct { hardware_pool *pool; unsigned index; } hardware_job;
struct hardware_pool {
    pthread_mutex_t mutex;
    pthread_cond_t start, done;
    pthread_t ids[16];
    hardware_job jobs[16];
    unsigned threads, started, remaining;
    uint64_t generation;
    int stop, copy, swapped;
    size_t count;
    const unsigned char *src;
    unsigned char *dst;
};
static void *hardware_worker(void *argument) {
    hardware_job *job = argument;
    hardware_pool *pool = job->pool;
    uint64_t generation = 0;
    if (pthread_mutex_lock(&pool->mutex)) exit(1);
    for (;;) {
        while (!pool->stop && generation == pool->generation)
            if (pthread_cond_wait(&pool->start, &pool->mutex)) exit(1);
        if (pool->stop) break;
        generation = pool->generation;
        size_t lo = pool->count * job->index / pool->threads;
        size_t hi = pool->count * (job->index + 1) / pool->threads;
        if (pthread_mutex_unlock(&pool->mutex)) exit(1);
        hardware_kernel(pool->src, pool->dst, lo, hi, pool->copy, pool->swapped);
        if (pthread_mutex_lock(&pool->mutex)) exit(1);
        if (!--pool->remaining && pthread_cond_signal(&pool->done)) exit(1);
    }
    if (pthread_mutex_unlock(&pool->mutex)) exit(1);
    return NULL;
}
static int hardware_pool_destroy(hardware_pool *pool) {
    if (pthread_mutex_lock(&pool->mutex)) return 0;
    pool->stop = 1;
    int valid = !pthread_cond_broadcast(&pool->start);
    if (pthread_mutex_unlock(&pool->mutex)) valid = 0;
    for (unsigned index = 0; index < pool->started; ++index)
        if (pthread_join(pool->ids[index], NULL)) valid = 0;
    if (!valid) return 0;
    if (pthread_cond_destroy(&pool->done)) valid = 0;
    if (pthread_cond_destroy(&pool->start)) valid = 0;
    if (pthread_mutex_destroy(&pool->mutex)) valid = 0;
    return valid;
}
static int hardware_pool_init(hardware_pool *pool, unsigned threads) {
    pool->threads = threads;
    if (pthread_mutex_init(&pool->mutex, NULL)) return 0;
    if (pthread_cond_init(&pool->start, NULL)) { pthread_mutex_destroy(&pool->mutex); return 0; }
    if (pthread_cond_init(&pool->done, NULL)) {
        pthread_cond_destroy(&pool->start); pthread_mutex_destroy(&pool->mutex); return 0;
    }
    for (unsigned index = 0; index < threads; ++index) {
        pool->jobs[index] = (hardware_job){pool, index};
        if (pthread_create(&pool->ids[index], NULL, hardware_worker, &pool->jobs[index])) {
            if (!hardware_pool_destroy(pool)) exit(1);
            return 0;
        }
        ++pool->started;
    }
    return 1;
}
static int hardware_dispatch(hardware_pool *pool) {
    if (pthread_mutex_lock(&pool->mutex)) return 0;
    pool->remaining = pool->threads;
    if (pool->generation == UINT64_MAX) exit(1);
    ++pool->generation;
    if (pthread_cond_broadcast(&pool->start)) exit(1);
    while (pool->remaining)
        if (pthread_cond_wait(&pool->done, &pool->mutex)) exit(1);
    return !pthread_mutex_unlock(&pool->mutex);
}

int main(int argc, char **argv) {
    unsigned threads, passes, order;
    if (argc != 9 || !hardware_decimal(argv[5], 16, &threads) ||
            !(threads == 1 || threads == 2 || threads == 4 || threads == 8 || threads == 16) ||
            !hardware_decimal(argv[6], 32, &passes) || !passes ||
            !hardware_decimal(argv[8], 1, &order)) return hardware_invalid();
    int copy = strcmp(argv[3], "copy") == 0;
    int ail = strcmp(argv[4], "ail") == 0;
    int resident = strcmp(argv[4], "resident") == 0;
    int profile = strcmp(argv[7], "profile") == 0;
    if ((!copy && strcmp(argv[3], "scale")) ||
            (!ail && !resident && strcmp(argv[4], "fresh")) ||
            (!profile && strcmp(argv[7], "plain")) ||
            (!resident && threads != 1) || (ail && copy)) return hardware_invalid();
#ifndef AIL_RUNTIME
    if (ail) return hardware_invalid();
#else
    hardware_profile = profile;
#endif
    uint64_t setup_start = hardware_now();
    size_t bytes = 0, expected_bytes = 0;
    unsigned char *src = hardware_read(argv[1], &bytes);
    unsigned char *expected = hardware_read(argv[2], &expected_bytes);
    unsigned char *snapshot = NULL, *persistent = NULL;
    int status = 1, pool_ready = 0;
    hardware_pool pool = {0};
    if (!src || !expected || bytes != expected_bytes) goto cleanup;
    snapshot = malloc(bytes ? bytes : 1);
    if (!snapshot) goto cleanup;
    memcpy(snapshot, src, bytes);
    if (resident) {
        persistent = malloc(bytes ? bytes : 1);
        if (!persistent) goto cleanup;
        volatile unsigned char *touch = persistent;
        for (size_t index = 0; index < bytes; ++index) touch[index] = 0;
    }
    const uint64_t one = 1;
    int swapped = order != (*(const unsigned char *)&one ? 0u : 1u);
    pool.src = src; pool.dst = persistent; pool.count = bytes / 8;
    pool.copy = copy; pool.swapped = swapped;
    if (resident && threads > 1) {
        if (!hardware_pool_init(&pool, threads)) goto cleanup;
        pool_ready = 1;
    }
    uint64_t setup_ns = 0, work_ns = 0, allocation_ns = 0, kernel_ns = 0;
    uint64_t release_ns = 0, verification_ns = 0, teardown_ns = 0;
    hardware_interval(&setup_ns, setup_start, hardware_now());
    for (unsigned pass = 0; pass < passes; ++pass) {
        unsigned char *output = persistent;
#ifdef AIL_RUNTIME
        ail_barena arena = {0};
        uint64_t prior_allocation = hardware_ail_allocation_ns;
#endif
        uint64_t work_start = hardware_now(), tick = profile && !resident && !ail ? hardware_now() : 0;
        if (!resident && !ail) {
            output = malloc(bytes ? bytes : 1);
            if (!output) goto cleanup;
        }
        if (profile && !resident && !ail) hardware_interval(&allocation_ns, tick, hardware_now());
        tick = profile ? hardware_now() : 0;
#ifdef AIL_RUNTIME
        if (ail) {
            /* The generated instrumentation separates arena/payload allocation. */
            ail_bytes result = ail_float64_scale_bytes(&arena, (ail_bytes){src, (int64_t)bytes}, order, 0.5, order, 0);
            output = (unsigned char *)result.p;
        } else
#endif
        if (pool_ready) {
            if (!hardware_dispatch(&pool)) exit(1);
        } else hardware_kernel(src, output, 0, bytes / 8, copy, swapped);
        if (profile) {
            uint64_t end = hardware_now();
#ifdef AIL_RUNTIME
            uint64_t allocated = ail ? hardware_ail_allocation_ns - prior_allocation : 0;
            if (end < tick || allocated > end - tick) exit(1);
            hardware_interval(&allocation_ns, 0, allocated);
            hardware_interval(&kernel_ns, tick + allocated, end);
#else
            hardware_interval(&kernel_ns, tick, end);
#endif
        }
        hardware_interval(&work_ns, work_start, hardware_now());
        uint64_t verify_start = hardware_now();
        int match = !bytes || memcmp(output, expected, bytes) == 0;
        int unchanged = memcmp(src, snapshot, bytes) == 0;
        hardware_interval(&verification_ns, verify_start, hardware_now());
        work_start = hardware_now(); tick = profile && !resident ? hardware_now() : 0;
#ifdef AIL_RUNTIME
        if (ail) ail_barena_free(&arena);
        else
#endif
        if (!resident) free(output);
        if (profile && !resident) hardware_interval(&release_ns, tick, hardware_now());
        hardware_interval(&work_ns, work_start, hardware_now());
        if (!match || !unchanged) {
            fprintf(stderr, "%s\n", !match ? "output mismatch" : "input changed");
            goto cleanup;
        }
    }
    {
        uint64_t start = hardware_now();
        if (pool_ready) {
            if (!hardware_pool_destroy(&pool)) exit(1);
            pool_ready = 0;
        }
        free(src); src = NULL; free(expected); expected = NULL;
        free(snapshot); snapshot = NULL; free(persistent); persistent = NULL;
        hardware_interval(&teardown_ns, start, hardware_now());
        struct rusage usage;
        if (getrusage(RUSAGE_SELF, &usage)) goto cleanup;
        fprintf(stderr, "{\"count\":%zu,\"passes\":%u,\"threads\":%u,\"order\":%u,\"operation\":\"%s\",\"storage\":\"%s\",\"mode\":\"%s\","
                "\"work_ns\":%" PRIu64 ",\"allocation_ns\":%" PRIu64 ",\"kernel_ns\":%" PRIu64 ",\"release_ns\":%" PRIu64
                ",\"verification_ns\":%" PRIu64 ",\"setup_ns\":%" PRIu64 ",\"teardown_ns\":%" PRIu64
                ",\"peak_rss_kib\":%ld,\"user_us\":%" PRIu64 ",\"system_us\":%" PRIu64 ",\"output_match\":true,\"input_unchanged\":true}\n",
                bytes / 8, passes, threads, order, argv[3], argv[4], argv[7], work_ns, allocation_ns, kernel_ns,
                release_ns, verification_ns, setup_ns, teardown_ns, usage.ru_maxrss,
                (uint64_t)usage.ru_utime.tv_sec * UINT64_C(1000000) + usage.ru_utime.tv_usec,
                (uint64_t)usage.ru_stime.tv_sec * UINT64_C(1000000) + usage.ru_stime.tv_usec);
        status = ferror(stderr) ? 1 : 0;
    }
cleanup:
    if (pool_ready && !hardware_pool_destroy(&pool)) exit(1);
    free(src); free(expected); free(snapshot); free(persistent);
    return status;
}
