#include <stdint.h>
#include <stddef.h>
#include <string.h>

int64_t native_find_byte(const unsigned char *data, size_t length,
                        int64_t value, int64_t start, int64_t end) {
    if (value < 0 || value > 255) return -2;
    if (length > INT64_MAX || length > PTRDIFF_MAX) return -3;
    int64_t size = (int64_t)length;
    if (start < 0) {
        start += size;
        if (start < 0) start = 0;
    }
    if (end < 0) {
        end += size;
        if (end < 0) end = 0;
    } else if (end > size) end = size;
    if (start >= end) return -1;
    const unsigned char *found = memchr(data + (size_t)start, (int)value,
                                        (size_t)(end - start));
    return found ? (int64_t)(found - data) : -1;
}
