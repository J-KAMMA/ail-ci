#include <stdint.h>
#include <stddef.h>

uint64_t native_fnv64(const unsigned char *data, size_t length, uint64_t state) {
    for (size_t i = 0; i < length; ++i) {
        state ^= data[i];
        state *= UINT64_C(1099511628211);
    }
    return state;
}
