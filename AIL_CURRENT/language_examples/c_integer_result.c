#include <stdint.h>
#include <stddef.h>

/* Input is ascending. The result borrows a contiguous part of that input. */
ail_c_int_view between(const int64_t *values, size_t count, int64_t low, int64_t high) {
    if (low > high) return (ail_c_int_view){NULL, 0};
    size_t first = 0, last = count;
    while (first < last) {
        size_t middle = first + (last - first) / 2;
        if (values[middle] < low) first = middle + 1;
        else last = middle;
    }
    size_t begin = first;
    last = count;
    while (first < last) {
        size_t middle = first + (last - first) / 2;
        if (values[middle] <= high) first = middle + 1;
        else last = middle;
    }
    return (ail_c_int_view){first > begin ? values + begin : NULL, first - begin};
}
