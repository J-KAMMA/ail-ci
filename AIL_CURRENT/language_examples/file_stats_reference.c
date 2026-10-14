/* Independent C11 reference for file_line_stats.ail.
 * Comparison profile: ASCII, excluding '_' and bytes 0x1c..0x1f;
 * whitespace is space, tab, CR, LF, VT, FF. Universal newlines.
 * Out-of-profile input, I/O failure, and int64 overflow fail before stdout.
 */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static int whitespace(unsigned char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\v' || c == '\f';
}

/* Validate the whole token before conversion: an oversized prefix followed
 * by a nondigit is a lexical error, not an integer overflow. */
static int parse(const unsigned char *line, size_t n, int64_t *value) {
    size_t first = 0;
    while (first < n && whitespace(line[first])) first++;
    while (n > first && whitespace(line[n - 1])) n--;
    int negative = first < n && line[first] == '-';
    if (first < n && (line[first] == '+' || line[first] == '-')) first++;
    if (first == n) return 0;
    for (size_t i = first; i < n; i++)
        if (line[i] < '0' || line[i] > '9') return 0;
    uint64_t magnitude = 0, limit = (uint64_t)INT64_MAX + (unsigned)negative;
    for (size_t i = first; i < n; i++) {
        unsigned digit = line[i] - '0';
        if (magnitude > (limit - digit) / 10) return -1;
        magnitude = magnitude * 10 + digit;
    }
    *value = negative ? (magnitude == (uint64_t)INT64_MAX + 1 ? INT64_MIN : -(int64_t)magnitude)
                      : (int64_t)magnitude;
    return 1;
}

static int account(const unsigned char *line, size_t n, int64_t *valid,
                   int64_t *invalid, int64_t *total) {
    int64_t value;
    int result = parse(line, n, &value);
    if (result < 0) return 0;
    if (!result) {
        if (*invalid == INT64_MAX) return 0;
        (*invalid)++;
    } else {
        if (*valid == INT64_MAX || (value > 0 && *total > INT64_MAX - value)
            || (value < 0 && *total < INT64_MIN - value)) return 0;
        *total += value;
        (*valid)++;
    }
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    for (const unsigned char *p = (const unsigned char *)argv[1]; *p; p++)
        if (*p > 127) return 1;
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 1;
    unsigned char *line = NULL;
    size_t length = 0, capacity = 0;
    int64_t valid = 0, invalid = 0, total = 0;
    int ok = 1, c;
    while ((c = fgetc(file)) != EOF) {
        if (c > 127 || c == '_' || (c >= 0x1c && c <= 0x1f)) { ok = 0; break; }
        if (c == '\r' || c == '\n') {
            if (c == '\r') {
                int next = fgetc(file);
                if (next != EOF && next != '\n' && ungetc(next, file) == EOF) { ok = 0; break; }
            }
            if (!account(line, length, &valid, &invalid, &total)) { ok = 0; break; }
            length = 0;
        } else {
            if (length == capacity) {
                if (capacity > SIZE_MAX / 2) { ok = 0; break; }
                size_t grown = capacity ? capacity * 2 : 256;
                unsigned char *buffer = realloc(line, grown);
                if (!buffer) { ok = 0; break; }
                line = buffer;
                capacity = grown;
            }
            line[length++] = (unsigned char)c;
        }
    }
    if (ferror(file)) ok = 0;
    if (ok && length && !account(line, length, &valid, &invalid, &total)) ok = 0;
    if (fclose(file)) ok = 0;
    free(line);
    if (!ok) return 1;
    if (printf("%" PRId64 "\n%" PRId64 "\n%" PRId64 "\n", valid, invalid, total) < 0
        || fflush(stdout) == EOF) return 1;
    return 0;
}
