#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef long long ll;

static int *fst, *lst, *nxt, *par, *nlen;
static unsigned *noff;
static ll *wt;
static int n = 0, cap = 0;
static char *nb;
static size_t nbl = 0, nbc = 0;
static char *ob;
static size_t obl = 0, obc = 0;

static void die(void) { exit(1); }

static void oput(const char *s, size_t l) {
    if (obl + l + 1 > obc) {
        while (obl + l + 1 > obc) obc = obc ? obc * 2 : 1 << 16;
        ob = realloc(ob, obc);
        if (!ob) die();
    }
    memcpy(ob + obl, s, l);
    obl += l;
}
static void oc(char c) { oput(&c, 1); }
static void onum(ll v) {
    char b[32];
    int l = snprintf(b, sizeof b, "%lld", v);
    oput(b, l);
}

static size_t nbadd(const char *s, size_t l) {
    if (nbl + l + 1 > nbc) {
        while (nbl + l + 1 > nbc) nbc = nbc ? nbc * 2 : 1 << 16;
        nb = realloc(nb, nbc);
        if (!nb) die();
    }
    size_t o = nbl;
    memcpy(nb + nbl, s, l);
    nbl += l;
    return o;
}

static int newnode(void) {
    if (n == cap) {
        cap = cap ? cap * 2 : 1024;
        fst = realloc(fst, cap * sizeof(int));
        lst = realloc(lst, cap * sizeof(int));
        nxt = realloc(nxt, cap * sizeof(int));
        par = realloc(par, cap * sizeof(int));
        nlen = realloc(nlen, cap * sizeof(int));
        noff = realloc(noff, cap * sizeof(unsigned));
        wt = realloc(wt, cap * sizeof(ll));
        if (!fst || !lst || !nxt || !par || !nlen || !noff || !wt) die();
    }
    fst[n] = lst[n] = nxt[n] = par[n] = -1;
    return n++;
}

static void addchild(int p, int c) {
    par[c] = p;
    nxt[c] = -1;
    if (lst[p] == -1) fst[p] = c;
    else nxt[lst[p]] = c;
    lst[p] = c;
}

static const char *nm(int v) { return nb + noff[v]; }

static int pre_next(int v, int *d) {
    if (fst[v] != -1) {
        if (d) (*d)++;
        return fst[v];
    }
    while (v != 0) {
        if (nxt[v] != -1) return nxt[v];
        v = par[v];
        if (d) (*d)--;
    }
    return -1;
}

static int parse_tree(const char *s, size_t len) {
    size_t p = 0;
    int cur = -1;
    int started = 0;
    for (;;) {
        /* parse a node */
        size_t st = p;
        while (p < len && s[p] >= 'a' && s[p] <= 'z') p++;
        size_t l = p - st;
        if (l < 1 || l > 16) return 0;
        if (p >= len || s[p] != ':') return 0;
        p++;
        size_t ws = p;
        ll w = 0;
        while (p < len && s[p] >= '0' && s[p] <= '9') {
            w = w * 10 + (s[p] - '0');
            p++;
            if (p - ws > 7) return 0;
        }
        size_t wl = p - ws;
        if (wl < 1) return 0;
        if (wl > 1 && s[ws] == '0') return 0;
        if (w > 1000000) return 0;
        int id = newnode();
        noff[id] = (unsigned)nbadd(s + st, l);
        nlen[id] = (int)l;
        wt[id] = w;
        if (cur != -1) addchild(cur, id);
        else if (started) return 0;
        started = 1;
        if (p < len && s[p] == '[') {
            p++;
            cur = id;
            continue;
        }
        for (;;) {
            if (p >= len) return cur == -1;
            if (s[p] == ' ') {
                if (cur == -1) return 0;
                p++;
                break;
            }
            if (s[p] == ']') {
                if (cur == -1) return 0;
                p++;
                cur = par[cur];
                continue;
            }
            return 0;
        }
    }
}

typedef struct { int type; ll num; const char *s; size_t sl; } Op;
enum { TOTAL, STATS, LEVEL, FIND, PRINT, PRUNE, SORT, MIRROR, FOLD, CUT };

static int parse_num(const char *s, size_t l, ll *out) {
    if (l < 1 || l > 16) return 0;
    if (l > 1 && s[0] == '0') return 0;
    ll v = 0;
    for (size_t i = 0; i < l; i++) {
        if (s[i] < '0' || s[i] > '9') return 0;
        v = v * 10 + (s[i] - '0');
    }
    if (v > 1000000000000000LL) return 0;
    *out = v;
    return 1;
}

static int parse_op(const char *s, size_t l, Op *op) {
#define KW(k) (l == sizeof(k) - 1 && memcmp(s, k, l) == 0)
#define KWA(k) (l > sizeof(k) && memcmp(s, k " ", sizeof(k)) == 0)
    op->s = NULL; op->sl = 0; op->num = 0;
    if (KW("total")) { op->type = TOTAL; return 1; }
    if (KW("stats")) { op->type = STATS; return 1; }
    if (KW("print")) { op->type = PRINT; return 1; }
    if (KW("sort")) { op->type = SORT; return 1; }
    if (KW("mirror")) { op->type = MIRROR; return 1; }
    if (KW("fold")) { op->type = FOLD; return 1; }
    if (KWA("level")) { op->type = LEVEL; return parse_num(s + 6, l - 6, &op->num); }
    if (KWA("prune")) { op->type = PRUNE; return parse_num(s + 6, l - 6, &op->num); }
    if (KWA("find") || KWA("cut")) {
        int f = KWA("find");
        size_t o = f ? 5 : 4;
        op->type = f ? FIND : CUT;
        op->s = s + o;
        op->sl = l - o;
        if (op->sl < 1) return 0;
        for (size_t i = 0; i < op->sl; i++)
            if (!((op->s[i] >= 'a' && op->s[i] <= 'z') || op->s[i] == '+')) return 0;
        return 1;
    }
    return 0;
}

static int findname(const char *s, size_t sl) {
    int d = 0;
    for (int v = 0; v != -1; v = pre_next(v, &d))
        if ((size_t)nlen[v] == sl && memcmp(nm(v), s, sl) == 0) return v;
    return -1;
}

static int *ord;
static ll *sub;
static void compute_sub(void) {
    int m = 0;
    for (int v = 0; v != -1; v = pre_next(v, NULL)) ord[m++] = v;
    for (int i = 0; i < m; i++) sub[ord[i]] = wt[ord[i]];
    for (int i = m - 1; i > 0; i--) sub[par[ord[i]]] += sub[ord[i]];
}

typedef struct { int id, idx; } Pr;
static int cmp(const void *a, const void *b) {
    const Pr *x = a, *y = b;
    if (sub[x->id] != sub[y->id]) return sub[x->id] > sub[y->id] ? -1 : 1;
    int lx = nlen[x->id], ly = nlen[y->id];
    int r = memcmp(nm(x->id), nm(y->id), lx < ly ? lx : ly);
    if (r) return r;
    if (lx != ly) return lx < ly ? -1 : 1;
    return x->idx - y->idx;
}

int main(void) {
    size_t cp = 1 << 20, len = 0;
    char *in = malloc(cp);
    if (!in) die();
    for (;;) {
        if (len == cp) { cp *= 2; in = realloc(in, cp); if (!in) die(); }
        size_t r = fread(in + len, 1, cp - len, stdin);
        if (r == 0) break;
        len += r;
    }
    if (len == 0) return 1;
    if (in[len - 1] == '\n') len--;
    /* split lines */
    size_t nl = 1;
    for (size_t i = 0; i < len; i++) {
        if (in[i] == '\r') return 1;
        if (in[i] == '\n') nl++;
    }
    Op *ops = malloc(sizeof(Op) * nl);
    size_t nops = 0;
    size_t ls = 0;
    int first = 1;
    for (size_t i = 0; i <= len; i++) {
        if (i == len || in[i] == '\n') {
            size_t l = i - ls;
            if (l == 0) return 1;
            if (first) {
                if (!parse_tree(in + ls, l)) return 1;
                first = 0;
            } else {
                if (!parse_op(in + ls, l, &ops[nops])) return 1;
                nops++;
            }
            ls = i + 1;
        }
    }
    ord = malloc(sizeof(int) * n);
    sub = malloc(sizeof(ll) * n);
    Pr *tmp = malloc(sizeof(Pr) * n);
    if (!ord || !sub || !tmp) die();

    for (size_t oi = 0; oi < nops; oi++) {
        Op *op = &ops[oi];
        switch (op->type) {
        case TOTAL: {
            ll t = 0;
            for (int v = 0; v != -1; v = pre_next(v, NULL)) t += wt[v];
            onum(t); oc('\n');
            break;
        }
        case STATS: {
            ll cnt = 0, leaves = 0, widest = 0;
            int d = 0, h = 0;
            for (int v = 0; v != -1; v = pre_next(v, &d)) {
                cnt++;
                if (d > h) h = d;
                if (fst[v] == -1) leaves++;
                else {
                    ll k = 0;
                    for (int c = fst[v]; c != -1; c = nxt[c]) k++;
                    if (k > widest) widest = k;
                }
            }
            oput("nodes=", 6); onum(cnt);
            oput(" leaves=", 8); onum(leaves);
            oput(" height=", 8); onum(h);
            oput(" widest=", 8); onum(widest);
            oc('\n');
            break;
        }
        case LEVEL: {
            ll c = 0, s = 0;
            int d = 0;
            for (int v = 0; v != -1; v = pre_next(v, &d))
                if (d == op->num) { c++; s += wt[v]; }
            onum(c); oc(' '); onum(s); oc('\n');
            break;
        }
        case FIND: {
            int v = findname(op->s, op->sl);
            if (v == -1) { oput("none\n", 5); break; }
            int k = 0;
            for (int u = v; u != -1; u = par[u]) ord[k++] = u;
            for (int i = k - 1; i >= 0; i--) {
                oput(nm(ord[i]), nlen[ord[i]]);
                if (i) oc('/');
            }
            oc('\n');
            break;
        }
        case PRINT: {
            int cur = 0;
            for (;;) {
                oput(nm(cur), nlen[cur]); oc(':'); onum(wt[cur]);
                if (fst[cur] != -1) { oc('['); cur = fst[cur]; continue; }
                int done = 0;
                for (;;) {
                    if (cur == 0) { done = 1; break; }
                    if (nxt[cur] != -1) { oc(' '); cur = nxt[cur]; break; }
                    cur = par[cur];
                    oc(']');
                }
                if (done) break;
            }
            oc('\n');
            break;
        }
        case PRUNE: {
            compute_sub();
            for (int v = 0; v != -1; v = pre_next(v, NULL)) {
                int c = fst[v];
                fst[v] = lst[v] = -1;
                while (c != -1) {
                    int nc = nxt[c];
                    if (sub[c] >= op->num) addchild(v, c);
                    c = nc;
                }
            }
            break;
        }
        case SORT: {
            compute_sub();
            for (int v = 0; v != -1; v = pre_next(v, NULL)) {
                int k = 0;
                for (int c = fst[v]; c != -1; c = nxt[c]) { tmp[k].id = c; tmp[k].idx = k; k++; }
                if (k > 1) {
                    qsort(tmp, k, sizeof(Pr), cmp);
                    fst[v] = lst[v] = -1;
                    for (int i = 0; i < k; i++) addchild(v, tmp[i].id);
                }
            }
            break;
        }
        case MIRROR: {
            for (int v = 0; v != -1; v = pre_next(v, NULL)) {
                int c = fst[v], prev = -1;
                if (c == -1 || nxt[c] == -1) continue;
                lst[v] = c;
                while (c != -1) {
                    int nc = nxt[c];
                    nxt[c] = prev;
                    prev = c;
                    c = nc;
                }
                fst[v] = prev;
            }
            break;
        }
        case FOLD: {
            int v = 0;
            while (v != -1) {
                int p = par[v];
                if (v != 0 && fst[v] != -1 && nxt[fst[v]] == -1 &&
                    (p == 0 || fst[p] != lst[p])) {
                    /* v starts a chain (parent root or parent has != 1 child) */
                    size_t tl = nlen[v];
                    int u = v;
                    while (fst[u] != -1 && nxt[fst[u]] == -1) {
                        u = fst[u];
                        tl += 1 + nlen[u];
                    }
                    char *buf = malloc(tl + 1);
                    if (!buf) die();
                    size_t o = 0;
                    ll w = 0;
                    int x = v;
                    for (;;) {
                        memcpy(buf + o, nm(x), nlen[x]);
                        o += nlen[x];
                        w += wt[x];
                        if (x == u) break;
                        buf[o++] = '+';
                        x = fst[x];
                    }
                    noff[v] = (unsigned)nbadd(buf, tl);
                    free(buf);
                    nlen[v] = (int)tl;
                    wt[v] = w;
                    fst[v] = fst[u];
                    lst[v] = lst[u];
                    for (int c = fst[v]; c != -1; c = nxt[c]) par[c] = v;
                }
                v = pre_next(v, NULL);
            }
            break;
        }
        case CUT: {
            int v = findname(op->s, op->sl);
            if (v == -1 || v == 0) break;
            int p = par[v], prev = -1;
            for (int c = fst[p]; c != v; c = nxt[c]) prev = c;
            int a = fst[v], b = lst[v];
            int after = nxt[v];
            if (a == -1) {
                if (prev == -1) fst[p] = after; else nxt[prev] = after;
                if (after == -1) lst[p] = prev;
            } else {
                for (int c = a; c != -1; c = nxt[c]) par[c] = p;
                if (prev == -1) fst[p] = a; else nxt[prev] = a;
                nxt[b] = after;
                if (after == -1) lst[p] = b;
            }
            break;
        }
        }
    }
    fwrite(ob, 1, obl, stdout);
    return 0;
}
