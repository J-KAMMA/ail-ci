#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#ifdef _WIN32
#include <windows.h>
#endif

extern int64_t native_file_identity_status(const unsigned char *, size_t,
                                         const unsigned char *, size_t);

static int fail(int status) {
    fputs(status == 2 ? "ValueError\n" : "I/O error\n", stderr);
    return status;
}

static int decimal(const char *s, int64_t *value) {
    int negative = *s == '-';
    if (*s == '-' || *s == '+') ++s;
    if (!*s) return 0;
    uint64_t n = 0, limit = (uint64_t)INT64_MAX + negative;
    for (; *s; ++s) {
        if (*s < '0' || *s > '9') return 0;
        unsigned digit = (unsigned)(*s - '0');
        if (n > (limit - digit) / 10) return 0;
        n = n * 10 + digit;
    }
    *value = negative ? (n == (uint64_t)INT64_MAX + 1 ? INT64_MIN : -(int64_t)n)
                      : (int64_t)n;
    return 1;
}

static FILE *open_path(const char *path, int writing) {
#ifdef _WIN32
    size_t n = strlen(path);
    if (n > INT_MAX) return NULL;
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path,
                                   (int)n, NULL, 0);
    if (length <= 0 || (size_t)length > SIZE_MAX / sizeof(wchar_t) - 1)
        return NULL;
    wchar_t *wide = malloc(((size_t)length + 1) * sizeof *wide);
    if (!wide) return NULL;
    FILE *file = NULL;
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, (int)n,
                            wide, length) == length) {
        wide[length] = 0;
        file = _wfopen(wide, writing ? L"wb" : L"rb");
    }
    free(wide);
    return file;
#else
    return fopen(path, writing ? "wb" : "rb");
#endif
}

static uint32_t le32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
           (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static unsigned le16(const unsigned char *p) {
    return (unsigned)p[0] | (unsigned)p[1] << 8;
}

/* Streaming input avoids the platform-dependent width of ftell/fseek. */
static int read_all(FILE *file, unsigned char **buffer, size_t *length) {
    size_t used = 0, capacity = 65536;
    unsigned char *data = malloc(capacity);
    if (!data) return 0;
    for (;;) {
        if (used == capacity) {
            if (capacity > SIZE_MAX / 2) { free(data); return 0; }
            size_t next = capacity * 2;
            unsigned char *grown = realloc(data, next);
            if (!grown) { free(data); return 0; }
            data = grown;
            capacity = next;
        }
        size_t count = fread(data + used, 1, capacity - used, file);
        used += count;
        if (ferror(file)) { free(data); return 0; }
        if (feof(file)) break;
        if (!count) { free(data); return 0; }
    }
    *buffer = data;
    *length = used;
    return 1;
}

static int validate(unsigned char *data, size_t n,
                    size_t *audio_start, size_t *audio_length) {
    if (n < 12 || memcmp(data, "RIFF", 4) || memcmp(data + 8, "WAVE", 4) ||
        (uint64_t)le32(data + 4) + 8 != (uint64_t)n) return 0;
    size_t offset = 12;
    int fmt_seen = 0, data_seen = 0;
    unsigned block = 0;
    while (offset < n) {
        if (n - offset < 8) return 0;
        uint32_t length = le32(data + offset + 4);
        size_t start = offset + 8;
        uint64_t padded = (uint64_t)length + (length & 1u);
        if (padded > n - start) return 0;
        if (!memcmp(data + offset, "fmt ", 4)) {
            if (fmt_seen++ || (length != 16 && length != 18)) return 0;
            const unsigned char *fmt = data + start;
            unsigned channels = le16(fmt + 2);
            uint32_t rate = le32(fmt + 4);
            block = le16(fmt + 12);
            if (le16(fmt) != 1 || (channels != 1 && channels != 2) ||
                le16(fmt + 14) != 16 || !rate || block != channels * 2 ||
                (uint64_t)rate * block != le32(fmt + 8)) return 0;
        } else if (!memcmp(data + offset, "data", 4)) {
            if (data_seen++) return 0;
            *audio_start = start;
            *audio_length = length;
        }
        offset = start + (size_t)padded;
    }
    return fmt_seen == 1 && data_seen == 1 && *audio_length % block == 0;
}

int main(int argc, char **argv) {
    int64_t numerator, denominator;
    if (argc != 6 || strcmp(argv[1], "gain") ||
        !decimal(argv[4], &numerator) || !decimal(argv[5], &denominator) ||
        numerator < -65536 || numerator > 65536 ||
        denominator < 1 || denominator > 65536) return fail(2);
    int64_t identity = native_file_identity_status(
        (const unsigned char *)argv[2], strlen(argv[2]),
        (const unsigned char *)argv[3], strlen(argv[3]));
    if (identity != 0) return fail(identity == 1 ? 2 : 3);
    FILE *input = open_path(argv[2], 0);
    if (!input) return fail(3);
    unsigned char *data = NULL;
    size_t n = 0, start = 0, length = 0;
    int read_ok = read_all(input, &data, &n);
    int close_ok = fclose(input) == 0;
    if (!read_ok || !close_ok) { free(data); return fail(3); }
    if (!validate(data, n, &start, &length)) { free(data); return fail(2); }
    for (size_t i = start; i < start + length; i += 2) {
        unsigned raw = le16(data + i);
        int64_t sample = raw < 32768 ? (int64_t)raw : (int64_t)raw - 65536;
        int64_t scaled = sample * numerator / denominator;
        if (scaled < -32768) scaled = -32768;
        if (scaled > 32767) scaled = 32767;
        unsigned encoded = (unsigned)(scaled < 0 ? scaled + 65536 : scaled);
        data[i] = (unsigned char)encoded;
        data[i + 1] = (unsigned char)(encoded >> 8);
    }
    FILE *output = open_path(argv[3], 1);
    if (!output) { free(data); return fail(3); }
    int write_ok = fwrite(data, 1, n, output) == n && !ferror(output);
    close_ok = fclose(output) == 0;
    free(data);
    return write_ok && close_ok ? 0 : fail(3);
}
