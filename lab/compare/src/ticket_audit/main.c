#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *p; size_t n; } F;

static void fail(long line, const char *cat, int code) {
    printf("line %ld: %s\n", line, cat);
    exit(code);
}
#define SYN(l) fail(l, "syntax", 3)
#define VAL(l) fail(l, "value", 4)

static int isdig(char c) { return c >= '0' && c <= '9'; }
static int isup(char c) { return c >= 'A' && c <= 'Z'; }
static int alldig(F f, size_t lo, size_t hi) {
    if (f.n < lo || f.n > hi) return 0;
    for (size_t i = 0; i < f.n; i++) if (!isdig(f.p[i])) return 0;
    return 1;
}

static int syn_code(F f) { return f.n == 3 && isup(f.p[0]) && isup(f.p[1]) && isup(f.p[2]); }
static int syn_name(F f) {
    if (f.n < 1 || f.n > 40) return 0;
    for (size_t i = 0; i < f.n; i++) {
        unsigned char c = f.p[i];
        if (c < 0x20 || c > 0x7e || c == '|') return 0;
    }
    return f.p[0] != ' ' && f.p[f.n - 1] != ' ';
}
static int syn_event(F f) { return alldig(f, 6, 6); }
static int syn_date(F f) {
    if (f.n != 10) return 0;
    for (int i = 0; i < 10; i++) {
        if (i == 4 || i == 7) { if (f.p[i] != '-') return 0; }
        else if (!isdig(f.p[i])) return 0;
    }
    return 1;
}
static int syn_time(F f) {
    return f.n == 5 && isdig(f.p[0]) && isdig(f.p[1]) && f.p[2] == ':' && isdig(f.p[3]) && isdig(f.p[4]);
}
static int syn_price(F f) {
    if (f.n < 4 || f.n > 7) return 0;
    size_t d = f.n - 3;
    if (f.p[d] != '.') return 0;
    for (size_t i = 0; i < d; i++) if (!isdig(f.p[i])) return 0;
    return isdig(f.p[d + 1]) && isdig(f.p[d + 2]);
}
static int syn_seat(F f) {
    if (f.n < 2 || f.n > 4 || !isup(f.p[0])) return 0;
    for (size_t i = 1; i < f.n; i++) if (!isdig(f.p[i])) return 0;
    return 1;
}
static int syn_buyer(F f) {
    if (f.n < 4 || f.n > 12) return 0;
    if (!(f.p[0] >= 'a' && f.p[0] <= 'z')) return 0;
    for (size_t i = 1; i < f.n; i++) {
        char c = f.p[i];
        if (!((c >= 'a' && c <= 'z') || isdig(c))) return 0;
    }
    return 1;
}

static long long num(F f) {
    long long v = 0;
    for (size_t i = 0; i < f.n; i++) v = v * 10 + (f.p[i] - '0');
    return v;
}
static int val_event(F f) {
    int d[6];
    for (int i = 0; i < 6; i++) d[i] = f.p[i] - '0';
    return (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0;
}
static int val_date(F f) {
    int y = (f.p[0] - '0') * 1000 + (f.p[1] - '0') * 100 + (f.p[2] - '0') * 10 + (f.p[3] - '0');
    int m = (f.p[5] - '0') * 10 + (f.p[6] - '0');
    int d = (f.p[8] - '0') * 10 + (f.p[9] - '0');
    if (y < 2000 || y > 2099 || m < 1 || m > 12 || d < 1) return 0;
    static const int dm[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int ld = dm[m - 1];
    if (m == 2 && y % 4 == 0) ld = 29;
    return d <= ld;
}
static int val_time(F f) {
    int h = (f.p[0] - '0') * 10 + (f.p[1] - '0');
    int m = (f.p[3] - '0') * 10 + (f.p[4] - '0');
    return h <= 23 && m <= 59;
}
static int val_nolead0(F f) { return !(f.n > 1 && f.p[0] == '0'); } /* zero allowed */

static int vidx(F f) { return (f.p[0] - 'A') * 676 + (f.p[1] - 'A') * 26 + (f.p[2] - 'A'); }

#define NV 17576
#define NE 1000000
static int venue_def[NV];
static int venue_cap[NV];
static int venue_events[NV];
static int venue_sold[NV];
static long long venue_rev[NV];

static char *ev_def; /* NE */
static int *ev_venue;
static int *ev_price;
static int *ev_sold;
static unsigned char **ev_bits;

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    FILE *fp = fopen(argv[1], "rb");
    if (!fp) return 1;
    size_t cap = 1 << 16, len = 0;
    char *buf = malloc(cap);
    for (;;) {
        if (len == cap) { cap *= 2; buf = realloc(buf, cap); }
        size_t r = fread(buf + len, 1, cap - len, fp);
        if (r == 0) break;
        len += r;
    }
    fclose(fp);

    ev_def = calloc(NE, 1);
    ev_venue = calloc(NE, sizeof(int));
    ev_price = calloc(NE, sizeof(int));
    ev_sold = calloc(NE, sizeof(int));
    ev_bits = calloc(NE, sizeof(unsigned char *));

    size_t pos = 0;
    long line = 0;
    int ended = 0;
    long records = 0, nv = 0, ne = 0, ns = 0, nr = 0;
    long long revenue = 0;

    while (pos < len) {
        size_t e = pos;
        while (e < len && buf[e] != '\n') e++;
        const char *lp = buf + pos;
        size_t ln = e - pos;
        pos = e + 1;
        line++;
        if (line == 1) {
            if (!(ln == 5 && memcmp(lp, "TKT/1", 5) == 0)) fail(1, "header", 2);
            continue;
        }
        if (ended) fail(line, "summary", 8);

        F f[8];
        int nf = 0;
        size_t st = 0;
        for (size_t i = 0; i <= ln; i++) {
            if (i == ln || lp[i] == '|') {
                if (nf < 8) { f[nf].p = lp + st; f[nf].n = i - st; }
                nf++;
                st = i + 1;
            }
        }
        if (nf > 7) SYN(line);
        F t = f[0];
        #define IS(s) (t.n == strlen(s) && memcmp(t.p, s, t.n) == 0)
        if (IS("V")) {
            if (nf != 4) SYN(line);
            if (!syn_code(f[1]) || !syn_name(f[2]) || !alldig(f[3], 1, 6)) SYN(line);
            if (!val_nolead0(f[3]) || f[3].p[0] == '0') VAL(line);
            long long c = num(f[3]);
            if (c < 1 || c > 100000) VAL(line);
            int v = vidx(f[1]);
            if (venue_def[v]) fail(line, "duplicate", 6);
            venue_def[v] = 1;
            venue_cap[v] = (int)c;
            nv++; records++;
        } else if (IS("E")) {
            if (nf != 6) SYN(line);
            if (!syn_event(f[1]) || !syn_code(f[2]) || !syn_date(f[3]) || !syn_time(f[4]) || !syn_price(f[5])) SYN(line);
            if (!val_event(f[1]) || !val_date(f[3]) || !val_time(f[4])) VAL(line);
            size_t d = f[5].n - 3;
            if (d > 1 && f[5].p[0] == '0') VAL(line);
            int cents = (int)(num((F){f[5].p, d}) * 100 + (f[5].p[d + 1] - '0') * 10 + (f[5].p[d + 2] - '0'));
            if (cents % 5 != 0) VAL(line);
            int v = vidx(f[2]);
            if (!venue_def[v]) fail(line, "reference", 5);
            int ev = (int)num(f[1]);
            if (ev_def[ev]) fail(line, "duplicate", 6);
            ev_def[ev] = 1;
            ev_venue[ev] = v;
            ev_price[ev] = cents;
            venue_events[v]++;
            ne++; records++;
        } else if (IS("S") || IS("R")) {
            int isS = t.p[0] == 'S';
            if (nf != (isS ? 4 : 3)) SYN(line);
            if (!syn_event(f[1]) || !syn_seat(f[2]) || (isS && !syn_buyer(f[3]))) SYN(line);
            if (!val_event(f[1]) || f[2].p[1] == '0') VAL(line);
            int ev = (int)num(f[1]);
            int seat = (f[2].p[0] - 'A') * 1000 + (int)num((F){f[2].p + 1, f[2].n - 1});
            if (!ev_def[ev]) fail(line, "reference", 5);
            if (isS) {
                int sold = ev_bits[ev] && (ev_bits[ev][seat >> 3] >> (seat & 7) & 1);
                if (sold) fail(line, "duplicate", 6);
                if (ev_sold[ev] >= venue_cap[ev_venue[ev]]) fail(line, "capacity", 7);
                if (!ev_bits[ev]) ev_bits[ev] = calloc(26000 / 8 + 1, 1);
                ev_bits[ev][seat >> 3] |= 1 << (seat & 7);
                ev_sold[ev]++;
                revenue += ev_price[ev];
                ns++;
            } else {
                int sold = ev_bits[ev] && (ev_bits[ev][seat >> 3] >> (seat & 7) & 1);
                if (!sold) fail(line, "reference", 5);
                ev_bits[ev][seat >> 3] &= ~(1 << (seat & 7));
                ev_sold[ev]--;
                revenue -= ev_price[ev];
                nr++;
            }
            records++;
        } else if (IS("END")) {
            if (nf != 3) SYN(line);
            if (!alldig(f[1], 1, 9) || !alldig(f[2], 1, 12)) SYN(line);
            if (!val_nolead0(f[1]) || !val_nolead0(f[2])) VAL(line);
            if (num(f[1]) != records || num(f[2]) != revenue) fail(line, "summary", 8);
            ended = 1;
        } else {
            SYN(line);
        }
    }
    if (line == 0) fail(1, "header", 2);
    if (!ended) fail(line + 1, "summary", 8);

    int top[3] = {-1, -1, -1};
    for (int ev = 0; ev < NE; ev++) {
        if (!ev_def[ev]) continue;
        int v = ev_venue[ev];
        venue_sold[v] += ev_sold[ev];
        venue_rev[v] += (long long)ev_sold[ev] * ev_price[ev];
        int k = ev;
        for (int i = 0; i < 3; i++) {
            if (top[i] < 0) { top[i] = k; break; }
            if (ev_sold[k] > ev_sold[top[i]]) { int tmp = top[i]; top[i] = k; k = tmp; }
        }
    }
    printf("venues %ld events %ld sold %ld refunds %ld\n", nv, ne, ns, nr);
    printf("revenue %lld.%02lld\n", revenue / 100, revenue % 100);
    for (int v = 0; v < NV; v++) {
        if (!venue_def[v]) continue;
        printf("%c%c%c events=%d tickets=%d revenue=%lld.%02lld\n", 'A' + v / 676, 'A' + v / 26 % 26, 'A' + v % 26,
               venue_events[v], venue_sold[v], venue_rev[v] / 100, venue_rev[v] % 100);
    }
    for (int i = 0; i < 3; i++)
        if (top[i] >= 0) printf("top %06d %d\n", top[i], ev_sold[top[i]]);
    return 0;
}
