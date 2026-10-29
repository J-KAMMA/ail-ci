#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { int id; int tf; long long score; } Ent;

static char **terms; static long long *tot; static int *dfc; static int nterms, capterms;
static int *htab; static size_t hcap;

static const char *stops[] = {"an","and","are","as","at","be","but","by","for","from","had","has","have","he","her","his","in","into","is","it","its","not","of","on","or","our","she","so","than","that","the","their","them","then","there","these","they","this","to","was","we","were","which","will","with","you","your",0};

static unsigned long hs(const char *s) { unsigned long h = 1469598103934665603UL; while (*s) { h ^= (unsigned char)*s++; h *= 1099511628211UL; } return h; }

static void grow(void) {
    size_t nc = hcap ? hcap * 2 : 1024;
    int *nt = malloc(nc * sizeof(int));
    for (size_t i = 0; i < nc; i++) nt[i] = -1;
    for (int i = 0; i < nterms; i++) {
        size_t p = hs(terms[i]) & (nc - 1);
        while (nt[p] >= 0) p = (p + 1) & (nc - 1);
        nt[p] = i;
    }
    free(htab); htab = nt; hcap = nc;
}

static int intern(const char *s) {
    if ((size_t)(nterms + 1) * 2 > hcap) grow();
    size_t p = hs(s) & (hcap - 1);
    while (htab[p] >= 0) {
        if (strcmp(terms[htab[p]], s) == 0) return htab[p];
        p = (p + 1) & (hcap - 1);
    }
    if (nterms == capterms) {
        capterms = capterms ? capterms * 2 : 1024;
        terms = realloc(terms, capterms * sizeof(char *));
        tot = realloc(tot, capterms * sizeof(long long));
        dfc = realloc(dfc, capterms * sizeof(int));
    }
    { size_t sl = strlen(s) + 1; terms[nterms] = malloc(sl); memcpy(terms[nterms], s, sl); } tot[nterms] = 0; dfc[nterms] = 0;
    htab[p] = nterms;
    return nterms++;
}

static int isw(unsigned char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c >= 0x80; }

typedef struct { Ent *e; int n; } Doc;
static Doc *docs; static int ndocs, capdocs;
static int *occ; static size_t nocc, capocc;

static int cmpint(const void *a, const void *b) { int x = *(const int *)a, y = *(const int *)b; return (x > y) - (x < y); }

static void finish_doc(void) {
    qsort(occ, nocc, sizeof(int), cmpint);
    Ent *e = malloc((nocc ? nocc : 1) * sizeof(Ent));
    int n = 0;
    for (size_t i = 0; i < nocc;) {
        size_t j = i;
        while (j < nocc && occ[j] == occ[i]) j++;
        e[n].id = occ[i]; e[n].tf = (int)(j - i); e[n].score = 0; n++;
        dfc[occ[i]]++; tot[occ[i]] += (long long)(j - i);
        i = j;
    }
    if (ndocs == capdocs) { capdocs = capdocs ? capdocs * 2 : 16; docs = realloc(docs, capdocs * sizeof(Doc)); }
    docs[ndocs].e = e; docs[ndocs].n = n; ndocs++;
    nocc = 0;
}

static void add_term(const unsigned char *s, size_t len) {
    char buf[len + 8];
    size_t n = 0;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = s[i];
        if (c == '\'') continue;
        if (c >= 'A' && c <= 'Z') c += 32;
        buf[n++] = (char)c;
    }
    buf[n] = 0;
    int alld = 1;
    for (size_t i = 0; i < n; i++) if (buf[i] < '0' || buf[i] > '9') { alld = 0; break; }
    if (alld && n > 0) { n = (size_t)snprintf(buf, len + 8, "#%zu", n); }
    if (n < 2) return;
    for (int i = 0; stops[i]; i++) if (strcmp(stops[i], buf) == 0) return;
    if (n >= 5 && memcmp(buf + n - 3, "ing", 3) == 0) { n -= 3; buf[n] = 0; }
    else if (n >= 4 && buf[n - 1] == 's' && buf[n - 2] != 's') { n--; buf[n] = 0; }
    int id = intern(buf);
    if (nocc == capocc) { capocc = capocc ? capocc * 2 : 1024; occ = realloc(occ, capocc * sizeof(int)); }
    occ[nocc++] = id;
}

static void do_line(const unsigned char *l, size_t len) {
    size_t i = 0;
    while (i < len) {
        if (!isw(l[i])) { i++; continue; }
        size_t j = i + 1;
        for (;;) {
            if (j < len && isw(l[j])) { j++; continue; }
            if (j + 1 < len && (l[j] == '\'' || l[j] == '-') && isw(l[j + 1])) { j += 2; continue; }
            break;
        }
        add_term(l + i, j - i);
        i = j;
    }
}

static int cmpent(const void *a, const void *b) {
    const Ent *x = a, *y = b;
    if (x->score != y->score) return x->score > y->score ? -1 : 1;
    return strcmp(terms[x->id], terms[y->id]);
}

static int cmpall(const void *a, const void *b) {
    int x = *(const int *)a, y = *(const int *)b;
    if (tot[x] != tot[y]) return tot[x] > tot[y] ? -1 : 1;
    return strcmp(terms[x], terms[y]);
}

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    const char *a = argv[1];
    if (!*a) return 1;
    long K = 0;
    for (const char *p = a; *p; p++) {
        if (*p < '0' || *p > '9') return 1;
        if (K <= 100000) K = K * 10 + (*p - '0');
    }
    if (K < 1 || K > 1000) return 1;

    size_t cap = 1 << 16, len = 0;
    unsigned char *buf = malloc(cap);
    for (;;) {
        if (len == cap) { cap *= 2; buf = realloc(buf, cap); }
        size_t r = fread(buf + len, 1, cap - len, stdin);
        if (r == 0) break;
        len += r;
    }
    size_t pos = 0;
    while (pos < len) {
        unsigned char *nl = memchr(buf + pos, '\n', len - pos);
        size_t end = nl ? (size_t)(nl - buf) : len;
        size_t ll = end - pos;
        const unsigned char *l = buf + pos;
        if ((ll == 2 && l[0] == '%' && l[1] == '%') || (ll == 3 && l[0] == '%' && l[1] == '%' && l[2] == '\r'))
            finish_doc();
        else
            do_line(l, ll);
        pos = nl ? end + 1 : len;
    }
    finish_doc();

    long long N = ndocs;
    for (int d = 0; d < ndocs; d++) {
        Ent *e = docs[d].e;
        for (int i = 0; i < docs[d].n; i++) {
            long long tf = e[i].tf;
            e[i].score = (tf * 1000 * (N + 1)) / ((long long)dfc[e[i].id] * (tf + 2));
        }
        qsort(e, docs[d].n, sizeof(Ent), cmpent);
        printf("doc %d:", d + 1);
        int m = docs[d].n < K ? docs[d].n : (int)K;
        for (int i = 0; i < m; i++) { putchar(' '); fputs(terms[e[i].id], stdout); printf("=%lld", e[i].score); }
        putchar('\n');
    }
    int *ids = malloc((nterms ? nterms : 1) * sizeof(int));
    for (int i = 0; i < nterms; i++) ids[i] = i;
    qsort(ids, nterms, sizeof(int), cmpall);
    printf("all:");
    int m = nterms < K ? nterms : (int)K;
    for (int i = 0; i < m; i++) { putchar(' '); fputs(terms[ids[i]], stdout); printf("=%lld", tot[ids[i]]); }
    putchar('\n');
    return 0;
}
