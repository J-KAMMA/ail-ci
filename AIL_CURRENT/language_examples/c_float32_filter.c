#include <string.h>

static float *filtered;

ail_c_float32_view native_filter(const float *values, size_t count, const float *weights, size_t width) {
    float *next = count ? malloc(count * sizeof *next) : NULL;
    if (count && !next) { fputs("out of memory\n", stderr); exit(1); }
    for (size_t i = 0; i < count; ++i) {
        volatile float sum = 0.0f;
        for (size_t j = 0; j < width && j <= i; ++j) {
            volatile float term = values[i - j] * weights[j];
            sum = sum + term;
        }
        next[i] = sum;
    }
    free(filtered);
    filtered = next;
    return (ail_c_float32_view){filtered, count};
}

void native_release(void) { free(filtered); filtered = NULL; }

uint32_t native_bits(float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof bits);
    return bits;
}
