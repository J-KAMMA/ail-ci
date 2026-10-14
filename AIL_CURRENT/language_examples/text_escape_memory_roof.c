#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Logical memcpy throughput baseline, not a physical hardware maximum. */
static int positive_decimal(const char *s, uint64_t *value)
{
    if (!*s || strspn(s, "0123456789") != strlen(s)) return 0;
    errno = 0;
    char *end;
    uintmax_t parsed = strtoumax(s, &end, 10);
    if (errno || *end || !parsed || parsed > UINT64_MAX) return 0;
    *value = (uint64_t)parsed;
    return 1;
}

int main(int argc, char **argv)
{
    uint64_t bytes, reps;
    if (argc != 3 || !positive_decimal(argv[1], &bytes) ||
        !positive_decimal(argv[2], &reps) || bytes > SIZE_MAX ||
        bytes > PTRDIFF_MAX || reps > INT64_MAX / 1009 ||
        reps > UINT64_MAX / 255) {
        fprintf(stderr, "usage: %s positive_bytes positive_reps (within width limits)\n", argv[0]);
        return 2;
    }
    size_t n = (size_t)bytes;
    unsigned char *src = malloc(n), *dst = malloc(n);
    if (!src || !dst) {
        free(src);
        free(dst);
        fprintf(stderr, "allocation failed\n");
        return 3;
    }
    for (size_t i = 0; i < n; ++i)
        src[i] = (unsigned char)(((i & 255u) * 31u + 17u) & 255u);
    memcpy(dst, src, n);
    __asm__ volatile ("" : : "r" (dst) : "memory");
    struct timespec start, stop;
    uint64_t checksum = 0;
    if (clock_gettime(CLOCK_MONOTONIC, &start)) goto clock_error;
    for (uint64_t k = 0; k < reps; ++k) {
        memcpy(dst, src, n);
        __asm__ volatile ("" : : "r" (dst) : "memory");
        checksum += dst[(size_t)((k * UINT64_C(1009)) % bytes)];
    }
    if (clock_gettime(CLOCK_MONOTONIC, &stop)) goto clock_error;
    for (size_t i = 0; i < n; ++i) {
        unsigned char expected = (unsigned char)(((i & 255u) * 31u + 17u) & 255u);
        if (src[i] != expected || dst[i] != expected) {
            fprintf(stderr, "full buffer verification failed at %zu\n", i);
            free(src);
            free(dst);
            return 4;
        }
    }
    if (start.tv_sec < 0 || stop.tv_sec < start.tv_sec) goto clock_error;
    uintmax_t seconds = (uintmax_t)stop.tv_sec - (uintmax_t)start.tv_sec;
    int64_t nanos = (int64_t)stop.tv_nsec - (int64_t)start.tv_nsec;
    if (nanos < 0) {
        if (!seconds) goto clock_error;
        --seconds;
        nanos += INT64_C(1000000000);
    }
    if (seconds > (UINT64_MAX - (uint64_t)nanos) / UINT64_C(1000000000))
        goto clock_error;
    uint64_t ns = (uint64_t)seconds * UINT64_C(1000000000) + (uint64_t)nanos;
    printf("{\"bytes\":%" PRIu64 ",\"reps\":%" PRIu64
           ",\"ns\":%" PRIu64 ",\"checksum\":%" PRIu64 "}\n",
           bytes, reps, ns, checksum);
    free(src);
    free(dst);
    return 0;

clock_error:
    fprintf(stderr, "clock failed or elapsed time exceeded width limits\n");
    free(src);
    free(dst);
    return 5;
}
