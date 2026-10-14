#include <stdint.h>
#include <stddef.h>

/* Borrowed read-only int64_t spans; never retain the pointer after return. */
int64_t count_above(const int64_t *values, size_t count, int64_t threshold) {
    int64_t result = 0;
    for (size_t i = 0; i < count; ++i) result += values[i] > threshold;
    return result;
}

/* Caller provides a sorted, ascending sequence. */
int64_t lower_bound(const int64_t *values, size_t count, int64_t key) {
    size_t first = 0, last = count;
    while (first < last) {
        size_t middle = first + (last - first) / 2;
        if (values[middle] < key) first = middle + 1;
        else last = middle;
    }
    return (int64_t)first;
}
