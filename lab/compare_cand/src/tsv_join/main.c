#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static int64_t *uid;
static char (*uname)[25];
static char (*uctry)[3];
static int64_t *uamt;
static int64_t *unum;
static size_t nusers, ucap_arr;

static int64_t *ukey;
static int *uval;
static size_t ucap, uhashn;

static char (*ckey)[3];
static int64_t *camt;
static int64_t *cnum;
static size_t ccap, ccount;

static int64_t good_users, good_orders, bad, unmatched;

static uint64_t hash64(uint64_t x) {
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

static uint64_t hash_country(const char *s) {
    uint64_t h = 1469598103934665603ULL;
    for (int i = 0; i < 2; i++) {
        h ^= (unsigned char)s[i];
        h *= 1099511628211ULL;
    }
    return h;
}

static void ugrow(size_t nc) {
    int64_t *nk = calloc(nc, sizeof(int64_t));
    int *nv = malloc(nc * sizeof(int));
    for (size_t i = 0; i < ucap; i++) {
        if (!ukey[i]) continue;
        size_t pos = hash64((uint64_t)ukey[i]) & (nc - 1);
        while (nk[pos]) pos = (pos + 1) & (nc - 1);
        nk[pos] = ukey[i];
        nv[pos] = uval[i];
    }
    free(ukey);
    free(uval);
    ukey = nk;
    uval = nv;
    ucap = nc;
}

static size_t ufind(int64_t id, int *found) {
    if (ucap == 0 || (uhashn + 1) * 2 >= ucap) ugrow(ucap ? ucap * 2 : 1024);
    size_t pos = hash64((uint64_t)id) & (ucap - 1);
    while (ukey[pos]) {
        if (ukey[pos] == id) {
            *found = 1;
            return pos;
        }
        pos = (pos + 1) & (ucap - 1);
    }
    *found = 0;
    return pos;
}

static void cgrow(size_t nc) {
    char (*nk)[3] = calloc(nc, sizeof(*nk));
    int64_t *na = calloc(nc, sizeof(int64_t));
    int64_t *nn = calloc(nc, sizeof(int64_t));
    for (size_t i = 0; i < ccap; i++) {
        if (!ckey[i][0]) continue;
        size_t pos = hash_country(ckey[i]) & (nc - 1);
        while (nk[pos][0]) pos = (pos + 1) & (nc - 1);
        memcpy(nk[pos], ckey[i], 3);
        na[pos] = camt[i];
        nn[pos] = cnum[i];
    }
    free(ckey);
    free(camt);
    free(cnum);
    ckey = nk;
    camt = na;
    cnum = nn;
    ccap = nc;
}

static size_t cfind(const char *cc, int *found) {
    if (ccap == 0 || (ccount + 1) * 2 >= ccap) cgrow(ccap ? ccap * 2 : 256);
    size_t pos = hash_country(cc) & (ccap - 1);
    while (ckey[pos][0]) {
        if (ckey[pos][0] == cc[0] && ckey[pos][1] == cc[1]) {
            *found = 1;
            return pos;
        }
        pos = (pos + 1) & (ccap - 1);
    }
    *found = 0;
    return pos;
}

static int name_ok(const unsigned char *s, size_t n) {
    if (n < 1 || n > 24) return 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = s[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
            || c == ' ' || c == '.' || c == '_' || c == '-') continue;
        return 0;
    }
    return 1;
}

static int country_ok(const unsigned char *s, size_t n) {
    if (n != 2) return 0;
    return s[0] >= 'A' && s[0] <= 'Z' && s[1] >= 'A' && s[1] <= 'Z';
}

static int parse_num(const unsigned char *s, size_t n, int64_t lo, int64_t hi, int64_t *out) {
    if (n == 0) return 0;
    int64_t v = 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = s[i];
        if (c < '0' || c > '9') return 0;
        if (v <= hi) v = v * 10 + (c - '0');
    }
    if (v < lo || v > hi) return 0;
    *out = v;
    return 1;
}

static int split3(const unsigned char *l, size_t ll, const unsigned char *f[3], size_t fl[3]) {
    size_t st = 0;
    int nf = 0;
    for (size_t i = 0; i <= ll; i++) {
        if (i == ll || l[i] == '\t') {
            if (nf < 3) {
                f[nf] = l + st;
                fl[nf] = i - st;
            }
            nf++;
            st = i + 1;
        }
    }
    return nf == 3;
}

static void process_user(const unsigned char *l, size_t ll) {
    const unsigned char *f[3];
    size_t fl[3];
    int64_t id;
    if (!split3(l, ll, f, fl) || !name_ok(f[1], fl[1]) || !country_ok(f[2], fl[2])
        || !parse_num(f[0], fl[0], 1, 2000000000, &id)) {
        bad++;
        return;
    }
    int found;
    size_t slot = ufind(id, &found);
    if (found) {
        bad++;
        return;
    }
    ukey[slot] = id;
    if (nusers == ucap_arr) {
        ucap_arr = ucap_arr ? ucap_arr * 2 : 1024;
        uid = realloc(uid, ucap_arr * sizeof(int64_t));
        uname = realloc(uname, ucap_arr * 25);
        uctry = realloc(uctry, ucap_arr * 3);
        uamt = realloc(uamt, ucap_arr * sizeof(int64_t));
        unum = realloc(unum, ucap_arr * sizeof(int64_t));
    }
    uval[slot] = (int)nusers;
    uid[nusers] = id;
    memcpy(uname[nusers], f[1], fl[1]);
    uname[nusers][fl[1]] = 0;
    memcpy(uctry[nusers], f[2], 2);
    uctry[nusers][2] = 0;
    uamt[nusers] = 0;
    unum[nusers] = 0;
    nusers++;
    uhashn++;
    good_users++;
}

static void process_order(const unsigned char *l, size_t ll) {
    const unsigned char *f[3];
    size_t fl[3];
    int64_t oid, id, amt;
    if (!split3(l, ll, f, fl) || !parse_num(f[0], fl[0], 1, 2000000000, &oid)
        || !parse_num(f[1], fl[1], 1, 2000000000, &id)
        || !parse_num(f[2], fl[2], 0, 100000000, &amt)) {
        bad++;
        return;
    }
    good_orders++;
    int found;
    size_t slot = ufind(id, &found);
    if (!found) {
        unmatched++;
        return;
    }
    int ui = uval[slot];
    uamt[ui] += amt;
    unum[ui] += 1;
    char cc[3];
    memcpy(cc, uctry[ui], 3);
    size_t cs = cfind(cc, &found);
    if (!found) {
        memcpy(ckey[cs], cc, 3);
        camt[cs] = 0;
        cnum[cs] = 0;
        ccount++;
    }
    camt[cs] += amt;
    cnum[cs] += 1;
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

static int cmp_country(const void *a, const void *b) {
    int x = *(const int *)a, y = *(const int *)b;
    if (camt[x] != camt[y]) return camt[x] > camt[y] ? -1 : 1;
    return strcmp(ckey[x], ckey[y]);
}

static int cmp_user(const void *a, const void *b) {
    int x = *(const int *)a, y = *(const int *)b;
    if (uamt[x] != uamt[y]) return uamt[x] > uamt[y] ? -1 : 1;
    if (uid[x] != uid[y]) return uid[x] < uid[y] ? -1 : 1;
    return 0;
}

int main(void) {
    size_t len;
    unsigned char *data = read_all(&len);
    if (len == 0) {
        fputs("users 0 orders 0 bad 0 unmatched 0\ntotal 0\n", stdout);
        free(data);
        return 0;
    }
    int sec = 0, found_users = 0, found_orders = 0;
    size_t pos = 0;
    while (pos < len) {
        unsigned char *nl = memchr(data + pos, '\n', len - pos);
        size_t end = nl ? (size_t)(nl - data) : len;
        const unsigned char *l = data + pos;
        size_t ll = end - pos;
        if (sec == 0 && ll == 6 && memcmp(l, "#users", 6) == 0) {
            sec = 1;
            found_users = 1;
        } else if (sec == 1 && ll == 7 && memcmp(l, "#orders", 7) == 0) {
            sec = 2;
            found_orders = 1;
        } else if (sec == 1) {
            process_user(l, ll);
        } else if (sec == 2) {
            process_order(l, ll);
        }
        pos = nl ? end + 1 : len;
    }
    if (!found_users || !found_orders) {
        fputs("users 0 orders 0 bad 0 unmatched 0\ntotal 0\n", stdout);
        free(data);
        return 0;
    }
    printf("users %lld orders %lld bad %lld unmatched %lld\n", (long long)good_users, (long long)good_orders,
           (long long)bad, (long long)unmatched);
    int *cidx = malloc((ccount ? ccount : 1) * sizeof(int));
    size_t used = 0;
    for (size_t i = 0; i < ccap; i++) if (ckey[i][0]) cidx[used++] = (int)i;
    qsort(cidx, used, sizeof(int), cmp_country);
    for (size_t i = 0; i < used; i++) {
        int j = cidx[i];
        printf("country %s orders %lld amount %lld\n", ckey[j], (long long)cnum[j], (long long)camt[j]);
    }
    int *uorder = malloc((nusers ? nusers : 1) * sizeof(int));
    used = 0;
    for (size_t i = 0; i < nusers; i++) if (unum[i] > 0) uorder[used++] = (int)i;
    qsort(uorder, used, sizeof(int), cmp_user);
    size_t m = used < 10 ? used : 10;
    for (size_t i = 0; i < m; i++) {
        int j = uorder[i];
        printf("user %lld %s %lld\n", (long long)uid[j], uname[j], (long long)uamt[j]);
    }
    int64_t total = 0;
    for (size_t i = 0; i < nusers; i++) total += uamt[i];
    printf("total %lld\n", (long long)total);
    free(cidx);
    free(uorder);
    free(data);
    return 0;
}
