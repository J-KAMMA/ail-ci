/* ailpath_core.h -- the C that pathlib (stage G10) adds to ailfile_core.h: three small primitives. It is
   embedded only into a program that reaches one of them, so every other program keeps its C byte for byte. */
#ifndef AILPATH_CORE_H
#define AILPATH_CORE_H

/* errno of stat(path): 0 when it works, -1 for a path CPython refuses with ValueError (embedded NUL) */
static int64_t ailf_stat_errno(const uint8_t *p, int64_t n) {
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    struct _stat64 st; int rc = _wstat64(pp, &st);
#else
    struct stat st; int rc = stat(pp, &st);
#endif
    int e = rc ? (errno ? errno : EIO) : 0;
    free(pp);
    return e;
}
/* os.readlink: the target of a symbolic link (EINVAL when the path is not one). Not built on Windows. */
static int ailf_readlink(const uint8_t *p, int64_t n, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ailf_pchar *pp = ailf_path(p, n); if (!pp) return -1;
#ifdef _WIN32
    free(pp);
    return ailf_oserr(EINVAL, p, n);
#else
    size_t cap = 256;
    for (;;) {
        char *b = (char *)malloc(cap);
        if (!b) { free(pp); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
        ssize_t r = readlink(pp, b, cap);
        if (r < 0) { int e = errno; free(b); free(pp); return ailf_oserr(e, p, n); }
        if ((size_t)r < cap) {
            int bad = ailf_buf_put(out, (const uint8_t *)b, (int64_t)r);
            free(b);
            if (bad) { free(pp); return -1; }
            break;
        }
        free(b); cap *= 2;
    }
    free(pp);
    return 0;
#endif
}
/* repr() of a str, as a buffer (pathlib's PosixPath('...') and its ValueError messages) */
static int ailf_repr_buf(const uint8_t *s, int64_t n, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    int64_t need = ailf_repr_str(NULL, 0, s, n);
    if (ailf_buf_reserve(out, need + 1)) return -1;
    ailf_repr_str((char *)out->p, need + 1, s, n);
    out->n = need;
    return 0;
}

#endif /* AILPATH_CORE_H */
