#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

typedef uint64_t u64;
typedef int64_t i64;

typedef struct { u64 key; uint32_t idx; } WE;
typedef struct { WE *a; size_t n, cap; } WH;

static void wpush(WH *h, u64 key, uint32_t idx) {
    if (h->n == h->cap) { h->cap = h->cap ? h->cap * 2 : 1024; h->a = realloc(h->a, h->cap * sizeof(WE)); }
    size_t i = h->n++;
    while (i > 0) {
        size_t p = (i - 1) / 2;
        if (h->a[p].key <= key) break;
        h->a[i] = h->a[p];
        i = p;
    }
    h->a[i].key = key; h->a[i].idx = idx;
}
static void wpop(WH *h) {
    WE last = h->a[--h->n];
    size_t i = 0, n = h->n;
    for (;;) {
        size_t c = 2 * i + 1;
        if (c >= n) break;
        if (c + 1 < n && h->a[c + 1].key < h->a[c].key) c++;
        if (h->a[c].key >= last.key) break;
        h->a[i] = h->a[c];
        i = c;
    }
    if (n) h->a[i] = last;
}

typedef struct { u64 *a; size_t n, cap; } UH;
static void upush(UH *h, u64 v) {
    if (h->n == h->cap) { h->cap = h->cap ? h->cap * 2 : 1024; h->a = realloc(h->a, h->cap * sizeof(u64)); }
    size_t i = h->n++;
    while (i > 0) {
        size_t p = (i - 1) / 2;
        if (h->a[p] <= v) break;
        h->a[i] = h->a[p];
        i = p;
    }
    h->a[i] = v;
}
static void upop(UH *h) {
    u64 last = h->a[--h->n];
    size_t i = 0, n = h->n;
    for (;;) {
        size_t c = 2 * i + 1;
        if (c >= n) break;
        if (c + 1 < n && h->a[c + 1] < h->a[c]) c++;
        if (h->a[c] >= last) break;
        h->a[i] = h->a[c];
        i = c;
    }
    if (n) h->a[i] = last;
}

static int cmpu(const void *x, const void *y) {
    u64 a = *(const u64 *)x, b = *(const u64 *)y;
    return a < b ? -1 : a > b;
}

static char *buf; static size_t bp;
static u64 rd(void) {
    while (buf[bp] < '0') bp++;
    u64 v = 0;
    while (buf[bp] >= '0') v = v * 10 + (buf[bp++] - '0');
    return v;
}

int main(void) {
    size_t cap = 1 << 20, len = 0;
    buf = malloc(cap + 1);
    for (;;) {
        size_t r = fread(buf + len, 1, cap - len, stdin);
        len += r;
        if (len < cap) break;
        cap *= 2; buf = realloc(buf, cap + 1);
    }
    buf[len] = 0;
    int B = (int)rd(); uint32_t S = (uint32_t)rd();
    int *cls = malloc(B * sizeof(int)), *rate = malloc(B * sizeof(int));
    for (int i = 0; i < B; i++) { cls[i] = (int)rd(); rate[i] = (int)rd(); }
    uint32_t *id = malloc((S + 1) * 4), *arr = malloc((S + 1) * 4), *cargo = malloc((S + 1) * 4), *op = malloc((S + 1) * 4);
    uint8_t *sz = malloc(S + 1), *pr = malloc(S + 1);
    for (uint32_t i = 0; i < S; i++) {
        id[i] = (uint32_t)rd(); arr[i] = (uint32_t)rd(); sz[i] = (uint8_t)rd();
        cargo[i] = (uint32_t)rd(); pr[i] = (uint8_t)rd(); op[i] = (uint32_t)rd();
    }
    u64 *ord = malloc((S + 1) * 8);
    for (uint32_t i = 0; i < S; i++) ord[i] = ((u64)arr[i] << 22) | i;
    qsort(ord, S, 8, cmpu);

    i64 *start = malloc((S + 1) * 8);
    int *bert = malloc((S + 1) * 4);
    i64 *bn = calloc(B, 8), *bu = calloc(B, 8);
    i64 *lastop = malloc(B * 8);
    for (int i = 0; i < B; i++) lastop[i] = -1;

    UH fr[4] = {{0}}; UH dep = {0};
    for (int i = 0; i < B; i++) upush(&fr[cls[i]], (u64)i);
    WH wh[4] = {{0}};
    i64 makespan = 0;
    uint32_t ai = 0;
    i64 wtot = 0, wmax = -1; i64 wid = -1;

    while (ai < S || dep.n) {
        u64 t = (u64)-1;
        if (ai < S) t = ord[ai] >> 22;
        if (dep.n && (dep.a[0] >> 11) < t) t = dep.a[0] >> 11;
        while (dep.n && (dep.a[0] >> 11) == t) {
            int b = (int)(dep.a[0] & 2047);
            upop(&dep);
            upush(&fr[cls[b]], (u64)b);
            if ((i64)t > makespan) makespan = (i64)t;
        }
        while (ai < S && (ord[ai] >> 22) == t) {
            uint32_t i = (uint32_t)(ord[ai] & ((1u << 22) - 1));
            ai++;
            wpush(&wh[sz[i]], ((u64)pr[i] << 60) | ((u64)arr[i] << 30) | id[i], i);
        }
        for (int c = 1; c <= 3; c++) {
            while (fr[c].n) {
                int bs = 0; u64 bk = (u64)-1;
                for (int s = 1; s <= c; s++)
                    if (wh[s].n && wh[s].a[0].key < bk) { bk = wh[s].a[0].key; bs = s; }
                if (!bs) break;
                uint32_t i = wh[bs].a[0].idx;
                wpop(&wh[bs]);
                int b = (int)fr[c].a[0];
                upop(&fr[c]);
                i64 svc = (cargo[i] + rate[b] - 1) / rate[b] + (lastop[b] == (i64)op[i] ? 1 : 4);
                lastop[b] = op[i];
                start[i] = (i64)t; bert[i] = b;
                bn[b]++; bu[b] += svc;
                upush(&dep, ((t + (u64)svc) << 11) | (u64)b);
                i64 w = (i64)t - (i64)arr[i];
                wtot += w;
                if (w > wmax || (w == wmax && (i64)id[i] < wid)) { wmax = w; wid = id[i]; }
            }
        }
    }
    if (S == 0) { wmax = 0; wid = -1; }
    for (uint32_t i = 0; i < S; i++) ord[i] = ((u64)id[i] << 22) | i;
    qsort(ord, S, 8, cmpu);
    u64 g = 0;
    for (uint32_t k = 0; k < S; k++) {
        uint32_t i = (uint32_t)(ord[k] & ((1u << 22) - 1));
        g = (g * 1000003ULL + (u64)start[i] * 31 + (u64)bert[i]) % 1000000007ULL;
    }
    printf("ships %u\nmakespan %lld\nwait total %lld max %lld ship %lld\n", S, (long long)makespan, (long long)wtot, (long long)wmax, (long long)wid);
    for (int b = 0; b < B; b++) printf("berth %d ships %lld busy %lld\n", b, (long long)bn[b], (long long)bu[b]);
    printf("digest %llu\n", (unsigned long long)g);
    return 0;
}
