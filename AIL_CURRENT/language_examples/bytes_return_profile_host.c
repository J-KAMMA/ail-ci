/* The common header supplies price_phases[5], price_now(), and PRICE_ENABLED. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/resource.h>

static int bytes_price_error(const char *message) {
    fprintf(stderr, "%s\n", message);
    return 1;
}
static int bytes_price_decimal(const char *text, uint64_t limit, uint64_t *value) {
    if (!*text || (text[0] == '0' && text[1])) return 0;
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
static int bytes_price_interval(uint64_t *total, uint64_t start, uint64_t end) {
    if (end < start || end - start > UINT64_MAX - *total) return 0;
    *total += end - start;
    return 1;
}
static int bytes_price_size(const char *path, size_t *length) {
    struct stat info;
    if (stat(path, &info) || !S_ISREG(info.st_mode) || info.st_size < 0 ||
            (uintmax_t)info.st_size > SIZE_MAX || (uintmax_t)info.st_size > PTRDIFF_MAX ||
            (uintmax_t)info.st_size > INT64_MAX) return 0;
    *length = (size_t)info.st_size;
    return 1;
}
static int bytes_price_verify(const char *expected, const char *output) {
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
static int bytes_price_reference(const char *path, int rejoin, size_t first, size_t second) {
    uint64_t start = PRICE_ENABLED ? price_now() : 0;
    FILE *file = fopen(path, "rb");
    if (!file) return bytes_price_error("input open failed");
    unsigned char *input = NULL, *result = NULL;
    int status = 1;
    if (fseek(file, 0, SEEK_END)) goto done;
    long end = ftell(file);
    if (end < 0 || (uintmax_t)end > SIZE_MAX || (uintmax_t)end > PTRDIFF_MAX ||
            (uintmax_t)end > INT64_MAX || fseek(file, 0, SEEK_SET)) goto done;
    size_t length = (size_t)end;
    if (first > length || second > length - first) goto done;
    input = malloc(length ? length : 1);
    if (!input || fread(input, 1, length, file) != length || fgetc(file) != EOF || ferror(file)) goto done;
    if (fclose(file)) { file = NULL; goto done; }
    file = NULL;
    if (PRICE_ENABLED && !bytes_price_interval(&price_phases[0], start, price_now())) goto done;
    start = PRICE_ENABLED ? price_now() : 0;
    size_t count = rejoin ? first + second : second;
    result = malloc(count ? count : 1);
    if (!result) goto done;
    if (rejoin) {
        if (first) memcpy(result, input, first);
        if (second) memcpy(result + first, input + first, second);
    } else if (count) memcpy(result, input + first, count);
    if (PRICE_ENABLED && !bytes_price_interval(&price_phases[2], start, price_now())) goto done;
    start = PRICE_ENABLED ? price_now() : 0;
    if (fwrite(result, 1, count, stdout) != count || ferror(stdout)) goto done;
    if (PRICE_ENABLED && !bytes_price_interval(&price_phases[4], start, price_now())) goto done;
    status = 0;
done:
    if (file && fclose(file)) status = 1;
    free(result);
    free(input);
    return status ? bytes_price_error("reference failed") : 0;
}
#endif
static int bytes_price_microseconds(struct timeval time, uint64_t *value) {
    if (time.tv_sec < 0 || time.tv_usec < 0 || time.tv_usec >= 1000000 ||
            (uintmax_t)time.tv_sec > (UINT64_MAX - (uint64_t)time.tv_usec) / UINT64_C(1000000)) return 0;
    *value = (uint64_t)time.tv_sec * UINT64_C(1000000) + (uint64_t)time.tv_usec;
    return 1;
}
int main(int argc, char **argv) {
    uint64_t first, second, passes;
    if (argc != 9 || !bytes_price_decimal(argv[5], INT64_MAX, &first) ||
            !bytes_price_decimal(argv[6], INT64_MAX, &second) ||
            !bytes_price_decimal(argv[7], 32, &passes) || !passes ||
            (strcmp(argv[4], "slice") && strcmp(argv[4], "rejoin")) ||
            (strcmp(argv[8], "plain") && strcmp(argv[8], "profile")) ||
            (strcmp(argv[8], "profile") == 0) != (PRICE_ENABLED == 1) ||
            (PRICE_ENABLED != 0 && PRICE_ENABLED != 1)) return bytes_price_error("invalid arguments");
    size_t input_length, expected_length;
    int rejoin = strcmp(argv[4], "rejoin") == 0;
    if (!bytes_price_size(argv[1], &input_length) || !bytes_price_size(argv[2], &expected_length) ||
            first > input_length || second > input_length - first ||
            expected_length != (rejoin ? first + second : second) ||
            !strcmp(argv[3], argv[1]) || !strcmp(argv[3], argv[2])) return bytes_price_error("invalid files or bounds");
    uint64_t work_ns = 0, verification_ns = 0;
    for (uint64_t pass = 0; pass < passes; ++pass) {
        uint64_t start = price_now();
        if (!freopen(argv[3], "wb", stdout)) return bytes_price_error("output reopen failed");
#ifdef AIL_PRICE
        char *args[5] = {argv[0], argv[4], argv[1], argv[5], argv[6]};
        ail_argv_set(5, args);
        int status = ail_price_program();
        if (ail_cleanup_top != NULL || ail_exc_top != -1) return bytes_price_error("AIL cleanup incomplete");
#else
        int status = bytes_price_reference(argv[1], rejoin, (size_t)first, (size_t)second);
#endif
        if (status || fflush(stdout) || ferror(stdout)) return bytes_price_error("program or output failed");
        if (!bytes_price_interval(&work_ns, start, price_now())) return bytes_price_error("work clock failed");
        start = price_now();
        int match = bytes_price_verify(argv[2], argv[3]);
        if (!bytes_price_interval(&verification_ns, start, price_now()) || !match)
            return bytes_price_error("complete output mismatch or verification failed");
    }
    struct rusage usage;
    uint64_t user_us, system_us;
    if (getrusage(RUSAGE_SELF, &usage) || usage.ru_maxrss < 0 ||
            !bytes_price_microseconds(usage.ru_utime, &user_us) ||
            !bytes_price_microseconds(usage.ru_stime, &system_us)) return bytes_price_error("resource measurement failed");
    fprintf(stderr, "{\"passes\":%" PRIu64 ",\"observer\":\"%s\",\"work_ns\":%" PRIu64
            ",\"verification_ns\":%" PRIu64 ",\"peak_rss_kib\":%" PRIu64
            ",\"user_us\":%" PRIu64 ",\"system_us\":%" PRIu64
            ",\"read_ns\":%" PRIu64 ",\"field_ns\":%" PRIu64 ",\"select_ns\":%" PRIu64
            ",\"join_ns\":%" PRIu64 ",\"write_ns\":%" PRIu64 ",\"output_match\":true}\n",
            passes, argv[8], work_ns, verification_ns, (uint64_t)usage.ru_maxrss, user_us, system_us,
            price_phases[0], price_phases[1], price_phases[2], price_phases[3], price_phases[4]);
    return ferror(stderr) ? 1 : 0;
}
