#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { char *key; long long value; } Row;

static int cmp_rows(const void *a, const void *b) {
    return strcmp(((const Row *)a)->key, ((const Row *)b)->key);
}

static char *read_all(size_t *len) {
    size_t cap = 1 << 20, n = 0;
    char *buf = malloc(cap + 1);
    if (!buf) return NULL;
    for (;;) {
        if (n == cap) {
            cap *= 2;
            char *next = realloc(buf, cap + 1);
            if (!next) { free(buf); return NULL; }
            buf = next;
        }
        size_t r = fread(buf + n, 1, cap - n, stdin);
        if (r == 0) break;
        n += r;
    }
    buf[n] = '\0';
    *len = n;
    return buf;
}

int main(void) {
    size_t len;
    char *data = read_all(&len);
    if (!data) return 1;
    size_t cap = 16, nrows = 0;
    Row *rows = malloc(cap * sizeof(Row));
    size_t start = 0;
    while (start < len) {
        size_t end = start;
        while (end < len && data[end] != '\n') end++;
        data[end] = '\0';
        if (end > start) {
            char *comma = strchr(data + start, ',');
            if (comma) {
                *comma = '\0';
                if (nrows == cap) {
                    cap *= 2;
                    rows = realloc(rows, cap * sizeof(Row));
                }
                rows[nrows].key = data + start;
                rows[nrows].value = strtoll(comma + 1, NULL, 10);
                nrows++;
            }
        }
        start = end + 1;
    }
    qsort(rows, nrows, sizeof(Row), cmp_rows);
    size_t i = 0;
    while (i < nrows) {
        size_t j = i + 1;
        long long total = rows[i].value;
        while (j < nrows && strcmp(rows[i].key, rows[j].key) == 0) {
            total += rows[j].value;
            j++;
        }
        printf("%s,%lld\n", rows[i].key, total);
        i = j;
    }
    free(rows);
    free(data);
    return 0;
}
