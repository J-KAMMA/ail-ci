#include <stdint.h>
#include <stddef.h>

static uint32_t state;

void native_reset(uint32_t seed) { state = seed; }

void native_update(const unsigned char *data, size_t length) {
    for (size_t i = 0; i < length; ++i) {
        state ^= data[i];
        state *= UINT32_C(16777619);
    }
}

uint32_t native_finish(void) { return state; }
