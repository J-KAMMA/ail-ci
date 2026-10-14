/* Prefix supplies shared clocks, phases, resident_data, resident_size, capture declaration. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <inttypes.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/resource.h>
#include <sched.h>

#ifndef PRICE_CPU
#define PRICE_CPU 4
#endif
#if PRICE_CPU != 4 || PRICE_CPU >= CPU_SETSIZE
#error PRICE_CPU must be 4
#endif
#ifndef PRICE_PASSES_MAX
#define PRICE_PASSES_MAX 256
#endif
#if PRICE_PASSES_MAX < 1 || PRICE_PASSES_MAX > 256
#error PRICE_PASSES_MAX must be between 1 and 256
#endif

#ifndef RESIDENT_AIL
static const unsigned char *resident_data;
static int64_t resident_size;
#endif

static unsigned char resident_output[512];
static size_t resident_output_size;
static const char *resident_capture_failure;

static void resident_capture(const unsigned char *data, int64_t length) {
    if (resident_capture_failure) return;
    if (length < 0 || (uintmax_t)length > sizeof resident_output - resident_output_size) {
        resident_capture_failure = "invalid or overflowing resident capture";
        return;
    }
    if (length && !data) {
        resident_capture_failure = "null resident capture data";
        return;
    }
    if (length) memcpy(resident_output + resident_output_size, data, (size_t)length);
    resident_output_size += (size_t)length;
}

static int resident_error(const char *message) {
    fprintf(stderr, "%s\n", message);
    return 1;
}

static int resident_affinity(void) {
    cpu_set_t mask;
    return sched_getaffinity(0, sizeof mask, &mask) == 0 &&
            CPU_COUNT(&mask) == 1 && CPU_ISSET(PRICE_CPU, &mask);
}

static int resident_passes(const char *text, uint64_t *value) {
    if (!*text || *text == '0') return 0;
    uint64_t result = 0;
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p < '0' || *p > '9') return 0;
        unsigned digit = *p - '0';
        if (result > PRICE_PASSES_MAX / 10 ||
                (result == PRICE_PASSES_MAX / 10 && digit > PRICE_PASSES_MAX % 10)) return 0;
        result = result * 10 + digit;
    }
    *value = result;
    return result >= 1 && result <= PRICE_PASSES_MAX;
}

static int resident_interval(uint64_t *total, uint64_t start, uint64_t end) {
    if (end < start || end - start > UINT64_MAX - *total) return 0;
    *total += end - start;
    return 1;
}

static int resident_file_size(const char *path, size_t *length) {
    struct stat info;
    if (stat(path, &info) || !S_ISREG(info.st_mode) || info.st_size < 0 ||
            (uintmax_t)info.st_size > SIZE_MAX || (uintmax_t)info.st_size > PTRDIFF_MAX ||
            (uintmax_t)info.st_size > INT64_MAX) return 0;
    *length = (size_t)info.st_size;
    return 1;
}

static int resident_file_read(const char *path, unsigned char *data, size_t length) {
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    int valid = fread(data, 1, length, file) == length && fgetc(file) == EOF && !ferror(file);
    if (fclose(file)) valid = 0;
    return valid;
}

#ifndef RESIDENT_AIL
static int resident_reference(void) {
    const unsigned char *input = resident_data;
    size_t length = (size_t)resident_size;
    uint64_t start = PRICE_ENABLED ? price_now() : 0;
    uint64_t count = length / 13, sum8 = 0, sum16le = 0, sum16be = 0, sum32le = 0, sum32be = 0;
    for (size_t offset = 0; offset < length; offset += 13) {
        const unsigned char *p = input + offset;
        sum8 += p[0];
        sum16le += (uint32_t)p[1] + (uint32_t)p[2] * UINT32_C(256);
        sum16be += (uint32_t)p[3] * UINT32_C(256) + (uint32_t)p[4];
        sum32le += (uint32_t)p[5] + (uint32_t)p[6] * UINT32_C(256) +
                (uint32_t)p[7] * UINT32_C(65536) + (uint32_t)p[8] * UINT32_C(16777216);
        sum32be += (uint32_t)p[9] * UINT32_C(16777216) + (uint32_t)p[10] * UINT32_C(65536) +
                (uint32_t)p[11] * UINT32_C(256) + (uint32_t)p[12];
    }
    if (PRICE_ENABLED) price_add(2, start);
    start = PRICE_ENABLED ? price_now() : 0;
    char report[512];
    int size = snprintf(report, sizeof report, "%" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %zu\n",
            count, sum8, sum16le, sum16be, sum32le, sum32be, length);
    if (size < 0 || (size_t)size >= sizeof report) return 1;
    resident_capture((const unsigned char *)report, size);
    if (PRICE_ENABLED) price_add(4, start);
    return resident_capture_failure != NULL;
}
#endif

static int resident_microseconds(struct timeval time, uint64_t *value) {
    if (time.tv_sec < 0 || time.tv_usec < 0 || time.tv_usec >= 1000000 ||
            (uintmax_t)time.tv_sec > (UINT64_MAX - (uint64_t)time.tv_usec) / UINT64_C(1000000)) return 0;
    *value = (uint64_t)time.tv_sec * UINT64_C(1000000) + (uint64_t)time.tv_usec;
    return 1;
}

int main(int argc, char **argv) {
    uint64_t passes;
    if (argc != 5 || !resident_passes(argv[3], &passes) ||
            (strcmp(argv[4], "plain") && strcmp(argv[4], "profile")) ||
            (strcmp(argv[4], "profile") == 0) != (PRICE_ENABLED == 1) ||
            (PRICE_ENABLED != 0 && PRICE_ENABLED != 1)) return resident_error("invalid arguments");
    int cpu_start = sched_getcpu();
    if (cpu_start != PRICE_CPU || !resident_affinity()) return resident_error("initial CPU affinity mismatch");
    size_t input_length, expected_length;
    if (!resident_file_size(argv[1], &input_length) || !resident_file_size(argv[2], &expected_length) ||
            input_length % 13 || (uint64_t)(input_length / 13) > UINT64_C(2147483648) ||
            expected_length > sizeof resident_output) return resident_error("invalid files or bounds");
    unsigned char *input = malloc(input_length ? input_length : 1);
    if (!input) return resident_error("resident input allocation failed");
    unsigned char expected[512];
    const char *failure = NULL;
    if (!resident_file_read(argv[1], input, input_length) ||
            !resident_file_read(argv[2], expected, expected_length)) {
        failure = "resident input or oracle read failed";
        goto done;
    }
    resident_data = input;
    resident_size = (int64_t)input_length;
    uint64_t work_ns = 0, verification_ns = 0;
    for (uint64_t pass = 0; pass < passes; ++pass) {
        resident_output_size = 0;
        resident_capture_failure = NULL;
        uint64_t start = price_now();
#ifdef RESIDENT_AIL
        char *args[2] = {argv[0], "resident-input"};
        ail_argv_set(2, args);
        int status = ail_price_program();
        if (ail_cleanup_top != NULL || ail_exc_top != -1) {
            failure = "AIL cleanup incomplete";
            goto done;
        }
#else
        int status = resident_reference();
#endif
        if (!resident_interval(&work_ns, start, price_now())) {
            failure = "work clock failed";
            goto done;
        }
        if (status || resident_capture_failure) {
            failure = resident_capture_failure ? resident_capture_failure : "resident program failed";
            goto done;
        }
        start = price_now();
        int match = resident_output_size == expected_length &&
                memcmp(resident_output, expected, expected_length) == 0;
        if (!resident_interval(&verification_ns, start, price_now()) || !match) {
            failure = "complete output mismatch or verification clock failed";
            goto done;
        }
    }
    int cpu_end = sched_getcpu();
    if (cpu_end != PRICE_CPU || !resident_affinity()) {
        failure = "final CPU affinity mismatch";
        goto done;
    }
    if (!PRICE_ENABLED) {
        for (unsigned phase = 0; phase < 5; ++phase) {
            if (price_phases[phase]) { failure = "plain observer has phase time"; goto done; }
        }
    }
    struct rusage usage;
    uint64_t user_us, system_us;
    if (getrusage(RUSAGE_SELF, &usage) || usage.ru_maxrss < 0 ||
            (uintmax_t)usage.ru_maxrss > UINT64_MAX ||
            !resident_microseconds(usage.ru_utime, &user_us) ||
            !resident_microseconds(usage.ru_stime, &system_us)) {
        failure = "resource measurement failed";
        goto done;
    }
    free(input);
    resident_data = NULL;
    resident_size = 0;
    fprintf(stderr, "{\"passes\":%" PRIu64 ",\"observer\":\"%s\",\"work_ns\":%" PRIu64
            ",\"verification_ns\":%" PRIu64 ",\"peak_rss_kib\":%" PRIu64
            ",\"user_us\":%" PRIu64 ",\"system_us\":%" PRIu64
            ",\"read_ns\":%" PRIu64 ",\"field_ns\":%" PRIu64 ",\"select_ns\":%" PRIu64
            ",\"join_ns\":%" PRIu64 ",\"write_ns\":%" PRIu64 ",\"output_match\":true"
            ",\"cpu_start\":%d,\"cpu_end\":%d,\"affinity_checked\":true}\n",
            passes, argv[4], work_ns, verification_ns, (uint64_t)usage.ru_maxrss, user_us, system_us,
            price_phases[0], price_phases[1], price_phases[2], price_phases[3], price_phases[4], cpu_start, cpu_end);
    return ferror(stderr) ? 1 : 0;
done:
    free(input);
    resident_data = NULL;
    resident_size = 0;
    return resident_error(failure ? failure : "resident measurement failed");
}
