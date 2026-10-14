/* Independent POSIX reference for the fixed LF byte-numbering diagnostic.
 * Not a physical roof or a replacement for the AIL online/error contract. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int emit(const void *data, size_t size) {
    const unsigned char *p = data;
    while (size) {
        ssize_t n = write(1, p, size);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 3;
        p += n;
        size -= (size_t)n;
    }
    return 0;
}

int main(void) {
    unsigned char data[8192];
    uint64_t number = 1;
    int start = 1;
    for (;;) {
        ssize_t n;
        do { n = read(0, data, sizeof data); } while (n < 0 && errno == EINTR);
        if (n < 0) return 3;
        if (!n) return 0;
        size_t offset = 0;
        while (offset < (size_t)n) {
            if (start) {
                if (number > INT64_MAX) return 4;
                char prefix[32];
                int length = snprintf(prefix, sizeof prefix, "%" PRIu64 ": ", number);
                if (length < 0 || (size_t)length >= sizeof prefix) return 3;
                if (emit(prefix, (size_t)length)) return 3;
                start = 0;
            }
            unsigned char *end = memchr(data + offset, '\n', (size_t)n - offset);
            size_t length = end ? (size_t)(end - data) + 1 - offset : (size_t)n - offset;
            if (emit(data + offset, length)) return 3;
            offset += length;
            if (end) { ++number; start = 1; }
        }
    }
}
