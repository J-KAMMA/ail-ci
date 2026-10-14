#include "crc32.h"

int64_t native_crc32(const unsigned char *data, size_t size) {
    return (int64_t)example_crc32(data, size);
}
