/* Concatenated after numeric_scale_profile.HOST with its main renamed. */
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static int resident_decimal(const char *text, uint64_t limit, uint64_t *value) {
    if (!text || !*text) return 0;
    uint64_t result = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p < '0' || *p > '9') return 0;
        unsigned digit = *p - '0';
        if (result > limit / 10 || (result == limit / 10 && digit > limit % 10)) return 0;
        result = result * 10 + digit;
    }
    *value = result;
    return 1;
}

static int resident_read(const char *path, void *buffer, size_t bytes) {
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    int valid = fread(buffer, 1, bytes, file) == bytes;
    if (fgetc(file) != EOF || ferror(file)) valid = 0;
    if (fclose(file)) valid = 0;
    return valid;
}

static int resident_add_interval(uint64_t *total, uint64_t start, uint64_t end) {
    if (end < start || end - start > UINT64_MAX - *total) return 0;
    *total += end - start;
    return 1;
}

int main(int argc, char **argv) {
    uint64_t count, thread_count, pass_count;
    if (argc != 8 || !resident_decimal(argv[4], UINT64_C(8388609), &count) ||
            !resident_decimal(argv[5], 16, &thread_count) ||
            !(thread_count == 1 || thread_count == 2 || thread_count == 4 ||
              thread_count == 8 || thread_count == 16) ||
            !resident_decimal(argv[6], 64, &pass_count) || !pass_count ||
            count > SIZE_MAX / sizeof(double)) return 2;
    int profile = strcmp(argv[7], "profile") == 0;
    if (!profile && strcmp(argv[7], "plain")) return 2;
    size_t n = (size_t)count, bytes = n * sizeof(double);
    double *src = malloc(bytes ? bytes : 1), *dst = malloc(bytes ? bytes : 1);
    double *original = malloc(bytes ? bytes : 1), *expected = malloc(bytes ? bytes : 1);
    int status = 1;
    if (!src || !dst || !original || !expected) goto cleanup;
    if (!resident_read(argv[1], src, bytes) || !resident_read(argv[2], expected, bytes)) {
        status = 3;
        goto cleanup;
    }
    memcpy(original, src, bytes);
    volatile double *touched = dst;
    for (size_t i = 0; i < n; ++i) touched[i] = 0.0;
    uint64_t kernel_ns = 0, verification_ns = 0, resident_start = now(1);
    for (uint64_t pass = 0; pass < pass_count; ++pass) {
        uint64_t start = profile ? now(1) : 0;
        /* A failed HOST transform may still have running pthreads. Terminate
           without releasing their buffers; process exit owns that failure cleanup. */
        if (!transform(src, dst, n, (unsigned)thread_count)) return 1;
        uint64_t end = profile ? now(1) : 0;
        if (profile && !resident_add_interval(&kernel_ns, start, end)) goto cleanup;
        start = now(1);
        int output_match = memcmp(dst, expected, bytes) == 0;
        int source_unchanged = memcmp(src, original, bytes) == 0;
        end = now(1);
        if (!resident_add_interval(&verification_ns, start, end) ||
                !output_match || !source_unchanged) goto cleanup;
    }
    free(src); src = NULL;
    free(original); original = NULL;
    free(expected); expected = NULL;
    /* Keep dst for final output: its write and free are outside resident_total. */
    uint64_t resident_end = now(1);
    if (resident_end < resident_start || verification_ns > resident_end - resident_start) goto cleanup;
    uint64_t total_ns = resident_end - resident_start;
    FILE *output = fopen(argv[3], "wb");
    if (!output) { status = 3; goto cleanup; }
    int written = fwrite(dst, 1, bytes, output) == bytes;
    if (fclose(output)) written = 0;
    if (!written) { status = 3; goto cleanup; }
    free(dst); dst = NULL;
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) goto cleanup;
    printf("{\"mode\":\"%s\",\"count\":%zu,\"threads\":%u,\"passes\":%" PRIu64
           ",\"kernel_ns\":%" PRIu64 ",\"verification_ns\":%" PRIu64
           ",\"resident_total_ns\":%" PRIu64 ",\"resident_workload_ns\":%" PRIu64
           ",\"peak_rss_kib\":%ld,\"user_us\":%" PRIu64 ",\"system_us\":%" PRIu64
           ",\"output_match\":true,\"source_unchanged\":true}\n",
           argv[7], n, (unsigned)thread_count, pass_count, kernel_ns, verification_ns,
           total_ns, total_ns - verification_ns, usage.ru_maxrss,
           (uint64_t)usage.ru_utime.tv_sec * UINT64_C(1000000) + usage.ru_utime.tv_usec,
           (uint64_t)usage.ru_stime.tv_sec * UINT64_C(1000000) + usage.ru_stime.tv_usec);
    status = ferror(stdout) ? 3 : 0;
cleanup:
    free(src); free(dst); free(original); free(expected);
    return status;
}
