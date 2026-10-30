#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static unsigned char *rd(size_t *len) {
    size_t cap = 1 << 16, n = 0;
    unsigned char *b = malloc(cap);
    if (!b) exit(2);
    for (;;) {
        if (n == cap) { cap *= 2; b = realloc(b, cap); if (!b) exit(2); }
        size_t r = fread(b + n, 1, cap - n, stdin);
        if (r == 0) break;
        n += r;
    }
    *len = n;
    return b;
}

static uint32_t hsh(const unsigned char *d, size_t n) {
    uint32_t h = 0;
    for (size_t i = 0; i < n; i++) h = h * 257u + d[i] + 1u;
    return h;
}

#define HB 20
static uint32_t key(const unsigned char *p) {
    uint32_t v = p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
    return (v * 2654435761u) >> (32 - HB);
}

static void flush(unsigned char *o, size_t *on, const unsigned char *L, int *ln) {
    if (!*ln) return;
    o[(*on)++] = (unsigned char)(*ln - 1);
    memcpy(o + *on, L, *ln);
    *on += *ln;
    *ln = 0;
}

static int pack(void) {
    size_t n;
    unsigned char *D = rd(&n);
    unsigned char *o = malloc(n + n / 128 + 64 + n / 4 * 0);
    if (!o) return 1;
    size_t on = 0;
    memcpy(o, "EP1", 3);
    o[3] = n; o[4] = n >> 8; o[5] = n >> 16; o[6] = n >> 24;
    on = 7;
    uint32_t *head = malloc(sizeof(uint32_t) * (1u << HB));
    uint32_t *prev = malloc(sizeof(uint32_t) * (n + 1));
    if (!head || !prev) return 1;
    memset(head, 0xff, sizeof(uint32_t) * (1u << HB));
    size_t ins = 0;
    unsigned char L[128];
    int ln = 0;
    size_t i = 0;
    while (i < n) {
        int found = 0;
        size_t bm = 0, bp = 0;
        if (i + 4 <= n) {
            while (ins < i) {
                if (ins + 4 <= n) {
                    uint32_t k = key(D + ins);
                    prev[ins] = head[k];
                    head[k] = (uint32_t)ins;
                }
                ins++;
            }
            uint32_t p = head[key(D + i)];
            int cnt = 0;
            size_t lim = n - i < 131 ? n - i : 131;
            while (p != 0xffffffffu && cnt < 8 && i - p <= 65535) {
                if (memcmp(D + p, D + i, 4) == 0) {
                    cnt++;
                    size_t m = 4;
                    while (m < lim && D[p + m] == D[i + m]) m++;
                    if (!found || m > bm) { bm = m; bp = p; found = 1; }
                }
                p = prev[p];
            }
        }
        if (found) {
            flush(o, &on, L, &ln);
            size_t dist = i - bp;
            o[on++] = (unsigned char)(0x80 + (bm - 4));
            o[on++] = dist >> 8;
            o[on++] = dist & 255;
            i += bm;
        } else {
            L[ln++] = D[i++];
            if (ln == 128) flush(o, &on, L, &ln);
        }
    }
    flush(o, &on, L, &ln);
    uint32_t h = hsh(D, n);
    o[on++] = h; o[on++] = h >> 8; o[on++] = h >> 16; o[on++] = h >> 24;
    fwrite(o, 1, on, stdout);
    return 0;
}

static int unpack(void) {
    size_t len;
    unsigned char *s = rd(&len);
    if (len < 7 || memcmp(s, "EP1", 3)) return 2;
    uint64_t n = s[3] | (s[4] << 8) | (s[5] << 16) | ((uint64_t)s[6] << 24);
    size_t pos = 7, on = 0, cap = 1 << 16;
    unsigned char *o = malloc(cap);
    if (!o) return 2;
    while (on < n) {
        if (pos >= len) return 2;
        unsigned c = s[pos++];
        size_t add;
        if (c < 0x80) {
            add = c + 1;
            if (len - pos < add) return 2;
            if (on + add > n) return 2;
        } else {
            if (len - pos < 2) return 2;
            add = (c - 0x80) + 4;
            if (on + add > n) return 2;
        }
        while (on + add > cap) { cap *= 2; o = realloc(o, cap); if (!o) return 2; }
        if (c < 0x80) {
            memcpy(o + on, s + pos, add);
            pos += add;
        } else {
            size_t dist = (s[pos] << 8) | s[pos + 1];
            pos += 2;
            if (dist == 0 || dist > on) return 2;
            for (size_t k = 0; k < add; k++) o[on + k] = o[on + k - dist];
        }
        on += add;
    }
    if (len - pos != 4) return 2;
    uint32_t h = s[pos] | (s[pos + 1] << 8) | (s[pos + 2] << 16) | ((uint32_t)s[pos + 3] << 24);
    if (h != hsh(o, on)) return 2;
    fwrite(o, 1, on, stdout);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    if (!strcmp(argv[1], "pack")) return pack();
    if (!strcmp(argv[1], "unpack")) return unpack();
    return 1;
}
