/* Prefix supplies price_phases[5], price_now(), price_add(), PRICE_ENABLED. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/resource.h>
#ifdef PRICE_CPU
#include <sched.h>
#if PRICE_CPU < 0 || PRICE_CPU >= CPU_SETSIZE
#error PRICE_CPU must be a valid CPU set index
#endif
static int records_affinity(void) {
    cpu_set_t mask;
    return sched_getaffinity(0, sizeof mask, &mask) == 0 &&
            CPU_COUNT(&mask) == 1 && CPU_ISSET(PRICE_CPU, &mask);
}
#endif

#ifndef PRICE_PASSES_MAX
#define PRICE_PASSES_MAX 32
#endif
#if PRICE_PASSES_MAX < 1 || PRICE_PASSES_MAX > 4096
#error PRICE_PASSES_MAX must be between 1 and 4096
#endif

static int records_error(const char *message) {
    fprintf(stderr, "%s\n", message);
    return 1;
}
static int records_passes(const char *text, uint64_t *value) {
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
static int records_interval(uint64_t *total, uint64_t start, uint64_t end) {
    if (end < start || end - start > UINT64_MAX - *total) return 0;
    *total += end - start;
    return 1;
}
static int records_size(const char *path, size_t *length) {
    struct stat info;
    if (stat(path, &info) || !S_ISREG(info.st_mode) || info.st_size < 0 ||
            (uintmax_t)info.st_size > SIZE_MAX || (uintmax_t)info.st_size > PTRDIFF_MAX ||
            (uintmax_t)info.st_size > INT64_MAX) return 0;
    *length = (size_t)info.st_size;
    return 1;
}
static int records_verify(const char *expected, const char *output) {
    FILE *left = fopen(expected, "rb"), *right = fopen(output, "rb");
    int match = left && right;
    unsigned char a[65536], b[65536];
    while (match) {
        size_t na = fread(a, 1, sizeof a, left), nb = fread(b, 1, sizeof b, right);
        if (na != nb || memcmp(a, b, na) || ferror(left) || ferror(right)) { match = 0; break; }
        if (na < sizeof a) { match = feof(left) && feof(right); break; }
    }
    if (left && fclose(left)) match = 0;
    if (right && fclose(right)) match = 0;
    return match;
}
#ifndef AIL_PRICE
static int records_reference(const char *path, size_t length) {
    uint64_t start = PRICE_ENABLED ? price_now() : 0;
    FILE *file = fopen(path, "rb");
    unsigned char *input = NULL;
    int status = 1;
    if (!file) goto done;
    input = malloc(length ? length : 1);
    if (!input || fread(input, 1, length, file) != length || fgetc(file) != EOF || ferror(file)) goto done;
    if (fclose(file)) { file = NULL; goto done; }
    file = NULL;
    if (PRICE_ENABLED && !records_interval(&price_phases[0], start, price_now())) goto done;
    start = PRICE_ENABLED ? price_now() : 0;
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
    if (PRICE_ENABLED && !records_interval(&price_phases[2], start, price_now())) goto done;
    start = PRICE_ENABLED ? price_now() : 0;
    if (fprintf(stdout, "%" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %zu\n",
            count, sum8, sum16le, sum16be, sum32le, sum32be, length) < 0 || ferror(stdout)) goto done;
    if (PRICE_ENABLED && !records_interval(&price_phases[4], start, price_now())) goto done;
    status = 0;
done:
    if (file && fclose(file)) status = 1;
    free(input);
    return status ? records_error("reference failed") : 0;
}
#endif
static int records_microseconds(struct timeval time, uint64_t *value) {
    if (time.tv_sec < 0 || time.tv_usec < 0 || time.tv_usec >= 1000000 ||
            (uintmax_t)time.tv_sec > (UINT64_MAX - (uint64_t)time.tv_usec) / UINT64_C(1000000)) return 0;
    *value = (uint64_t)time.tv_sec * UINT64_C(1000000) + (uint64_t)time.tv_usec;
    return 1;
}
int main(int argc, char **argv) {
    uint64_t passes;
    if (argc != 6 || !records_passes(argv[4], &passes) ||
            (strcmp(argv[5], "plain") && strcmp(argv[5], "profile")) ||
            (strcmp(argv[5], "profile") == 0) != (PRICE_ENABLED == 1) ||
            (PRICE_ENABLED != 0 && PRICE_ENABLED != 1)) return records_error("invalid arguments");
    size_t input_length, expected_length;
    if (!records_size(argv[1], &input_length) || !records_size(argv[2], &expected_length) ||
            input_length % 13 || (uint64_t)(input_length / 13) > UINT64_C(2147483648) ||
            !strcmp(argv[1], argv[2]) || !strcmp(argv[1], argv[3]) || !strcmp(argv[2], argv[3]))
        return records_error("invalid files or bounds");
#ifdef PRICE_CPU
    int cpu_start = sched_getcpu();
    if (cpu_start != PRICE_CPU || !records_affinity()) return records_error("initial CPU affinity mismatch");
#endif
    uint64_t work_ns = 0, verification_ns = 0;
    for (uint64_t pass = 0; pass < passes; ++pass) {
        uint64_t start = price_now();
        if (!freopen(argv[3], "wb", stdout)) return records_error("output reopen failed");
#ifdef AIL_PRICE
        char *args[2] = {argv[0], argv[1]};
        ail_argv_set(2, args);
        int status = ail_price_program();
        if (ail_cleanup_top != NULL || ail_exc_top != -1) return records_error("AIL cleanup incomplete");
#else
        int status = records_reference(argv[1], input_length);
#endif
        if (status || fflush(stdout) || ferror(stdout)) return records_error("program or output failed");
        if (!records_interval(&work_ns, start, price_now())) return records_error("work clock failed");
        start = price_now();
        int match = records_verify(argv[2], argv[3]);
        if (!records_interval(&verification_ns, start, price_now()) || !match)
            return records_error("complete output mismatch or verification failed");
    }
#ifdef PRICE_CPU
    int cpu_end = sched_getcpu();
    if (cpu_end != PRICE_CPU || !records_affinity()) return records_error("final CPU affinity mismatch");
#endif
    struct rusage usage;
    uint64_t user_us, system_us;
    if (getrusage(RUSAGE_SELF, &usage) || usage.ru_maxrss < 0 ||
            (uintmax_t)usage.ru_maxrss > UINT64_MAX ||
            !records_microseconds(usage.ru_utime, &user_us) ||
            !records_microseconds(usage.ru_stime, &system_us)) return records_error("resource measurement failed");
    fprintf(stderr, "{\"passes\":%" PRIu64 ",\"observer\":\"%s\",\"work_ns\":%" PRIu64
            ",\"verification_ns\":%" PRIu64 ",\"peak_rss_kib\":%" PRIu64
            ",\"user_us\":%" PRIu64 ",\"system_us\":%" PRIu64
            ",\"read_ns\":%" PRIu64 ",\"field_ns\":%" PRIu64 ",\"select_ns\":%" PRIu64
            ",\"join_ns\":%" PRIu64 ",\"write_ns\":%" PRIu64 ",\"output_match\":true"
#ifdef PRICE_CPU
            ",\"cpu_start\":%d,\"cpu_end\":%d,\"affinity_checked\":true"
#endif
            "}\n",
            passes, argv[5], work_ns, verification_ns, (uint64_t)usage.ru_maxrss, user_us, system_us,
            price_phases[0], price_phases[1], price_phases[2], price_phases[3], price_phases[4]
#ifdef PRICE_CPU
            , cpu_start, cpu_end
#endif
            );
    return ferror(stderr) ? 1 : 0;
}
