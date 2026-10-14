/* C comparator for ASCII decimal lines of at most 62 bytes, with int64 sums. */
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char line[64];
    int64_t count = 0, total = 0;
    while (fgets(line, sizeof line, stdin)) {
        size_t len = strlen(line);
        if (len == sizeof line - 1 && line[len - 1] != '\n') return 2;
        errno = 0;
        char *end;
        long long value = strtoll(line, &end, 10);
        if (errno == ERANGE || end == line) return 2;
        if (*end == '\r') end++;
        if (*end == '\n') end++;
        if (*end || __builtin_add_overflow(total, (int64_t)value, &total)
                 || count == INT64_MAX) return 2;
        count++;
    }
    if (ferror(stdin)) return 2;
    printf("%" PRId64 "\n%" PRId64 "\n", count, total);
    return 0;
}
