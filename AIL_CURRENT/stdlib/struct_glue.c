/* The IEEE-754 conversions `struct` needs. Each function copies the bits of one C floating type
   to/from the integer of the same width, so no rounding or normalisation happens here. */
#include <math.h>
#include <stdint.h>
#include <string.h>

int64_t ail_struct_double_bits(double value)
{
    uint64_t bits;
    memcpy(&bits, &value, sizeof bits);
    return (int64_t)bits;
}

double ail_struct_bits_double(int64_t bits)
{
    uint64_t raw = (uint64_t)bits;
    double value;
    memcpy(&value, &raw, sizeof value);
    return value;
}

int32_t ail_struct_float_bits(double value)
{
    uint32_t bits;
    float single = (float)value;
    memcpy(&bits, &single, sizeof bits);
    return (int32_t)bits;
}

double ail_struct_bits_float(int32_t bits)
{
    uint32_t raw = (uint32_t)bits;
    float single;
    memcpy(&single, &raw, sizeof single);
    return (double)single;
}

int ail_struct_float_overflow(double value)
{
    float single = (float)value;
    return isfinite(value) && !isfinite(single);
}

#if defined(__FLT16_MAX__)
int32_t ail_struct_half_bits(double value)
{
    uint16_t bits;
    _Float16 half = (_Float16)value;
    memcpy(&bits, &half, sizeof bits);
    return (int32_t)bits;
}

int ail_struct_half_overflow(double value)
{
    _Float16 half = (_Float16)value;
    return isfinite(value) && !isfinite((double)half);
}

double ail_struct_bits_half(int32_t bits)
{
    uint16_t raw = (uint16_t)bits;
    _Float16 half;
    memcpy(&half, &raw, sizeof half);
    return (double)half;
}
#else
int32_t ail_struct_half_bits(double value)
{
    (void)value;
    return 0;
}

double ail_struct_bits_half(int32_t bits)
{
    (void)bits;
    return 0.0;
}

int ail_struct_half_overflow(double value)
{
    (void)value;
    return 0;
}
#endif
