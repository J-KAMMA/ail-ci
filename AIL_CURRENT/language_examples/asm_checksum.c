/* Little-endian signed 64-bit words; missing padding words contribute zero. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>

int64_t native_accumulate7(int64_t total, int64_t a, int64_t b, int64_t c,
                           int64_t d, int64_t e, int64_t f);

int64_t native_word(const unsigned char *data, size_t size, int64_t index) {
    if (index < 0 || (uint64_t)index >= size/8) return 0;
    uint64_t bits = 0;
    for (unsigned j = 0; j < 8; ++j)
        bits |= (uint64_t)data[(size_t)index*8+j] << (8*j);
    int64_t value;
    memcpy(&value, &bits, sizeof value);
    return value;
}
