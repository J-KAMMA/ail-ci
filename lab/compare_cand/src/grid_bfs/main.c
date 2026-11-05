#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define OPEN 46
#define WALL 35

static int next_line(const unsigned char **pp, const unsigned char *end,
                     const unsigned char **start, size_t *len) {
    const unsigned char *p = *pp;
    if (p >= end) return 0;
    const unsigned char *st = p;
    while (p < end && *p != '\n') p++;
    *start = st;
    *len = (size_t)(p - st);
    if (p < end) p++;
    *pp = p;
    return 1;
}

static int parse_uint(const unsigned char *s, size_t n, size_t *ip, long long *out) {
    size_t i = *ip;
    if (i >= n) return 0;
    unsigned c = s[i];
    if (c < '0' || c > '9') return 0;
    long long v = 0;
    while (i < n) {
        c = s[i];
        if (c < '0' || c > '9') break;
        v = v * 10 + (long long)(c - '0');
        if (v > 100000000LL) return 0;
        i++;
    }
    *ip = i;
    *out = v;
    return 1;
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
    size_t len = 0;
    unsigned char *data = read_all(&len);
    const unsigned char *p = data;
    const unsigned char *end = data + len;
    const unsigned char *line;
    size_t llen;

    if (!next_line(&p, end, &line, &llen)) return 2;
    size_t idx = 0;
    long long H, W, Q;
    if (!parse_uint(line, llen, &idx, &H)) return 2;
    if (idx >= llen || line[idx] != ' ') return 2;
    idx++;
    if (!parse_uint(line, llen, &idx, &W)) return 2;
    if (idx >= llen || line[idx] != ' ') return 2;
    idx++;
    if (!parse_uint(line, llen, &idx, &Q)) return 2;
    if (idx != llen) return 2;
    if (H < 1 || H > 2000 || W < 1 || W > 2000 || Q < 0 || Q > 20) return 2;

    int n = (int)(H * W);
    unsigned char *grid = malloc((size_t)n);
    long long r;
    for (r = 0; r < H; r++) {
        if (!next_line(&p, end, &line, &llen)) return 2;
        if (llen != (size_t)W) return 2;
        long long j;
        for (j = 0; j < W; j++) {
            if (line[j] != OPEN && line[j] != WALL) return 2;
        }
        memcpy(grid + (size_t)r * (size_t)W, line, (size_t)W);
    }

    int qs[20];
    int qt[20];
    long long k;
    for (k = 0; k < Q; k++) {
        if (!next_line(&p, end, &line, &llen)) return 2;
        idx = 0;
        long long r1, c1, r2, c2;
        if (!parse_uint(line, llen, &idx, &r1)) return 2;
        if (idx >= llen || line[idx] != ' ') return 2;
        idx++;
        if (!parse_uint(line, llen, &idx, &c1)) return 2;
        if (idx >= llen || line[idx] != ' ') return 2;
        idx++;
        if (!parse_uint(line, llen, &idx, &r2)) return 2;
        if (idx >= llen || line[idx] != ' ') return 2;
        idx++;
        if (!parse_uint(line, llen, &idx, &c2)) return 2;
        if (idx != llen) return 2;
        if (r1 < 0 || r1 >= H || c1 < 0 || c1 >= W || r2 < 0 || r2 >= H || c2 < 0 || c2 >= W) return 2;
        qs[k] = (int)(r1 * W + c1);
        qt[k] = (int)(r2 * W + c2);
    }
    if (next_line(&p, end, &line, &llen)) return 2;

    int *dist = malloc((size_t)n * sizeof(int));
    int *queue = malloc((size_t)n * sizeof(int));
    long long total = 0;
    for (k = 0; k < Q; k++) {
        int s = qs[k];
        int t = qt[k];
        if (grid[s] == WALL || grid[t] == WALL) {
            printf("dist -1 seen 0\n");
            continue;
        }
        memset(dist, 0xFF, (size_t)n * sizeof(int));
        int head = 0, tail = 1;
        queue[0] = s;
        dist[s] = 0;
        int seen = 0;
        int d = -1;
        while (head < tail) {
            int v = queue[head];
            head++;
            seen++;
            if (v == t) {
                d = dist[v];
                break;
            }
            int nd = dist[v] + 1;
            int rr = v / (int)W;
            int cc = v - rr * (int)W;
            if (rr > 0) {
                int u = v - (int)W;
                if (grid[u] == OPEN && dist[u] == -1) { dist[u] = nd; queue[tail] = u; tail++; }
            }
            if (rr + 1 < (int)H) {
                int u = v + (int)W;
                if (grid[u] == OPEN && dist[u] == -1) { dist[u] = nd; queue[tail] = u; tail++; }
            }
            if (cc > 0) {
                int u = v - 1;
                if (grid[u] == OPEN && dist[u] == -1) { dist[u] = nd; queue[tail] = u; tail++; }
            }
            if (cc + 1 < (int)W) {
                int u = v + 1;
                if (grid[u] == OPEN && dist[u] == -1) { dist[u] = nd; queue[tail] = u; tail++; }
            }
        }
        printf("dist %d seen %d\n", d, seen);
        if (d != -1) total += d;
    }
    printf("total %lld\n", total);

    free(dist);
    free(queue);
    free(grid);
    free(data);
    return 0;
}
