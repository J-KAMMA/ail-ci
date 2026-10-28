/* The IEEE-754 conversions `struct` needs (see struct.py): the C compiler's memcpy keeps the bits
   exactly, and _Float16 is the half-precision form CPython's 'e' packs. */
#include <stdint.h>

int64_t ail_struct_double_bits(double value);
double ail_struct_bits_double(int64_t bits);
int32_t ail_struct_float_bits(double value);
double ail_struct_bits_float(int32_t bits);
int ail_struct_float_overflow(double value);
int32_t ail_struct_half_bits(double value);
double ail_struct_bits_half(int32_t bits);
int ail_struct_half_overflow(double value);
