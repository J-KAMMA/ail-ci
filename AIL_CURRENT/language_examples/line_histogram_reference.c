/* LF-delimited UTF-8 byte lines only. Keys may contain NUL; Unicode line separators are outside
   this C comparison profile. Keep first-seen order, as the AIL/Python program does. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *key; size_t len, count; uint64_t hash; } Entry;

static void oom(void) { fputs("out of memory\n", stderr); exit(1); }

static unsigned char *read_all(const char *path, size_t *len) {
    FILE *file = fopen(path, "rb");
    if (!file) { fputs("read error\n", stderr); exit(3); }
    size_t cap = 65536, n = 0;
    unsigned char *data = malloc(cap);
    if (!data) oom();
    for (;;) {
        if (n == cap) {
            if (cap > SIZE_MAX / 2) oom();
            cap *= 2;
            unsigned char *grown = realloc(data, cap);
            if (!grown) oom();
            data = grown;
        }
        size_t got = fread(data + n, 1, cap - n, file);
        n += got;
        if (got == 0) {
            if (ferror(file)) { fputs("read error\n", stderr); exit(3); }
            break;
        }
    }
    fclose(file);
    *len = n;
    return data;
}

static uint64_t hash_line(const unsigned char *p, size_t n) {
    uint64_t h = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < n; ++i) h = (h ^ p[i]) * UINT64_C(1099511628211);
    return h;
}

static void rehash(size_t **slots, size_t *cap, const Entry *entries, size_t used) {
    if (*cap > SIZE_MAX / 2 / sizeof(**slots)) oom();
    size_t next = *cap * 2;
    size_t *fresh = calloc(next, sizeof(*fresh));
    if (!fresh) oom();
    for (size_t i = 0; i < used; ++i) {
        size_t pos = (size_t)entries[i].hash & (next - 1);
        while (fresh[pos]) pos = (pos + 1) & (next - 1);
        fresh[pos] = i + 1;
    }
    free(*slots);
    *slots = fresh;
    *cap = next;
}

static void add_line(const unsigned char *p, size_t n, Entry **entries, size_t *used,
                     size_t *entry_cap, size_t **slots, size_t *slot_cap) {
    if (*used >= *slot_cap / 2) rehash(slots, slot_cap, *entries, *used);
    uint64_t hash = hash_line(p, n);
    size_t pos = (size_t)hash & (*slot_cap - 1);
    while ((*slots)[pos]) {
        Entry *e = &(*entries)[(*slots)[pos] - 1];
        if (e->hash == hash && e->len == n && !memcmp(e->key, p, n)) {
            if (e->count == SIZE_MAX) oom();
            ++e->count;
            return;
        }
        pos = (pos + 1) & (*slot_cap - 1);
    }
    if (*used == *entry_cap) {
        if (*entry_cap > SIZE_MAX / 2 / sizeof(**entries)) oom();
        size_t next = *entry_cap ? *entry_cap * 2 : 128;
        Entry *grown = realloc(*entries, next * sizeof(*grown));
        if (!grown) oom();
        *entries = grown;
        *entry_cap = next;
    }
    (*entries)[*used] = (Entry){(const char *)p, n, 1, hash};
    (*slots)[pos] = ++*used;
}

int main(int argc, char **argv) {
    if (argc != 2) { fputs("usage: line_histogram <utf8-file>\n", stderr); return 2; }
    size_t n;
    unsigned char *data = read_all(argv[1], &n);
    size_t slot_cap = 1024, entry_cap = 0, used = 0;
    size_t *slots = calloc(slot_cap, sizeof(*slots));
    Entry *entries = NULL;
    if (!slots) oom();
    size_t start = 0;
    for (size_t i = 0; i < n; ++i) {
        if (data[i] != '\n') continue;
        add_line(data + start, i - start, &entries, &used, &entry_cap, &slots, &slot_cap);
        start = i + 1;
    }
    if (start < n)
        add_line(data + start, n - start, &entries, &used, &entry_cap, &slots, &slot_cap);
    for (size_t i = 0; i < used; ++i) {
        if (fwrite(entries[i].key, 1, entries[i].len, stdout) != entries[i].len ||
            fputc('\t', stdout) == EOF || printf("%zu\n", entries[i].count) < 0) {
            fputs("write error\n", stderr);
            return 1;
        }
    }
    free(slots);
    free(entries);
    free(data);
    return 0;
}
