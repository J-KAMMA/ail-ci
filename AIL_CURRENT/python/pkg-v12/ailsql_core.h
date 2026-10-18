/* ailsql_core.h -- stage G11: the sqlite3 module, over the system libsqlite3 (docs/design/GENERAL_PURPOSE.md).

   Plain C on top of ailfile_core.h (it borrows ailf_buf). Connections and cursors are small integers:
   a connection is 1, 2, ...; a cursor is (1 << 32) + index. Nothing here knows an AIL type: strings are
   (pointer, length) pairs of UTF-8, results of text are malloc'd buffers the adapter copies. An error never
   longjmps: a function returns a negative value and fills `ails_e`; the adapter raises the exception.

   It follows CPython 3.12's _sqlite3 module (Modules/_sqlite/connection.c, cursor.c, statement.c) where the
   behaviour can be seen: the implicit BEGIN before insert/update/delete/replace under the default
   isolation level "", the rowcount and lastrowid rules, the one-statement check, the wording of the
   ProgrammingErrors, and the exception class chosen for a SQLite result code. */
#ifndef AILSQL_CORE_H
#define AILSQL_CORE_H

#include <sqlite3.h>
#include <strings.h>

/* exception codes of the typed runtime (pyfunc.EXC_NAMES); VALUE/RUNTIME/OVERFLOW are the existing ones */
enum { AILS_C_VALUE = 1, AILS_C_RUNTIME = 7, AILS_C_OVERFLOW = 10,
       AILS_C_ERROR = 19, AILS_C_DATABASE = 20, AILS_C_OPERATIONAL = 21, AILS_C_INTEGRITY = 22,
       AILS_C_PROGRAMMING = 23, AILS_C_INTERFACE = 24, AILS_C_DATA = 25, AILS_C_INTERNAL = 26,
       AILS_C_NOTSUPPORTED = 27 };

static struct { int code; char msg[1400]; } ails_e;

static int ails_fail(int code, const char *text) {
    ails_e.code = code;
    snprintf(ails_e.msg, sizeof ails_e.msg, "%s", text);
    return -1;
}
static int ails_failf(int code, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    ails_e.code = code;
    vsnprintf(ails_e.msg, sizeof ails_e.msg, fmt, ap);
    va_end(ap);
    return -1;
}
static int ails_nomem(void) { return ails_fail(AILS_C_RUNTIME, "out of memory"); }

/* _pysqlite_seterror: the class follows the primary result code, the message is sqlite3_errmsg() */
static int ails_class_of(int rc) {
    switch (rc & 0xff) {
    case SQLITE_INTERNAL: case SQLITE_NOTFOUND: return AILS_C_INTERNAL;
    case SQLITE_NOMEM: return AILS_C_RUNTIME;
    case SQLITE_ERROR: case SQLITE_PERM: case SQLITE_ABORT: case SQLITE_BUSY: case SQLITE_LOCKED:
    case SQLITE_READONLY: case SQLITE_INTERRUPT: case SQLITE_IOERR: case SQLITE_FULL: case SQLITE_CANTOPEN:
    case SQLITE_PROTOCOL: case SQLITE_EMPTY: case SQLITE_SCHEMA: return AILS_C_OPERATIONAL;
    case SQLITE_CORRUPT: return AILS_C_DATABASE;
    case SQLITE_TOOBIG: return AILS_C_DATA;
    case SQLITE_CONSTRAINT: case SQLITE_MISMATCH: return AILS_C_INTEGRITY;
    case SQLITE_MISUSE: case SQLITE_RANGE: return AILS_C_INTERFACE;
    default: return AILS_C_DATABASE;
    }
}
static int ails_dberr(sqlite3 *db) {
    int rc = sqlite3_errcode(db);
    const char *m = sqlite3_errmsg(db);
    return ails_fail(ails_class_of(rc), m ? m : "unknown error");
}

/* ---------------------------------------------------------------- tables */

typedef struct {
    sqlite3 *db;
    int open;
    char begin[40];          /* "" in autocommit mode (isolation_level=None), else "BEGIN <level>" */
} ails_conn;

typedef struct {
    int64_t conn;            /* connection handle (index + 1) */
    sqlite3_stmt *st;        /* the statement being run, NULL when finished */
    int closed, live;
    int implicit;            /* made by connection.execute() and not reused since: a result nobody holds can be dropped */
    int dml, nparams, named; /* named: values came by name (a dict) */
    int64_t nsupplied;
    unsigned char *bound;    /* named mode: which parameters got a value */
    char *pname;             /* a pending name (the next value binds to it) */
    int fresh;               /* the first row is current but has not been delivered yet */
    int hasrow;              /* a row is current */
    int counted;             /* rowcount already took sqlite3_changes() of this statement */
    int64_t rowcount, lastrowid;
    int has_last;            /* an execute() has set lastrowid (a fresh cursor, or one that only ran executemany, reads None in CPython) */
} ails_cur;

static ails_conn *ails_conns; static int64_t ails_nconns;
static ails_cur *ails_curs; static int64_t ails_ncurs, ails_curcap;
static int64_t *ails_freecurs; static int64_t ails_nfree;
#define AILS_CUR0 ((int64_t)1 << 32)

static ails_conn *ails_getconn(int64_t h) {
    if (h < 1 || h > ails_nconns) { ails_fail(AILS_C_PROGRAMMING, "Cannot operate on a closed database."); return NULL; }
    ails_conn *c = &ails_conns[h - 1];
    if (!c->open) { ails_fail(AILS_C_PROGRAMMING, "Cannot operate on a closed database."); return NULL; }
    return c;
}
static ails_cur *ails_getcur_raw(int64_t h) {
    int64_t i = h - AILS_CUR0;
    if (h < AILS_CUR0 || i >= ails_ncurs || !ails_curs[i].live) { ails_fail(AILS_C_PROGRAMMING, "Cannot operate on a closed cursor."); return NULL; }
    return &ails_curs[i];
}
/* check_cursor + check_connection of cursor.c */
static ails_cur *ails_getcur(int64_t h) {
    ails_cur *c = ails_getcur_raw(h);
    if (!c) return NULL;
    if (c->closed) { ails_fail(AILS_C_PROGRAMMING, "Cannot operate on a closed cursor."); return NULL; }
    if (!ails_getconn(c->conn)) return NULL;
    return c;
}

static void ails_stmt_done(ails_cur *c) {
    if (c->st) { sqlite3_finalize(c->st); c->st = NULL; }
    c->fresh = c->hasrow = 0;
}
static void ails_cur_clear_binds(ails_cur *c) {
    free(c->bound); c->bound = NULL;
    free(c->pname); c->pname = NULL;
    c->named = 0; c->nsupplied = 0;
}
static int64_t ails_cur_new(int64_t conn) {
    int64_t i;
    if (ails_nfree) i = ails_freecurs[--ails_nfree];
    else {
        if (ails_ncurs == ails_curcap) {
            int64_t cap = ails_curcap ? ails_curcap * 2 : 16;
            ails_cur *q = (ails_cur *)realloc(ails_curs, (size_t)cap * sizeof *q);
            if (!q) return ails_nomem();
            ails_curs = q; ails_curcap = cap;
        }
        i = ails_ncurs++;
    }
    memset(&ails_curs[i], 0, sizeof ails_curs[i]);
    ails_curs[i].conn = conn; ails_curs[i].live = 1; ails_curs[i].rowcount = -1;
    return AILS_CUR0 + i;
}
static int ails_cur_free(int64_t h) {
    ails_cur *c = ails_getcur_raw(h);
    if (!c) return 0;                       /* freeing twice is harmless */
    ails_stmt_done(c); ails_cur_clear_binds(c);
    c->live = 0;
    int64_t *q = (int64_t *)realloc(ails_freecurs, (size_t)(ails_nfree + 1) * sizeof *q);
    if (q) { ails_freecurs = q; ails_freecurs[ails_nfree++] = h - AILS_CUR0; }
    return 0;
}
/* the cursor of `conn.execute(...)` that the program does not keep: freed here, a cursor it holds is left alone */
static int ails_cur_drop(int64_t h) {
    int64_t i = h - AILS_CUR0;
    if (h >= AILS_CUR0 && i < ails_ncurs && ails_curs[i].live && ails_curs[i].implicit) return ails_cur_free(h);
    return 0;
}
static int ails_cur_close(int64_t h) {
    ails_cur *c = ails_getcur_raw(h);
    if (!c) return -1;
    if (c->closed) return 0;
    if (!ails_getconn(c->conn)) return -1;     /* cursor.close() on a closed connection */
    ails_stmt_done(c); c->closed = 1;
    return 0;
}

/* ---------------------------------------------------------------- connections */

static int64_t ails_connect(const uint8_t *path, int64_t n, int64_t iso) {
    if (n && memchr(path, 0, (size_t)n)) return ails_fail(AILS_C_VALUE, "embedded null byte");
    char *p = (char *)malloc((size_t)n + 1);
    if (!p) return ails_nomem();
    if (n) memcpy(p, path, (size_t)n);
    p[n] = 0;
    sqlite3 *db = NULL;
    int rc = sqlite3_open_v2(p, &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, NULL);
    free(p);
    if (rc != SQLITE_OK) {
        if (db) { ails_dberr(db); sqlite3_close(db); } else ails_fail(AILS_C_OPERATIONAL, "unable to open database file");
        return -1;
    }
    sqlite3_busy_timeout(db, 5000);
    sqlite3_extended_result_codes(db, 1);
    ails_conn *q = (ails_conn *)realloc(ails_conns, (size_t)(ails_nconns + 1) * sizeof *q);
    if (!q) { sqlite3_close(db); return ails_nomem(); }
    ails_conns = q;
    ails_conn *c = &ails_conns[ails_nconns];
    memset(c, 0, sizeof *c);
    c->db = db; c->open = 1;
    static const char *const levels[] = {"BEGIN ", "BEGIN DEFERRED", "BEGIN IMMEDIATE", "BEGIN EXCLUSIVE"};
    if (iso >= 0 && iso <= 3) snprintf(c->begin, sizeof c->begin, "%s", levels[iso]);
    return ++ails_nconns;
}

static int ails_exec_simple(sqlite3 *db, const char *sql) {
    sqlite3_stmt *st = NULL;
    int rc = sqlite3_prepare_v2(db, sql, -1, &st, NULL);
    if (rc != SQLITE_OK) return ails_dberr(db);
    rc = sqlite3_step(st);
    if (rc != SQLITE_DONE && rc != SQLITE_ROW) { ails_dberr(db); sqlite3_finalize(st); return -1; }
    rc = sqlite3_finalize(st);
    if (rc != SQLITE_OK) return ails_dberr(db);
    return 0;
}
/* the handle of a connection, whether a connection or a cursor was given */
static int64_t ails_owner(int64_t h) {
    if (h >= AILS_CUR0) { ails_cur *c = ails_getcur(h); return c ? c->conn : -1; }
    return h;
}
static int ails_commit(int64_t h) {
    ails_conn *c = ails_getconn(ails_owner(h));
    if (!c) return -1;
    if (!sqlite3_get_autocommit(c->db)) return ails_exec_simple(c->db, "COMMIT");
    return 0;
}
static int ails_rollback(int64_t h) {
    ails_conn *c = ails_getconn(ails_owner(h));
    if (!c) return -1;
    if (!sqlite3_get_autocommit(c->db)) return ails_exec_simple(c->db, "ROLLBACK");
    return 0;
}
static int ails_close(int64_t h) {
    if (h >= AILS_CUR0) return ails_cur_close(h);
    if (h < 1 || h > ails_nconns) return ails_fail(AILS_C_PROGRAMMING, "Cannot operate on a closed database.");
    ails_conn *c = &ails_conns[h - 1];
    if (!c->open) return 0;                  /* closing twice is allowed */
    for (int64_t i = 0; i < ails_ncurs; i++)
        if (ails_curs[i].live && ails_curs[i].conn == h) ails_stmt_done(&ails_curs[i]);
    c->open = 0;
    sqlite3 *db = c->db; c->db = NULL;
    sqlite3_close_v2(db);
    return 0;
}
static int64_t ails_in_transaction(int64_t h) {
    ails_conn *c = ails_getconn(ails_owner(h));
    if (!c) return -1;
    return !sqlite3_get_autocommit(c->db);
}
static int64_t ails_total_changes(int64_t h) {
    ails_conn *c = ails_getconn(ails_owner(h));
    if (!c) return -1;
    return (int64_t)sqlite3_total_changes(c->db);
}

/* ---------------------------------------------------------------- statements */

/* lstrip_sql() of statement.c: the first byte that is not blank or comment, NULL when there is none */
static const char *ails_lstrip_sql(const char *sql) {
    for (const char *pos = sql; *pos; pos++) {
        switch (*pos) {
        case ' ': case '\t': case '\f': case '\n': case '\r': break;
        case '-':
            if (pos[1] == '-') { pos += 2; while (pos[0] && pos[0] != '\n') pos++; if (pos[0] == '\0') return NULL; continue; }
            return pos;
        case '/':
            if (pos[1] == '*') { pos += 2; while (pos[0] && (pos[0] != '*' || pos[1] != '/')) pos++; if (pos[0] == '\0') return NULL; pos++; continue; }
            return pos;
        default: return pos;
        }
    }
    return NULL;
}

/* cursor.execute / the first half of executemany: the statement is prepared and checked; nothing runs.
   `h` is a connection (a fresh cursor is made) or a cursor (it is reused). Returns the cursor. */
static int64_t ails_prep(int64_t h, const uint8_t *sql, int64_t n) {
    int64_t cur;
    if (h >= AILS_CUR0) {
        ails_cur *c = ails_getcur(h);
        if (!c) return -1;
        ails_stmt_done(c); ails_cur_clear_binds(c);
        c->implicit = 0;
        cur = h;
    } else {
        if (!ails_getconn(h)) return -1;
        cur = ails_cur_new(h);
        if (cur < 0) return -1;
        ails_curs[cur - AILS_CUR0].implicit = 1;
    }
    ails_cur *c = &ails_curs[cur - AILS_CUR0];
    ails_conn *cn = &ails_conns[c->conn - 1];
    if (n && memchr(sql, 0, (size_t)n)) { if (h < AILS_CUR0) ails_cur_free(cur); return ails_fail(AILS_C_PROGRAMMING, "the query contains a null character"); }
    char *q = (char *)malloc((size_t)n + 1);
    if (!q) { if (h < AILS_CUR0) ails_cur_free(cur); return ails_nomem(); }
    if (n) memcpy(q, sql, (size_t)n);
    q[n] = 0;
    sqlite3_stmt *st = NULL; const char *tail = NULL;
    int rc = sqlite3_prepare_v2(cn->db, q, (int)n + 1, &st, &tail);
    int bad = 0;
    if (rc != SQLITE_OK) { ails_dberr(cn->db); bad = 1; }
    else if (ails_lstrip_sql(tail)) { ails_fail(AILS_C_PROGRAMMING, "You can only execute one statement at a time."); bad = 1; }
    if (bad) { if (st) sqlite3_finalize(st); free(q); if (h < AILS_CUR0) ails_cur_free(cur); return -1; }
    const char *p = ails_lstrip_sql(q);
    c->dml = p && (strncasecmp(p, "insert", 6) == 0 || strncasecmp(p, "update", 6) == 0
                   || strncasecmp(p, "delete", 6) == 0 || strncasecmp(p, "replace", 7) == 0);
    free(q);
    c->st = st;
    c->nparams = st ? sqlite3_bind_parameter_count(st) : 0;
    c->rowcount = c->dml ? 0 : -1;
    c->counted = 0;
    return cur;
}

/* ---- binding. The value goes to the next `?` (positional) or to the pending name. */
/* which parameter indexes receive the next value: positional -> one index; named -> every index of that name */
static int ails_bind_any(ails_cur *c, int kind, int64_t iv, double dv, const uint8_t *p, int64_t n) {
    if (!c->st) return 0;
    int first, last;
    if (c->pname) {
        if (!c->named) {
            if (c->nparams > 0) { c->bound = (unsigned char *)calloc((size_t)c->nparams + 1, 1); if (!c->bound) return ails_nomem(); }
            c->named = 1;
        }
        first = 1; last = c->nparams;
    } else {
        c->nsupplied++;
        first = last = (int)(c->nsupplied > c->nparams ? 0 : c->nsupplied);
        if (!first) return 0;
    }
    for (int i = first; i <= last; i++) {
        if (c->pname) {
            const char *nm = sqlite3_bind_parameter_name(c->st, i);
            if (!nm || strcmp(nm + 1, c->pname) != 0) continue;
            c->bound[i] = 1;
        }
        int rc = SQLITE_OK;
        switch (kind) {
        case 0: rc = sqlite3_bind_int64(c->st, i, iv); break;
        case 1: rc = sqlite3_bind_double(c->st, i, dv); break;
        case 2: rc = sqlite3_bind_text64(c->st, i, (const char *)(p ? p : (const uint8_t *)""), (sqlite3_uint64)n, SQLITE_TRANSIENT, SQLITE_UTF8); break;
        case 3: rc = n ? sqlite3_bind_blob64(c->st, i, p, (sqlite3_uint64)n, SQLITE_TRANSIENT) : sqlite3_bind_zeroblob(c->st, i, 0); break;
        default: rc = sqlite3_bind_null(c->st, i); break;
        }
        if (rc != SQLITE_OK) { ails_dberr(ails_conns[c->conn - 1].db); free(c->pname); c->pname = NULL; return -1; }
    }
    if (c->pname) { free(c->pname); c->pname = NULL; }
    return 0;
}
/* the parameters come as a dict (even an empty one): the placeholders are checked by name */
static int ails_set_named(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    if (!c->named && c->nparams > 0) { c->bound = (unsigned char *)calloc((size_t)c->nparams + 1, 1); if (!c->bound) return ails_nomem(); }
    c->named = 1;
    return 0;
}
static int ails_bind_name(int64_t h, const uint8_t *k, int64_t n) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    free(c->pname);
    c->pname = (char *)malloc((size_t)n + 1);
    if (!c->pname) return ails_nomem();
    if (n) memcpy(c->pname, k, (size_t)n);
    c->pname[n] = 0;
    return 0;
}
static int ails_bind_int(int64_t h, int64_t v) { ails_cur *c = ails_getcur(h); return c ? ails_bind_any(c, 0, v, 0, NULL, 0) : -1; }
static int ails_bind_float(int64_t h, double v) { ails_cur *c = ails_getcur(h); return c ? ails_bind_any(c, 1, 0, v, NULL, 0) : -1; }
static int ails_bind_text(int64_t h, const uint8_t *p, int64_t n) { ails_cur *c = ails_getcur(h); return c ? ails_bind_any(c, 2, 0, 0, p, n) : -1; }
static int ails_bind_blob(int64_t h, const uint8_t *p, int64_t n) { ails_cur *c = ails_getcur(h); return c ? ails_bind_any(c, 3, 0, 0, p, n) : -1; }
static int ails_bind_null(int64_t h) { ails_cur *c = ails_getcur(h); return c ? ails_bind_any(c, 4, 0, 0, NULL, 0) : -1; }

/* bind_parameters(): the count check for a sequence, the name check for a dict */
static int ails_check_binds(ails_cur *c) {
    if (!c->st) return 0;
    if (c->named) {
        for (int i = 1; i <= c->nparams; i++) {
            const char *nm = sqlite3_bind_parameter_name(c->st, i);
            if (!nm) return ails_failf(AILS_C_PROGRAMMING, "Binding %d has no name, but you supplied a dictionary (which has only names).", i);
            if (!c->bound[i]) return ails_failf(AILS_C_PROGRAMMING, "You did not supply a value for binding parameter :%s.", nm + 1);
        }
        return 0;
    }
    if (c->nsupplied != c->nparams)
        return ails_failf(AILS_C_PROGRAMMING, "Incorrect number of bindings supplied. The current statement uses %d, and there are %lld supplied.",
                          c->nparams, (long long)c->nsupplied);
    return 0;
}

static int ails_begin(ails_cur *c, ails_conn *cn) {
    if (cn->begin[0] && c->dml && sqlite3_get_autocommit(cn->db)) return ails_exec_simple(cn->db, cn->begin);
    return 0;
}

/* One step of the running statement. multi: an executemany step, where a row is an error. */
static int ails_step_first(ails_cur *c, ails_conn *cn, int multi) {
    if (!c->st) return 0;
    int rc = sqlite3_step(c->st);
    if (rc != SQLITE_DONE && rc != SQLITE_ROW) {
        ails_dberr(cn->db);
        sqlite3_reset(c->st);
        return -1;
    }
    if (rc == SQLITE_ROW) {
        if (multi) { sqlite3_reset(c->st); return ails_fail(AILS_C_PROGRAMMING, "executemany() can only execute DML statements."); }
        c->fresh = c->hasrow = 1;
    } else if (c->dml) {
        c->rowcount += (int64_t)sqlite3_changes(cn->db); c->counted = 1;
    }
    return 0;
}

/* cursor.execute() after the binds: BEGIN if needed, check the binds, run to the first row or the end */
static int ails_exec(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    ails_conn *cn = &ails_conns[c->conn - 1];
    if (ails_begin(c, cn)) return -1;
    if (ails_check_binds(c)) return -1;
    if (ails_step_first(c, cn, 0)) return -1;
    if (!c->hasrow) ails_stmt_done(c);
    c->lastrowid = (int64_t)sqlite3_last_insert_rowid(cn->db); c->has_last = 1;
    return 0;
}

/* executemany: begin once, then (bind..., mstep) per row; lastrowid is left alone */
static int ails_mbegin(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    return ails_begin(c, &ails_conns[c->conn - 1]);
}
static int ails_mrow(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    if (c->st) sqlite3_reset(c->st);
    c->nsupplied = 0; c->named = 0;
    free(c->bound); c->bound = NULL;
    return 0;
}
static int ails_mstep(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    ails_conn *cn = &ails_conns[c->conn - 1];
    if (ails_check_binds(c)) return -1;
    if (!c->st) return 0;
    int rc = sqlite3_step(c->st);
    if (rc != SQLITE_DONE && rc != SQLITE_ROW) { ails_dberr(cn->db); sqlite3_reset(c->st); return -1; }
    if (rc == SQLITE_ROW) { sqlite3_reset(c->st); return ails_fail(AILS_C_PROGRAMMING, "executemany() can only execute DML statements."); }
    if (c->dml) c->rowcount += (int64_t)sqlite3_changes(cn->db);
    sqlite3_reset(c->st);
    return 0;
}
static int ails_mend(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    ails_stmt_done(c);
    return 0;
}

/* executescript: commit what is open, then run every statement */
static int64_t ails_script(int64_t h, const uint8_t *sql, int64_t n) {
    int64_t owner = ails_owner(h);
    ails_conn *cn = ails_getconn(owner);
    if (!cn) return -1;
    int64_t cur = h;
    if (h < AILS_CUR0) { cur = ails_cur_new(owner); if (cur < 0) return -1; ails_curs[cur - AILS_CUR0].implicit = 1; }
    else { ails_cur *c = ails_getcur(h); if (!c) return -1; ails_stmt_done(c); ails_cur_clear_binds(c); c->implicit = 0; }
    if (n && memchr(sql, 0, (size_t)n)) { if (h < AILS_CUR0) ails_cur_free(cur); return ails_fail(AILS_C_PROGRAMMING, "the query contains a null character"); }
    if (!sqlite3_get_autocommit(cn->db) && ails_exec_simple(cn->db, "COMMIT")) { if (h < AILS_CUR0) ails_cur_free(cur); return -1; }
    char *q = (char *)malloc((size_t)n + 1);
    if (!q) { if (h < AILS_CUR0) ails_cur_free(cur); return ails_nomem(); }
    if (n) memcpy(q, sql, (size_t)n);
    q[n] = 0;
    const char *script = q;
    for (;;) {
        sqlite3_stmt *st = NULL; const char *tail = NULL;
        int rc = sqlite3_prepare_v2(cn->db, script, -1, &st, &tail);
        if (rc != SQLITE_OK) { ails_dberr(cn->db); free(q); if (h < AILS_CUR0) ails_cur_free(cur); return -1; }
        script = tail;
        if (st) {
            do { rc = sqlite3_step(st); } while (rc == SQLITE_ROW);
            if (rc != SQLITE_DONE) { ails_dberr(cn->db); sqlite3_finalize(st); free(q); if (h < AILS_CUR0) ails_cur_free(cur); return -1; }
            rc = sqlite3_finalize(st);
            if (rc != SQLITE_OK) { ails_dberr(cn->db); free(q); if (h < AILS_CUR0) ails_cur_free(cur); return -1; }
        }
        if (*script == 0) break;
    }
    free(q);
    return cur;
}

static int64_t ails_cursor(int64_t h) {
    if (!ails_getconn(h)) return -1;
    return ails_cur_new(h);
}

/* ---------------------------------------------------------------- reading rows */

/* the next row of the statement: 1 a row, 0 the end */
static int ails_next(int64_t h) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    if (!c->st) return 0;
    if (c->fresh) { c->fresh = 0; return 1; }
    ails_conn *cn = &ails_conns[c->conn - 1];
    int rc = sqlite3_step(c->st);
    if (rc == SQLITE_ROW) { c->hasrow = 1; return 1; }
    c->hasrow = 0;
    if (rc != SQLITE_DONE) { ails_dberr(cn->db); sqlite3_reset(c->st); ails_stmt_done(c); return -1; }
    if (c->dml && !c->counted) { c->rowcount += (int64_t)sqlite3_changes(cn->db); c->counted = 1; }
    ails_stmt_done(c);
    return 0;
}

static const char *ails_type_name(int t) {
    switch (t) { case SQLITE_INTEGER: return "INTEGER"; case SQLITE_FLOAT: return "REAL"; case SQLITE_TEXT: return "TEXT";
    case SQLITE_BLOB: return "BLOB"; default: return "NULL"; }
}
static ails_cur *ails_rowcur(int64_t h, int64_t i) {
    ails_cur *c = ails_getcur(h);
    if (!c) return NULL;
    if (!c->st || !c->hasrow) { ails_fail(AILS_C_PROGRAMMING, "no row is available"); return NULL; }
    if (i < 0 || i >= sqlite3_column_count(c->st)) { ails_failf(AILS_C_RUNTIME, "sqlite3: the row has no column %lld", (long long)i); return NULL; }
    return c;
}
/* the declared row has n columns */
static int ails_cols(int64_t h, int64_t n) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    if (!c->st || !c->hasrow) return ails_fail(AILS_C_PROGRAMMING, "no row is available");
    int have = sqlite3_column_count(c->st);
    if (have != n) return ails_failf(AILS_C_RUNTIME, "sqlite3: the query returns %d columns but the declared row type has %lld", have, (long long)n);
    return 0;
}
static int ails_isnull(int64_t h, int64_t i) {
    ails_cur *c = ails_rowcur(h, i);
    if (!c) return -1;
    return sqlite3_column_type(c->st, (int)i) == SQLITE_NULL;
}
static int ails_want(ails_cur *c, int64_t i, int type, const char *declared) {
    int t = sqlite3_column_type(c->st, (int)i);
    if (t == type) return 0;
    if (t == SQLITE_NULL) return ails_failf(AILS_C_RUNTIME, "sqlite3: column %lld is NULL but the declared type is %s; declare it Optional[%s]", (long long)i, declared, declared);
    return ails_failf(AILS_C_RUNTIME, "sqlite3: column %lld holds %s but the declared type is %s", (long long)i, ails_type_name(t), declared);
}
static int64_t ails_col_int(int64_t h, int64_t i, int *err) {
    *err = 0;
    ails_cur *c = ails_rowcur(h, i);
    if (!c || ails_want(c, i, SQLITE_INTEGER, "int")) { *err = 1; return 0; }
    return (int64_t)sqlite3_column_int64(c->st, (int)i);
}
static double ails_col_float(int64_t h, int64_t i, int *err) {
    *err = 0;
    ails_cur *c = ails_rowcur(h, i);
    if (!c || ails_want(c, i, SQLITE_FLOAT, "float")) { *err = 1; return 0; }
    return sqlite3_column_double(c->st, (int)i);
}
/* strict UTF-8, as Python decodes it (no surrogates, no overlongs, nothing above U+10FFFF) */
static int ails_utf8_ok(const uint8_t *s, int64_t n) {
    for (int64_t i = 0; i < n;) {
        uint8_t c = s[i];
        if (c < 0x80) { i++; continue; }
        int w; uint32_t cp;
        if (c >= 0xC2 && c <= 0xDF) { w = 2; cp = c & 0x1F; }
        else if (c >= 0xE0 && c <= 0xEF) { w = 3; cp = c & 0x0F; }
        else if (c >= 0xF0 && c <= 0xF4) { w = 4; cp = c & 0x07; }
        else return 0;
        if (i + w > n) return 0;
        for (int k = 1; k < w; k++) { if ((s[i + k] & 0xC0) != 0x80) return 0; cp = (cp << 6) | (s[i + k] & 0x3F); }
        if ((w == 3 && cp < 0x800) || (w == 4 && (cp < 0x10000 || cp > 0x10FFFF)) || (cp >= 0xD800 && cp < 0xE000)) return 0;
        i += w;
    }
    return 1;
}
static int ails_col_text(int64_t h, int64_t i, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ails_cur *c = ails_rowcur(h, i);
    if (!c || ails_want(c, i, SQLITE_TEXT, "str")) return -1;
    const uint8_t *p = (const uint8_t *)sqlite3_column_text(c->st, (int)i);
    int64_t n = sqlite3_column_bytes(c->st, (int)i);
    if (!p) return ails_nomem();
    if (!ails_utf8_ok(p, n)) {
        const char *name = sqlite3_column_name(c->st, (int)i);
        char shown[200]; int64_t o = 0;
        for (int64_t k = 0; k < n && o < 190; k++) {
            if (p[k] < 0x80) shown[o++] = (char)p[k]; else { shown[o++] = (char)0xEF; shown[o++] = (char)0xBF; shown[o++] = (char)0xBD; }
        }
        shown[o] = 0;
        return ails_failf(AILS_C_OPERATIONAL, "Could not decode to UTF-8 column '%s' with text '%s'", name ? name : "", shown);
    }
    if (ailf_buf_put(out, p, n)) return ails_nomem();
    return 0;
}
static int ails_col_blob(int64_t h, int64_t i, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ails_cur *c = ails_rowcur(h, i);
    if (!c || ails_want(c, i, SQLITE_BLOB, "bytes")) return -1;
    const uint8_t *p = (const uint8_t *)sqlite3_column_blob(c->st, (int)i);
    int64_t n = sqlite3_column_bytes(c->st, (int)i);
    if (n && !p) return ails_nomem();
    if (ailf_buf_put(out, p, n)) return ails_nomem();
    return 0;
}

static int ails_rowcount(int64_t h, int64_t *out) { ails_cur *c = ails_getcur(h); if (!c) return -1; *out = c->rowcount; return 0; }
/* lastrowid: the program may only read an int when CPython has one; None (a fresh cursor, or only executemany ran) is a RuntimeError here */
static int ails_lastrowid(int64_t h, int64_t *out) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    if (!c->has_last) return ails_fail(AILS_C_RUNTIME, "sqlite3: lastrowid is None here (no execute() has run on this cursor)\n  write instead: test cur.lastrowid is None first");
    *out = c->lastrowid;
    return 0;
}
static int ails_haslast(int64_t h, int64_t *out) { ails_cur *c = ails_getcur(h); if (!c) return -1; *out = c->has_last; return 0; }
/* lastrowid as print() shows it: None or the number */
static int ails_lastshow(int64_t h, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    char t[32];
    int n = c->has_last ? snprintf(t, sizeof t, "%lld", (long long)c->lastrowid) : snprintf(t, sizeof t, "None");
    if (ailf_buf_put(out, (const uint8_t *)t, n)) return ails_nomem();
    return 0;
}
/* a parameter sequence of `given` items: the length check of bind_parameters(), before any value is bound */
static int ails_blen(int64_t h, int64_t given) {
    ails_cur *c = ails_getcur(h);
    if (!c) return -1;
    if (given == c->nparams) return 0;
    return ails_failf(AILS_C_PROGRAMMING, "Incorrect number of bindings supplied. The current statement uses %d, and there are %lld supplied.",
                      c->nparams, (long long)given);
}

/* repr() of bytes, for printing a row */
static int ails_repr_bytes_(const uint8_t *s, int64_t n, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    int sq = 0, dq = 0;
    for (int64_t i = 0; i < n; i++) { if (s[i] == '\'') sq = 1; else if (s[i] == '"') dq = 1; }
    char q = (sq && !dq) ? '"' : '\'';
    if (ailf_buf_putc(out, 'b') || ailf_buf_putc(out, (uint8_t)q)) return -1;
    for (int64_t i = 0; i < n; i++) {
        uint8_t c = s[i];
        if (c == (uint8_t)q || c == '\\') { if (ailf_buf_putc(out, '\\') || ailf_buf_putc(out, c)) return -1; }
        else if (c == '\t') { if (ailf_buf_put(out, (const uint8_t *)"\\t", 2)) return -1; }
        else if (c == '\n') { if (ailf_buf_put(out, (const uint8_t *)"\\n", 2)) return -1; }
        else if (c == '\r') { if (ailf_buf_put(out, (const uint8_t *)"\\r", 2)) return -1; }
        else if (c < 0x20 || c >= 0x7f) {
            char t[8]; snprintf(t, sizeof t, "\\x%02x", c);
            if (ailf_buf_put(out, (const uint8_t *)t, 4)) return -1;
        } else if (ailf_buf_putc(out, c)) return -1;
    }
    return ailf_buf_putc(out, (uint8_t)q);
}

static int ails_repr_bytes(const uint8_t *s, int64_t n, ailf_buf *out) {
    if (ails_repr_bytes_(s, n, out)) return ails_nomem();
    return 0;
}

#endif /* AILSQL_CORE_H */
