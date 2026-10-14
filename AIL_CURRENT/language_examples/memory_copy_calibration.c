#define _POSIX_C_SOURCE 200809L
/* Calibrated memcpy workload, not a physical memory roof. */
#include <stdint.h>
#include <inttypes.h>
#include <errno.h>
#include <pthread.h>
#include <time.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#include <stdio.h>

typedef struct {
    unsigned char *dst;
    const unsigned char *src;
    size_t offset, count;
    unsigned passes;
    pthread_barrier_t *barrier;
} worker;

static void fatal(const char *message) {
    fprintf(stderr, "%s\n", message);
    _Exit(1);
}

static void wait_barrier(pthread_barrier_t *barrier) {
    int error = pthread_barrier_wait(barrier);
    if (error && error != PTHREAD_BARRIER_SERIAL_THREAD) fatal("pthread barrier wait failed");
}

static void *copy_worker(void *argument) {
    worker *w = argument;
    wait_barrier(w->barrier);
    wait_barrier(w->barrier);
    for (unsigned pass = 0; pass < w->passes; ++pass) {
        memcpy(w->dst + w->offset, w->src + w->offset, w->count);
        atomic_signal_fence(memory_order_seq_cst);
    }
    wait_barrier(w->barrier);
    return NULL;
}

static int decimal(const char *text, uint64_t *result) {
    if (!*text) return 0;
    uint64_t value = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p < '0' || *p > '9') return 0;
        unsigned digit = *p - '0';
        if (value > (UINT64_MAX - digit) / 10) return 0;
        value = value * 10 + digit;
    }
    *result = value;
    return 1;
}

int main(int argc, char **argv) {
    uint64_t bytes, threads, passes;
    if (argc != 4 || !decimal(argv[1], &bytes) || !decimal(argv[2], &threads)
            || !decimal(argv[3], &passes) || bytes < UINT64_C(8388608)
            || bytes > UINT64_C(134217728) || bytes % 256
            || !(threads == 1 || threads == 2 || threads == 4 || threads == 8 || threads == 16)
            || bytes % threads || passes < 1 || passes > 128
            || bytes > SIZE_MAX / 2) {
        fputs("usage: memory_copy_calibration bytes[8MiB..128MiB,multiple256] threads[1,2,4,8,16] passes[1..128]\n", stderr);
        return 2;
    }
    unsigned char *src = NULL, *dst = NULL;
    int error = posix_memalign((void **)&src, 64, (size_t)bytes);
    if (!error) error = posix_memalign((void **)&dst, 64, (size_t)bytes);
    if (error) {
        free(src); free(dst);
        fputs("aligned allocation failed\n", stderr);
        return 1;
    }
    for (size_t i = 0; i < (size_t)bytes; ++i) src[i] = (unsigned char)((17 * i + 5) & 255);
    memset(dst, 0, (size_t)bytes);
    pthread_barrier_t barrier;
    if (pthread_barrier_init(&barrier, NULL, (unsigned)threads + 1)) {
        free(src); free(dst);
        fputs("pthread barrier initialization failed\n", stderr);
        return 1;
    }
    worker workers[16];
    pthread_t ids[16];
    size_t chunk = (size_t)(bytes / threads);
    for (unsigned i = 0; i < (unsigned)threads; ++i) {
        workers[i] = (worker){dst, src, i * chunk, chunk, (unsigned)passes, &barrier};
        if (pthread_create(&ids[i], NULL, copy_worker, &workers[i])) fatal("pthread creation failed");
    }
    wait_barrier(&barrier);
    struct timespec start, end;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &start)) fatal("start clock failed");
    wait_barrier(&barrier);
    wait_barrier(&barrier);
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &end)) fatal("completion clock failed");
    for (unsigned i = 0; i < (unsigned)threads; ++i)
        if (pthread_join(ids[i], NULL)) fatal("pthread join failed");
    if (pthread_barrier_destroy(&barrier)) fatal("pthread barrier destruction failed");
    int64_t seconds = (int64_t)end.tv_sec - (int64_t)start.tv_sec;
    if (seconds < 0 || seconds > INT64_MAX / INT64_C(1000000000) - 1) fatal("clock duration out of range");
    int64_t wall = seconds * INT64_C(1000000000) + (int64_t)end.tv_nsec - (int64_t)start.tv_nsec;
    if (wall <= 0) fatal("nonpositive clock duration");
    uint64_t checksum = 0;
    for (size_t i = 0; i < (size_t)bytes; ++i) {
        unsigned char expected = (unsigned char)((17 * i + 5) & 255);
        if (src[i] != expected || dst[i] != expected) fatal("copy verification failed");
        checksum += dst[i];
    }
    printf("{\"version\":1,\"bytes\":%" PRIu64 ",\"threads\":%" PRIu64 ",\"passes\":%" PRIu64
           ",\"wall_ns\":%" PRId64 ",\"payload_bytes\":%" PRIu64 ",\"logical_copy_traffic_bytes\":%" PRIu64
           ",\"checksum\":%" PRIu64 ",\"source_unchanged\":true,\"output_match\":true}\n",
           bytes, threads, passes, wall, bytes * passes, 2 * bytes * passes, checksum);
    free(src); free(dst);
    return 0;
}
