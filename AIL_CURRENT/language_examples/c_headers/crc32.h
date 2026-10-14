#ifndef EXAMPLE_CRC32_H
#define EXAMPLE_CRC32_H
#include <stddef.h>
#include "detail/crc_constants.h"

static uint32_t example_crc32(const unsigned char *data, size_t size) {
    uint32_t crc = UINT32_MAX;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1u) ? EXAMPLE_CRC_POLYNOMIAL : 0u);
    }
    return crc ^ UINT32_MAX;
}
#endif
