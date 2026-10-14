#include <stddef.h>
#include <stdint.h>

int64_t native_byte_count(const unsigned char *data, size_t length) {
    (void)data;
    return (int64_t)length;
}

int64_t native_checksum(const unsigned char *data, size_t length) {
    uint64_t checksum = 0;
    for (size_t i = 0; i < length; ++i)
        checksum = (checksum + (i % 1000000007ULL + 1) * data[i]) % 1000000007ULL;
    return (int64_t)checksum;
}
