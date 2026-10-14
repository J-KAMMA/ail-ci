#include "series.h"
#include <stdio.h>

int main(void) {
    const int64_t input[] = {9, -2, 7, 7, 12};
    series_int_view values = {input, 5};
    series_int_buffer selected = {0}, changes = {0}, bounds = {0};
    series_error error;
    if (series_above(values, 7, &selected, &error) ||
        series_differences(values, &changes, &error) ||
        series_bounds(values, &bounds, &error)) {
        fprintf(stderr, "%s\n", error.message);
        series_free(selected.data); series_free(changes.data); series_free(bounds.data);
        return 1;
    }
    const int64_t expected_selected[] = {7, 7, 9, 12};
    const int64_t expected_changes[] = {-11, 9, 0, 5};
    int failed = selected.size != 4 || changes.size != 4 || bounds.size != 2;
    if (!failed) {
        for (size_t i = 0; i < 4; ++i)
            failed |= selected.data[i] != expected_selected[i] || changes.data[i] != expected_changes[i];
        failed |= bounds.data[0] != -2 || bounds.data[1] != 12;
    }
    const int64_t overflowing[] = {INT64_MIN, INT64_MAX};
    int64_t *previous = changes.data;
    failed |= series_differences((series_int_view){overflowing, 2}, &changes, &error) != 8;
    failed |= changes.data != previous || changes.size != 4;
    if (!failed) failed |= changes.data[0] != -11 || changes.data[3] != 5;
    series_free(selected.data); series_free(changes.data); series_free(bounds.data);
    series_int_buffer filtered = {0};
    if (series_filtered_differences(values, 7, &filtered, &error)) return 3;
    failed |= filtered.size != 3;
    if (!failed) failed |= filtered.data[0] != 0 || filtered.data[1] != 2 || filtered.data[2] != 3;
    series_free(filtered.data);
    int64_t total = -1;
    failed |= series_filtered_change_total(values, 7, &total, &error) != 0 || total != 5;
    if (failed) return 2;
    puts("selected=4 differences=4 bounds=-2,12");
    return 0;
}
