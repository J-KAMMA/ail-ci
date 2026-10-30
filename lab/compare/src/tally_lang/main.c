#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef uint32_t u32;

enum { T_NUM, T_WORD, T_OP };
typedef struct { int type; u32 num; char s[8]; char *name; } Tok;

/* operator codes */
enum { O_MAX, O_MIN, O_EQ, O_NE, O_LT, O_GT, O_ADD, O_SUB, O_MUL, O_DIV, O_MOD, O_ROT,
       O_NEG, O_POP, O_NOT, O_LP, O_RP, O_COMMA, O_ASSIGN };

typedef struct { int type; int op; u32 num; int var; } TokB; /* unused */

typedef struct Node {
    int kind; /* 0 num, 1 var, 2 bin, 3 un */
    int op;
    u32 num;
    int var;
    struct Node *a, *b;
} Node;

typedef struct { int op_or_kw; int type; u32 num; char *name; } T;
enum { TK_NUM, TK_WORD, TK_KW, TK_OP };
enum { K_SET, K_OUT, K_LOOP, K_WHEN, K_ELSE, K_END, K_BREAK };
static const char *kwn[] = {"set", "out", "loop", "when", "else", "end", "break"};

static char **vnames; static int nvars, capvars;
static int varidx(const char *s) {
    for (int i = 0; i < nvars; i++) if (!strcmp(vnames[i], s)) return i;
    if (nvars == capvars) { capvars = capvars ? capvars * 2 : 64; vnames = realloc(vnames, capvars * sizeof(char *)); }
    vnames[nvars] = malloc(strlen(s) + 1);
    strcpy(vnames[nvars], s);
    return nvars++;
}

typedef struct {
    int kind; /* K_* */
    int line;
    int var;
    Node **exprs; int nexpr;
    int other; /* loop/when: end idx ; else: end idx */
    int elsei; /* when: else idx or -1 */
} Stmt;

static Stmt *stmts; static int nst, capst;

static T *toks; static int ntok, pos;
static int perr;

static Node *mk(int kind) { Node *n = calloc(1, sizeof(Node)); n->kind = kind; return n; }

static int isop(int op) { return pos < ntok && toks[pos].type == TK_OP && toks[pos].op_or_kw == op; }

static int depth;
static Node *p_expr(void);
static Node *p_un(void);

static Node *p_prim(void) {
    if (pos >= ntok) { perr = 1; return NULL; }
    T *t = &toks[pos];
    if (t->type == TK_NUM) { pos++; Node *n = mk(0); n->num = t->num; return n; }
    if (t->type == TK_WORD) { pos++; Node *n = mk(1); n->var = varidx(t->name); return n; }
    if (t->type == TK_OP && t->op_or_kw == O_LP) {
        pos++;
        if (++depth > 32) { perr = 1; return NULL; }
        Node *e = p_expr();
        if (perr) return NULL;
        if (!isop(O_RP)) { perr = 1; return NULL; }
        pos++; depth--;
        return e;
    }
    perr = 1; return NULL;
}

static Node *p_un(void) {
    if (pos < ntok && toks[pos].type == TK_OP) {
        int op = toks[pos].op_or_kw;
        if (op == O_SUB || op == O_POP || op == O_NOT) {
            pos++;
            Node *a = p_un();
            if (perr) return NULL;
            Node *n = mk(3); n->op = op == O_SUB ? O_NEG : op; n->a = a; return n;
        }
    }
    return p_prim();
}

static Node *p_rot(void) {
    Node *l = p_un();
    if (perr) return NULL;
    if (isop(O_ROT)) {
        pos++;
        Node *r = p_rot();
        if (perr) return NULL;
        Node *n = mk(2); n->op = O_ROT; n->a = l; n->b = r; return n;
    }
    return l;
}

static Node *p_mul(void) {
    Node *l = p_rot();
    while (!perr && pos < ntok && toks[pos].type == TK_OP &&
           (toks[pos].op_or_kw == O_MUL || toks[pos].op_or_kw == O_DIV || toks[pos].op_or_kw == O_MOD)) {
        int op = toks[pos++].op_or_kw;
        Node *r = p_rot();
        if (perr) return NULL;
        Node *n = mk(2); n->op = op; n->a = l; n->b = r; l = n;
    }
    return l;
}

static Node *p_add(void) {
    Node *l = p_mul();
    while (!perr && pos < ntok && toks[pos].type == TK_OP &&
           (toks[pos].op_or_kw == O_ADD || toks[pos].op_or_kw == O_SUB)) {
        int op = toks[pos++].op_or_kw;
        Node *r = p_mul();
        if (perr) return NULL;
        Node *n = mk(2); n->op = op; n->a = l; n->b = r; l = n;
    }
    return l;
}

static int iscmp(void) {
    if (pos >= ntok || toks[pos].type != TK_OP) return 0;
    int o = toks[pos].op_or_kw;
    return o == O_EQ || o == O_NE || o == O_LT || o == O_GT;
}

static Node *p_cmp(void) {
    Node *l = p_add();
    if (perr) return NULL;
    if (iscmp()) {
        int op = toks[pos++].op_or_kw;
        Node *r = p_add();
        if (perr) return NULL;
        Node *n = mk(2); n->op = op; n->a = l; n->b = r; l = n;
        if (iscmp()) { perr = 1; return NULL; }
    }
    return l;
}

static Node *p_expr(void) {
    Node *l = p_cmp();
    while (!perr && pos < ntok && toks[pos].type == TK_OP &&
           (toks[pos].op_or_kw == O_MAX || toks[pos].op_or_kw == O_MIN)) {
        int op = toks[pos++].op_or_kw;
        Node *r = p_cmp();
        if (perr) return NULL;
        Node *n = mk(2); n->op = op; n->a = l; n->b = r; l = n;
    }
    return l;
}

static Node *parse_full_expr(void) {
    depth = 0;
    return p_expr();
}

/* tokenize a line (comment already removed, len given). returns 0 on error */
static int tokenize(const char *s, int len) {
    ntok = 0;
    static int cap = 0;
    int i = 0;
    while (i < len) {
        char c = s[i];
        if (c == ' ' || c == '\t' || c == '\r') { i++; continue; }
        if (ntok >= cap) { cap = cap ? cap * 2 : 256; toks = realloc(toks, cap * sizeof(T)); }
        T *t = &toks[ntok];
        t->name = NULL;
        if (c >= '0' && c <= '9') {
            unsigned long long v = 0;
            while (i < len && s[i] >= '0' && s[i] <= '9') {
                v = v * 10 + (s[i] - '0');
                if (v > 4294967295ULL) return 0;
                i++;
            }
            if (i < len && ((s[i] >= 'a' && s[i] <= 'z') || s[i] == '_')) return 0;
            t->type = TK_NUM; t->num = (u32)v; ntok++; continue;
        }
        if ((c >= 'a' && c <= 'z') || c == '_') {
            int j = i;
            while (j < len && ((s[j] >= 'a' && s[j] <= 'z') || s[j] == '_' || (s[j] >= '0' && s[j] <= '9'))) j++;
            char *w = malloc(j - i + 1);
            memcpy(w, s + i, j - i); w[j - i] = 0;
            i = j;
            int kw = -1;
            for (int k = 0; k < 7; k++) if (!strcmp(w, kwn[k])) kw = k;
            if (kw >= 0) { t->type = TK_KW; t->op_or_kw = kw; free(w); }
            else { t->type = TK_WORD; t->name = w; }
            ntok++; continue;
        }
        t->type = TK_OP;
        char d = i + 1 < len ? s[i + 1] : 0;
        int op = -1, l = 1;
        if (c == '<' && d == '>') { op = O_MAX; l = 2; }
        else if (c == '>' && d == '<') { op = O_MIN; l = 2; }
        else if (c == '=' && d == '=') { op = O_EQ; l = 2; }
        else if (c == '!' && d == '=') { op = O_NE; l = 2; }
        else switch (c) {
            case '<': op = O_LT; break;
            case '>': op = O_GT; break;
            case '+': op = O_ADD; break;
            case '-': op = O_SUB; break;
            case '*': op = O_MUL; break;
            case '/': op = O_DIV; break;
            case '%': op = O_MOD; break;
            case '~': op = O_ROT; break;
            case '#': op = O_POP; break;
            case '!': op = O_NOT; break;
            case '(': op = O_LP; break;
            case ')': op = O_RP; break;
            case ',': op = O_COMMA; break;
            case '=': op = O_ASSIGN; break;
            default: return 0;
        }
        t->op_or_kw = op; i += l; ntok++;
    }
    return 1;
}

static Stmt *newst(void) {
    if (nst == capst) { capst = capst ? capst * 2 : 256; stmts = realloc(stmts, capst * sizeof(Stmt)); }
    Stmt *s = &stmts[nst++];
    memset(s, 0, sizeof *s);
    s->elsei = -1;
    return s;
}

/* returns 1 ok, 0 parse error */
static int parse_line(int lineno, int *bs, int *nb) {
    pos = 0; perr = 0;
    if (ntok == 0) return 1;
    if (toks[0].type != TK_KW) return 0;
    int kw = toks[0].op_or_kw;
    pos = 1;
    switch (kw) {
    case K_SET: {
        if (ntok < 2 || toks[1].type != TK_WORD) return 0;
        int v = varidx(toks[1].name);
        pos = 2;
        if (!isop(O_ASSIGN)) return 0;
        pos++;
        Node *e = parse_full_expr();
        if (perr || pos != ntok) return 0;
        Stmt *s = newst(); s->kind = K_SET; s->line = lineno; s->var = v;
        s->exprs = malloc(sizeof(Node *)); s->exprs[0] = e; s->nexpr = 1;
        return 1;
    }
    case K_OUT: {
        int cap = 4, n = 0;
        Node **ex = malloc(cap * sizeof(Node *));
        for (;;) {
            Node *e = parse_full_expr();
            if (perr) return 0;
            if (n == cap) { cap *= 2; ex = realloc(ex, cap * sizeof(Node *)); }
            ex[n++] = e;
            if (isop(O_COMMA)) { pos++; continue; }
            break;
        }
        if (pos != ntok) return 0;
        Stmt *s = newst(); s->kind = K_OUT; s->line = lineno; s->exprs = ex; s->nexpr = n;
        return 1;
    }
    case K_LOOP: case K_WHEN: {
        Node *e = parse_full_expr();
        if (perr || pos != ntok) return 0;
        if (*nb >= 16) return 0;
        Stmt *s = newst(); s->kind = kw; s->line = lineno;
        s->exprs = malloc(sizeof(Node *)); s->exprs[0] = e; s->nexpr = 1;
        bs[(*nb)++] = nst - 1;
        return 1;
    }
    case K_ELSE: {
        if (ntok != 1 || *nb == 0) return 0;
        Stmt *w = &stmts[bs[*nb - 1]];
        if (w->kind != K_WHEN || w->elsei >= 0) return 0;
        Stmt *s = newst(); s->kind = K_ELSE; s->line = lineno;
        w = &stmts[bs[*nb - 1]];
        w->elsei = nst - 1;
        return 1;
    }
    case K_END: {
        if (ntok != 1 || *nb == 0) return 0;
        int o = bs[--(*nb)];
        Stmt *s = newst(); s->kind = K_END; s->line = lineno;
        stmts[o].other = nst - 1;
        if (stmts[o].elsei >= 0) stmts[stmts[o].elsei].other = nst - 1;
        s->other = o;
        return 1;
    }
    case K_BREAK: {
        if (ntok != 1) return 0;
        int ok = 0;
        for (int i = 0; i < *nb; i++) if (stmts[bs[i]].kind == K_LOOP) ok = 1;
        if (!ok) return 0;
        Stmt *s = newst(); s->kind = K_BREAK; s->line = lineno;
        return 1;
    }
    }
    return 0;
}

static u32 *vals; static unsigned char *vset;
static int rerr;

static u32 ev(Node *n) {
    if (rerr) return 0;
    switch (n->kind) {
    case 0: return n->num;
    case 1:
        if (!vset[n->var]) { rerr = 1; return 0; }
        return vals[n->var];
    case 3: {
        u32 a = ev(n->a);
        if (rerr) return 0;
        switch (n->op) {
        case O_NEG: return (u32)(0u - a);
        case O_POP: return (u32)__builtin_popcount(a);
        default: return a == 0;
        }
    }
    default: {
        u32 a = ev(n->a);
        if (rerr) return 0;
        u32 b = ev(n->b);
        if (rerr) return 0;
        switch (n->op) {
        case O_MAX: return a > b ? a : b;
        case O_MIN: return a < b ? a : b;
        case O_EQ: return a == b;
        case O_NE: return a != b;
        case O_LT: return a < b;
        case O_GT: return a > b;
        case O_ADD: return a + b;
        case O_SUB: return a - b;
        case O_MUL: return a * b;
        case O_DIV: if (!b) { rerr = 1; return 0; } return a / b;
        case O_MOD: if (!b) { rerr = 1; return 0; } return a % b;
        case O_ROT: { unsigned k = b & 31; return k ? (a << k) | (a >> (32 - k)) : a; }
        }
    }
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 1;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    size_t cap = 1 << 16, len = 0;
    unsigned char *buf = malloc(cap);
    for (;;) {
        if (len == cap) { cap *= 2; buf = realloc(buf, cap); }
        size_t r = fread(buf + len, 1, cap - len, f);
        if (r == 0) break;
        len += r;
    }
    fclose(f);

    int bs[16], nb = 0;
    int lineno = 0;
    size_t p = 0;
    while (p < len) {
        size_t e = p;
        while (e < len && buf[e] != '\n') e++;
        lineno++;
        size_t ll = e - p;
        int bad = ll > 1000;
        for (size_t i = p; i < e && !bad; i++) {
            unsigned char c = buf[i];
            if (!(c == 9 || c == 13 || (c >= 32 && c <= 126))) bad = 1;
        }
        if (!bad) {
            size_t cl = ll;
            for (size_t i = 0; i < ll; i++) if (buf[p + i] == ';') { cl = i; break; }
            if (!tokenize((const char *)buf + p, (int)cl)) bad = 1;
            else if (!parse_line(lineno, bs, &nb)) bad = 1;
        }
        if (bad) { printf("parse error line %d\n", lineno); return 2; }
        p = e + 1;
    }
    if (nb > 0) { printf("parse error line %d\n", stmts[bs[nb - 1]].line); return 2; }

    vals = calloc(nvars + 1, sizeof(u32));
    vset = calloc(nvars + 1, 1);
    struct { int pc; u32 rem; } fr[17];
    int nf = 0;
    static char obuf[1 << 16];
    size_t ol = 0;
    int pc = 0;
    while (pc < nst) {
        Stmt *s = &stmts[pc];
        switch (s->kind) {
        case K_SET: {
            u32 v = ev(s->exprs[0]);
            if (rerr) goto fail;
            vals[s->var] = v; vset[s->var] = 1; pc++; break;
        }
        case K_OUT: {
            u32 tmp[64]; u32 *vv = tmp;
            if (s->nexpr > 64) vv = malloc(s->nexpr * sizeof(u32));
            for (int i = 0; i < s->nexpr; i++) { vv[i] = ev(s->exprs[i]); if (rerr) goto fail; }
            for (int i = 0; i < s->nexpr; i++) {
                if (ol + 16 > sizeof obuf) { fwrite(obuf, 1, ol, stdout); ol = 0; }
                ol += sprintf(obuf + ol, i ? " %u" : "%u", vv[i]);
            }
            if (ol + 2 > sizeof obuf) { fwrite(obuf, 1, ol, stdout); ol = 0; }
            obuf[ol++] = '\n';
            if (vv != tmp) free(vv);
            pc++; break;
        }
        case K_LOOP: {
            u32 n = ev(s->exprs[0]);
            if (rerr) goto fail;
            if (n == 0) pc = s->other + 1;
            else { fr[nf].pc = pc; fr[nf].rem = n; nf++; pc++; }
            break;
        }
        case K_WHEN: {
            u32 c = ev(s->exprs[0]);
            if (rerr) goto fail;
            if (c) pc++;
            else if (s->elsei >= 0) pc = s->elsei + 1;
            else pc = s->other + 1;
            break;
        }
        case K_ELSE: pc = s->other + 1; break;
        case K_END: {
            if (stmts[s->other].kind == K_LOOP) {
                if (--fr[nf - 1].rem > 0) pc = fr[nf - 1].pc + 1;
                else { nf--; pc++; }
            } else pc++;
            break;
        }
        case K_BREAK: {
            nf--;
            pc = stmts[fr[nf].pc].other + 1;
            break;
        }
        }
    }
    fwrite(obuf, 1, ol, stdout);
    return 0;
fail:
    fwrite(obuf, 1, ol, stdout);
    printf("runtime error line %d\n", stmts[pc].line);
    return 3;
}
