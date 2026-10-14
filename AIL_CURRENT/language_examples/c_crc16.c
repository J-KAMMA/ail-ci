#include <stdint.h>
#include <stddef.h>

uint16_t native_crc16(const unsigned char *data, size_t length, uint16_t seed) {
    uint32_t crc = seed;
    for (size_t i = 0; i < length; ++i) {
        crc ^= (uint32_t)data[i] << 8;
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = ((crc << 1) ^ ((crc & 0x8000u) ? 0x1021u : 0)) & 0xffffu;
    }
    return (uint16_t)crc;
}
