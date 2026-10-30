#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int code(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'C') return 10 + c - 'A';
    return -1;
}

static int fail(void) { return 1; }

int main(int argc, char **argv) {
    if (argc != 3) return fail();
    const char *r = argv[1];
    unsigned char B[13] = {0}, S[13] = {0};
    if (*r != 'B') return fail();
    r++;
    int last = -1;
    while (*r && *r != '/') {
        int c = code(*r);
        if (c < 0 || c <= last) return fail();
        B[c] = 1; last = c; r++;
    }
    if (*r != '/') return fail();
    r++;
    if (*r != 'S') return fail();
    r++;
    last = -1;
    while (*r) {
        int c = code(*r);
        if (c < 0 || c <= last) return fail();
        S[c] = 1; last = c; r++;
    }
    const char *g = argv[2];
    if (!*g) return fail();
    long gens = 0;
    for (; *g; g++) {
        if (*g < '0' || *g > '9') return fail();
        gens = gens * 10 + (*g - '0');
        if (gens > 100000) return fail();
    }

    size_t cap = 1 << 16, len = 0;
    char *in = malloc(cap);
    if (!in) return fail();
    size_t n;
    while ((n = fread(in + len, 1, cap - len, stdin)) > 0) {
        len += n;
        if (len == cap) {
            cap *= 2;
            in = realloc(in, cap);
            if (!in) return fail();
        }
    }
    size_t p = 0;
    long W = 0, H = 0;
    if (p >= len || in[p] < '1' || in[p] > '9') return fail();
    while (p < len && in[p] >= '0' && in[p] <= '9') {
        W = W * 10 + (in[p++] - '0');
        if (W > 4096) return fail();
    }
    if (p >= len || in[p] != ' ') return fail();
    p++;
    if (p >= len || in[p] < '1' || in[p] > '9') return fail();
    while (p < len && in[p] >= '0' && in[p] <= '9') {
        H = H * 10 + (in[p++] - '0');
        if (H > 4096) return fail();
    }
    if (p >= len || in[p] != '\n') return fail();
    p++;
    size_t need = (size_t)H * (W + 1);
    if (len - p != need && len - p != need - 1) return fail();
    unsigned char *cur = malloc((size_t)W * H), *nxt = malloc((size_t)W * H);
    if (!cur || !nxt) return fail();
    for (long y = 0; y < H; y++) {
        for (long x = 0; x < W; x++) {
            char c = in[p++];
            if (c == 'o') cur[y * W + x] = 1;
            else if (c == '.') cur[y * W + x] = 0;
            else return fail();
        }
        if (y < H - 1 || p < len) {
            if (p >= len || in[p] != '\n') return fail();
            p++;
        }
    }
    if (p != len) return fail();
    free(in);

    int *xl = malloc(sizeof(int) * W), *xr = malloc(sizeof(int) * W);
    for (long x = 0; x < W; x++) {
        xl[x] = (int)((x + W - 1) % W);
        xr[x] = (int)((x + 1) % W);
    }
    unsigned char lut[3][13];
    for (int w = 0; w < 13; w++) {
        lut[0][w] = B[w] ? 1 : 0;
        lut[1][w] = S[w] ? 1 : 2;
        lut[2][w] = 0;
    }
    char *out = malloc(1 << 20);
    size_t ol = 0, oc = 1 << 20;
    for (long gi = 1; gi <= gens; gi++) {
        long A = 0, Sc = 0;
        for (long y = 0; y < H; y++) {
            const unsigned char *up = cur + ((y + H - 1) % H) * W;
            const unsigned char *mid = cur + y * W;
            const unsigned char *dn = cur + ((y + 1) % H) * W;
            unsigned char *o = nxt + y * W;
            for (long x = 0; x < W; x++) {
                int l = xl[x], rr = xr[x];
                int w = 2 * ((up[x] == 1) + (dn[x] == 1) + (mid[l] == 1) + (mid[rr] == 1))
                      + (up[l] == 1) + (up[rr] == 1) + (dn[l] == 1) + (dn[rr] == 1);
                unsigned char s = lut[mid[x]][w];
                o[x] = s;
                A += (s == 1);
                Sc += (s == 2);
            }
        }
        unsigned char *t = cur; cur = nxt; nxt = t;
        if (ol + 64 > oc) { oc *= 2; out = realloc(out, oc); }
        ol += sprintf(out + ol, "%ld %ld %ld\n", gi, A, Sc);
        if (ol > (1 << 19)) { fwrite(out, 1, ol, stdout); ol = 0; }
    }
    fwrite(out, 1, ol, stdout);
    char *row = malloc(W + 1);
    for (long y = 0; y < H; y++) {
        for (long x = 0; x < W; x++) {
            unsigned char s = cur[y * W + x];
            row[x] = s == 1 ? 'o' : s == 2 ? 'x' : '.';
        }
        row[W] = '\n';
        fwrite(row, 1, W + 1, stdout);
    }
    return 0;
}
