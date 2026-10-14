"""Known reflected CRC-32 recurrence replaced by a constant 1 KiB lookup table."""
HEADER = '''#ifndef EXAMPLE_CRC32_H
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
'''
SPLIT = '''#include "crc.h"

uint32_t example_crc_update(uint32_t crc, const unsigned char *data, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1u) ? UINT32_C(0xedb88320) : 0u);
    }
    return crc;
}
'''


def _entry(value):
    for _ in range(8):
        value = (value >> 1) ^ (0xedb88320 if value & 1 else 0)
    return value


def transform(source):
    if source not in (HEADER,SPLIT):
        raise ValueError('expected exact original CRC header or split update source')
    polynomial = 'EXAMPLE_CRC_POLYNOMIAL' if source == HEADER else 'UINT32_C(0xedb88320)'
    recurrence = ('        crc ^= data[i];\n'
                  '        for (unsigned bit = 0; bit < 8; ++bit)\n'
                  f'            crc = (crc >> 1) ^ ((crc & 1u) ? {polynomial} : 0u);')
    constants=[f'UINT32_C(0x{_entry(i):08x})' for i in range(256)]
    table='static const uint32_t ail_crc_table[256] = {\n'+ '\n'.join(
        '    '+', '.join(constants[i:i+4])+',' for i in range(0,256,4))+'\n};\n\n'
    if source == HEADER:
        table='_Static_assert(EXAMPLE_CRC_POLYNOMIAL == UINT32_C(0xedb88320), "CRC polynomial changed");\n'+table
    marker='static uint32_t example_crc32(' if source == HEADER else 'uint32_t example_crc_update('
    return source.replace(marker,table+marker,1).replace(recurrence,
        '        crc = (crc >> 8) ^ ail_crc_table[(crc ^ (uint32_t)data[i]) & UINT32_C(255)];',1)
