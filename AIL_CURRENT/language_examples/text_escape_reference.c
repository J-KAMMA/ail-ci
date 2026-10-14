#if defined(TEXT_ESCAPE_PROFILE) && !defined(_WIN32)
#define _POSIX_C_SOURCE 200809L
#include <time.h>
#endif
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if defined(TEXT_ESCAPE_PROFILE) && !defined(_WIN32)
static uint64_t now_ns(void) {
    struct timespec stamp;
    if (clock_gettime(CLOCK_MONOTONIC, &stamp) != 0) return 0;
    return (uint64_t)stamp.tv_sec * UINT64_C(1000000000) + (uint64_t)stamp.tv_nsec;
}
#endif
#ifdef _WIN32
#include <wchar.h>
typedef wchar_t path_char;
#define open_file(path, mode) _wfopen(path, L##mode)
#else
typedef char path_char;
#define open_file(path, mode) fopen(path, mode)
#endif

static int report(int code) {
    const char *message = code == 2
        ? "usage: text_escape <utf8-input> <utf8-output>\n"
        : code == 4 ? "input must be UTF-8\n" : "text escape file error\n";
    fputs(message, stderr);
    return code;
}

static int valid_utf8(const unsigned char *data, size_t size) {
    size_t i = 0;
    while (i < size) {
        unsigned char first = data[i++];
        size_t count;
        unsigned char low = 0x80, high = 0xbf;
        if (first < 0x80) continue;
        if (first >= 0xc2 && first <= 0xdf) count = 1;
        else if (first >= 0xe0 && first <= 0xef) {
            count = 2;
            if (first == 0xe0) low = 0xa0;
            if (first == 0xed) high = 0x9f;
        } else if (first >= 0xf0 && first <= 0xf4) {
            count = 3;
            if (first == 0xf0) low = 0x90;
            if (first == 0xf4) high = 0x8f;
        } else return 0;
        if (count > size - i || data[i] < low || data[i] > high) return 0;
        ++i;
        while (--count) {
            if (data[i] < 0x80 || data[i] > 0xbf) return 0;
            ++i;
        }
    }
    return 1;
}

static unsigned char escape_suffix(unsigned char c) {
    switch (c) {
        case '\\': return '\\';
        case 0: return '0';
        case '\t': return 't';
        case '\r': return 'r';
        case '\n': return 'n';
        default: return 0;
    }
}

static unsigned char *escape_text(const unsigned char *data, size_t size,
                                  size_t *result_size) {
    size_t output_size = size;
    for (size_t i = 0; i < size; ++i) {
        if (escape_suffix(data[i])) {
            if (output_size == SIZE_MAX) return NULL;
            ++output_size;
        }
    }
    unsigned char *output = malloc(output_size ? output_size : 1);
    if (!output) return NULL;
    size_t position = 0;
    for (size_t i = 0; i < size; ++i) {
        unsigned char suffix = escape_suffix(data[i]);
        if (suffix) {
            output[position++] = '\\';
            output[position++] = suffix;
        } else output[position++] = data[i];
    }
    *result_size = output_size;
    return output;
}

static int run(int argc, path_char **argv) {
    if (argc != 3) return report(2);
#if defined(TEXT_ESCAPE_PROFILE) && !defined(_WIN32)
    uint64_t total_start = now_ns();
#endif
    FILE *input = open_file(argv[1], "rb");
    if (!input) return report(3);
    unsigned char *data = NULL;
    size_t size = 0, capacity = 0;
    unsigned char block[65536];
    int failed = 0;
    size_t count;
    while ((count = fread(block, 1, sizeof block, input)) != 0) {
        if (count > SIZE_MAX - size) { failed = 1; break; }
        size_t needed = size + count;
        if (needed > capacity) {
            size_t next = capacity ? capacity : sizeof block;
            while (next < needed) {
                if (next > SIZE_MAX / 2) { next = needed; break; }
                next *= 2;
            }
            unsigned char *grown = realloc(data, next);
            if (!grown) { failed = 1; break; }
            data = grown;
            capacity = next;
        }
        memcpy(data + size, block, count);
        size = needed;
    }
    if (ferror(input)) failed = 1;
    if (fclose(input) != 0) failed = 1;
    if (failed) { free(data); return report(3); }
    if (!valid_utf8(data, size)) { free(data); return report(4); }
#if defined(TEXT_ESCAPE_PROFILE) && !defined(_WIN32)
    uint64_t mapping_start = now_ns();
#endif
    size_t output_size;
    unsigned char *output = escape_text(data, size, &output_size);
#if defined(TEXT_ESCAPE_PROFILE) && !defined(_WIN32)
    uint64_t mapping_end = now_ns();
#endif
    if (!output) { free(data); return report(3); }
    free(data);
    FILE *destination = open_file(argv[2], "wb");
    if (!destination) { free(output); return report(3); }
    failed = fwrite(output, 1, output_size, destination) != output_size;
    if (fclose(destination) != 0) failed = 1;
    free(output);
#if defined(TEXT_ESCAPE_PROFILE) && !defined(_WIN32)
    if (!failed) {
        uint64_t total_end = now_ns();
        if (total_start && mapping_start && mapping_end && total_end)
            fprintf(stderr, "text_escape_profile mapping_ns=%llu total_ns=%llu\n",
                    (unsigned long long)(mapping_end - mapping_start),
                    (unsigned long long)(total_end - total_start));
        else fprintf(stderr, "text_escape_profile clock_error\n");
    }
#endif
    return failed ? report(3) : 0;
}

#ifdef _WIN32
int wmain(int argc, wchar_t **argv) { return run(argc, argv); }
#else
int main(int argc, char **argv) { return run(argc, argv); }
#endif
