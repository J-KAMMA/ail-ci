/* Borrowed results stay valid until the next moving_average/release call. */
static double *scratch;
static size_t capacity;

ail_c_float_view moving_average(const double *values, size_t count, int64_t window) {
    if (window <= 0 || (uint64_t)window > count) return (ail_c_float_view){NULL, 0};
    size_t width = (size_t)window, length = count - width + 1;
    if (length > capacity) {
        double *next = realloc(scratch, length * sizeof *next);
        if (!next) { fputs("moving_average allocation failed\n", stderr); exit(1); }
        scratch = next;
        capacity = length;
    }
    double total = 0.0;
    for (size_t i = 0; i < width; i++) total += values[i];
    scratch[0] = total / (double)width;
    for (size_t i = width; i < count; i++) {
        total -= values[i - width];
        total += values[i];
        scratch[i - width + 1] = total / (double)width;
    }
    return (ail_c_float_view){scratch, length};
}

int64_t release_smoothing(void) {
    free(scratch);
    scratch = NULL;
    capacity = 0;
    return 0;
}
