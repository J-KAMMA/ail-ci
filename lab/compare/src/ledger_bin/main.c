#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct { uint32_t id; int shut; int64_t bal; size_t name_off; int name_len; } Acct;
typedef struct { int op; size_t off; uint32_t a, b, c; } Rec;

static unsigned char *buf; static size_t n;

static void sterr(size_t x, const char *k) { printf("error at offset %zu: %s\n", x, k); exit(2); }

/* read var at *p; returns 0 ok */
static const char *rdvar(size_t *p, uint32_t *out) {
    uint64_t v = 0; int cnt = 0; unsigned char last = 0;
    for (;;) {
        if (*p >= n) return "truncated";
        unsigned char b = buf[(*p)++];
        v |= (uint64_t)(b & 0x7f) << (7 * cnt);
        cnt++; last = b;
        if (b & 0x80) { if (cnt == 5) return "varint"; continue; }
        break;
    }
    if (cnt >= 2 && last == 0) return "varint";
    if (v > 4294967295ULL) return "varint";
    *out = (uint32_t)v;
    return NULL;
}

static Acct *accs; static size_t na, capa;
static size_t *ht; static size_t hcap;

static size_t hfind(uint32_t id) {
    size_t h = ((uint64_t)id * 2654435761ULL) & (hcap - 1);
    while (ht[h] && accs[ht[h] - 1].id != id) h = (h + 1) & (hcap - 1);
    return h;
}
static void hgrow(void) {
    size_t nc = hcap ? hcap * 2 : 1024;
    free(ht); ht = calloc(nc, sizeof(size_t)); hcap = nc;
    for (size_t i = 0; i < na; i++) ht[hfind(accs[i].id)] = i + 1;
}
static Acct *lookup(uint32_t id) {
    if (!hcap) return NULL;
    size_t h = hfind(id);
    return ht[h] ? &accs[ht[h] - 1] : NULL;
}
static int cmp_id(const void *a, const void *b) {
    const Acct *x = a, *y = b; return (x->id > y->id) - (x->id < y->id);
}
static int cmp_top(const void *a, const void *b) {
    const Acct *x = *(Acct *const *)a, *y = *(Acct *const *)b;
    if (x->bal != y->bal) return x->bal < y->bal ? 1 : -1;
    return (x->id > y->id) - (x->id < y->id);
}

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    size_t cap = 1 << 16; buf = malloc(cap);
    for (;;) {
        if (n == cap) { cap *= 2; buf = realloc(buf, cap); }
        size_t r = fread(buf + n, 1, cap - n, f);
        n += r;
        if (r == 0) break;
    }
    if (ferror(f)) return 1;
    fclose(f);

    if (n < 6 || buf[0] != 0xC7 || buf[1] != 'L' || buf[2] != 'X' || buf[3] != 'F' || buf[4] != 2 || buf[5] > 1)
        sterr(0, "header");
    int strict = buf[5] & 1;

    Rec *recs = NULL; size_t nr = 0, capr = 0;
    size_t p = 6;
    while (p < n) {
        size_t x = p;
        int op = buf[p++];
        if (op < 1 || op > 5) sterr(x, "opcode");
        Rec r; memset(&r, 0, sizeof r); r.op = op; r.off = x;
        const char *e;
        if (op == 1) {
            if ((e = rdvar(&p, &r.a))) sterr(x, e);
            if (p >= n) sterr(x, "truncated");
            int nl = buf[p++];
            if (nl < 1 || nl > 32) sterr(x, "name");
            r.b = (uint32_t)p; r.c = 0;
            for (int i = 0; i < nl; i++) {
                if (p >= n) sterr(x, "truncated");
                unsigned char ch = buf[p++];
                if (ch < 0x21 || ch > 0x7e) sterr(x, "name");
            }
            uint32_t init;
            if ((e = rdvar(&p, &init))) sterr(x, e);
            r.c = init;
            /* name_len stored in op-specific way: recover from buf[r.b-1] */
        } else if (op == 2) {
            if ((e = rdvar(&p, &r.a))) sterr(x, e);
            if ((e = rdvar(&p, &r.b))) sterr(x, e);
            if ((e = rdvar(&p, &r.c))) sterr(x, e);
        } else if (op == 3) {
            if ((e = rdvar(&p, &r.a))) sterr(x, e);
        } else if (op == 4) {
            if ((e = rdvar(&p, &r.a))) sterr(x, e);
            if ((e = rdvar(&p, &r.b))) sterr(x, e);
        } else {
            uint32_t len;
            if ((e = rdvar(&p, &len))) sterr(x, e);
            if ((uint64_t)(n - p) < len) sterr(x, "truncated");
            p += len;
        }
        if (p >= n) sterr(x, "truncated");
        unsigned c = 0;
        for (size_t i = x; i < p; i++) c = (c * 31 + buf[i]) % 251;
        if (buf[p] != c) sterr(x, "check");
        p++;
        if (nr == capr) { capr = capr ? capr * 2 : 1024; recs = realloc(recs, capr * sizeof(Rec)); }
        recs[nr++] = r;
    }

    long long rej[5] = {0}; /* dup unknown shut self funds */
    static const char *rn[5] = {"dup", "unknown", "shut", "self", "funds"};
    for (size_t i = 0; i < nr; i++) {
        Rec *r = &recs[i];
        int rs = -1;
        if (r->op == 1) {
            if (lookup(r->a)) rs = 0;
            else {
                if (na == capa) { capa = capa ? capa * 2 : 1024; accs = realloc(accs, capa * sizeof(Acct)); }
                if ((na + 1) * 2 > hcap) { /* grow before insert */
                    hgrow();
                    while ((na + 1) * 2 > hcap) hgrow();
                }
                Acct *a = &accs[na++];
                a->id = r->a; a->shut = 0; a->bal = r->c;
                a->name_off = r->b; a->name_len = buf[r->b - 1];
                ht[hfind(a->id)] = na;
            }
        } else if (r->op == 2) {
            Acct *fa = lookup(r->a), *ta = lookup(r->b);
            if (!fa) rs = 1; else if (!ta) rs = 1;
            else if (fa->shut) rs = 2; else if (ta->shut) rs = 2;
            else if (r->a == r->b) rs = 3;
            else if ((int64_t)r->c > fa->bal) rs = 4;
            else { fa->bal -= r->c; ta->bal += r->c; }
        } else if (r->op == 3) {
            Acct *a = lookup(r->a);
            if (!a) rs = 1; else if (a->shut) rs = 2; else a->shut = 1;
        } else if (r->op == 4) {
            Acct *a = lookup(r->a);
            if (!a) rs = 1; else if (a->shut) rs = 2; else a->bal += r->b;
        }
        if (rs >= 0) {
            if (strict) { printf("rejected at offset %zu: %s\n", r->off, rn[rs]); return 3; }
            rej[rs]++;
        }
    }

    long long open = 0, shut = 0; int64_t total = 0;
    for (size_t i = 0; i < na; i++) { if (accs[i].shut) shut++; else open++; total += accs[i].bal; }
    printf("records: %zu\n", nr);
    printf("accounts: %lld open, %lld shut\n", open, shut);
    printf("rejected: dup=%lld unknown=%lld shut=%lld self=%lld funds=%lld\n", rej[0], rej[1], rej[2], rej[3], rej[4]);
    printf("total: %lld\n", (long long)total);

    Acct *top[5]; int nt = 0;
    for (size_t i = 0; i < na; i++) {
        if (accs[i].shut) continue;
        Acct *a = &accs[i];
        int pos = nt < 5 ? nt : 5;
        /* insertion into sorted top list */
        int j = pos;
        while (j > 0 && cmp_top(&top[j - 1], &a) > 0) j--;
        if (j >= 5) continue;
        int end = nt < 5 ? nt : 4;
        for (int k = end; k > j; k--) top[k] = top[k - 1];
        top[j] = a;
        if (nt < 5) nt++;
    }
    for (int i = 0; i < nt; i++) {
        printf("top: %u ", top[i]->id);
        fwrite(buf + top[i]->name_off, 1, top[i]->name_len, stdout);
        printf(" %lld\n", (long long)top[i]->bal);
    }
    qsort(accs, na, sizeof(Acct), cmp_id);
    unsigned __int128 g = 0;
    for (size_t i = 0; i < na; i++)
        g = (g * 1000003u + (unsigned __int128)accs[i].id * 7 + (unsigned __int128)(uint64_t)accs[i].bal) % 1000000007u;
    printf("digest: %llu\n", (unsigned long long)g);
    return 0;
}
