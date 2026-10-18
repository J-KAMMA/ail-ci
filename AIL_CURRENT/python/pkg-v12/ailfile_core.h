/* ailfile_core.h -- stage G7: the file layer behind open(), shared by the typed and the general
   runtime (cruntime.py embeds this text; ailfile_cli.c-style test drivers include it directly).

   Plain C. No AIL types: every string is a (pointer, length) pair of UTF-8 bytes, every result is
   a malloc'd buffer the adapter copies into its own arena. Errors never longjmp here: a function
   returns a negative value and fills `ailf_e`; the adapter raises the language exception.

   The structure mirrors CPython 3.12's io stack on purpose, because the observable behaviour
   (what a read after a write sees, where tell() points, how a chunk boundary splits a CRLF) comes
   from it:

     FileIO       the file descriptor                          -> ailf.fd
     Buffered*    one buffer, read window or write queue       -> ailf.buf / rpos / rend / wlen
     TextIOWrapper chunked decoder with universal newlines     -> ailf.snap / dec / dpos
*/
#ifndef AILFILE_CORE_H
#define AILFILE_CORE_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>
#include <limits.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#ifdef _WIN32
#include <io.h>
#include <direct.h>
#include <wchar.h>
#include <process.h>
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#include <dirent.h>
extern char **environ;
#endif

/* ------------------------------------------------------------------ errors */

enum { AILF_E_NONE = 0, AILF_E_OS, AILF_E_VALUE, AILF_E_UNSUP, AILF_E_UDECODE, AILF_E_UENCODE,
       AILF_E_KEY, AILF_E_FATAL, AILF_E_NOMEM };
typedef struct {
    int kind;            /* AILF_E_* */
    int err;             /* errno for AILF_E_OS */
    char msg[1100];      /* str(e) exactly as CPython prints it */
    char fn1[600], fn2[600];  /* filenames of an OSError (UTF-8), "" when none */
    int has_fn1, has_fn2;
} ailf_error_t;
static ailf_error_t ailf_e;

static int ailf_fail(int kind, const char *text) {
    ailf_e.kind = kind; ailf_e.err = 0; ailf_e.has_fn1 = ailf_e.has_fn2 = 0;
    ailf_e.fn1[0] = ailf_e.fn2[0] = 0;
    snprintf(ailf_e.msg, sizeof ailf_e.msg, "%s", text);
    return -1;
}
static int ailf_failf(int kind, const char *fmt, ...);
#include <stdarg.h>
static int ailf_failf(int kind, const char *fmt, ...) {
    va_list ap; va_start(ap, fmt);
    ailf_e.kind = kind; ailf_e.err = 0; ailf_e.has_fn1 = ailf_e.has_fn2 = 0;
    ailf_e.fn1[0] = ailf_e.fn2[0] = 0;
    vsnprintf(ailf_e.msg, sizeof ailf_e.msg, fmt, ap);
    va_end(ap);
    return -1;
}

/* Python's repr() of a str, enough for messages: ASCII exact, other printable text raw. */
static int64_t ailf_repr_str(char *out, int64_t cap, const uint8_t *s, int64_t n) {
    int single = 0, dbl = 0;
    for (int64_t i = 0; i < n; i++) { if (s[i] == '\'') single = 1; else if (s[i] == '"') dbl = 1; }
    char q = (single && !dbl) ? '"' : '\'';
    int64_t o = 0;
#define AILF_RPUT(c) do { if (o + 1 < cap) out[o] = (char)(c); o++; } while (0)
    AILF_RPUT(q);
    for (int64_t i = 0; i < n;) {
        uint8_t c = s[i];
        if (c == (uint8_t)q || c == '\\') { AILF_RPUT('\\'); AILF_RPUT(c); i++; }
        else if (c == '\n') { AILF_RPUT('\\'); AILF_RPUT('n'); i++; }
        else if (c == '\r') { AILF_RPUT('\\'); AILF_RPUT('r'); i++; }
        else if (c == '\t') { AILF_RPUT('\\'); AILF_RPUT('t'); i++; }
        else if (c < 0x20 || c == 0x7f) {
            char tmp[8]; snprintf(tmp, sizeof tmp, "\\x%02x", c);
            for (char *t = tmp; *t; t++) AILF_RPUT(*t);
            i++;
        } else if (c < 0x80) { AILF_RPUT(c); i++; }
        else {
            int w = c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
            if (i + w > n) w = (int)(n - i);
            uint32_t cp = 0;
            if (w == 2) cp = ((c & 0x1Fu) << 6) | (s[i + 1] & 0x3Fu);
            else if (w == 3) cp = ((c & 0x0Fu) << 12) | ((s[i + 1] & 0x3Fu) << 6) | (s[i + 2] & 0x3Fu);
            else if (w == 4) cp = ((c & 0x07u) << 18) | ((s[i + 1] & 0x3Fu) << 12) | ((s[i + 2] & 0x3Fu) << 6) | (s[i + 3] & 0x3Fu);
            /* what str.isprintable() rejects among the common cases: C1 controls, NBSP-like and
               invisible format characters, line/paragraph separators, private use, specials */
            int printable = !(cp >= 0x80 && cp < 0xA0) && cp != 0xA0 && cp != 0xAD
                && !(cp >= 0x2000 && cp <= 0x200F) && !(cp >= 0x2028 && cp <= 0x202F)
                && !(cp >= 0x205F && cp <= 0x206F) && cp != 0x3000 && cp != 0xFEFF
                && !(cp >= 0xE000 && cp <= 0xF8FF) && !(cp >= 0xFFF0 && cp <= 0xFFFF)
                && cp != 0x1680 && cp != 0x180E;
            if (printable) { for (int k = 0; k < w; k++) AILF_RPUT(s[i + k]); }
            else {
                char tmp[16];
                if (cp < 0x100) snprintf(tmp, sizeof tmp, "\\x%02x", cp);
                else if (cp < 0x10000) snprintf(tmp, sizeof tmp, "\\u%04x", cp);
                else snprintf(tmp, sizeof tmp, "\\U%08x", cp);
                for (char *t = tmp; *t; t++) AILF_RPUT(*t);
            }
            i += w;
        }
    }
    AILF_RPUT(q);
#undef AILF_RPUT
    if (cap > 0) out[o < cap ? o : cap - 1] = 0;
    return o;
}

/* An OSError the way CPython words it: "[Errno 2] No such file or directory: 'x'"; two names
   (rename) are "'a' -> 'b'". Returns -1 so callers can `return ailf_oserr(...)`. */
static int ailf_oserr2(int err, const uint8_t *f1, int64_t n1, const uint8_t *f2, int64_t n2) {
    ailf_e.kind = AILF_E_OS; ailf_e.err = err;
    ailf_e.has_fn1 = f1 != NULL; ailf_e.has_fn2 = f2 != NULL;
    ailf_e.fn1[0] = ailf_e.fn2[0] = 0;
    if (f1) { int64_t k = n1 < (int64_t)sizeof ailf_e.fn1 - 1 ? n1 : (int64_t)sizeof ailf_e.fn1 - 1; memcpy(ailf_e.fn1, f1, (size_t)k); ailf_e.fn1[k] = 0; }
    if (f2) { int64_t k = n2 < (int64_t)sizeof ailf_e.fn2 - 1 ? n2 : (int64_t)sizeof ailf_e.fn2 - 1; memcpy(ailf_e.fn2, f2, (size_t)k); ailf_e.fn2[k] = 0; }
    const char *why = strerror(err);
    int o = snprintf(ailf_e.msg, sizeof ailf_e.msg, "[Errno %d] %s", err, why ? why : "Unknown error");
    if (f1 && o > 0 && o < (int)sizeof ailf_e.msg - 8) {
        ailf_e.msg[o++] = ':'; ailf_e.msg[o++] = ' ';
        o += (int)ailf_repr_str(ailf_e.msg + o, (int64_t)sizeof ailf_e.msg - o, f1, n1 < 500 ? n1 : 500);
        if (f2 && o < (int)sizeof ailf_e.msg - 8) {
            ailf_e.msg[o++] = ' '; ailf_e.msg[o++] = '-'; ailf_e.msg[o++] = '>'; ailf_e.msg[o++] = ' ';
            o += (int)ailf_repr_str(ailf_e.msg + o, (int64_t)sizeof ailf_e.msg - o, f2, n2 < 500 ? n2 : 500);
        }
        if (o >= (int)sizeof ailf_e.msg) o = (int)sizeof ailf_e.msg - 1;
        ailf_e.msg[o] = 0;
    }
    return -1;
}
static int ailf_oserr(int err, const uint8_t *f1, int64_t n1) { return ailf_oserr2(err, f1, n1, NULL, 0); }

/* ------------------------------------------------------------------ growable byte buffer */

typedef struct { uint8_t *p; int64_t n, cap; } ailf_buf;
static int ailf_buf_reserve(ailf_buf *b, int64_t extra) {
    if (b->n + extra + 1 <= b->cap) return 0;
    int64_t cap = b->cap ? b->cap : 256;
    while (cap < b->n + extra + 1) {
        if (cap > INT64_MAX / 2) return ailf_fail(AILF_E_NOMEM, "out of memory");
        cap *= 2;
    }
    uint8_t *q = (uint8_t *)realloc(b->p, (size_t)cap);
    if (!q) return ailf_fail(AILF_E_NOMEM, "out of memory");
    b->p = q; b->cap = cap;
    return 0;
}
static int ailf_buf_put(ailf_buf *b, const uint8_t *s, int64_t n) {
    if (n <= 0) return 0;
    if (ailf_buf_reserve(b, n)) return -1;
    memcpy(b->p + b->n, s, (size_t)n); b->n += n;
    return 0;
}
static int ailf_buf_putc(ailf_buf *b, uint8_t c) {
    if (b->n + 2 > b->cap && ailf_buf_reserve(b, 1)) return -1;
    b->p[b->n++] = c;
    return 0;
}
static int ailf_buf_putcp(ailf_buf *b, uint32_t c) {
    if (ailf_buf_reserve(b, 4)) return -1;
    if (c < 0x80) b->p[b->n++] = (uint8_t)c;
    else if (c < 0x800) { b->p[b->n++] = (uint8_t)(0xC0 | (c >> 6)); b->p[b->n++] = (uint8_t)(0x80 | (c & 0x3F)); }
    else if (c < 0x10000) {
        b->p[b->n++] = (uint8_t)(0xE0 | (c >> 12)); b->p[b->n++] = (uint8_t)(0x80 | ((c >> 6) & 0x3F));
        b->p[b->n++] = (uint8_t)(0x80 | (c & 0x3F));
    } else {
        b->p[b->n++] = (uint8_t)(0xF0 | (c >> 18)); b->p[b->n++] = (uint8_t)(0x80 | ((c >> 12) & 0x3F));
        b->p[b->n++] = (uint8_t)(0x80 | ((c >> 6) & 0x3F)); b->p[b->n++] = (uint8_t)(0x80 | (c & 0x3F));
    }
    return 0;
}
static void ailf_buf_free(ailf_buf *b) { free(b->p); b->p = NULL; b->n = b->cap = 0; }

/* ------------------------------------------------------------------ portable file calls */

#ifdef _WIN32
typedef wchar_t ailf_pchar;
#define AILF_READ(fd, p, n) _read((fd), (p), (unsigned)((n) > 0x40000000 ? 0x40000000 : (n)))
#define AILF_WRITE(fd, p, n) _write((fd), (p), (unsigned)((n) > 0x40000000 ? 0x40000000 : (n)))
#define AILF_LSEEK(fd, off, wh) _lseeki64((fd), (off), (wh))
#define AILF_CLOSE(fd) _close(fd)
typedef struct _stat64 ailf_stat_t;
#define AILF_FSTAT(fd, st) _fstat64((fd), (st))
#define AILF_S_ISDIR(m) (((m) & _S_IFMT) == _S_IFDIR)
#define AILF_S_ISREG(m) (((m) & _S_IFMT) == _S_IFREG)
#else
typedef char ailf_pchar;
#define AILF_READ(fd, p, n) read((fd), (p), (size_t)(n))
#define AILF_WRITE(fd, p, n) write((fd), (p), (size_t)(n))
#define AILF_LSEEK(fd, off, wh) lseek((fd), (off_t)(off), (wh))
#define AILF_CLOSE(fd) close(fd)
typedef struct stat ailf_stat_t;
#define AILF_FSTAT(fd, st) fstat((fd), (st))
#define AILF_S_ISDIR(m) S_ISDIR(m)
#define AILF_S_ISREG(m) S_ISREG(m)
#endif

/* A path as the OS wants it. POSIX: the UTF-8 bytes with a NUL. Windows: UTF-16. A NUL inside the
   path is CPython's ValueError("embedded null byte"). The result is malloc'd. */
static ailf_pchar *ailf_path(const uint8_t *s, int64_t n) {
    if (n && memchr(s, 0, (size_t)n)) { ailf_fail(AILF_E_VALUE, "embedded null byte"); return NULL; }
#ifdef _WIN32
    wchar_t *w = (wchar_t *)malloc(((size_t)n + 1) * sizeof(wchar_t));
    if (!w) { ailf_fail(AILF_E_NOMEM, "out of memory"); return NULL; }
    int64_t o = 0;
    for (int64_t i = 0; i < n;) {
        uint32_t c = s[i];
        int k = 1;
        if (c >= 0xF0) { k = 4; c &= 0x07; } else if (c >= 0xE0) { k = 3; c &= 0x0F; } else if (c >= 0xC0) { k = 2; c &= 0x1F; }
        for (int j = 1; j < k && i + j < n; j++) c = (c << 6) | (s[i + j] & 0x3F);
        i += k;
        if (c >= 0x10000) { c -= 0x10000; w[o++] = (wchar_t)(0xD800 + (c >> 10)); w[o++] = (wchar_t)(0xDC00 + (c & 0x3FF)); }
        else w[o++] = (wchar_t)c;
    }
    w[o] = 0;
    return w;
#else
    char *p = (char *)malloc((size_t)n + 1);
    if (!p) { ailf_fail(AILF_E_NOMEM, "out of memory"); return NULL; }
    if (n) memcpy(p, s, (size_t)n);
    p[n] = 0;
    return p;
#endif
}
#ifdef _WIN32
/* UTF-16 -> UTF-8 into a growable buffer (names read from the OS). */
static int ailf_put_wide(ailf_buf *b, const wchar_t *w) {
    for (; *w; w++) {
        uint32_t c = (uint32_t)*w;
        if (c >= 0xD800 && c < 0xDC00 && w[1] >= 0xDC00 && w[1] < 0xE000) {
            c = 0x10000 + ((c - 0xD800) << 10) + ((uint32_t)w[1] - 0xDC00); w++;
        }
        if (ailf_buf_putcp(b, c)) return -1;
    }
    return 0;
}
#endif

/* ------------------------------------------------------------------ the file object */

#define AILF_CHUNK 8192

enum { AILF_ENC_UTF8 = 0, AILF_ENC_ASCII = 1, AILF_ENC_LATIN1 = 2 };
enum { AILF_ERR_STRICT = 0, AILF_ERR_REPLACE = 1, AILF_ERR_IGNORE = 2 };

typedef struct ailf {
    int used;
    uint32_t gen;
    int fd;
    int readable, writable, appending, text, seekable, line_buffered, unbuffered;
    uint8_t *name; int64_t namelen;       /* the path as given, for messages */
    /* Buffered layer */
    uint8_t *buf; int64_t cap;
    int64_t rpos, rend;                   /* read window buf[rpos..rend) */
    int64_t wlen;                         /* queued writes buf[0..wlen) */
    int64_t off;                          /* OS file offset */
    /* Text layer */
    int enc, errh;
    int ru, rt;                           /* universal newlines on read / translate */
    char rnl[3]; int rnllen;              /* terminator when not universal */
    char wnl[3]; int wnllen;              /* write translation target; 0 = none */
    uint8_t *snap; int64_t snaplen, snapcap; int snap_pendcr, snap_ntail; uint8_t snap_tail[4];
    int have_snap;
    uint8_t *dec; int64_t dlen, dpos, dcap; int64_t dchars_used;
    int pendcr; uint8_t tail[4]; int ntail;
    int eof;
    int telling;
    int rewound;                          /* a write handed the read-ahead back (see ailf_after_write) */
} ailf;

static ailf **ailf_slots; static int64_t ailf_nslots, ailf_capslots;
static int64_t *ailf_freeslots; static int64_t ailf_nfree, ailf_capfree;
static int ailf_atexit_set;

static void ailf_flush_all(void);
static void ailf_atexit(void) { ailf_flush_all(); }

/* A handle is (flags << 40) | (generation << 24) | (slot + 1). The flags outlive the file so that
   an operation on a closed file can still be worded the way CPython words it. */
#define AILF_H_TEXT ((int64_t)1 << 40)
#define AILF_H_RAW  ((int64_t)1 << 41)
#define AILF_H_RD   ((int64_t)1 << 42)
#define AILF_H_WR   ((int64_t)1 << 43)
#define AILF_H_MASK (((int64_t)1 << 40) - 1)
static ailf *ailf_get(int64_t h) {
    if (h <= 0) return NULL;
    int64_t low = h & AILF_H_MASK;
    int64_t idx = (low & 0xFFFFFF) - 1;
    if (idx < 0 || idx >= ailf_nslots) return NULL;
    ailf *f = ailf_slots[idx];
    if (!f || !f->used || (int64_t)f->gen != (low >> 24)) return NULL;
    return f;
}
/* the error for an operation on a closed (or never opened) file; op names the method */
static int ailf_closed_err_op(int64_t h, const char *op) {
    if (!strcmp(op, "flush")) return ailf_fail(AILF_E_VALUE, ((h & AILF_H_WR) && !(h & AILF_H_TEXT) && !(h & AILF_H_RAW)) ? "flush of closed file" : "I/O operation on closed file.");
    if (h & AILF_H_TEXT) return ailf_fail(AILF_E_VALUE, "I/O operation on closed file.");
    if (h & AILF_H_RAW) return ailf_fail(AILF_E_VALUE, "I/O operation on closed file");
    if ((!strcmp(op, "read") || !strcmp(op, "readline")) && !(h & AILF_H_RD)) return ailf_fail(AILF_E_UNSUP, "read");
    if (!strcmp(op, "write") && !(h & AILF_H_WR)) return ailf_fail(AILF_E_UNSUP, "write");
    if (!strcmp(op, "read")) return ailf_fail(AILF_E_VALUE, "read of closed file");
    if (!strcmp(op, "readline")) return ailf_fail(AILF_E_VALUE, "readline of closed file");
    if (!strcmp(op, "write")) return ailf_fail(AILF_E_VALUE, "write to closed file");
    if (!strcmp(op, "seek")) return ailf_fail(AILF_E_VALUE, "seek of closed file");
    if (!strcmp(op, "flush")) return ailf_fail(AILF_E_VALUE, ((h & AILF_H_WR) && !(h & AILF_H_TEXT) && !(h & AILF_H_RAW)) ? "flush of closed file" : "I/O operation on closed file.");
    return ailf_fail(AILF_E_VALUE, "I/O operation on closed file");
}
static ailf *ailf_need_op(int64_t h, const char *op) {
    ailf *f = ailf_get(h);
    if (!f) ailf_closed_err_op(h, op);
    return f;
}
#define ailf_need(h) ailf_need_op((h), "other")

/* ------------------------------------------------------------------ buffered layer (BufferedRandom) */

/* After the queued bytes are written, where the file position is. An O_APPEND write lands at the end
   of the file; CPython's BufferedRandom keeps its own idea of the position when the write followed a
   read (the read-ahead was handed back), so an implicit flush (read, seek, buffer full) keeps the
   logical position there, while an explicit flush() and a plain append-only file follow the OS. */
static void ailf_after_write(ailf *f, int64_t n, int explicit_flush) {
    if (f->appending && f->seekable) {
        if (f->rewound && !explicit_flush) {
            f->off += n;
            int64_t o = (int64_t)AILF_LSEEK(f->fd, f->off, SEEK_SET);
            if (o >= 0) f->off = o;
        } else {
            int64_t o = (int64_t)AILF_LSEEK(f->fd, 0, SEEK_CUR);
            if (o >= 0) f->off = o; else f->off += n;
        }
    } else f->off += n;
    if (explicit_flush) f->rewound = 0;
}
static int ailf_flush_write_ex(ailf *f, int explicit_flush) {
    int64_t done = 0;
    while (done < f->wlen) {
        int64_t k = (int64_t)AILF_WRITE(f->fd, f->buf + done, f->wlen - done);
        if (k < 0) {
            if (errno == EINTR) continue;
            int e = errno;
            f->wlen = 0;
            return ailf_oserr(e, NULL, 0);
        }
        done += k;
    }
    if (f->wlen) ailf_after_write(f, f->wlen, explicit_flush);
    else if (explicit_flush) f->rewound = 0;
    f->wlen = 0;
    return 0;
}
static int ailf_flush_write(ailf *f) { return ailf_flush_write_ex(f, 0); }
/* Give back the read-ahead: the OS offset moves back to the logical position. */
static int ailf_drop_window(ailf *f) {
    if (f->rend > f->rpos) {
        if (f->seekable) {
            int64_t target = f->off - (f->rend - f->rpos);
            int64_t o = (int64_t)AILF_LSEEK(f->fd, target, SEEK_SET);
            if (o < 0) { f->rpos = f->rend = 0; return ailf_oserr(errno, NULL, 0); }
            f->off = o;
        }
    }
    f->rpos = f->rend = 0;
    return 0;
}
static int64_t ailf_logical(const ailf *f) { return f->off - (f->rend - f->rpos) + f->wlen; }

static int ailf_fill(ailf *f) {   /* refill an empty read window; returns bytes available, 0 = EOF, -1 error */
    if (f->wlen && ailf_flush_write(f)) return -1;
    f->rpos = f->rend = 0;
    for (;;) {
        int64_t k = (int64_t)AILF_READ(f->fd, f->buf, f->cap);
        if (k < 0) { if (errno == EINTR) continue; return ailf_oserr(errno, NULL, 0); }
        f->rend = k; f->off += k;
        return k;
    }
}
/* up to n bytes appended to out; loops until n bytes or EOF. n < 0 reads to EOF. */
static int ailf_raw_read(ailf *f, int64_t n, ailf_buf *out) {
    if (f->wlen && ailf_flush_write(f)) return -1;
    int64_t want = n;
    while (n < 0 || want > 0) {
        int64_t avail = f->rend - f->rpos;
        if (avail > 0) {
            int64_t take = (n < 0 || avail < want) ? avail : want;
            if (ailf_buf_put(out, f->buf + f->rpos, take)) return -1;
            f->rpos += take; if (n >= 0) want -= take;
            continue;
        }
        if (n >= 0 && want >= f->cap) {          /* big read: straight into the output */
            if (ailf_buf_reserve(out, want)) return -1;
            int64_t k = (int64_t)AILF_READ(f->fd, out->p + out->n, want);
            if (k < 0) { if (errno == EINTR) continue; return ailf_oserr(errno, NULL, 0); }
            if (k == 0) break;
            out->n += k; want -= k; f->off += k;
            continue;
        }
        int64_t got = ailf_fill(f);
        if (got < 0) return -1;
        if (got == 0) break;
    }
    return 0;
}
/* read1: whatever the window holds (refilling once if empty), at most max bytes */
static int ailf_raw_read1(ailf *f, int64_t max, ailf_buf *out) {
    if (f->wlen && ailf_flush_write(f)) return -1;
    if (f->rend == f->rpos && max > f->cap) {       /* BufferedReader.read1(n) with an empty buffer: one raw read of n bytes */
        if (ailf_buf_reserve(out, max)) return -1;
        for (;;) {
            int64_t k = (int64_t)AILF_READ(f->fd, out->p + out->n, max);
            if (k < 0) { if (errno == EINTR) continue; return ailf_oserr(errno, NULL, 0); }
            out->n += k; f->off += k;
            return 0;
        }
    }
    if (f->rend == f->rpos) { int64_t got = ailf_fill(f); if (got < 0) return -1; if (got == 0) return 0; }
    int64_t avail = f->rend - f->rpos, take = avail < max ? avail : max;
    if (ailf_buf_put(out, f->buf + f->rpos, take)) return -1;
    f->rpos += take;
    return 0;
}
static int ailf_raw_write(ailf *f, const uint8_t *p, int64_t n) {
    if (f->rend > f->rpos) f->rewound = 1;
    if (f->rend > f->rpos || f->rpos) { if (ailf_drop_window(f)) return -1; }
    if (n <= 0) return 0;
    if (n >= f->cap) {
        if (ailf_flush_write(f)) return -1;
        int64_t done = 0;
        while (done < n) {
            int64_t k = (int64_t)AILF_WRITE(f->fd, p + done, n - done);
            if (k < 0) { if (errno == EINTR) continue; return ailf_oserr(errno, NULL, 0); }
            done += k;
        }
        ailf_after_write(f, n, 0);
        return 0;
    }
    if (f->wlen + n > f->cap && ailf_flush_write(f)) return -1;
    memcpy(f->buf + f->wlen, p, (size_t)n); f->wlen += n;
    if (f->unbuffered || f->wlen >= f->cap) return ailf_flush_write(f);
    return 0;
}
static int ailf_raw_seek(ailf *f, int64_t off, int whence, int64_t *result) {
    if (whence == 1 && f->rewound) { off += ailf_logical(f); whence = 0; }   /* logical position, before the flush */
    if (ailf_flush_write(f)) return -1;
    if (whence == 1) { off += ailf_logical(f); whence = 0; }
    int64_t o = (int64_t)AILF_LSEEK(f->fd, off, whence);
    if (o < 0) return ailf_oserr(errno, NULL, 0);     /* a failed seek keeps the read window */
    f->rpos = f->rend = 0;
    f->off = o; *result = o; f->rewound = 0;
    return 0;
}

static void ailf_text_reset(ailf *f) {   /* forget decoded text and the decoder state */
    f->dlen = f->dpos = f->dchars_used = 0;
    f->have_snap = 0; f->snaplen = 0; f->pendcr = 0; f->ntail = 0; f->eof = 0;
}

static void ailf_release(ailf *f) {
    free(f->buf); f->buf = NULL; free(f->name); f->name = NULL;
    free(f->snap); f->snap = NULL; free(f->dec); f->dec = NULL;
    f->snapcap = f->dcap = 0;
}

static void ailf_flush_all(void) {
    for (int64_t i = 0; i < ailf_nslots; i++) {
        ailf *f = ailf_slots[i];
        if (f && f->used && f->wlen) ailf_flush_write(f);
    }
}

/* ------------------------------------------------------------------ opening */

static int ailf_lower_eq(const char *a, const char *b) {
    for (; *a && *b; a++, b++) {
        char x = *a >= 'A' && *a <= 'Z' ? (char)(*a + 32) : *a;
        if (x != *b) return 0;
    }
    return !*a && !*b;
}
/* codecs.lookup() normalisation: lower case, runs of non-alphanumerics (but '.') become '_' */
static int ailf_encoding(const uint8_t *s, int64_t n, int *enc) {
    char t[64]; int64_t o = 0; int punct = 0;
    for (int64_t i = 0; i < n && o < 60; i++) {
        uint8_t c = s[i];
        if ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '.') {
            if (punct && o) t[o++] = '_';
            t[o++] = (char)(c >= 'A' && c <= 'Z' ? c + 32 : c);
            punct = 0;
        } else punct = 1;
    }
    t[o] = 0;
    static const char *const utf8[] = {"utf_8", "u8", "utf", "utf8", "utf8_ucs2", "utf8_ucs4", "cp65001", NULL};
    static const char *const ascii[] = {"ascii", "646", "ansi_x3.4_1968", "ansi_x3_4_1968", "ansi_x3.4_1986",
        "cp367", "csascii", "ibm367", "iso646_us", "iso_646.irv_1991", "iso_ir_6", "us", "us_ascii", NULL};
    static const char *const latin1[] = {"latin_1", "iso8859_1", "iso_8859_1", "iso_8859_1_1987", "iso_ir_100",
        "l1", "latin", "latin1", "cp819", "csisolatin1", "ibm819", "8859", "iso8859", NULL};
    for (int i = 0; utf8[i]; i++) if (!strcmp(t, utf8[i])) { *enc = AILF_ENC_UTF8; return 0; }
    for (int i = 0; ascii[i]; i++) if (!strcmp(t, ascii[i])) { *enc = AILF_ENC_ASCII; return 0; }
    for (int i = 0; latin1[i]; i++) if (!strcmp(t, latin1[i])) { *enc = AILF_ENC_LATIN1; return 0; }
    return -1;
}

static int64_t ailf_register(ailf *tmp) {
    int64_t idx;
    if (ailf_nfree) idx = ailf_freeslots[--ailf_nfree];
    else {
        if (ailf_nslots == ailf_capslots) {
            int64_t cap = ailf_capslots ? ailf_capslots * 2 : 16;
            ailf **q = (ailf **)realloc(ailf_slots, (size_t)cap * sizeof *q);
            if (!q) return ailf_fail(AILF_E_NOMEM, "out of memory");
            ailf_slots = q; ailf_capslots = cap;
        }
        ailf *f = (ailf *)calloc(1, sizeof *f);
        if (!f) return ailf_fail(AILF_E_NOMEM, "out of memory");
        f->gen = 0;
        idx = ailf_nslots++;
        ailf_slots[idx] = f;
    }
    ailf *f = ailf_slots[idx];
    uint32_t gen = f->gen + 1;
    if (gen >= 0x7FFFFF) gen = 1;
    *f = *tmp;
    f->gen = gen; f->used = 1;
    if (!ailf_atexit_set) { ailf_atexit_set = 1; atexit(ailf_atexit); }
    int64_t flags = (f->text ? AILF_H_TEXT : 0) | (f->unbuffered && !f->text ? AILF_H_RAW : 0)
                  | (f->readable ? AILF_H_RD : 0) | (f->writable ? AILF_H_WR : 0);
    return flags | ((int64_t)gen << 24) | (idx + 1);
}

/* open(file, mode, buffering, encoding, errors, newline) with CPython's checks in CPython's order.
   hasenc/haserr/hasnl say whether the argument was given (None otherwise). Returns the handle. */
static int64_t ailf_open(const uint8_t *path, int64_t plen, const uint8_t *mode, int64_t mlen,
                         int64_t buffering, const uint8_t *encn, int64_t encl, int hasenc,
                         const uint8_t *errn, int64_t errl, int haserr,
                         const uint8_t *nl, int64_t nll, int hasnl) {
    int creating = 0, reading = 0, writing = 0, appending = 0, updating = 0, text = 0, binary = 0;
    int seen[256] = {0};
    for (int64_t i = 0; i < mlen; i++) {
        uint8_t c = mode[i];
        if (!strchr("axrwb+t", c) || c == 0 || seen[c]) {
            char rep[200]; ailf_repr_str(rep, sizeof rep, mode, mlen);
            return ailf_failf(AILF_E_VALUE, "invalid mode: %s", rep);
        }
        seen[c] = 1;
        switch (c) { case 'x': creating = 1; break; case 'r': reading = 1; break; case 'w': writing = 1; break;
                     case 'a': appending = 1; break; case '+': updating = 1; break; case 't': text = 1; break;
                     case 'b': binary = 1; break; }
    }
    if (text && binary) return ailf_fail(AILF_E_VALUE, "can't have text and binary mode at once");
    if (creating + reading + writing + appending > 1)
        return ailf_fail(AILF_E_VALUE, "must have exactly one of create/read/write/append mode");
    if (!(creating || reading || writing || appending))
        return ailf_fail(AILF_E_VALUE, "Must have exactly one of create/read/write/append mode and at most one plus");
    if (binary && hasenc) return ailf_fail(AILF_E_VALUE, "binary mode doesn't take an encoding argument");
    if (binary && haserr) return ailf_fail(AILF_E_VALUE, "binary mode doesn't take an errors argument");
    if (binary && hasnl) return ailf_fail(AILF_E_VALUE, "binary mode doesn't take a newline argument");
    ailf_pchar *pp = ailf_path(path, plen);
    if (!pp) return -1;
    int oflags;
    if (reading) oflags = updating ? O_RDWR : O_RDONLY;
    else if (writing) oflags = (updating ? O_RDWR : O_WRONLY) | O_CREAT | O_TRUNC;
    else if (creating) oflags = (updating ? O_RDWR : O_WRONLY) | O_CREAT | O_EXCL;
    else oflags = (updating ? O_RDWR : O_WRONLY) | O_CREAT | O_APPEND;
#ifdef O_CLOEXEC
    oflags |= O_CLOEXEC;
#endif
    int fd;
    for (;;) {
#ifdef _WIN32
        fd = _wopen(pp, oflags | _O_BINARY | _O_NOINHERIT, _S_IREAD | _S_IWRITE);
#else
        fd = open(pp, oflags, 0666);
#endif
        if (fd < 0 && errno == EINTR) continue;
        break;
    }
    free(pp);
    if (fd < 0) return ailf_oserr(errno, path, plen);
    ailf_stat_t st;
    if (AILF_FSTAT(fd, &st) == 0 && AILF_S_ISDIR(st.st_mode)) {
        AILF_CLOSE(fd);
        return ailf_oserr(EISDIR, path, plen);
    }
    ailf tmp;
    memset(&tmp, 0, sizeof tmp);
    tmp.fd = fd; tmp.readable = reading || updating; tmp.writable = !reading || updating;
    tmp.appending = appending; tmp.text = !binary; tmp.telling = 1;
    int64_t pos = (int64_t)AILF_LSEEK(fd, 0, SEEK_CUR);
    tmp.seekable = pos >= 0;
    tmp.off = pos >= 0 ? pos : 0;
    if (appending && tmp.seekable) { int64_t e = (int64_t)AILF_LSEEK(fd, 0, SEEK_END); if (e >= 0) tmp.off = e; }
    int bad = 0; const char *badmsg = NULL;
    if (buffering == 1) { if (!binary) tmp.line_buffered = 1; buffering = -1; }
    if (buffering < -1) { buffering = -1; }
    if (buffering == 0) {
        if (!binary) { bad = 1; badmsg = "can't have unbuffered text I/O"; }
        tmp.unbuffered = 1;
    }
    if (!bad && !binary) {
        /* TextIOWrapper(): the newline check comes first, then the codec */
        if (hasnl && nll != 0 && !(nll == 1 && (nl[0] == '\n' || nl[0] == '\r')) && !(nll == 2 && nl[0] == '\r' && nl[1] == '\n')) {
            char rep[200]; (void)rep;
            ailf_failf(AILF_E_VALUE, "illegal newline value: %.*s", (int)(nll < 200 ? nll : 200), (const char *)nl);
            bad = 2;
        } else {
            tmp.enc = AILF_ENC_UTF8;
            if (hasenc && ailf_encoding(encn, encl, &tmp.enc)) {
                ailf_failf(AILF_E_FATAL, "unsupported encoding '%.*s' (supported: utf-8, ascii, latin-1)", (int)(encl < 100 ? encl : 100), (const char *)encn);
                bad = 2;
            }
        }
        if (!bad) {
            tmp.errh = AILF_ERR_STRICT;
            if (haserr) {
                if (errl == 6 && !memcmp(errn, "strict", 6)) tmp.errh = AILF_ERR_STRICT;
                else if (errl == 7 && !memcmp(errn, "replace", 7)) tmp.errh = AILF_ERR_REPLACE;
                else if (errl == 6 && !memcmp(errn, "ignore", 6)) tmp.errh = AILF_ERR_IGNORE;
                else {
                    ailf_failf(AILF_E_FATAL, "unsupported error handler '%.*s' (supported: strict, replace, ignore)", (int)(errl < 100 ? errl : 100), (const char *)errn);
                    bad = 2;
                }
            }
        }
        if (!bad) {
            if (!hasnl) { tmp.ru = 1; tmp.rt = 1; tmp.wnllen = 0;
#ifdef _WIN32
                tmp.wnl[0] = '\r'; tmp.wnl[1] = '\n'; tmp.wnllen = 2;
#endif
            }
            else if (nll == 0) { tmp.ru = 1; tmp.rt = 0; }
            else { tmp.ru = 0; tmp.rt = 0; memcpy(tmp.rnl, nl, (size_t)nll); tmp.rnllen = (int)nll;
                   if (!(nll == 1 && nl[0] == '\n')) { memcpy(tmp.wnl, nl, (size_t)nll); tmp.wnllen = (int)nll; } }
        }
    }
    if (bad) {
        if (bad == 1) ailf_fail(AILF_E_VALUE, badmsg);
        AILF_CLOSE(fd);
        return -1;
    }
    tmp.cap = AILF_CHUNK;
    tmp.buf = (uint8_t *)malloc((size_t)tmp.cap);
    tmp.name = (uint8_t *)malloc((size_t)plen + 1);
    if (!tmp.buf || !tmp.name) { free(tmp.buf); free(tmp.name); AILF_CLOSE(fd); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
    memcpy(tmp.name, path, (size_t)plen); tmp.namelen = plen;
    int64_t h = ailf_register(&tmp);
    if (h < 0) { free(tmp.buf); free(tmp.name); AILF_CLOSE(fd); }
    return h;
}

static int ailf_close(int64_t h) {
    ailf *f = ailf_get(h);
    if (!f) return 0;                       /* closing a closed file is fine */
    int rc = 0;
    if (f->wlen && ailf_flush_write(f)) rc = -1;
    int saved_kind = ailf_e.kind, saved_err = ailf_e.err; char saved_msg[sizeof ailf_e.msg];
    if (rc) memcpy(saved_msg, ailf_e.msg, sizeof saved_msg);
    if (AILF_CLOSE(f->fd) != 0 && !rc) rc = ailf_oserr(errno, NULL, 0);
    if (rc && saved_kind) { /* keep the first error */ }
    (void)saved_err;
    f->used = 0;
    ailf_release(f);
    if (ailf_nfree == ailf_capfree) {
        int64_t cap = ailf_capfree ? ailf_capfree * 2 : 16;
        int64_t *q = (int64_t *)realloc(ailf_freeslots, (size_t)cap * sizeof *q);
        if (q) { ailf_freeslots = q; ailf_capfree = cap; }
    }
    if (ailf_nfree < ailf_capfree) ailf_freeslots[ailf_nfree++] = (h & 0xFFFFFF) - 1;
    return rc;
}

static int ailf_flush(int64_t h) {
    ailf *f = ailf_need_op(h, "flush"); if (!f) return -1;
    int rc = 0;
    if (f->wlen) rc = ailf_flush_write_ex(f, 1); else f->rewound = 0;
    if (f->text) f->telling = f->seekable;           /* TextIOWrapper.flush() re-enables tell() */
    return rc;
}

/* ------------------------------------------------------------------ binary operations */

static int ailf_need_read(ailf *f, const char *bin_name) {
    if (!f->readable) return ailf_fail(AILF_E_UNSUP, f->text ? "not readable" : f->unbuffered ? "File not open for reading" : bin_name);
    return 0;
}
static int ailf_need_write(ailf *f, const char *bin_name) {
    if (!f->writable) return ailf_fail(AILF_E_UNSUP, f->text ? "not writable" : f->unbuffered ? "File not open for writing" : bin_name);
    return 0;
}

/* read(n): the bytes in out (malloc'd, caller frees out->p), n < 0 reads to EOF */
static int ailf_bread(int64_t h, int64_t n, ailf_buf *out) {
    ailf *f = ailf_need_op(h, "read"); if (!f) return -1;
    if (ailf_need_read(f, "read")) return -1;
    if (n < -1) return ailf_fail(AILF_E_VALUE, "read length must be non-negative or -1");
    out->p = NULL; out->n = out->cap = 0;
    if (n == 0) return 0;
    if (ailf_raw_read(f, n, out)) { ailf_buf_free(out); return -1; }
    return 0;
}
static int ailf_bread1_line(ailf *f, int64_t limit, ailf_buf *out) {
    if (f->wlen && ailf_flush_write(f)) return -1;
    for (;;) {
        if (limit >= 0 && out->n >= limit) return 0;
        if (f->rend == f->rpos) { int64_t got = ailf_fill(f); if (got < 0) return -1; if (got == 0) return 0; }
        int64_t avail = f->rend - f->rpos;
        if (limit >= 0 && avail > limit - out->n) avail = limit - out->n;
        const uint8_t *nlp = (const uint8_t *)memchr(f->buf + f->rpos, '\n', (size_t)avail);
        int64_t take = nlp ? (nlp - (f->buf + f->rpos)) + 1 : avail;
        if (ailf_buf_put(out, f->buf + f->rpos, take)) return -1;
        f->rpos += take;
        if (nlp) return 0;
    }
}
static int ailf_breadline(int64_t h, int64_t limit, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    if (limit == 0 && !(h & AILF_H_TEXT) && (!(h & AILF_H_RD) || (h & AILF_H_RAW))) return 0;   /* IOBase.readline(0) never calls read() */
    ailf *f = ailf_need_op(h, "readline"); if (!f) return -1;
    if (ailf_need_read(f, "read")) return -1;
    if (limit < 0) limit = -1;
    if (limit == 0) return 0;
    if (ailf_bread1_line(f, limit, out)) { ailf_buf_free(out); return -1; }
    return 0;
}
static int64_t ailf_bwrite(int64_t h, const uint8_t *p, int64_t n) {
    ailf *f = ailf_need_op(h, "write"); if (!f) return -1;
    if (ailf_need_write(f, "write")) return -1;
    if (ailf_raw_write(f, p, n)) return -1;
    return n;
}
static int64_t ailf_bseek(int64_t h, int64_t off, int64_t whence) {
    ailf *f = ailf_need_op(h, "seek"); if (!f) return -1;
    if (!f->seekable) return ailf_fail(AILF_E_UNSUP, "File or stream is not seekable.");
    if (whence < 0 || whence > 2) return ailf_failf(AILF_E_VALUE, "whence value %lld unsupported", (long long)whence);
    int64_t r;
    if (ailf_raw_seek(f, off, (int)whence, &r)) return -1;
    return r;
}
static int64_t ailf_btell(int64_t h) {
    ailf *f = ailf_need(h); if (!f) return -1;
    if (!f->seekable) return ailf_oserr(ESPIPE, NULL, 0);
    return ailf_logical(f);
}

/* ------------------------------------------------------------------ text: decoding */

/* bytes -> UTF-8 text, CPython's decoders and their error messages. `src` is decoded as one run;
   an incomplete trailing sequence is left in *used when not final. */
static int ailf_u8_error(int errh, const uint8_t *s, int64_t start, int64_t end, const char *why, ailf_buf *out) {
    if (errh == AILF_ERR_STRICT) {
        if (end - start == 1) return ailf_failf(AILF_E_UDECODE, "'utf-8' codec can't decode byte 0x%02x in position %lld: %s", s[start], (long long)start, why);
        return ailf_failf(AILF_E_UDECODE, "'utf-8' codec can't decode bytes in position %lld-%lld: %s", (long long)start, (long long)(end - 1), why);
    }
    if (errh == AILF_ERR_REPLACE) return ailf_buf_putcp(out, 0xFFFD);
    return 0;
}
static int ailf_decode_stage1(int enc, int errh, const uint8_t *s, int64_t n, int final, ailf_buf *out, int64_t *used) {
    int64_t i = 0;
    if (ailf_buf_reserve(out, n)) return -1;
    if (enc == AILF_ENC_LATIN1) {
        for (; i < n; i++) { if (s[i] < 0x80) { if (ailf_buf_putc(out, s[i])) return -1; } else if (ailf_buf_putcp(out, s[i])) return -1; }
        *used = n; return 0;
    }
    if (enc == AILF_ENC_ASCII) {
        for (; i < n; i++) {
            if (s[i] < 0x80) { if (ailf_buf_putc(out, s[i])) return -1; continue; }
            if (errh == AILF_ERR_STRICT) return ailf_failf(AILF_E_UDECODE, "'ascii' codec can't decode byte 0x%02x in position %lld: ordinal not in range(128)", s[i], (long long)i);
            if (errh == AILF_ERR_REPLACE && ailf_buf_putcp(out, 0xFFFD)) return -1;
        }
        *used = n; return 0;
    }
    while (i < n) {
        uint8_t c = s[i];
        if (c < 0x80) {
            int64_t j = i + 1;
            while (j < n && s[j] < 0x80) j++;
            if (ailf_buf_put(out, s + i, j - i)) return -1;
            i = j; continue;
        }
        int64_t start = i; const char *why; int64_t endpos;
        if (c >= 0xC2 && c <= 0xDF) {
            if (i + 1 >= n) { if (!final) break; why = "unexpected end of data"; endpos = n; goto bad; }
            uint8_t c1 = s[i + 1];
            if ((c1 & 0xC0) != 0x80) { why = "invalid continuation byte"; endpos = start + 1; goto bad; }
            if (ailf_buf_putcp(out, ((uint32_t)(c & 0x1F) << 6) | (c1 & 0x3F))) return -1;
            i += 2; continue;
        }
        if (c >= 0xE0 && c <= 0xEF) {
            if (i + 1 >= n) { if (!final) break; why = "unexpected end of data"; endpos = n; goto bad; }
            uint8_t c1 = s[i + 1];
            int ok1 = c == 0xE0 ? (c1 >= 0xA0 && c1 <= 0xBF) : c == 0xED ? (c1 >= 0x80 && c1 <= 0x9F) : (c1 & 0xC0) == 0x80;
            if (!ok1) { why = "invalid continuation byte"; endpos = start + 1; goto bad; }
            if (i + 2 >= n) { if (!final) break; why = "unexpected end of data"; endpos = n; goto bad; }
            uint8_t c2 = s[i + 2];
            if ((c2 & 0xC0) != 0x80) { why = "invalid continuation byte"; endpos = start + 2; goto bad; }
            if (ailf_buf_putcp(out, ((uint32_t)(c & 0x0F) << 12) | ((uint32_t)(c1 & 0x3F) << 6) | (c2 & 0x3F))) return -1;
            i += 3; continue;
        }
        if (c >= 0xF0 && c <= 0xF4) {
            if (i + 1 >= n) { if (!final) break; why = "unexpected end of data"; endpos = n; goto bad; }
            uint8_t c1 = s[i + 1];
            int ok1 = c == 0xF0 ? (c1 >= 0x90 && c1 <= 0xBF) : c == 0xF4 ? (c1 >= 0x80 && c1 <= 0x8F) : (c1 & 0xC0) == 0x80;
            if (!ok1) { why = "invalid continuation byte"; endpos = start + 1; goto bad; }
            if (i + 2 >= n) { if (!final) break; why = "unexpected end of data"; endpos = n; goto bad; }
            uint8_t c2 = s[i + 2];
            if ((c2 & 0xC0) != 0x80) { why = "invalid continuation byte"; endpos = start + 2; goto bad; }
            if (i + 3 >= n) { if (!final) break; why = "unexpected end of data"; endpos = n; goto bad; }
            uint8_t c3 = s[i + 3];
            if ((c3 & 0xC0) != 0x80) { why = "invalid continuation byte"; endpos = start + 3; goto bad; }
            if (ailf_buf_putcp(out, ((uint32_t)(c & 0x07) << 18) | ((uint32_t)(c1 & 0x3F) << 12) | ((uint32_t)(c2 & 0x3F) << 6) | (c3 & 0x3F))) return -1;
            i += 4; continue;
        }
        why = "invalid start byte"; endpos = start + 1;
    bad:
        if (ailf_u8_error(errh, s, start, endpos, why, out)) return -1;
        if (ailf_e.kind == AILF_E_UDECODE && errh == AILF_ERR_STRICT) return -1;
        i = endpos;
    }
    *used = i;
    return 0;
}


/* stage 2: the incremental newline decoder (_pyio.IncrementalNewlineDecoder). A '\r' that ends
   a chunk is held back (pendcr) until the next chunk shows whether a '\n' follows. */
static int ailf_newline_stage(int ru, int rt, int *pendcr, const uint8_t *t, int64_t m, int final, ailf_buf *out) {
    if (!ru) return ailf_buf_put(out, t, m);
    int prefix = (*pendcr && (m > 0 || final));
    if (prefix) *pendcr = 0;
    int64_t L = m + prefix;
    int hold = 0;
    if (!final && L > 0) { uint8_t last = m > 0 ? t[m - 1] : (uint8_t)'\r'; if (last == '\r') hold = 1; }
    if (hold) *pendcr = 1;
    int64_t Le = L - hold;
    int64_t i = 0;                       /* next index into t */
    if (prefix && Le > 0) {
        if (rt) {
            if (ailf_buf_putc(out, '\n')) return -1;
            if (Le > 1 && t[0] == '\n') i = 1;
        } else if (ailf_buf_putc(out, '\r')) return -1;
    }
    int64_t e = Le - prefix;             /* end index into t */
    if (e < i) e = i;
    if (!rt) return ailf_buf_put(out, t + i, e - i);
    while (i < e) {
        const uint8_t *cr = (const uint8_t *)memchr(t + i, '\r', (size_t)(e - i));
        int64_t stop = cr ? cr - t : e;
        if (ailf_buf_put(out, t + i, stop - i)) return -1;
        if (!cr) break;
        if (ailf_buf_putc(out, '\n')) return -1;
        i = stop + 1;
        if (i < e && t[i] == '\n') i++;
    }
    return 0;
}

/* raw bytes -> `d` (appended): the decoder, then the newline decoder, keeping an incomplete tail
   in the file's decoder state. On error the decoder state is left as it was. */
static int ailf_decode_into(ailf *f, const uint8_t *src, int64_t n, int final, ailf_buf *d) {
    ailf_buf comb = {0}, s1 = {0};
    const uint8_t *in = src; int64_t inn = n;
    int saved_ntail = f->ntail, saved_pend = f->pendcr; uint8_t saved_tail[4]; memcpy(saved_tail, f->tail, 4);
    if (f->ntail) {
        if (ailf_buf_put(&comb, f->tail, f->ntail) || ailf_buf_put(&comb, src, n)) { ailf_buf_free(&comb); return -1; }
        in = comb.p; inn = comb.n; f->ntail = 0;
    }
    int64_t used = 0;
    if (ailf_decode_stage1(f->enc, f->errh, in, inn, final, &s1, &used)) {
        f->ntail = saved_ntail; memcpy(f->tail, saved_tail, 4); f->pendcr = saved_pend;
        ailf_buf_free(&comb); ailf_buf_free(&s1); return -1;
    }
    if (used < inn) { f->ntail = (int)(inn - used); memcpy(f->tail, in + used, (size_t)f->ntail); }
    int rc = ailf_newline_stage(f->ru, f->rt, &f->pendcr, s1.p ? s1.p : (const uint8_t *)"", s1.n, final, d);
    ailf_buf_free(&comb); ailf_buf_free(&s1);
    return rc;
}
static void ailf_set_dec(ailf *f, ailf_buf *d) {   /* the decoded text of the current chunk */
    free(f->dec);
    f->dec = d->p; f->dlen = d->n; f->dcap = d->cap; f->dpos = 0; f->dchars_used = 0;
}
static void ailf_decoder_reset(ailf *f) { f->pendcr = 0; f->ntail = 0; }
static void ailf_clear_decoded(ailf *f) { f->dlen = f->dpos = f->dchars_used = 0; f->have_snap = 0; f->snaplen = 0; }

/* TextIOWrapper._read_chunk: the next chunk, decoded, replaces the used-up one.
   1 = data, 0 = end of file, -1 = error (the previous chunk and snapshot are left alone). */
static int ailf_read_chunk(ailf *f, int64_t hint) {
    ailf_buf in = {0}, d = {0};
    int64_t want = hint > AILF_CHUNK ? hint : AILF_CHUNK;
    int tail_n = f->ntail; uint8_t tail[4]; memcpy(tail, f->tail, 4);
    int pend = f->pendcr;
    if (ailf_raw_read1(f, want, &in)) { ailf_buf_free(&in); return -1; }
    int final = in.n == 0;
    if (ailf_decode_into(f, in.p ? in.p : (const uint8_t *)"", in.n, final, &d)) { ailf_buf_free(&in); ailf_buf_free(&d); return -1; }
    ailf_set_dec(f, &d);
    f->eof = final;
    if (f->telling) {
        ailf_buf sb = {f->snap, 0, f->snapcap};
        if (ailf_buf_put(&sb, tail, tail_n) || ailf_buf_put(&sb, in.p, in.n)) { f->snap = sb.p; f->snapcap = sb.cap; ailf_buf_free(&in); return -1; }
        f->snap = sb.p; f->snapcap = sb.cap; f->snaplen = sb.n;
        f->snap_pendcr = pend; f->have_snap = 1;
    }
    ailf_buf_free(&in);
    return final ? 0 : 1;
}

static int64_t ailf_count_chars(const uint8_t *p, int64_t n) {
    int64_t c = 0;
    for (int64_t i = 0; i < n; i++) c += (p[i] & 0xC0) != 0x80;
    return c;
}
/* byte length of the first `chars` characters of p[0..n) */
static int64_t ailf_bytes_of_chars(const uint8_t *p, int64_t n, int64_t chars) {
    int64_t i = 0;
    while (i < n && chars > 0) {
        i++;
        while (i < n && (p[i] & 0xC0) == 0x80) i++;
        chars--;
    }
    return i;
}

static int ailf_text_ok(ailf *f) {
    if (!f->text) return ailf_fail(AILF_E_UNSUP, "text operation on a binary file");
    return 0;
}

/* read(n) of a text file: UTF-8 in out. n < 0 reads everything */
static int ailf_tread(int64_t h, int64_t n, ailf_buf *out) {
    ailf *f = ailf_need(h); if (!f) return -1;
    if (ailf_text_ok(f) || ailf_need_read(f, "read")) return -1;
    out->p = NULL; out->n = out->cap = 0;
    if (f->wlen && ailf_flush_write(f)) return -1;
    if (n < 0) {
        if (ailf_buf_put(out, f->dec + f->dpos, f->dlen - f->dpos)) goto fail;
        f->dpos = f->dlen;
        ailf_buf all = {0}, d = {0};
        if (ailf_raw_read(f, -1, &all)) { ailf_buf_free(&all); goto fail; }
        int rc = ailf_decode_into(f, all.p ? all.p : (const uint8_t *)"", all.n, 1, &d);
        ailf_buf_free(&all);
        if (rc) { ailf_buf_free(&d); goto fail; }
        if (ailf_buf_put(out, d.p, d.n)) { ailf_buf_free(&d); goto fail; }
        ailf_buf_free(&d);
        if (f->have_snap) ailf_clear_decoded(f);
        return 0;
    }
    int64_t remaining = n;
    for (;;) {
        int64_t availb = f->dlen - f->dpos;
        if (availb > 0 && remaining > 0) {
            int64_t take = ailf_bytes_of_chars(f->dec + f->dpos, availb, remaining);
            remaining -= ailf_count_chars(f->dec + f->dpos, take);
            if (ailf_buf_put(out, f->dec + f->dpos, take)) goto fail;
            f->dpos += take;
        }
        if (remaining <= 0) break;
        int got = ailf_read_chunk(f, remaining);
        if (got < 0) goto fail;
        if (got == 0) {                      /* EOF: the final decode may still have produced text */
            int64_t availe = f->dlen - f->dpos;
            if (availe > 0) {
                int64_t take = ailf_bytes_of_chars(f->dec + f->dpos, availe, remaining);
                if (ailf_buf_put(out, f->dec + f->dpos, take)) goto fail;
                f->dpos += take;
            }
            break;
        }
    }
    return 0;
fail:
    ailf_buf_free(out);
    return -1;
}

/* the end of the first line of seg[0..m): length including the terminator, or -1 when the line
   continues into the next chunk. `acc` is what the line holds so far (for "\r\n" across chunks). */
static int64_t ailf_find_eol(const ailf *f, const uint8_t *seg, int64_t m, const ailf_buf *acc, int eof) {
    if (f->ru) {
        if (f->rt) {
            const uint8_t *p = (const uint8_t *)memchr(seg, '\n', (size_t)m);
            return p ? (p - seg) + 1 : -1;
        }
        for (int64_t i = 0; i < m; i++) {
            if (seg[i] == '\n') return i + 1;
            if (seg[i] == '\r') {
                if (i + 1 < m && seg[i + 1] == '\n') return i + 2;
                return i + 1;       /* a CR that ends the buffer is a line end: the decoder holds back a CR that a LF could follow */
            }
        }
        return -1;
    }
    if (f->rnllen == 1) {
        const uint8_t *p = (const uint8_t *)memchr(seg, (unsigned char)f->rnl[0], (size_t)m);
        return p ? (p - seg) + 1 : -1;
    }
    /* "\r\n" */
    if (acc && acc->n > 0 && acc->p[acc->n - 1] == '\r' && m > 0 && seg[0] == '\n') return 1;
    for (int64_t i = 0; i + 1 < m; i++) if (seg[i] == '\r' && seg[i + 1] == '\n') return i + 2;
    return -1;
}

/* readline(limit) of a text file */
static int ailf_treadline(int64_t h, int64_t limit, ailf_buf *out) {
    ailf *f = ailf_need(h); if (!f) return -1;
    if (ailf_text_ok(f) || ailf_need_read(f, "read")) return -1;
    out->p = NULL; out->n = out->cap = 0;
    if (limit < 0) limit = -1;
    if (f->wlen && ailf_flush_write(f)) return -1;
    int64_t chars = 0;
    for (;;) {
        /* the C implementation fetches a chunk first, even for readline(0) */
        while (f->dlen - f->dpos == 0) {
            int got = ailf_read_chunk(f, 0);
            if (got < 0) goto fail;
            if (got == 0 && f->dlen - f->dpos == 0) { ailf_clear_decoded(f); return 0; }     /* end of file */
            if (got == 0) break;
        }
        int64_t availb = f->dlen - f->dpos;
        if (availb > 0) {
            const uint8_t *seg = f->dec + f->dpos;
            int64_t eol = ailf_find_eol(f, seg, availb, out, f->eof);
            int64_t take = eol >= 0 ? eol : availb;
            int done = eol >= 0;
            if (limit >= 0) {
                int64_t room = limit - chars;
                int64_t cut = ailf_bytes_of_chars(seg, take, room);
                if (cut < take) { take = cut; done = 1; }              /* limit reached inside the line */
                else if (!done && chars + ailf_count_chars(seg, take) >= limit) done = 1;
            }
            if (ailf_buf_put(out, seg, take)) goto fail;
            chars += ailf_count_chars(seg, take);
            f->dpos += take;
            if (done) return 0;
            continue;
        }
    }
fail:
    ailf_buf_free(out);
    return -1;
}

/* ---- encoding for write() */

static int ailf_encode_error(int enc, int64_t pos, int64_t endpos, uint32_t first, int64_t count) {
    const char *name = enc == AILF_ENC_ASCII ? "ascii" : "latin-1";
    int lim = enc == AILF_ENC_ASCII ? 128 : 256;
    if (count == 1) {
        char c[16];
        if (first < 0x100) snprintf(c, sizeof c, "\\x%02x", first);
        else if (first < 0x10000) snprintf(c, sizeof c, "\\u%04x", first);
        else snprintf(c, sizeof c, "\\U%08x", first);
        return ailf_failf(AILF_E_UENCODE, "'%s' codec can't encode character '%s' in position %lld: ordinal not in range(%d)", name, c, (long long)pos, lim);
    }
    return ailf_failf(AILF_E_UENCODE, "'%s' codec can't encode characters in position %lld-%lld: ordinal not in range(%d)", name, (long long)pos, (long long)(endpos - 1), lim);
}
static uint32_t ailf_cp_at(const uint8_t *s, int64_t n, int64_t i, int *w) {
    uint8_t c = s[i];
    if (c < 0x80) { *w = 1; return c; }
    int k = c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
    if (i + k > n) k = (int)(n - i);
    *w = k;
    uint32_t cp = k == 2 ? c & 0x1Fu : k == 3 ? c & 0x0Fu : c & 0x07u;
    for (int j = 1; j < k; j++) cp = (cp << 6) | (s[i + j] & 0x3Fu);
    return cp;
}
static int ailf_encode_text(ailf *f, const uint8_t *s, int64_t n, ailf_buf *out) {
    if (f->enc == AILF_ENC_UTF8) return ailf_buf_put(out, s, n);
    uint32_t lim = f->enc == AILF_ENC_ASCII ? 0x80 : 0x100;
    int64_t ci = 0;
    for (int64_t i = 0; i < n;) {
        int w; uint32_t cp = ailf_cp_at(s, n, i, &w);
        if (cp < lim) { if (ailf_buf_putc(out, (uint8_t)cp)) return -1; i += w; ci++; continue; }
        int64_t j = i, run = 0; uint32_t first = cp;
        while (j < n) { int w2; uint32_t c2 = ailf_cp_at(s, n, j, &w2); if (c2 < lim) break; j += w2; run++; }
        if (f->errh == AILF_ERR_STRICT) return ailf_encode_error(f->enc, ci, ci + run, first, run);
        if (f->errh == AILF_ERR_REPLACE) for (int64_t k = 0; k < run; k++) if (ailf_buf_putc(out, '?')) return -1;
        i = j; ci += run;
    }
    return 0;
}

/* write(s) of a text file; returns the number of characters */
static int64_t ailf_twrite(int64_t h, const uint8_t *s, int64_t n) {
    ailf *f = ailf_need(h); if (!f) return -1;
    if (ailf_text_ok(f) || ailf_need_write(f, "write")) return -1;
    int64_t chars = ailf_count_chars(s, n);
    ailf_buf tr = {0}, enc = {0};
    const uint8_t *src = s; int64_t srcn = n;
    int has_nl = memchr(s, '\n', (size_t)n) != NULL;
    if (f->wnllen && has_nl) {
        for (int64_t i = 0; i < n; i++) {
            if (s[i] == '\n') { if (ailf_buf_put(&tr, (const uint8_t *)f->wnl, f->wnllen)) { ailf_buf_free(&tr); return -1; } }
            else if (ailf_buf_putc(&tr, s[i])) { ailf_buf_free(&tr); return -1; }
        }
        src = tr.p; srcn = tr.n;
    }
    if (ailf_encode_text(f, src ? src : (const uint8_t *)"", srcn, &enc)) { ailf_buf_free(&tr); ailf_buf_free(&enc); return -1; }
    int rc = ailf_raw_write(f, enc.p ? enc.p : (const uint8_t *)"", enc.n);
    int line_flush = f->line_buffered && (has_nl || memchr(s, '\r', (size_t)n));
    ailf_buf_free(&tr); ailf_buf_free(&enc);
    if (rc) return -1;
    if (line_flush && ailf_flush_write(f)) return -1;
    if (f->have_snap) { f->dlen = f->dpos = f->dchars_used = 0; f->have_snap = 0; f->snaplen = 0; }
    ailf_decoder_reset(f);                /* TextIOWrapper.write: stale decoded text goes only when a snapshot exists */
    return chars;
}

/* ---- tell / seek of a text file */

/* output characters produced by decoding the first L bytes of the snapshot (not final) */
static int64_t ailf_snap_chars(const ailf *f, int64_t L) {
    ailf_buf s1 = {0}, d = {0}; int64_t used = 0; int pend = f->snap_pendcr;
    ailf tmp; memset(&tmp, 0, sizeof tmp);
    tmp.enc = f->enc; tmp.errh = f->errh;          /* the same handler as the real decode (ignore drops bytes) */
    if (ailf_decode_stage1(tmp.enc, tmp.errh, f->snap, L, 0, &s1, &used)) { ailf_buf_free(&s1); return -1; }
    if (ailf_newline_stage(f->ru, f->rt, &pend, s1.p ? s1.p : (const uint8_t *)"", s1.n, 0, &d)) { ailf_buf_free(&s1); ailf_buf_free(&d); return -1; }
    int64_t c = ailf_count_chars(d.p ? d.p : (const uint8_t *)"", d.n);
    ailf_buf_free(&s1); ailf_buf_free(&d);
    return c;
}
static int64_t ailf_ttell(int64_t h) {
    ailf *f = ailf_need(h); if (!f) return -1;
    if (ailf_text_ok(f)) return -1;
    if (!f->seekable) return ailf_fail(AILF_E_UNSUP, "underlying stream is not seekable");
    if (!f->telling) return ailf_fail(AILF_E_OS, "telling position disabled by next() call");
    if (f->wlen && ailf_flush_write(f)) return -1;
    int64_t pos = ailf_logical(f);
    if (!f->have_snap) return pos;           /* (pyio: decoded text must be empty here) */
    int64_t used_chars = ailf_count_chars(f->dec, f->dpos);
    int64_t start = pos - f->snaplen;
    if (used_chars == 0) return start;
    /* smallest prefix of the snapshot whose decoding yields `used_chars` characters */
    int64_t lo = 0, hi = f->snaplen;
    while (lo < hi) {
        int64_t mid = lo + (hi - lo) / 2;
        int64_t c = ailf_snap_chars(f, mid);
        if (c < 0) return -1;
        if (c >= used_chars) hi = mid; else lo = mid + 1;
    }
    int64_t L = lo;
    int64_t c = ailf_snap_chars(f, L);
    if (c > used_chars && L > 0) L--;     /* the byte that released a held CR also produced the next character */
    return start + L;
}
static int64_t ailf_tseek(int64_t h, int64_t off, int64_t whence) {
    ailf *f = ailf_need(h); if (!f) return -1;
    if (ailf_text_ok(f)) return -1;
    if (!f->seekable) return ailf_fail(AILF_E_UNSUP, "underlying stream is not seekable");
    if (whence == 1) {
        if (off != 0) return ailf_fail(AILF_E_UNSUP, "can't do nonzero cur-relative seeks");
        return ailf_ttell(h);
    }
    if (whence == 2) {
        if (off != 0) return ailf_fail(AILF_E_UNSUP, "can't do nonzero end-relative seeks");
        if (f->wlen && ailf_flush_write(f)) return -1;
        f->telling = f->seekable;
        int64_t r;
        if (ailf_raw_seek(f, 0, 2, &r)) return -1;
        ailf_clear_decoded(f); ailf_decoder_reset(f);
        return r;
    }
    if (whence != 0) return ailf_failf(AILF_E_VALUE, "invalid whence (%lld, should be 0, 1 or 2)", (long long)whence);
    if (off < 0) return ailf_failf(AILF_E_VALUE, "negative seek position %lld", (long long)off);
    if (f->wlen && ailf_flush_write(f)) return -1;
    f->telling = f->seekable;
    int64_t r;
    if (ailf_raw_seek(f, off, 0, &r)) return -1;
    ailf_clear_decoded(f); ailf_decoder_reset(f);
    f->have_snap = 1; f->snaplen = 0; f->snap_pendcr = 0;     /* the C seek leaves a snapshot (flags 0, no bytes) behind */
    return r;
}
/* readline used by `for line in f`: tell() is disabled until the iteration ends */
static int ailf_tnext(int64_t h, ailf_buf *out) {
    ailf *f = ailf_need(h); if (!f) return -1;
    f->telling = 0;
    if (ailf_treadline(h, -1, out)) return -1;
    if (out->n == 0) { f->have_snap = 0; f->snaplen = 0; f->telling = f->seekable; }   /* StopIteration */
    return 0;
}
static int ailf_bnext(int64_t h, ailf_buf *out) { return ailf_breadline(h, -1, out); }

/* readable()/writable() of a closed buffered file that cannot do it are still False (IOBase's
   answer); a raw file or one that could asks the closed descriptor and fails */
static int64_t ailf_readable(int64_t h) {
    ailf *f = ailf_get(h); if (f) return f->readable;
    if (!(h & AILF_H_RAW) && !(h & AILF_H_RD)) return 0;
    return ailf_fail(AILF_E_VALUE, "I/O operation on closed file");
}
static int64_t ailf_writable(int64_t h) {
    ailf *f = ailf_get(h); if (f) return f->writable;
    if (!(h & AILF_H_RAW) && !(h & AILF_H_WR)) return 0;
    return ailf_fail(AILF_E_VALUE, "I/O operation on closed file");
}
static int64_t ailf_seekable(int64_t h) {
    ailf *f = ailf_get(h); if (f) return f->seekable;
    return ailf_fail(AILF_E_VALUE, "I/O operation on closed file");
}

/* ================================================================== os */

/* The OS error of the call that just failed, shaped for the adapter (errno on POSIX; on Windows
   the CRT already sets errno for the wide-character calls used here, the few WinAPI calls map
   GetLastError() through ailf_winerr()). */
#ifdef _WIN32
static int ailf_winerr(DWORD e) {
    switch (e) {
    case ERROR_FILE_NOT_FOUND: case ERROR_PATH_NOT_FOUND: case ERROR_INVALID_DRIVE: return ENOENT;
    case ERROR_ACCESS_DENIED: case ERROR_SHARING_VIOLATION: case ERROR_WRITE_PROTECT: return EACCES;
    case ERROR_ALREADY_EXISTS: case ERROR_FILE_EXISTS: return EEXIST;
    case ERROR_DIR_NOT_EMPTY: return ENOTEMPTY;
    case ERROR_DIRECTORY: return ENOTDIR;
    case ERROR_NOT_SAME_DEVICE: return EXDEV;
    case ERROR_NOT_ENOUGH_MEMORY: case ERROR_OUTOFMEMORY: return ENOMEM;
    default: return EINVAL;
    }
}
#endif

static int64_t ailf_getcwd(ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
#ifdef _WIN32
    wchar_t *w = _wgetcwd(NULL, 0);
    if (!w) return ailf_oserr(errno, NULL, 0);
    int rc = ailf_put_wide(out, w);
    free(w);
    if (rc) return -1;
#else
    size_t cap = 256;
    for (;;) {
        char *b = (char *)malloc(cap);
        if (!b) return ailf_fail(AILF_E_NOMEM, "out of memory");
        if (getcwd(b, cap)) { ailf_buf_put(out, (const uint8_t *)b, (int64_t)strlen(b)); free(b); break; }
        int e = errno; free(b);
        if (e == ERANGE) { cap *= 2; continue; }
        return ailf_oserr(e, NULL, 0);
    }
#endif
    return 0;
}

static int ailf_chdir(const uint8_t *p, int64_t n) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    int rc = _wchdir(pp);
#else
    int rc = chdir(pp);
#endif
    free(pp);
    return rc ? ailf_oserr(errno, p, n) : 0;
}

/* The entries of a directory in the order the OS returns them (what os.listdir / os.scandir give).
   Output: one record per entry, "<type><name>", records separated by NUL; type 'd' for a directory
   (symlinks to directories included, as DirEntry.is_dir() answers), 'f' otherwise. */
static int ailf_scandir(const uint8_t *p, int64_t n, ailf_buf *out, int with_type) {
    out->p = NULL; out->n = out->cap = 0;
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    size_t wl = wcslen(pp);
    wchar_t *pat = (wchar_t *)malloc((wl + 3) * sizeof(wchar_t));
    if (!pat) { free(pp); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
    memcpy(pat, pp, wl * sizeof(wchar_t));
    size_t pl = wl;
    if (pl && pat[pl - 1] != L'\\' && pat[pl - 1] != L'/' && pat[pl - 1] != L':') pat[pl++] = L'\\';
    pat[pl++] = L'*'; pat[pl] = 0;
    WIN32_FIND_DATAW fd;
    HANDLE hf = FindFirstFileW(pat, &fd);
    free(pat);
    if (hf == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError(); free(pp);
        return ailf_oserr(e == ERROR_DIRECTORY ? ENOTDIR : ailf_winerr(e), p, n);
    }
    do {
        if (!wcscmp(fd.cFileName, L".") || !wcscmp(fd.cFileName, L"..")) continue;
        int isdir = (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (out->n && ailf_buf_putc(out, 0)) { FindClose(hf); free(pp); ailf_buf_free(out); return -1; }
        if (with_type && ailf_buf_putc(out, isdir ? 'd' : 'f')) { FindClose(hf); free(pp); ailf_buf_free(out); return -1; }
        if (ailf_put_wide(out, fd.cFileName)) { FindClose(hf); free(pp); ailf_buf_free(out); return -1; }
    } while (FindNextFileW(hf, &fd));
    FindClose(hf);
    free(pp);
    return 0;
#else
    DIR *d = opendir(pp);
    if (!d) { free(pp); return ailf_oserr(errno, p, n); }
    size_t pl = strlen(pp);
    for (;;) {
        errno = 0;
        struct dirent *e = readdir(d);
        if (!e) { if (errno) { int er = errno; closedir(d); free(pp); ailf_buf_free(out); return ailf_oserr(er, p, n); } break; }
        const char *name = e->d_name;
        if (!strcmp(name, ".") || !strcmp(name, "..")) continue;
        if (out->n && ailf_buf_putc(out, 0)) { closedir(d); free(pp); ailf_buf_free(out); return -1; }
        if (with_type) {
            char kind = 'f';
            size_t nl = strlen(name);
            char *full = (char *)malloc(pl + nl + 2);
            if (full) {
                memcpy(full, pp, pl); full[pl] = '/'; memcpy(full + pl + 1, name, nl + 1);
                struct stat st;
                if (stat(full, &st) == 0 && S_ISDIR(st.st_mode)) kind = 'd';
                free(full);
            }
            if (ailf_buf_putc(out, (uint8_t)kind)) { closedir(d); free(pp); ailf_buf_free(out); return -1; }
        }
        if (ailf_buf_put(out, (const uint8_t *)name, (int64_t)strlen(name))) {
            closedir(d); free(pp); ailf_buf_free(out); return -1;
        }
    }
    closedir(d);
    free(pp);
    return 0;
#endif
}

/* 0 when the path does not exist (or cannot be examined), 1 regular file, 2 directory,
   3 other; follow=0 looks at a symlink itself (4 = symlink). */
static int64_t ailf_stat_kind(const uint8_t *p, int64_t n, int follow) {
    ailf_pchar *pp = ailf_path(p, n);
    if (!pp) { return 0; }                     /* os.path.exists() swallows ValueError */
#ifdef _WIN32
    struct _stat64 st;
    int rc = _wstat64(pp, &st);
    free(pp);
    if (rc) return 0;
    (void)follow;
    return AILF_S_ISDIR(st.st_mode) ? 2 : AILF_S_ISREG(st.st_mode) ? 1 : 3;
#else
    struct stat st;
    int rc = follow ? stat(pp, &st) : lstat(pp, &st);
    free(pp);
    if (rc) return 0;
    if (!follow && S_ISLNK(st.st_mode)) return 4;
    return S_ISDIR(st.st_mode) ? 2 : S_ISREG(st.st_mode) ? 1 : 3;
#endif
}
static int64_t ailf_getsize(const uint8_t *p, int64_t n) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    struct _stat64 st; int rc = _wstat64(pp, &st);
#else
    struct stat st; int rc = stat(pp, &st);
#endif
    free(pp);
    if (rc) return ailf_oserr(errno, p, n);
    return (int64_t)st.st_size;
}

static int ailf_mkdir(const uint8_t *p, int64_t n, int64_t mode) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    (void)mode; int rc = _wmkdir(pp);
#else
    int rc = mkdir(pp, (mode_t)mode);
#endif
    free(pp);
    return rc ? ailf_oserr(errno, p, n) : 0;
}
static int ailf_rmdir(const uint8_t *p, int64_t n) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    int rc = _wrmdir(pp);
#else
    int rc = rmdir(pp);
#endif
    free(pp);
    return rc ? ailf_oserr(errno, p, n) : 0;
}
static int ailf_chmod(const uint8_t *p, int64_t n, int64_t mode) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    int rc = _wchmod(pp, (int)mode);
#else
    int rc = chmod(pp, (mode_t)mode);
#endif
    free(pp);
    return rc ? ailf_oserr(errno, p, n) : 0;
}
static int ailf_unlink(const uint8_t *p, int64_t n) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    int rc = _wunlink(pp);
#else
    int rc = unlink(pp);
#endif
    free(pp);
    return rc ? ailf_oserr(errno, p, n) : 0;
}
static int ailf_rename(const uint8_t *a, int64_t an, const uint8_t *b, int64_t bn, int replace) {
    ailf_pchar *pa = ailf_path(a, an); if (!pa) return -1;
    ailf_pchar *pb = ailf_path(b, bn); if (!pb) { free(pa); return -1; }
#ifdef _WIN32
    int rc;
    if (replace) { rc = MoveFileExW(pa, pb, MOVEFILE_REPLACE_EXISTING) ? 0 : -1; if (rc) errno = ailf_winerr(GetLastError()); }
    else rc = _wrename(pa, pb);
#else
    (void)replace;
    int rc = rename(pa, pb);
#endif
    free(pa); free(pb);
    return rc ? ailf_oserr2(errno, a, an, b, bn) : 0;
}

/* os.environ / os.getenv: 1 and the value when set, 0 when not */
static int ailf_getenv(const uint8_t *k, int64_t kn, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    if (kn == 0 || memchr(k, '=', (size_t)kn)) return 0;
    ailf_pchar *kp = ailf_path(k, kn); if (!kp) return 0;
#ifdef _WIN32
    const wchar_t *v = _wgetenv(kp);
    free(kp);
    if (!v) return 0;
    if (ailf_put_wide(out, v)) return -1;
    return 1;
#else
    const char *v = getenv(kp);
    free(kp);
    if (!v) return 0;
    if (ailf_buf_put(out, (const uint8_t *)v, (int64_t)strlen(v))) return -1;
    return 1;
#endif
}
static int ailf_setenv(const uint8_t *k, int64_t kn, const uint8_t *v, int64_t vn) {
    if (kn == 0 || memchr(k, '=', (size_t)kn)) return ailf_oserr(EINVAL, NULL, 0);
    ailf_pchar *kp = ailf_path(k, kn); if (!kp) return -1;
    ailf_pchar *vp = ailf_path(v, vn); if (!vp) { free(kp); return -1; }
#ifdef _WIN32
    int rc = _wputenv_s(kp, vp);
#else
    int rc = setenv(kp, vp, 1);
#endif
    free(kp); free(vp);
    return rc ? ailf_oserr(errno ? errno : EINVAL, NULL, 0) : 0;
}
static int ailf_unsetenv(const uint8_t *k, int64_t kn) {
    if (kn == 0 || memchr(k, '=', (size_t)kn)) return ailf_oserr(EINVAL, NULL, 0);
    ailf_pchar *kp = ailf_path(k, kn); if (!kp) return -1;
#ifdef _WIN32
    ailf_pchar *vp = ailf_path((const uint8_t *)"", 0);
    int rc = _wputenv_s(kp, vp); free(vp);
#else
    int rc = unsetenv(kp);
#endif
    free(kp);
    return rc ? ailf_oserr(errno ? errno : EINVAL, NULL, 0) : 0;
}

#endif /* AILFILE_CORE_H */
