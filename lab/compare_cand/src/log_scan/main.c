#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct {
    uint32_t ip;
    int hour;
    int status;
    int64_t nbytes;
    const unsigned char *path;
    int path_len;
} Parsed;

typedef struct {
    char key[65];
    int len;
    int64_t count;
    int64_t bytes;
    int used;
} PEnt;

typedef struct {
    uint32_t ip;
    int used;
} IEnt;

static PEnt *ptab;
static size_t pcap, pn;
static IEnt *itab;
static size_t icap, in;

static int two(const unsigned char *s, size_t n, size_t i, int lo, int hi, int *out) {
    if (i + 2 > n) return 0;
    int a = s[i] - '0';
    int b = s[i + 1] - '0';
    if (a < 0 || a > 9 || b < 0 || b > 9) return 0;
    int v = a * 10 + b;
    if (v < lo || v > hi) return 0;
    *out = v;
    return 1;
}

static int month_ok(const unsigned char *s, size_t n, size_t i) {
    if (i + 3 > n) return 0;
    unsigned v = ((unsigned)s[i] << 16) | ((unsigned)s[i + 1] << 8) | (unsigned)s[i + 2];
    switch (v) {
        case 0x4A616E: case 0x466562: case 0x4D6172: case 0x417072:
        case 0x4D6179: case 0x4A756E: case 0x4A756C: case 0x417567:
        case 0x536570: case 0x4F6374: case 0x4E6F76: case 0x446563:
            return 1;
        default:
            return 0;
    }
}

static int method_ok(const unsigned char *s, size_t a, size_t b) {
    size_t n = b - a;
    if (n == 3) {
        if (s[a] == 'G' && s[a + 1] == 'E' && s[a + 2] == 'T') return 1;
        if (s[a] == 'P' && s[a + 1] == 'U' && s[a + 2] == 'T') return 1;
        return 0;
    }
    if (n == 4) {
        return s[a] == 'P' && s[a + 1] == 'O' && s[a + 2] == 'S' && s[a + 3] == 'T';
    }
    if (n == 6) {
        return s[a] == 'D' && s[a + 1] == 'E' && s[a + 2] == 'L'
            && s[a + 3] == 'E' && s[a + 4] == 'T' && s[a + 5] == 'E';
    }
    return 0;
}

static int path_ok(const unsigned char *s, size_t a, size_t b) {
    size_t n = b - a;
    if (n < 1 || n > 64 || s[a] != '/') return 0;
    for (size_t i = a; i < b; i++) {
        unsigned char c = s[i];
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) continue;
        if (c == '/' || c == '.' || c == '_' || c == '-') continue;
        return 0;
    }
    return 1;
}

static int parse_line(const unsigned char *l, size_t n, Parsed *p) {
    size_t i = 0;
    uint32_t ip = 0;
    for (int k = 0; k < 4; k++) {
        if (k) {
            if (i >= n || l[i] != '.') return 0;
            i++;
        }
        size_t start = i;
        unsigned v = 0;
        while (i < n && i - start < 3 && l[i] >= '0' && l[i] <= '9') {
            v = v * 10 + (unsigned)(l[i] - '0');
            i++;
        }
        if (i == start || v > 255) return 0;
        ip = (ip << 8) | v;
    }
    if (i + 6 > n) return 0;
    if (!(l[i] == ' ' && l[i + 1] == '-' && l[i + 2] == ' ' && l[i + 3] == '-'
          && l[i + 4] == ' ' && l[i + 5] == '[')) return 0;
    i += 6;
    int day;
    if (!two(l, n, i, 1, 31, &day)) return 0;
    i += 2;
    if (i >= n || l[i] != '/') return 0;
    i++;
    if (!month_ok(l, n, i)) return 0;
    i += 3;
    if (i >= n || l[i] != '/') return 0;
    i++;
    if (i + 4 > n) return 0;
    for (int k = 0; k < 4; k++) {
        if (l[i + k] < '0' || l[i + k] > '9') return 0;
    }
    i += 4;
    if (i >= n || l[i] != ':') return 0;
    i++;
    int hh;
    if (!two(l, n, i, 0, 23, &hh)) return 0;
    i += 2;
    if (i >= n || l[i] != ':') return 0;
    i++;
    if (!two(l, n, i, 0, 59, &day)) return 0;
    i += 2;
    if (i >= n || l[i] != ':') return 0;
    i++;
    if (!two(l, n, i, 0, 59, &day)) return 0;
    i += 2;
    if (i + 7 > n) return 0;
    if (!(l[i] == ' ' && l[i + 1] == '+' && l[i + 2] == '0' && l[i + 3] == '0'
          && l[i + 4] == '0' && l[i + 5] == '0' && l[i + 6] == ']')) return 0;
    i += 7;
    if (i >= n || l[i] != ' ') return 0;
    i++;
    if (i >= n || l[i] != '"') return 0;
    i++;
    size_t ms = i;
    while (i < n && l[i] != ' ') i++;
    if (i >= n || !method_ok(l, ms, i)) return 0;
    i++;
    size_t ps = i;
    while (i < n && l[i] != ' ') i++;
    if (i >= n || !path_ok(l, ps, i)) return 0;
    size_t pe = i;
    i++;
    if (i + 8 > n) return 0;
    if (!(l[i] == 'H' && l[i + 1] == 'T' && l[i + 2] == 'T' && l[i + 3] == 'P'
          && l[i + 4] == '/' && l[i + 5] == '1' && l[i + 6] == '.' && l[i + 7] == '1')) return 0;
    i += 8;
    if (i >= n || l[i] != '"') return 0;
    i++;
    if (i >= n || l[i] != ' ') return 0;
    i++;
    if (i + 3 > n) return 0;
    int s0 = l[i] - '0';
    int s1 = l[i + 1] - '0';
    int s2 = l[i + 2] - '0';
    if (s0 < 0 || s0 > 9 || s1 < 0 || s1 > 9 || s2 < 0 || s2 > 9) return 0;
    int status = s0 * 100 + s1 * 10 + s2;
    if (status < 100 || status > 599) return 0;
    i += 3;
    if (i >= n || l[i] != ' ') return 0;
    i++;
    if (i >= n) return 0;
    int64_t nb = 0;
    if (l[i] == '-') {
        if (i + 1 != n) return 0;
    } else {
        if (l[i] < '0' || l[i] > '9') return 0;
        while (i < n) {
            unsigned char c = l[i];
            if (c < '0' || c > '9') return 0;
            nb = nb * 10 + (int64_t)(c - '0');
            if (nb > 1000000000000LL) return 0;
            i++;
        }
    }
    p->ip = ip;
    p->hour = hh;
    p->status = status;
    p->nbytes = nb;
    p->path = l + ps;
    p->path_len = (int)(pe - ps);
    return 1;
}

static uint64_t phash(const unsigned char *s, int n) {
    uint64_t h = 1469598103934665603ULL;
    for (int i = 0; i < n; i++) {
        h ^= (unsigned char)s[i];
        h *= 1099511628211ULL;
    }
    return h;
}

static void pgrow(void) {
    size_t nc = pcap ? pcap * 2 : 1024;
    PEnt *nt = calloc(nc, sizeof(PEnt));
    for (size_t i = 0; i < pcap; i++) {
        if (!ptab[i].used) continue;
        size_t pos = phash((const unsigned char *)ptab[i].key, ptab[i].len) & (nc - 1);
        while (nt[pos].used) pos = (pos + 1) & (nc - 1);
        nt[pos] = ptab[i];
    }
    free(ptab);
    ptab = nt;
    pcap = nc;
}

static PEnt *pfind(const unsigned char *s, int n) {
    if (pcap == 0 || (pn + 1) * 2 >= pcap) pgrow();
    size_t pos = phash(s, n) & (pcap - 1);
    while (ptab[pos].used) {
        if (ptab[pos].len == n && memcmp(ptab[pos].key, s, n) == 0) return &ptab[pos];
        pos = (pos + 1) & (pcap - 1);
    }
    ptab[pos].used = 1;
    ptab[pos].len = n;
    memcpy(ptab[pos].key, s, (size_t)n);
    ptab[pos].key[n] = 0;
    ptab[pos].count = 0;
    ptab[pos].bytes = 0;
    pn++;
    return &ptab[pos];
}

static void igrow(void) {
    size_t nc = icap ? icap * 2 : 256;
    IEnt *nt = calloc(nc, sizeof(IEnt));
    for (size_t i = 0; i < icap; i++) {
        if (!itab[i].used) continue;
        size_t pos = (itab[i].ip * 2654435761u) & (nc - 1);
        while (nt[pos].used) pos = (pos + 1) & (nc - 1);
        nt[pos] = itab[i];
    }
    free(itab);
    itab = nt;
    icap = nc;
}

static void iadd(uint32_t ip) {
    if (icap == 0 || (in + 1) * 2 >= icap) igrow();
    size_t pos = (ip * 2654435761u) & (icap - 1);
    while (itab[pos].used) {
        if (itab[pos].ip == ip) return;
        pos = (pos + 1) & (icap - 1);
    }
    itab[pos].used = 1;
    itab[pos].ip = ip;
    in++;
}

static int cmp_path(const void *a, const void *b) {
    const PEnt *x = *(const PEnt *const *)a;
    const PEnt *y = *(const PEnt *const *)b;
    if (x->count != y->count) return x->count > y->count ? -1 : 1;
    return strcmp(x->key, y->key);
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

int main(void) {
    size_t len;
    unsigned char *data = read_all(&len);
    if (len == 0) {
        fputs("lines 0 bad 0\nstatus 2xx 0 3xx 0 4xx 0 5xx 0\nbytes 0\nips 0\n", stdout);
        free(data);
        return 0;
    }
    int64_t good = 0, bad = 0, total = 0;
    int64_t scount[6] = {0, 0, 0, 0, 0, 0};
    int64_t hcount[24] = {0};
    int64_t hbytes[24] = {0};
    size_t pos = 0;
    Parsed p;
    while (pos < len) {
        size_t e = pos;
        while (e < len && data[e] != '\n') e++;
        if (parse_line(data + pos, e - pos, &p)) {
            good++;
            total += p.nbytes;
            int cls = p.status / 100;
            if (cls >= 2 && cls <= 5) scount[cls]++;
            hcount[p.hour]++;
            hbytes[p.hour] += p.nbytes;
            PEnt *pe = pfind(p.path, p.path_len);
            pe->count++;
            pe->bytes += p.nbytes;
            iadd(p.ip);
        } else {
            bad++;
        }
        pos = e + 1;
    }
    printf("lines %lld bad %lld\n", (long long)good, (long long)bad);
    printf("status 2xx %lld 3xx %lld 4xx %lld 5xx %lld\n",
           (long long)scount[2], (long long)scount[3], (long long)scount[4], (long long)scount[5]);
    printf("bytes %lld\n", (long long)total);
    for (int h = 0; h < 24; h++) {
        if (hcount[h]) printf("hour %02d %lld %lld\n", h, (long long)hcount[h], (long long)hbytes[h]);
    }
    PEnt **arr = malloc((pn ? pn : 1) * sizeof(PEnt *));
    size_t used = 0;
    for (size_t i = 0; i < pcap; i++) {
        if (ptab[i].used) arr[used++] = &ptab[i];
    }
    qsort(arr, used, sizeof(PEnt *), cmp_path);
    size_t m = used < 10 ? used : 10;
    for (size_t i = 0; i < m; i++) {
        printf("path %s %lld %lld\n", arr[i]->key, (long long)arr[i]->count, (long long)arr[i]->bytes);
    }
    printf("ips %llu\n", (unsigned long long)in);
    free(arr);
    free(data);
    free(ptab);
    free(itab);
    return 0;
}
