/* argv[1] is a UTF-8 output path; saving replaces its existing contents. */
#include "records.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    if (argc != 2) { fprintf(stderr, "usage: record_files OUTPUT\n"); return 2; }
    unsigned char *input = malloc(65537);
    if (!input) return 1;
    for (size_t i = 0; i < 65537; i++) input[i] = (unsigned char)i;
    records_view path = {(const unsigned char *)argv[1], strlen(argv[1])};
    records_buffer result = {0}; records_error error; int64_t saved = 0;
    int status = records_save_record(path, (records_view){input, 65537}, &saved, &error);
    if (!status) status = records_load_record(path, &result, &error);
    if (status) {
        fprintf(stderr, "%d: %s\n", status, error.message);
        free(input); return 1;
    }
    int correct = saved == 65545 && result.size == 65537 && !memcmp(result.data, input, 65537);
    free(input);
    /* Empty pathname cannot name a file: the host survives and retains result. */
    records_buffer unchanged = result;
    int missing = records_load_record((records_view){NULL, 0}, &result, &error);
    printf("saved=%lld restored=%zu missing=%d\n", (long long)saved, result.size, missing);
    correct = correct && missing == 6 && result.data == unchanged.data && result.size == unchanged.size;
    records_free(result.data);
    return !correct;
}
