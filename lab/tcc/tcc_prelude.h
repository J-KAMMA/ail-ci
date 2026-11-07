/* Measurement-only shim for TinyCC (never part of a normal build).

   The generated C calls GCC's __builtin_{add,sub,mul}_overflow, which tcc does
   not implement.  Prepending this header gives portable int64 checks.  tcc
   defines __TINYC__, so the definitions exist only in the tcc measurement.

   Not covered here (and not coverable by a prelude): __int128, which the
   general runtime uses in its slice and pow paths, and tcc's lack of a 128-bit
   integer type. */
#include <stdint.h>
#ifdef __TINYC__
static int ail_tcc_add_overflow(int64_t a, int64_t b, int64_t *r) {
    *r = (int64_t)((uint64_t)a + (uint64_t)b);
    return ((a ^ *r) & (b ^ *r)) < 0;
}
static int ail_tcc_sub_overflow(int64_t a, int64_t b, int64_t *r) {
    *r = (int64_t)((uint64_t)a - (uint64_t)b);
    return ((a ^ b) & (a ^ *r)) < 0;
}
static int ail_tcc_mul_overflow(int64_t a, int64_t b, int64_t *r) {
    if (a == 0 || b == 0) { *r = 0; return 0; }
    if (a == -1) { if (b == INT64_MIN) { *r = b; return 1; } *r = -b; return 0; }
    if (b == -1) { if (a == INT64_MIN) { *r = a; return 1; } *r = -a; return 0; }
    if (a > 0) {
        if (b > 0) { if (a > INT64_MAX / b) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
        else { if (b < INT64_MIN / a) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
    } else {
        if (b > 0) { if (a < INT64_MIN / b) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
        else { if (a < INT64_MAX / b) { *r = (int64_t)((uint64_t)a * (uint64_t)b); return 1; } }
    }
    *r = a * b;
    return 0;
}
#define __builtin_add_overflow(a, b, r) ail_tcc_add_overflow((a), (b), (r))
#define __builtin_sub_overflow(a, b, r) ail_tcc_sub_overflow((a), (b), (r))
#define __builtin_mul_overflow(a, b, r) ail_tcc_mul_overflow((a), (b), (r))
#endif
