#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
    const char *names[4] = {"DEBUG", "INFO", "WARN", "ERROR"};
    long long status[4] = {0, 0, 0, 0};
    long long hours[24] = {0};
    size_t start = 0;
    while (start < len) {
        size_t end = start;
        while (end < len && data[end] != '\n') end++;
        data[end] = '\0';
        if (end > start) {
            char *space1 = strchr(data + start, ' ');
            if (space1) {
                char *space2 = strchr(space1 + 1, ' ');
                if (space2) {
                    int hour = (space1[1] - '0') * 10 + (space1[2] - '0');
                    if (hour >= 0 && hour < 24) hours[hour]++;
                    char *st = space2 + 1;
                    char *space3 = strchr(st, ' ');
                    size_t slen = space3 ? (size_t)(space3 - st) : strlen(st);
                    for (int k = 0; k < 4; k++) {
                        if (strlen(names[k]) == slen && strncmp(st, names[k], slen) == 0) {
                            status[k]++;
                            break;
                        }
                    }
                }
            }
        }
        start = end + 1;
    }
    for (int k = 0; k < 3; k++) {
        for (int j = k + 1; j < 4; j++) {
            if (strcmp(names[k], names[j]) > 0) {
                const char *tmp = names[k]; names[k] = names[j]; names[j] = tmp;
                long long t = status[k]; status[k] = status[j]; status[j] = t;
            }
        }
    }
    for (int k = 0; k < 4; k++) if (status[k]) printf("status %s %lld\n", names[k], status[k]);
    for (int h = 0; h < 24; h++) if (hours[h]) printf("hour %02d %lld\n", h, hours[h]);
    free(data);
    return 0;
}
