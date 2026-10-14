/* Binary64 numeric profile: NaN class only, no NaN sign/payload promise.
 * Per-thread borrowed arrays are copied by the AIL adapter before reuse. */
#include <float.h>
#include <stdint.h>
#include <string.h>

_Static_assert(sizeof(double) == 8 && FLT_RADIX == 2 && DBL_MANT_DIG == 53 &&
               DBL_MAX_EXP == 1024, "binary64 double required");

ail_c_bytes_view native_binary64_pack_records(const double *values, size_t count,
                                            int64_t reverse) {
    static _Thread_local unsigned char output[65537];
    output[0] = 1;
    if (count > 8192 || (!values && count) || (reverse != 0 && reverse != 1))
        return (ail_c_bytes_view){output, 1};
    for (size_t i = 0; i < count; i++) {
        uint64_t bits;
        memcpy(&bits, values + i, 8);
        for (unsigned b = 0; b < 8; b++)
            output[1 + i * 8 + (reverse ? 7 - b : b)] = (unsigned char)(bits >> (8 * b));
    }
    output[0] = 0;
    return (ail_c_bytes_view){output, count * 8 + 1};
}

ail_c_float_view native_binary64_unpack_records(const unsigned char *data, size_t size,
                                               int64_t reverse) {
    static _Thread_local double values[8192];
    if (size > 65536 || size % 8 || (!data && size) || (reverse != 0 && reverse != 1))
        return (ail_c_float_view){NULL, 0};
    for (size_t i = 0; i < size / 8; i++) {
        uint64_t bits = 0;
        for (unsigned b = 0; b < 8; b++)
            bits |= (uint64_t)data[i * 8 + (reverse ? 7 - b : b)] << (8 * b);
        memcpy(values + i, &bits, 8);
    }
    return (ail_c_float_view){values, size / 8};
}
