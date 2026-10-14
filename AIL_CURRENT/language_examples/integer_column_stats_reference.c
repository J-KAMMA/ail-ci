#if defined(AIL_STATS_PHASES) && !defined(_WIN32)
#define _POSIX_C_SOURCE 200809L
#endif
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <windows.h>
#endif
#ifdef AIL_STATS_PHASES
#include <time.h>
static uint64_t stats_clock_ns(void) {
#ifdef _WIN32
    return (uint64_t)GetTickCount64() * UINT64_C(1000000);
#else
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) {
        fputs("reference clock failed\n", stderr);
        _Exit(2);
    }
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
#endif
}
#define PHASE_START(name) uint64_t name = stats_clock_ns()
#define PHASE_END(name) name = stats_clock_ns() - name
#else
#define PHASE_START(name) ((void)0)
#define PHASE_END(name) ((void)0)
#endif

typedef struct { int64_t count, total, minimum, maximum; } integer_stats;

static int parse_decimal(const unsigned char *p, size_t n, int64_t *out) {
    if (!p || !n) return 0;
    size_t i = 0;
    int negative = p[0] == '-';
    if (negative || p[0] == '+') ++i;
    if (i == n) return 0;
    int64_t value = 0, limit = negative ? INT64_MIN : -INT64_MAX;
    for (; i < n; ++i) {
        if (p[i] < '0' || p[i] > '9') return 0;
        int digit = p[i] - '0';
        if (value < limit / 10 || (value == limit / 10 && digit > -(limit % 10))) return 0;
        value = value * 10 - digit;
    }
    *out = negative ? value : -value;
    return 1;
}

static int validate_utf8(const unsigned char *p, size_t n) {
    for (size_t i = 0; i < n;) {
        unsigned char first = p[i];
        size_t width;
        uint32_t value, minimum;
        if (first < 0x80) { ++i; continue; }
        if (first >= 0xc2 && first <= 0xdf) { width = 2; value = first & 0x1f; minimum = 0x80; }
        else if (first >= 0xe0 && first <= 0xef) { width = 3; value = first & 0x0f; minimum = 0x800; }
        else if (first >= 0xf0 && first <= 0xf4) { width = 4; value = first & 7; minimum = 0x10000; }
        else return 0;
        if (width > n - i) return 0;
        for (size_t j = 1; j < width; ++j) {
            unsigned char c = p[i + j];
            if ((c & 0xc0) != 0x80) return 0;
            value = (value << 6) | (c & 0x3f);
        }
        if (value < minimum || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff)) return 0;
        i += width;
    }
    return 1;
}

/* Both objects must be queried before opening an output stream. */
static int distinct_paths(const char *input, const char *output) {
    if (!strcmp(input, output)) return 0;
#ifdef _WIN32
    HANDLE a = CreateFileA(input, FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
        OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
    if (a == INVALID_HANDLE_VALUE) return 0;
    BY_HANDLE_FILE_INFORMATION ia, ib;
    int distinct = 0;
    if (GetFileInformationByHandle(a, &ia)) {
        HANDLE b = CreateFileA(output, FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL,
            OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, NULL);
        if (b == INVALID_HANDLE_VALUE) {
            DWORD error = GetLastError();
            distinct = error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND;
        } else {
            if (GetFileInformationByHandle(b, &ib))
                distinct = ia.dwVolumeSerialNumber != ib.dwVolumeSerialNumber ||
                           ia.nFileIndexHigh != ib.nFileIndexHigh || ia.nFileIndexLow != ib.nFileIndexLow;
            CloseHandle(b);
        }
    }
    CloseHandle(a);
    return distinct;
#else
    struct stat a, b;
    if (stat(input, &a)) return 0;
    if (stat(output, &b)) return errno == ENOENT || errno == ENOTDIR;
    return a.st_dev != b.st_dev || a.st_ino != b.st_ino;
#endif
}

static int read_all(const char *path, unsigned char **out, size_t *length) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    size_t n = 0, cap = (size_t)PTRDIFF_MAX < 65536 ? (size_t)PTRDIFF_MAX : 65536;
    unsigned char *p = (unsigned char *)malloc(cap);
    int ok = p != NULL;
    while (ok) {
        if (n == cap) {
            size_t limit = (size_t)PTRDIFF_MAX;
            if (cap == limit) { ok = 0; break; }
            size_t next = cap > limit / 2 ? limit : cap * 2;
            unsigned char *grown = (unsigned char *)realloc(p, next);
            if (!grown) { ok = 0; break; }
            p = grown; cap = next;
        }
        size_t got = fread(p + n, 1, cap - n, f);
        n += got;
        if (!got) { if (ferror(f)) ok = 0; break; }
    }
    if (fclose(f)) ok = 0;
    if (!ok) { free(p); return 0; }
    *out = p; *length = n;
    return 1;
}

/* UTF-8 was validated in full, so continuation bytes cannot masquerade as breaks. */
static size_t line_break(const unsigned char *p, size_t n) {
    unsigned char c = p[0];
    if (c == '\r') return n > 1 && p[1] == '\n' ? 2 : 1;
    if (c == '\n' || c == '\v' || c == '\f' || c == 0x1c || c == 0x1d || c == 0x1e) return 1;
    if (n >= 2 && c == 0xc2 && p[1] == 0x85) return 2;
    if (n >= 3 && c == 0xe2 && p[1] == 0x80 && (p[2] == 0xa8 || p[2] == 0xa9)) return 3;
    return 0;
}

static int add_row(integer_stats *s, const unsigned char *p, size_t n, int64_t column) {
    size_t start = 0;
    int64_t selected = 0;
    for (size_t i = 0;; ++i) {
        if (i == n || p[i] == '\t') {
            if (selected == column) {
                int64_t value;
                if (!parse_decimal(p + start, i - start, &value) || s->count == INT64_MAX ||
                    (value > 0 && s->total > INT64_MAX - value) ||
                    (value < 0 && s->total < INT64_MIN - value)) return 0;
                if (!s->count || value < s->minimum) s->minimum = value;
                if (!s->count || value > s->maximum) s->maximum = value;
                s->total += value; ++s->count;
                return 1;
            }
            if (i == n) return 0;
            if (selected == INT64_MAX) return 0;
            ++selected; start = i + 1;
        }
    }
}

static int collect_stats(const unsigned char *p, size_t n, int64_t column, integer_stats *s) {
    if (column < 0) return 0;
    size_t start = 0, i = 0;
    while (i < n) {
        size_t width = line_break(p + i, n - i);
        if (width) {
            if (!add_row(s, p + start, i - start, column)) return 0;
            i += width; start = i;
        } else ++i;
    }
    return start == n || add_row(s, p + start, n - start, column);
}

static int failure(const char *message) {
    fprintf(stderr, "%s\n", message);
    return 2;
}

int main(int argc, char **argv) {
    int64_t column;
    if (argc != 4) return failure("usage: integer_column_stats input-path output-path column");
    if (!parse_decimal((const unsigned char *)argv[3], strlen(argv[3]), &column) || column < 0)
        return failure("invalid column");
    if (!distinct_paths(argv[1], argv[2])) return failure("input unavailable or output aliases input");
    unsigned char *data = NULL;
    size_t length = 0;
    PHASE_START(read_ns);
    if (!read_all(argv[1], &data, &length)) return failure("input read failed");
    PHASE_END(read_ns);
    PHASE_START(decode_ns);
    int decoded = validate_utf8(data, length);
    PHASE_END(decode_ns);
    if (!decoded) { free(data); return failure("invalid UTF-8"); }
    integer_stats stats = {0};
    PHASE_START(stats_ns);
    int collected = collect_stats(data, length, column, &stats);
    PHASE_END(stats_ns);
    free(data);
    if (!collected) return failure("invalid integer column or overflowing statistics");
    char report[128];
    PHASE_START(render_ns);
    int size = snprintf(report, sizeof report, "%" PRId64 "\t%" PRId64 "\t%" PRId64 "\t%" PRId64 "\n",
                        stats.count, stats.total, stats.minimum, stats.maximum);
    PHASE_END(render_ns);
    if (size < 0 || (size_t)size >= sizeof report) return failure("report rendering failed");
    PHASE_START(write_ns);
    FILE *output = fopen(argv[2], "wb");
    if (!output) return failure("output open failed");
    int written = fwrite(report, 1, (size_t)size, output) == (size_t)size;
    if (fclose(output)) written = 0;
    PHASE_END(write_ns);
    if (!written) return failure("output write failed");
#ifdef AIL_STATS_PHASES
    fprintf(stderr, "STATS_PHASE read_ns=%" PRIu64 " decode_ns=%" PRIu64 " stats_ns=%" PRIu64
                    " render_ns=%" PRIu64 " write_ns=%" PRIu64 "\n",
            read_ns, decode_ns, stats_ns, render_ns, write_ns);
#endif
    return 0;
}
