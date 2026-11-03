#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { char *word; long long count; } Count;

static int cmp_words(const void *a, const void *b) {
    return strcmp(*(char *const *)a, *(char *const *)b);
}

static int cmp_counts(const void *a, const void *b) {
    const Count *x = a, *y = b;
    if (x->count != y->count) return x->count > y->count ? -1 : 1;
    return strcmp(x->word, y->word);
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
    for (size_t i = 0; i < len; i++) {
        if (data[i] >= 'A' && data[i] <= 'Z') data[i] += 32;
    }
    size_t cap = 1024, nwords = 0;
    char **words = malloc(cap * sizeof(char *));
    size_t i = 0;
    while (i < len) {
        char c = data[i];
        if ((c >= 'a' && c <= 'z')) {
            size_t start = i;
            while (i < len && data[i] >= 'a' && data[i] <= 'z') i++;
            if (nwords == cap) {
                cap *= 2;
                words = realloc(words, cap * sizeof(char *));
            }
            data[i] = '\0';
            words[nwords++] = data + start;
        } else {
            i++;
        }
    }
    qsort(words, nwords, sizeof(char *), cmp_words);
    Count *counts = malloc((nwords ? nwords : 1) * sizeof(Count));
    size_t ncounts = 0;
    i = 0;
    while (i < nwords) {
        size_t j = i + 1;
        long long n = 1;
        while (j < nwords && strcmp(words[i], words[j]) == 0) { n++; j++; }
        counts[ncounts].word = words[i];
        counts[ncounts].count = n;
        ncounts++;
        i = j;
    }
    qsort(counts, ncounts, sizeof(Count), cmp_counts);
    size_t shown = ncounts < 20 ? ncounts : 20;
    for (i = 0; i < shown; i++) printf("%lld %s\n", counts[i].count, counts[i].word);
    free(counts);
    free(words);
    free(data);
    return 0;
}
