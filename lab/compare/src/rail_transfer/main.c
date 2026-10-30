#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef long long ll;
typedef struct { ll t; int b; int v; } H;

static char *buf; static size_t bp;
static ll rd(void) {
    while (buf[bp] < '0') bp++;
    ll x = 0;
    while (buf[bp] >= '0') x = x * 10 + (buf[bp++] - '0');
    return x;
}
static int cmpll(const void *a, const void *b) {
    ll x = *(const ll *)a, y = *(const ll *)b;
    return (x > y) - (x < y);
}
typedef struct { H *a; size_t n, cap; } Hp;
static inline int less(const H *a, const H *b) {
    return a->t < b->t || (a->t == b->t && a->b < b->b);
}
static void push(Hp *p, H h) {
    if (p->n + 1 >= p->cap) { p->cap *= 2; p->a = realloc(p->a, sizeof(H) * p->cap); }
    H *hp = p->a;
    size_t i = p->n++;
    while (i > 0) {
        size_t q = (i - 1) >> 1;
        if (!less(&h, &hp[q])) break;
        hp[i] = hp[q]; i = q;
    }
    hp[i] = h;
}
static H pop(Hp *p) {
    H *hp = p->a;
    H top = hp[0], x = hp[--p->n];
    size_t n = p->n, i = 0;
    for (;;) {
        size_t c = 2 * i + 1;
        if (c >= n) break;
        if (c + 1 < n && less(&hp[c + 1], &hp[c])) c++;
        if (!less(&hp[c], &x)) break;
        hp[i] = hp[c]; i = c;
    }
    if (n) hp[i] = x;
    return top;
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
    /* ensure terminator is < '0' */
    int N = (int)rd(); int M = (int)rd(); int Q = (int)rd();
    int *X = malloc(sizeof(int) * (N + 1));
    for (int i = 0; i < N; i++) X[i] = (int)rd();
    int *eu = malloc(sizeof(int) * (M + 1)), *ev = malloc(sizeof(int) * (M + 1));
    int *el = malloc(sizeof(int) * (M + 1)), *et = malloc(sizeof(int) * (M + 1));
    ll *keys = malloc(sizeof(ll) * (2 * (size_t)M + 1));
    size_t nk = 0;
    for (int i = 0; i < M; i++) {
        eu[i] = (int)rd(); ev[i] = (int)rd(); el[i] = (int)rd(); et[i] = (int)rd();
        if (eu[i] == ev[i]) continue;
        keys[nk++] = (ll)el[i] * N + eu[i];
        keys[nk++] = (ll)el[i] * N + ev[i];
    }
    qsort(keys, nk, sizeof(ll), cmpll);
    size_t K = 0;
    for (size_t i = 0; i < nk; i++) if (i == 0 || keys[i] != keys[i - 1]) keys[K++] = keys[i];
    /* line node k : station keys[k] % N */
    size_t V = (size_t)N + K;
    int *deg = calloc(V + 2, sizeof(int));
    #define FIND(key, out) do { size_t lo = 0, hi = K; while (lo < hi) { size_t m = (lo + hi) >> 1; if (keys[m] < (key)) lo = m + 1; else hi = m; } out = (int)lo; } while (0)
    int *ea = malloc(sizeof(int) * (M + 1)), *eb = malloc(sizeof(int) * (M + 1));
    for (int i = 0; i < M; i++) {
        if (eu[i] == ev[i]) { ea[i] = -1; continue; }
        int a, b;
        ll ka = (ll)el[i] * N + eu[i], kb = (ll)el[i] * N + ev[i];
        FIND(ka, a); FIND(kb, b);
        ea[i] = a; eb[i] = b;
        deg[a]++; deg[b]++;
    }
    size_t *st = malloc(sizeof(size_t) * (K + 2));
    st[0] = 0;
    for (size_t k = 0; k < K; k++) st[k + 1] = st[k] + deg[k];
    int *to = malloc(sizeof(int) * (st[K] + 1)), *w = malloc(sizeof(int) * (st[K] + 1));
    size_t *pos = malloc(sizeof(size_t) * (K + 1));
    memcpy(pos, st, sizeof(size_t) * K);
    for (int i = 0; i < M; i++) {
        if (ea[i] < 0) continue;
        to[pos[ea[i]]] = eb[i]; w[pos[ea[i]]++] = et[i];
        to[pos[eb[i]]] = ea[i]; w[pos[eb[i]]++] = et[i];
    }
    /* hub -> line nodes */
    size_t *hs = calloc(N + 2, sizeof(size_t));
    int *stn = malloc(sizeof(int) * (K + 1));
    for (size_t k = 0; k < K; k++) { stn[k] = (int)(keys[k] % N); hs[stn[k] + 1]++; }
    for (int i = 0; i < N; i++) hs[i + 1] += hs[i];
    int *hl = malloc(sizeof(int) * (K + 1));
    size_t *hpos = malloc(sizeof(size_t) * (N + 1));
    memcpy(hpos, hs, sizeof(size_t) * N);
    for (size_t k = 0; k < K; k++) hl[hpos[stn[k]]++] = (int)k;


    ll *dt[2]; int *db[2]; char *done[2]; int *touched[2]; size_t nt[2];
    Hp hh[2];
    for (int d = 0; d < 2; d++) {
        dt[d] = malloc(sizeof(ll) * V); db[d] = malloc(sizeof(int) * V);
        for (size_t i = 0; i < V; i++) dt[d][i] = -1;
        done[d] = calloc(V, 1);
        touched[d] = malloc(sizeof(int) * V);
        hh[d].cap = 1 << 16; hh[d].n = 0; hh[d].a = malloc(sizeof(H) * hh[d].cap);
    }
    const ll INF = (ll)4e18;
    ll mt; int mb;

#define MEET(d, node) do { int _o = 1 - (d); if (dt[_o][node] >= 0) { \
        ll _t = dt[d][node] + dt[_o][node]; int _b = db[d][node] + db[_o][node]; \
        if (_t < mt || (_t == mt && _b < mb)) { mt = _t; mb = _b; } } } while (0)
#define RELAX(d, node, T, B) do { ll _t = (T); int _b = (B); int _n = (node); \
        if (dt[d][_n] < 0) { touched[d][nt[d]++] = _n; } \
        if (dt[d][_n] < 0 || _t < dt[d][_n] || (_t == dt[d][_n] && _b < db[d][_n])) { \
            dt[d][_n] = _t; db[d][_n] = _b; \
            H _h = { _t, _b, _n }; push(&hh[d], _h); MEET(d, _n); } } while (0)

    for (int q = 0; q < Q; q++) {
        int S = (int)rd(), D = (int)rd();
        if (S == D) { puts("0 0"); continue; }
        nt[0] = nt[1] = 0; hh[0].n = hh[1].n = 0;
        mt = INF; mb = 0;
        RELAX(0, S, 0, 0);
        for (size_t j = hs[S]; j < hs[S + 1]; j++) RELAX(0, N + hl[j], 0, 1);
        RELAX(1, D, 0, 0);
        for (size_t j = hs[D]; j < hs[D + 1]; j++) RELAX(1, N + hl[j], 0, 0);
        while (hh[0].n && hh[1].n) {
            H *f = &hh[0].a[0], *g = &hh[1].a[0];
            if (mt != INF) {
                ll st_ = f->t + g->t; int sb = f->b + g->b;
                if (st_ > mt || (st_ == mt && sb >= mb)) break;
            }
            int d = hh[0].n <= hh[1].n ? 0 : 1;
            H h = pop(&hh[d]);
            int u = h.v;
            if (done[d][u] || h.t != dt[d][u] || h.b != db[d][u]) continue;
            done[d][u] = 1;
            if (u < N) {
                if (d == 0) {
                    ll x = X[u];
                    for (size_t j = hs[u]; j < hs[u + 1]; j++) {
                        int n = N + hl[j];
                        if (!done[0][n]) RELAX(0, n, h.t + x, h.b + 1);
                    }
                } else {
                    for (size_t j = hs[u]; j < hs[u + 1]; j++) {
                        int n = N + hl[j];
                        if (!done[1][n]) RELAX(1, n, h.t, h.b);
                    }
                }
            } else {
                int k = u - N;
                int s = stn[k];
                if (!done[d][s]) {
                    if (d == 0) RELAX(0, s, h.t, h.b);
                    else RELAX(1, s, h.t + X[s], h.b + 1);
                }
                for (size_t j = st[k]; j < st[k + 1]; j++) {
                    int n = N + to[j];
                    if (!done[d][n]) RELAX(d, n, h.t + w[j], h.b);
                }
            }
        }
        if (mt != INF) printf("%lld %d\n", mt, mb);
        else puts("none");
        for (int d = 0; d < 2; d++)
            for (size_t i = 0; i < nt[d]; i++) { dt[d][touched[d][i]] = -1; done[d][touched[d][i]] = 0; }
    }
    return 0;
}
