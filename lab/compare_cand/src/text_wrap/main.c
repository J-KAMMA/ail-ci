#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static unsigned char *read_all(size_t *len) {
    size_t cap = 1 << 20, n = 0;
    unsigned char *b = malloc(cap);
    if (!b) {
        *len = 0;
        return NULL;
    }
    for (;;) {
        if (n == cap) {
            cap *= 2;
            unsigned char *nb = realloc(b, cap);
            if (!nb) {
                free(b);
                *len = 0;
                return NULL;
            }
            b = nb;
        }
        size_t r = fread(b + n, 1, cap - n, stdin);
        if (r == 0) break;
        n += r;
    }
    *len = n;
    return b;
}

int main(void) {
    size_t n;
    unsigned char *data = read_all(&n);
    if (!data) return 2;

    size_t e = 0;
    while (e < n && data[e] != 10) e++;
    if (e < 1 || e > 3) {
        free(data);
        return 2;
    }
    long long w = 0;
    for (size_t k = 0; k < e; k++) {
        unsigned char c = data[k];
        if (c < 48 || c > 57) {
            free(data);
            return 2;
        }
        w = w * 10 + (long long)(c - 48);
    }
    if (w < 10 || w > 200) {
        free(data);
        return 2;
    }

    size_t pos = (e < n) ? e + 1 : n;
    long long paragraphs = 0, lines = 0, words = 0, longest = 0, h = 0;
    int emitted_any = 0, in_para = 0, first_line = 0;
    long long cur_len = 0;

    for (;;) {
        e = pos;
        while (e < n && data[e] != 10) e++;
        size_t a = pos;
        int blank = 1;
        for (size_t k = a; k < e; k++) {
            if (data[k] != 32) {
                blank = 0;
                break;
            }
        }
        if (blank) {
            if (in_para) {
                in_para = 0;
                cur_len = 0;
            }
        } else {
            size_t k = a;
            while (k < e) {
                unsigned char c = data[k];
                if (c == 32 || c == 9) {
                    k++;
                    continue;
                }
                size_t ws = k;
                while (k < e) {
                    c = data[k];
                    if (c == 32 || c == 9) break;
                    k++;
                }
                long long wl = (long long)(k - ws);
                words++;
                if (!in_para) {
                    in_para = 1;
                    first_line = 1;
                    paragraphs++;
                }
                if (cur_len == 0) {
                    if (first_line) {
                        if (emitted_any) {
                            h = (h * 131 + 10) % 1000000007LL;
                            h = (h * 131 + 10) % 1000000007LL;
                        }
                        emitted_any = 1;
                        first_line = 0;
                    } else {
                        h = (h * 131 + 10) % 1000000007LL;
                    }
                    lines++;
                    cur_len = wl;
                } else if (cur_len + 1 + wl <= w) {
                    h = (h * 131 + 32) % 1000000007LL;
                    cur_len += 1 + wl;
                } else {
                    h = (h * 131 + 10) % 1000000007LL;
                    lines++;
                    cur_len = wl;
                }
                for (size_t p = ws; p < k; p++) {
                    h = (h * 131 + (long long)data[p]) % 1000000007LL;
                }
                if (cur_len > longest) longest = cur_len;
            }
        }
        if (e >= n) break;
        pos = e + 1;
    }

    printf("paragraphs %lld lines %lld words %lld longest %lld hash %lld\n",
           paragraphs, lines, words, longest, h);
    free(data);
    return 0;
}
