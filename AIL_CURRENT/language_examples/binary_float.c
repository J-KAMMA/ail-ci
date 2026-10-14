#include <float.h>
#include <limits.h>
#include <string.h>

_Static_assert(CHAR_BIT == 8 && sizeof(double) == 8 && DBL_MANT_DIG == 53 &&
               DBL_MAX_EXP == 1024 && sizeof(uint64_t) == 8, "binary64 platform required");

/* The AIL adapter immediately copies this borrowed, per-thread result. */
ail_c_bytes_view native_binary64_pack(double value, int64_t reverse) {
    static _Thread_local unsigned char output[8];
    if (reverse != 0 && reverse != 1) return (ail_c_bytes_view){NULL, 0};
    uint64_t bits;
    memcpy(&bits, &value, sizeof bits);
    for (unsigned i = 0; i < 8; ++i)
        output[reverse ? 7-i : i] = (unsigned char)(bits >> (8*i));
    return (ail_c_bytes_view){output, sizeof output};
}

double native_binary64_unpack(const unsigned char *data, size_t size, int64_t reverse) {
    if (!data || size != 8 || (reverse != 0 && reverse != 1)) return 0.0;
    uint64_t bits = 0;
    for (unsigned i = 0; i < 8; ++i)
        bits |= (uint64_t)data[reverse ? 7-i : i] << (8*i);
    double value;
    memcpy(&value, &bits, sizeof value);
    return value;
}
