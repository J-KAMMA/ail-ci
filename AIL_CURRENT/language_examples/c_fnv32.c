#include <stdint.h>
#include <stddef.h>

uint32_t native_fnv1a(const unsigned char *data, size_t length, uint32_t state) {
    for (size_t i = 0; i < length; ++i) {
        state ^= data[i];
        state *= UINT32_C(16777619);
    }
    return state;
}
