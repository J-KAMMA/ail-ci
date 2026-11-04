#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct { char region[17]; char product[17]; } GKey;
typedef struct { int64_t qty; int64_t rev; } GVal;

static GKey *gk;
static GVal *gv;
static size_t gcap, gn;

static char (*rkey)[17];
static int64_t *rval;
static size_t rcap, rn;

static uint64_t mix(uint64_t h, const char *s, size_t n) {
    for (size_t i = 0; i < n; i++) {
        h ^= (unsigned char)s[i];
        h *= 1099511628211ULL;
    }
    return h;
}

static uint64_t ghash(const char *r, const char *p) {
    uint64_t h = 1469598103934665603ULL;
    h = mix(h, r, strlen(r));
    h ^= 124;
    h *= 1099511628211ULL;
    return mix(h, p, strlen(p));
}

static uint64_t rhash(const char *r) {
    return mix(1469598103934665603ULL, r, strlen(r));
}

static void ggrow(size_t nc) {
    GKey *nk = calloc(nc, sizeof(GKey));
    GVal *nv = calloc(nc, sizeof(GVal));
    for (size_t i = 0; i < gcap; i++) {
        if (!gk[i].region[0]) continue;
        size_t pos = ghash(gk[i].region, gk[i].product) & (nc - 1);
        while (nk[pos].region[0]) pos = (pos + 1) & (nc - 1);
        nk[pos] = gk[i];
        nv[pos] = gv[i];
    }
    free(gk);
    free(gv);
    gk = nk;
    gv = nv;
    gcap = nc;
}

static size_t gfind(const char *r, const char *p, int *found) {
    if (gcap == 0 || (gn + 1) * 2 >= gcap) ggrow(gcap ? gcap * 2 : 1024);
    size_t pos = ghash(r, p) & (gcap - 1);
    while (gk[pos].region[0]) {
        if (strcmp(gk[pos].region, r) == 0 && strcmp(gk[pos].product, p) == 0) {
            *found = 1;
            return pos;
        }
        pos = (pos + 1) & (gcap - 1);
    }
    *found = 0;
    return pos;
}

static void rgrow(size_t nc) {
    char (*nk)[17] = calloc(nc, sizeof(*nk));
    int64_t *nv = calloc(nc, sizeof(int64_t));
    for (size_t i = 0; i < rcap; i++) {
        if (!rkey[i][0]) continue;
        size_t pos = rhash(rkey[i]) & (nc - 1);
        while (nk[pos][0]) pos = (pos + 1) & (nc - 1);
        strcpy(nk[pos], rkey[i]);
        nv[pos] = rval[i];
    }
    free(rkey);
    free(rval);
    rkey = nk;
    rval = nv;
    rcap = nc;
}

static size_t rfind(const char *r, int *found) {
    if (rcap == 0 || (rn + 1) * 2 >= rcap) rgrow(rcap ? rcap * 2 : 256);
    size_t pos = rhash(r) & (rcap - 1);
    while (rkey[pos][0]) {
        if (strcmp(rkey[pos], r) == 0) {
            *found = 1;
            return pos;
        }
        pos = (pos + 1) & (rcap - 1);
    }
    *found = 0;
    return pos;
}

static int name_len(const unsigned char *s, size_t n) {
    if (n < 1 || n > 16) return 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = s[i];
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_')) return 0;
    }
    return 1;
}

static int parse_num(const unsigned char *s, size_t n, int allow_neg, int64_t *out) {
    size_t i = 0;
    int neg = 0;
    if (allow_neg && i < n && s[i] == '-') {
        neg = 1;
        i++;
    }
    if (i >= n) return 0;
    int64_t v = 0;
    for (; i < n; i++) {
        unsigned char c = s[i];
        if (c < '0' || c > '9') return 0;
        if (v <= 10000001) v = v * 10 + (c - '0');
    }
    *out = neg ? -v : v;
    return 1;
}

static void process_line(const unsigned char *l, size_t ll, long long *good, long long *bad) {
    const unsigned char *fs[4];
    size_t fl[4];
    int nf = 0;
    size_t st = 0;
    for (size_t i = 0; i <= ll; i++) {
        if (i == ll || l[i] == ',') {
            if (nf < 4) {
                fs[nf] = l + st;
                fl[nf] = i - st;
            }
            nf++;
            st = i + 1;
        }
    }
    if (nf != 4 || !name_len(fs[0], fl[0]) || !name_len(fs[1], fl[1]) || fl[2] == 0 || fl[3] == 0) {
        (*bad)++;
        return;
    }
    int64_t q, p;
    if (!parse_num(fs[2], fl[2], 1, &q) || !parse_num(fs[3], fl[3], 0, &p)) {
        (*bad)++;
        return;
    }
    if (q < -1000 || q > 1000 || p < 0 || p > 10000000) {
        (*bad)++;
        return;
    }
    char reg[17], prod[17];
    memcpy(reg, fs[0], fl[0]);
    reg[fl[0]] = 0;
    memcpy(prod, fs[1], fl[1]);
    prod[fl[1]] = 0;
    int found;
    size_t gi = gfind(reg, prod, &found);
    if (!found) {
        strcpy(gk[gi].region, reg);
        strcpy(gk[gi].product, prod);
        gv[gi].qty = 0;
        gv[gi].rev = 0;
        gn++;
    }
    int64_t rev = q * p;
    gv[gi].qty += q;
    gv[gi].rev += rev;
    size_t ri = rfind(reg, &found);
    if (!found) {
        strcpy(rkey[ri], reg);
        rval[ri] = 0;
        rn++;
    }
    rval[ri] += rev;
    (*good)++;
}

static unsigned char *read_all(size_t *len) {
    size_t cap = 1 << 20, n = 0;
    unsigned char *b = malloc(cap);
    for (;;) {
        if (n == cap) {
            cap *= 2;
            b = realloc(b, cap);
        }
        size_t r = fread(b + n, 1, cap - n, stdin);
        if (r == 0) break;
        n += r;
    }
    *len = n;
    return b;
}

static int cmp_group(const void *a, const void *b) {
    int x = *(const int *)a, y = *(const int *)b;
    if (gv[x].rev != gv[y].rev) return gv[x].rev > gv[y].rev ? -1 : 1;
    int c = strcmp(gk[x].region, gk[y].region);
    if (c) return c;
    return strcmp(gk[x].product, gk[y].product);
}

static int cmp_region(const void *a, const void *b) {
    int x = *(const int *)a, y = *(const int *)b;
    return strcmp(rkey[x], rkey[y]);
}

int main(void) {
    size_t len;
    unsigned char *data = read_all(&len);
    if (len == 0) {
        fputs("rows 0 bad 0 groups 0\ntotal 0\n", stdout);
        free(data);
        return 0;
    }
    long long good = 0, bad = 0;
    size_t pos = 0;
    int first = 1;
    while (pos < len) {
        unsigned char *nl = memchr(data + pos, '\n', len - pos);
        size_t end = nl ? (size_t)(nl - data) : len;
        if (first) first = 0;
        else process_line(data + pos, end - pos, &good, &bad);
        pos = nl ? end + 1 : len;
    }
    printf("rows %lld bad %lld groups %llu\n", good, bad, (unsigned long long)gn);
    int *idx = malloc((gn ? gn : 1) * sizeof(int));
    size_t used = 0;
    for (size_t i = 0; i < gcap; i++) if (gk[i].region[0]) idx[used++] = (int)i;
    qsort(idx, used, sizeof(int), cmp_group);
    size_t m = used < 10 ? used : 10;
    for (size_t i = 0; i < m; i++) {
        size_t j = (size_t)idx[i];
        printf("%s %s %lld %lld\n", gk[j].region, gk[j].product, (long long)gv[j].qty, (long long)gv[j].rev);
    }
    int *ridx = malloc((rn ? rn : 1) * sizeof(int));
    used = 0;
    for (size_t i = 0; i < rcap; i++) if (rkey[i][0]) ridx[used++] = (int)i;
    qsort(ridx, used, sizeof(int), cmp_region);
    int64_t total = 0;
    for (size_t i = 0; i < used; i++) {
        size_t j = (size_t)ridx[i];
        printf("region %s revenue %lld\n", rkey[j], (long long)rval[j]);
        total += rval[j];
    }
    printf("total %lld\n", (long long)total);
    free(idx);
    free(ridx);
    free(data);
    return 0;
}
