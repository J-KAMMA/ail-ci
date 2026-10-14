/* Fixed diagnostic reference: prepare the complete independent LF-numbered output,
 * then time only its POSIX delivery in <=64KiB batches. No online/error equivalence. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define INPUT_CAP (32U * 1024U * 1024U + 1U)
#define OUTPUT_CAP (64U * 1024U * 1024U)
#ifndef NUMBER_PROFILE_CLOCK
#define NUMBER_PROFILE_CLOCK CLOCK_MONOTONIC
#endif

static uint64_t now(void) {
    struct timespec t;
    if (clock_gettime(NUMBER_PROFILE_CLOCK, &t)) exit(3);
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

int main(void) {
    unsigned char *input = malloc(INPUT_CAP + 1U);
    if (!input) return 3;
    size_t size = 0;
    for (;;) {
        ssize_t n = read(0, input + size, INPUT_CAP + 1U - size);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { free(input); return 3; }
        if (!n) break;
        size += (size_t)n;
        if (size > INPUT_CAP) { free(input); return 2; }
    }
    size_t required = size;
    uint64_t number = 1;
    for (size_t offset = 0; offset < size; ++number) {
        int length = snprintf(NULL, 0, "%" PRIu64 ": ", number);
        if (length < 0 || (size_t)length > OUTPUT_CAP - required) { free(input); return 2; }
        required += (size_t)length;
        unsigned char *end = memchr(input + offset, '\n', size - offset);
        offset = end ? (size_t)(end - input) + 1 : size;
    }
    unsigned char *output = malloc(required ? required : 1);
    if (!output) { free(input); return 3; }
    size_t written = 0;
    number = 1;
    for (size_t offset = 0; offset < size; ++number) {
        char prefix[32];
        int length = snprintf(prefix, sizeof prefix, "%" PRIu64 ": ", number);
        if (length < 0 || (size_t)length >= sizeof prefix) { free(output); free(input); return 3; }
        memcpy(output + written, prefix, (size_t)length);
        written += (size_t)length;
        unsigned char *end = memchr(input + offset, '\n', size - offset);
        size_t count = end ? (size_t)(end - input) + 1 - offset : size - offset;
        memcpy(output + written, input + offset, count);
        written += count;
        offset += count;
    }
    free(input);
    if (written != required) { free(output); return 3; }
    uint64_t clock_max = 0;
    for (int i = 0; i < 64; ++i) {
        uint64_t start = now(), elapsed = now() - start;
        if (elapsed > clock_max) clock_max = elapsed;
    }
    size_t attempts = 0;
    uint64_t start = now();
    for (size_t offset = 0; offset < required;) {
        size_t count = required - offset;
        if (count > 65536) count = 65536;
        ++attempts;
        ssize_t n = write(1, output + offset, count);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { free(output); return 3; }
        offset += (size_t)n;
    }
    uint64_t elapsed = now() - start;
    fprintf(stderr, "NUMBER_WRITE_REFERENCE "
#ifdef NUMBER_PROFILE_CLOCK_NAME
            NUMBER_PROFILE_CLOCK_NAME " "
#endif
            "%" PRIu64 " %zu %zu %" PRIu64 "\n",
            elapsed, required, attempts, clock_max);
    free(output);
    return 0;
}
