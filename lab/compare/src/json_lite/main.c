#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char *s; size_t i, n; long long total; } Parser;

static void skip_ws(Parser *p) {
    while (p->i < p->n) {
        char c = p->s[p->i];
        if (c == ' ' || c == '\t' || c == '\r' || c == '\n') p->i++;
        else break;
    }
}

static void skip_string(Parser *p) {
    p->i++;
    while (p->i < p->n) {
        if (p->s[p->i] == '\\') p->i += 2;
        else if (p->s[p->i] == '"') { p->i++; return; }
        else p->i++;
    }
}

static void parse_value(Parser *p) {
    skip_ws(p);
    if (p->i >= p->n) return;
    char c = p->s[p->i];
    if (c == '{') {
        p->i++;
        skip_ws(p);
        if (p->i < p->n && p->s[p->i] == '}') { p->i++; return; }
        for (;;) {
            skip_ws(p);
            if (p->i >= p->n) return;
            skip_string(p);
            skip_ws(p);
            if (p->i < p->n && p->s[p->i] == ':') p->i++;
            parse_value(p);
            skip_ws(p);
            if (p->i < p->n && p->s[p->i] == ',') { p->i++; continue; }
            if (p->i < p->n && p->s[p->i] == '}') p->i++;
            return;
        }
    }
    if (c == '[') {
        p->i++;
        skip_ws(p);
        if (p->i < p->n && p->s[p->i] == ']') { p->i++; return; }
        for (;;) {
            skip_ws(p);
            if (p->i < p->n && p->s[p->i] == ']') { p->i++; return; }
            if (p->i >= p->n) return;
            parse_value(p);
            skip_ws(p);
            if (p->i < p->n && p->s[p->i] == ',') { p->i++; continue; }
            if (p->i < p->n && p->s[p->i] == ']') p->i++;
            return;
        }
    }
    if (c == '"') { skip_string(p); return; }
    if (c == '-' || (c >= '0' && c <= '9')) {
        size_t start = p->i;
        if (p->s[p->i] == '-') p->i++;
        while (p->i < p->n && p->s[p->i] >= '0' && p->s[p->i] <= '9') p->i++;
        char tmp[64];
        size_t len = p->i - start;
        if (len >= sizeof tmp) len = sizeof tmp - 1;
        memcpy(tmp, p->s + start, len);
        tmp[len] = '\0';
        p->total += strtoll(tmp, NULL, 10);
        return;
    }
    if (p->i + 4 <= p->n && strncmp(p->s + p->i, "true", 4) == 0) { p->i += 4; return; }
    if (p->i + 5 <= p->n && strncmp(p->s + p->i, "false", 5) == 0) { p->i += 5; return; }
    if (p->i + 4 <= p->n && strncmp(p->s + p->i, "null", 4) == 0) { p->i += 4; return; }
    p->i++;
}

static char *read_all(size_t *len) {
    size_t cap = 1 << 20, n = 0;
    char *buf = malloc(cap + 1);
    if (!buf) return NULL;
    for (;;) {
        if (n == cap) {
            cap *= 2;
            char *next = realloc(buf, cap + 1);
            if (!next) { free(buf); return NULL; }
            buf = next;
        }
        size_t r = fread(buf + n, 1, cap - n, stdin);
        if (r == 0) break;
        n += r;
    }
    buf[n] = '\0';
    *len = n;
    return buf;
}

int main(void) {
    size_t len;
    char *data = read_all(&len);
    if (!data) return 1;
    Parser p = {data, 0, len, 0};
    while (p.i < p.n) {
        parse_value(&p);
        skip_ws(&p);
        if (p.i >= p.n) break;
        if (p.i < p.n && p.s[p.i] == '\0') break;
    }
    printf("%lld\n", p.total);
    free(data);
    return 0;
}
