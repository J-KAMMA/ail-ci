#include <string.h>

static float *clipped;

ail_c_float32_view native_clip(const float *values, size_t count, float limit) {
    float *next = count ? malloc(count * sizeof *next) : NULL;
    if (count && !next) { fputs("out of memory\n", stderr); exit(1); }
    for (size_t i = 0; i < count; ++i)
        next[i] = values[i] < -limit ? -limit : values[i] > limit ? limit : values[i];
    free(clipped);
    clipped = next;
    return (ail_c_float32_view){clipped, count};
}

void native_release(void) { free(clipped); clipped = NULL; }

uint32_t native_bits(float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof bits);
    return bits;
}
