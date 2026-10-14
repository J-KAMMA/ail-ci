#include <stdint.h>
#include <stddef.h>

int64_t count_between(const double *values, size_t count, double low, double high) {
    int64_t matches = 0;
    for (size_t i = 0; i < count; i++)
        if (values[i] >= low && values[i] <= high) matches++;
    return matches;
}

double total(const double *values, size_t count) {
    double result = 0.0;
    for (size_t i = 0; i < count; i++) result += values[i];
    return result;
}
