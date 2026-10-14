/* Independent byte-preserving reference for the regular binary64-LE profile.
 * Default: bulk streaming ring. SAMPLE_TAIL_SEEK: retained-range file read.
 * SAMPLE_TAIL_PROFILE: Linux monotonic timing, success-only stderr JSON. */
#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <ctype.h>
#ifdef _WIN32
#include <wchar.h>
#include <wctype.h>
typedef wchar_t character;
#define SPACE(c) iswspace(c)
#define ENTRY wmain
#define OPEN(p,m) _wfopen(p,L##m)
#define SEEK _fseeki64
#define TELL _ftelli64
#else
typedef char character;
#define SPACE(c) isspace((unsigned char)(c))
#define ENTRY main
#define OPEN(p,m) fopen(p,m)
#define SEEK fseeko
#define TELL ftello
#endif
#if defined(SAMPLE_TAIL_PROFILE) && !defined(_WIN32)
#include <time.h>
static uint64_t now_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) abort();
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
#else
static uint64_t now_ns(void) { return 0; }
#endif
static int capacity(const character *p, uint64_t *value) {
    while (SPACE(*p)) ++p;
    int negative = *p == '-';
    if (*p == '+' || *p == '-') ++p;
    uint64_t n = 0;
    uint64_t maximum = (uint64_t)INT64_MAX + (unsigned)negative;
    int digit = 0;
    for (;;) {
        if (*p >= '0' && *p <= '9') {
            unsigned d = (unsigned)(*p++ - '0');
            if (n > (maximum - d) / 10) return -1;
            n = n * 10 + d;
            digit = 1;
        } else break;
    }
    while (SPACE(*p)) ++p;
    if (*p || !digit || negative || !n) return 0;
    *value = n;
    return 1;
}
typedef struct { unsigned char *p; size_t allocated, length, head, limit; } Ring;
static int feed(Ring *r, const unsigned char *p, size_t n) {
    if (n >= r->limit) { p += n - r->limit; n = r->limit; r->length = r->head = 0; }
    size_t wanted = r->length + (n > r->limit - r->length ? r->limit - r->length : n);
    if (wanted > r->allocated) {
        size_t allocated = r->allocated ? r->allocated : 8;
        while (allocated < wanted) {
            if (allocated > r->limit / 2) { allocated = r->limit; break; }
            allocated *= 2;
        }
        unsigned char *q = malloc(allocated);
        if (!q) return 0;
        size_t first = r->length < r->allocated - r->head ? r->length : r->allocated - r->head;
        if (first) memcpy(q, r->p + r->head, first);
        if (r->length > first) memcpy(q + first, r->p, r->length - first);
        free(r->p); r->p = q; r->allocated = allocated; r->head = 0;
    }
    if (n > r->limit - r->length) {
        size_t drop = n - (r->limit - r->length);
        r->head = r->head >= r->allocated - drop ? r->head - (r->allocated - drop) : r->head + drop;
        r->length -= drop;
    }
    size_t end = r->head >= r->allocated - r->length ? r->head - (r->allocated - r->length) : r->head + r->length;
    size_t first = n < r->allocated - end ? n : r->allocated - end;
    if (first) memcpy(r->p + end, p, first);
    if (n > first) memcpy(r->p, p + first, n - first);
    r->length += n;
    return 1;
}
int ENTRY(int argc, character **argv) {
    if (argc != 4) {
        fputs("usage: sample_tail <input-f64le> <output-f64le> <capacity>\n", stderr); return 2;
    }
    int result = 0;
    uint64_t samples, payload = 0, read_payload = 0, feed_ns = 0, read_ns = 0, write_ns = 0;
    int parsed = capacity(argv[3], &samples);
    if (parsed <= 0) result = parsed < 0 ? 1 : 4;
    Ring r = {0};
    /* Huge valid capacities allocate only as input arrives; never multiply unchecked. */
    if (!result) r.limit = samples > (SIZE_MAX / 8) ? SIZE_MAX - SIZE_MAX % 8 : (size_t)samples * 8;
    FILE *in = result ? NULL : OPEN(argv[1], "rb");
    if (!result && !in) result = 3;
#ifdef SAMPLE_TAIL_SEEK
    if (!result) {
        uint64_t start = now_ns();
        if (SEEK(in, 0, SEEK_END)) result = 3;
        int64_t size = result ? -1 : (int64_t)TELL(in);
        if (size < 0) result = 3;
        else {
            payload = (uint64_t)size;
            if (payload % 8) result = 4;
            else {
                r.length = payload < r.limit ? (size_t)payload : r.limit;
                if (SEEK(in, size - (int64_t)r.length, SEEK_SET)) result = 3;
                if (!result && r.length) {
                    r.p = malloc(r.length); r.allocated = r.length;
                    if (!r.p) result = 3;
                    else {
                        read_payload = fread(r.p, 1, r.length, in);
                        if (read_payload != r.length) result = 3;
                    }
                }
            }
        }
        read_ns += now_ns() - start;
    }
#else
    unsigned char chunk[65536 + 8];
    size_t pending = 0;
    while (!result) {
        uint64_t start = now_ns();
        size_t n = fread(chunk + pending, 1, 65536, in);
        read_ns += now_ns() - start;
        if (UINT64_MAX - payload < n) { result = 3; break; }
        payload += n;
        read_payload += n;
        if (ferror(in)) { result = 3; break; }
        size_t total = pending + n, aligned = total - total % 8;
        start = now_ns();
        if (aligned && !feed(&r, chunk, aligned)) result = 3;
        feed_ns += now_ns() - start;
        pending = total - aligned;
        if (pending) memmove(chunk, chunk + aligned, pending);
        if (!n) { if (pending) result = 4; break; }
    }
#endif
    if (in && fclose(in) && !result) result = 3;
    if (!result) {
        uint64_t start = now_ns();
        FILE *out = OPEN(argv[2], "wb");
        if (!out) result = 3;
        else {
            size_t first = r.length < r.allocated - r.head ? r.length : r.allocated - r.head;
            if ((first && fwrite(r.p + r.head, 1, first, out) != first) ||
                (r.length > first && fwrite(r.p, 1, r.length - first, out) != r.length - first)) result = 3;
            if (fclose(out)) result = 3;
        }
        write_ns += now_ns() - start;
    }
#ifdef SAMPLE_TAIL_PROFILE
    if (!result) fprintf(stderr, "PROFILE {\"feed_ns\":%llu,\"read_ns\":%llu,\"write_ns\":%llu,\"input_payload_bytes\":%llu,\"read_payload_bytes\":%llu,\"retained_bytes\":%llu}\n",
        (unsigned long long)feed_ns, (unsigned long long)read_ns, (unsigned long long)write_ns,
        (unsigned long long)payload, (unsigned long long)read_payload, (unsigned long long)r.length);
#endif
    free(r.p);
    if (result == 1) fputs("integer overflow\n", stderr);
    if (result == 3) fputs("sample data file error\n", stderr);
    if (result == 4) fputs("capacity must be positive and input must contain binary64 samples\n", stderr);
    return result;
}
