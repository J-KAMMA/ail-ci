/* The preceding common timing header defines ail_pipeline_profile,
   ail_pipeline_phases[5], and ail_pipeline_now(). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <float.h>
#include <sys/types.h>
#include <sys/resource.h>

_Static_assert(sizeof(double) == 8 && FLT_RADIX == 2 && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
               "IEEE binary64 required");

static int pipeline_error(const char *message) {
    fprintf(stderr, "%s\n", message);
    return 1;
}
static int pipeline_decimal(const char *text, unsigned limit, unsigned *result) {
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
static int pipeline_interval(uint64_t *sum, uint64_t start, uint64_t end) {
    if (end < start || end - start > UINT64_MAX - *sum) return 0;
    *sum += end - start;
    return 1;
}
static unsigned char *pipeline_read(const char *path, size_t *length) {
    FILE *file = fopen(path, "rb");
    if (!file) return NULL;
    unsigned char *data = NULL;
    if (fseeko(file, 0, SEEK_END)) goto done;
    off_t end = ftello(file);
    if (end < 0 || (uintmax_t)end > SIZE_MAX || (uintmax_t)end > PTRDIFF_MAX ||
            (uintmax_t)end > INT64_MAX || end % 8 || fseeko(file, 0, SEEK_SET)) goto done;
    size_t bytes = (size_t)end;
    data = malloc(bytes ? bytes : 1);
    if (!data) goto done;
    if (fread(data, 1, bytes, file) != bytes || fgetc(file) != EOF || ferror(file)) {
        free(data); data = NULL;
    } else {
        *length = bytes;
    }
done:
    if (fclose(file)) { free(data); data = NULL; }
    return data;
}
static int pipeline_verify(const char *path, const unsigned char *expected, size_t bytes) {
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    unsigned char chunk[65536];
    int valid = 1;
    for (size_t offset = 0; offset < bytes;) {
        size_t take = bytes - offset;
        if (take > sizeof chunk) take = sizeof chunk;
        if (fread(chunk, 1, take, file) != take || memcmp(chunk, expected + offset, take)) {
            valid = 0; break;
        }
        offset += take;
    }
    if (fgetc(file) != EOF || ferror(file)) valid = 0;
    if (fclose(file)) valid = 0;
    return valid;
}
#ifndef AIL_PIPELINE
static uint64_t pipeline_swap64(uint64_t bits) {
    return ((bits & UINT64_C(0x00000000000000ff)) << 56) |
           ((bits & UINT64_C(0x000000000000ff00)) << 40) |
           ((bits & UINT64_C(0x0000000000ff0000)) << 24) |
           ((bits & UINT64_C(0x00000000ff000000)) << 8) |
           ((bits & UINT64_C(0x000000ff00000000)) >> 8) |
           ((bits & UINT64_C(0x0000ff0000000000)) >> 24) |
           ((bits & UINT64_C(0x00ff000000000000)) >> 40) |
           ((bits & UINT64_C(0xff00000000000000)) >> 56);
}
static int pipeline_reference(const char *input, unsigned order, double factor) {
    size_t bytes = 0;
    uint64_t start = ail_pipeline_profile ? ail_pipeline_now() : 0;
    unsigned char *data = pipeline_read(input, &bytes);
    if (!data) return pipeline_error("input read failed");
    if (ail_pipeline_profile && !pipeline_interval(&ail_pipeline_phases[0], start, ail_pipeline_now())) {
        free(data); return pipeline_error("read clock interval failed");
    }
    start = ail_pipeline_profile ? ail_pipeline_now() : 0;
    const uint64_t one = 1;
    unsigned host_order = *(const unsigned char *)&one ? 0 : 1;
    if (order == host_order) {
        for (size_t offset = 0; offset < bytes; offset += 8) {
            double value;
            memcpy(&value, data + offset, 8);
            value = value * factor;
            memcpy(data + offset, &value, 8);
        }
    } else {
        for (size_t offset = 0; offset < bytes; offset += 8) {
            uint64_t bits;
            double value;
            memcpy(&bits, data + offset, 8);
            bits = pipeline_swap64(bits);
            memcpy(&value, &bits, 8);
            value = value * factor;
            memcpy(&bits, &value, 8);
            bits = pipeline_swap64(bits);
            memcpy(data + offset, &bits, 8);
        }
    }
    if (ail_pipeline_profile && !pipeline_interval(&ail_pipeline_phases[2], start, ail_pipeline_now())) {
        free(data); return pipeline_error("map clock interval failed");
    }
    start = ail_pipeline_profile ? ail_pipeline_now() : 0;
    int written = fwrite(data, 1, bytes, stdout) == bytes && !ferror(stdout);
    if (ail_pipeline_profile && !pipeline_interval(&ail_pipeline_phases[4], start, ail_pipeline_now())) written = 0;
    free(data);
    return written ? 0 : pipeline_error("output write failed");
}
#endif

int main(int argc, char **argv) {
    unsigned order, passes;
    if (argc != 8 || !pipeline_decimal(argv[4], 1, &order) ||
            !pipeline_decimal(argv[6], 32, &passes) || !passes)
        return pipeline_error("invalid arguments");
    ail_pipeline_profile = strcmp(argv[7], "profile") == 0;
    if (!ail_pipeline_profile && strcmp(argv[7], "plain")) return pipeline_error("invalid mode");
    char *end;
    double factor = strtod(argv[5], &end);
    if (!*argv[5] || isspace((unsigned char)*argv[5]) || *end || !isfinite(factor))
        return pipeline_error("invalid finite factor");
    size_t bytes = 0;
    unsigned char *expected = pipeline_read(argv[2], &bytes);
    if (!expected) return pipeline_error("expected file read failed");
    uint64_t work_ns = 0, verification_ns = 0;
    for (unsigned pass = 0; pass < passes; ++pass) {
        uint64_t start = ail_pipeline_now();
        if (!freopen(argv[3], "wb", stdout)) { free(expected); return pipeline_error("output reopen failed"); }
#ifdef AIL_PIPELINE
        char *args[4] = {argv[0], argv[1], argv[4], argv[5]};
        ail_argv_set(4, args);
        int status = ail_pipeline_main();
#else
        int status = pipeline_reference(argv[1], order, factor);
#endif
        if (status || fflush(stdout) || ferror(stdout)) { free(expected); return pipeline_error("pipeline failed"); }
        if (!pipeline_interval(&work_ns, start, ail_pipeline_now())) { free(expected); return pipeline_error("work clock interval failed"); }
        start = ail_pipeline_now();
        int match = pipeline_verify(argv[3], expected, bytes);
        if (!pipeline_interval(&verification_ns, start, ail_pipeline_now()) || !match) {
            free(expected); return pipeline_error("complete output mismatch or verification failed");
        }
    }
    free(expected);
    struct rusage usage;
    if (getrusage(RUSAGE_SELF, &usage)) return pipeline_error("resource measurement failed");
    fprintf(stderr, "{\"count\":%zu,\"passes\":%u,\"order\":%u,\"mode\":\"%s\",\"work_ns\":%" PRIu64
            ",\"read_ns\":%" PRIu64 ",\"decode_ns\":%" PRIu64 ",\"map_ns\":%" PRIu64
            ",\"encode_ns\":%" PRIu64 ",\"write_ns\":%" PRIu64 ",\"verification_ns\":%" PRIu64
            ",\"peak_rss_kib\":%ld,\"user_us\":%" PRIu64 ",\"system_us\":%" PRIu64 ",\"output_match\":true}\n",
            bytes / 8, passes, order, argv[7], work_ns, ail_pipeline_phases[0], ail_pipeline_phases[1],
            ail_pipeline_phases[2], ail_pipeline_phases[3], ail_pipeline_phases[4], verification_ns, usage.ru_maxrss,
            (uint64_t)usage.ru_utime.tv_sec * UINT64_C(1000000) + usage.ru_utime.tv_usec,
            (uint64_t)usage.ru_stime.tv_sec * UINT64_C(1000000) + usage.ru_stime.tv_usec);
    return ferror(stderr) ? 1 : 0;
}
