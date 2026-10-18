/* ailproc_core.h -- the process layer under subprocess.run (stage G8).

   Plain C, no AIL types: it sits after ailfile_core.h in the same translation unit (it uses
   ailf_buf, ailf_e and the decoders there) and is shared by the typed runtime and the general
   runtime (filert.py holds the adapters). A program carries it only when it calls subprocess.

   A request is built with ailp_begin / ailp_add_arg / ailp_set_cwd / ailp_env_* / ailp_input_*,
   then ailp_run runs it to the end (spawn, feed stdin, drain stdout and stderr, wait, kill on a
   timeout) and returns a result handle. The result's bytes are decoded on demand
   (ailp_out_text) with CPython's wording of the decode errors, universal newlines included.
   CalledProcessError / TimeoutExpired keep their attributes in one "last error" record that the
   handler's `e.returncode` / `e.cmd` / `e.stdout` read.

   POSIX: fork + execve with an error pipe (the failing stage tells whether the file name in the
   OSError is the program or the cwd, as _posixsubprocess does), poll over the pipes (no deadlock on
   large output), waitpid with CPython's back-off while a timeout runs.
   Windows: CreateProcessW with the command line of subprocess.list2cmdline, inheritable pipe
   ends, one reader thread per output pipe and one writer thread for stdin, WaitForSingleObject. */
#ifndef AILPROC_CORE_H
#define AILPROC_CORE_H

#ifndef _WIN32
#include <sys/wait.h>
#include <poll.h>
#include <signal.h>
#include <time.h>
#include <sys/syscall.h>
#endif
#include <math.h>

/* ------------------------------------------------------------------ the request */

typedef struct {
    ailf_buf argv; int64_t nargs;            /* elements back to back, each NUL-terminated */
    ailf_buf cwd; int hascwd;
    ailf_buf env; int64_t nenv; int hasenv;  /* "key=value" NUL-terminated */
    ailf_buf input; int hasinput;
} ailp_req_t;
static ailp_req_t ailp_req;

enum { AILP_PIPE_OUT = 1, AILP_PIPE_ERR = 2, AILP_ERR_TO_OUT = 4, AILP_NULL_OUT = 8, AILP_NULL_ERR = 16,
       AILP_TIMEOUT = 32, AILP_NULL_IN = 64, AILP_PIPE_IN = 128 };

static int ailp_begin(void) {
    ailf_buf_free(&ailp_req.argv); ailf_buf_free(&ailp_req.cwd); ailf_buf_free(&ailp_req.env);
    ailf_buf_free(&ailp_req.input);
    memset(&ailp_req, 0, sizeof ailp_req);
    return 0;
}
static int ailp_add_arg(const uint8_t *s, int64_t n) {
    if (n && memchr(s, 0, (size_t)n)) return ailf_fail(AILF_E_VALUE, "embedded null byte");
    if (ailf_buf_put(&ailp_req.argv, s, n) || ailf_buf_putc(&ailp_req.argv, 0)) return -1;
    ailp_req.nargs++;
    return 0;
}
static int ailp_set_cwd(const uint8_t *s, int64_t n) {
    if (n && memchr(s, 0, (size_t)n)) return ailf_fail(AILF_E_VALUE, "embedded null byte");
    ailf_buf_free(&ailp_req.cwd);
    if (ailf_buf_put(&ailp_req.cwd, s, n) || ailf_buf_putc(&ailp_req.cwd, 0)) return -1;
    ailp_req.hascwd = 1;
    return 0;
}
static int ailp_env_begin(void) {
    ailf_buf_free(&ailp_req.env); ailp_req.nenv = 0; ailp_req.hasenv = 1;
    return 0;
}
static int ailp_env_add(const uint8_t *k, int64_t kn, const uint8_t *v, int64_t vn) {
    if ((kn && memchr(k, 0, (size_t)kn)) || (vn && memchr(v, 0, (size_t)vn))) return ailf_fail(AILF_E_VALUE, "embedded null byte");
    if (kn == 0 || memchr(k, '=', (size_t)kn)) return ailf_fail(AILF_E_VALUE, "illegal environment variable name");
    if (ailf_buf_put(&ailp_req.env, k, kn) || ailf_buf_putc(&ailp_req.env, '=') ||
        ailf_buf_put(&ailp_req.env, v, vn) || ailf_buf_putc(&ailp_req.env, 0)) return -1;
    ailp_req.nenv++;
    return 0;
}
static int ailp_input_bytes(const uint8_t *p, int64_t n) {
    ailf_buf_free(&ailp_req.input);
    if (ailf_buf_put(&ailp_req.input, p, n)) return -1;
    ailp_req.hasinput = 1;
    return 0;
}
/* the text of `input=` as the pipe carries it: encoded, and "\n" -> os.linesep (Popen's stdin is a
   TextIOWrapper with newline=None) */
static int ailp_input_text(const uint8_t *s, int64_t n, int64_t enc, int64_t errh) {
    ailf_buf tmp = {0};
    ailf_buf_free(&ailp_req.input);
    ailp_req.hasinput = 1;
#ifdef _WIN32
    for (int64_t i = 0; i < n; i++) {
        if (s[i] == '\n') { if (ailf_buf_putc(&tmp, '\r')) return -1; }
        if (ailf_buf_putc(&tmp, s[i])) return -1;
    }
    s = tmp.p ? tmp.p : (const uint8_t *)""; n = tmp.n;
#endif
    if (enc == AILF_ENC_UTF8) {
        int rc = ailf_buf_put(&ailp_req.input, s, n);
        ailf_buf_free(&tmp);
        return rc;
    }
    ailf dummy; memset(&dummy, 0, sizeof dummy);
    dummy.enc = (int)enc; dummy.errh = (int)errh;
    int rc = ailf_encode_text(&dummy, s, n, &ailp_req.input);
    ailf_buf_free(&tmp);
    return rc;
}

/* ------------------------------------------------------------------ results */

typedef struct {
    int64_t rc; int timedout;
    ailf_buf argv; int64_t nargs;
    ailf_buf out, err;
    char tsrc[96];                           /* the timeout text when it is the remaining time */
} ailp_res_t;
static ailp_res_t **ailp_slots; static int64_t ailp_nslots;

static int64_t ailp_new_res(ailp_res_t **out) {
    ailp_res_t *r = (ailp_res_t *)calloc(1, sizeof *r);
    if (!r) return ailf_fail(AILF_E_NOMEM, "out of memory");
    int64_t i = 0;
    while (i < ailp_nslots && ailp_slots[i]) i++;
    if (i == ailp_nslots) {
        ailp_res_t **q = (ailp_res_t **)realloc(ailp_slots, (size_t)(ailp_nslots + 8) * sizeof *q);
        if (!q) { free(r); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
        ailp_slots = q;
        for (int64_t k = ailp_nslots; k < ailp_nslots + 8; k++) ailp_slots[k] = NULL;
        ailp_nslots += 8;
    }
    ailp_slots[i] = r; *out = r;
    return i + 1;
}
static ailp_res_t *ailp_res(int64_t h) {
    return h >= 1 && h <= ailp_nslots ? ailp_slots[h - 1] : NULL;
}
static int ailp_free(int64_t h) {
    ailp_res_t *r = ailp_res(h);
    if (!r) return 0;
    ailf_buf_free(&r->argv); ailf_buf_free(&r->out); ailf_buf_free(&r->err);
    free(r); ailp_slots[h - 1] = NULL;
    return 0;
}
static int64_t ailp_rc(int64_t h) { ailp_res_t *r = ailp_res(h); return r ? r->rc : 0; }
static int64_t ailp_timedout(int64_t h) { ailp_res_t *r = ailp_res(h); return r ? r->timedout : 0; }

/* the decoded text of one stream: which 1 = stdout, 2 = stderr; universal newlines as
   Popen._translate_newlines does (CRLF and CR become LF) */
static int ailp_out_text(int64_t h, int64_t which, int64_t enc, int64_t errh, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ailp_res_t *r = ailp_res(h);
    if (!r) return 0;
    ailf_buf *raw = which == 1 ? &r->out : &r->err;
    if (!raw->n) return 0;
    ailf_buf s1 = {0}; int64_t used = 0; int pend = 0;
    if (ailf_decode_stage1((int)enc, (int)errh, raw->p, raw->n, 1, &s1, &used)) { ailf_buf_free(&s1); return -1; }
    if (ailf_newline_stage(1, 1, &pend, s1.p ? s1.p : (const uint8_t *)"", s1.n, 1, out)) { ailf_buf_free(&s1); ailf_buf_free(out); return -1; }
    ailf_buf_free(&s1);
    return 0;
}
static int ailp_out_bytes(int64_t h, int64_t which, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ailp_res_t *r = ailp_res(h);
    if (!r) return 0;
    ailf_buf *raw = which == 1 ? &r->out : &r->err;
    return ailf_buf_put(out, raw->p, raw->n);
}

/* ------------------------------------------------------------------ the last error */

static struct {
    int kind; int64_t rc;                    /* 1 CalledProcessError, 2 TimeoutExpired */
    ailf_buf cmd; int64_t ncmd;
    ailf_buf out, err;
    char timeout[96];
} ailp_last;

static int ailp_err_begin(int64_t kind, int64_t rc, const uint8_t *t, int64_t tn) {
    ailf_buf_free(&ailp_last.cmd); ailf_buf_free(&ailp_last.out); ailf_buf_free(&ailp_last.err);
    memset(&ailp_last, 0, sizeof ailp_last);
    ailp_last.kind = (int)kind; ailp_last.rc = rc;
    if (tn > (int64_t)sizeof ailp_last.timeout - 1) tn = (int64_t)sizeof ailp_last.timeout - 1;
    memcpy(ailp_last.timeout, t, (size_t)tn); ailp_last.timeout[tn] = 0;
    return 0;
}
static int ailp_err_arg(const uint8_t *s, int64_t n) {
    if (ailf_buf_put(&ailp_last.cmd, s, n) || ailf_buf_putc(&ailp_last.cmd, 0)) return -1;
    ailp_last.ncmd++;
    return 0;
}
static int ailp_err_out(const uint8_t *s, int64_t n) { return ailf_buf_put(&ailp_last.out, s, n); }
static int ailp_err_err(const uint8_t *s, int64_t n) { return ailf_buf_put(&ailp_last.err, s, n); }
/* a finished (or timed-out) result becomes the last error; the handle is released */
static int ailp_err_from(int64_t h, const uint8_t *t, int64_t tn) {
    ailp_res_t *r = ailp_res(h);
    if (!r) return 0;
    ailp_err_begin(r->timedout ? 2 : 1, r->rc, r->tsrc[0] ? (const uint8_t *)r->tsrc : t,
                   r->tsrc[0] ? (int64_t)strlen(r->tsrc) : tn);
    ailp_last.cmd = r->argv; ailp_last.ncmd = r->nargs;
    ailp_last.out = r->out; ailp_last.err = r->err;
    memset(&r->argv, 0, sizeof r->argv); memset(&r->out, 0, sizeof r->out); memset(&r->err, 0, sizeof r->err);
    ailp_free(h);
    return 0;
}
static int64_t ailp_get_rc(void) { return ailp_last.rc; }
static int ailp_get_buf(ailf_buf *dst, const ailf_buf *src) {
    dst->p = NULL; dst->n = dst->cap = 0;
    return ailf_buf_put(dst, src->p, src->n);
}
static int ailp_get_cmd(ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    /* the elements joined by NUL, without the last terminator */
    return ailf_buf_put(out, ailp_last.cmd.p, ailp_last.cmd.n ? ailp_last.cmd.n - 1 : 0);
}
static int ailp_get_timeout(ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    return ailf_buf_put(out, (const uint8_t *)ailp_last.timeout, (int64_t)strlen(ailp_last.timeout));
}

/* repr() of a str */
static int ailp_repr(const uint8_t *s, int64_t n, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    int64_t need = ailf_repr_str(NULL, 0, s, n);
    if (ailf_buf_reserve(out, need + 1)) return -1;
    ailf_repr_str((char *)out->p, need + 1, s, n);
    out->n = need;
    return 0;
}
/* repr() of a bytes */
static int ailp_repr_bytes(const uint8_t *s, int64_t n, ailf_buf *out) {
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

static int ailp_put_cstr(ailf_buf *b, const char *s) { return ailf_buf_put(b, (const uint8_t *)s, (int64_t)strlen(s)); }
/* repr() of the command list: ['a', 'b'] */
static int ailp_put_cmd_repr(ailf_buf *b) {
    if (ailf_buf_putc(b, '[')) return -1;
    const uint8_t *p = ailp_last.cmd.p;
    for (int64_t i = 0; i < ailp_last.ncmd; i++) {
        int64_t len = (int64_t)strlen((const char *)p);
        ailf_buf r;
        if (i && ailp_put_cstr(b, ", ")) return -1;
        if (ailp_repr(p, len, &r)) return -1;
        int rc = ailf_buf_put(b, r.p, r.n);
        ailf_buf_free(&r);
        if (rc) return -1;
        p += len + 1;
    }
    return ailf_buf_putc(b, ']');
}

/* signal.Signals(n).name for the signals of this platform ("" when Python has no member) */
static const char *ailp_signal_name(int sig) {
#define AILP_SIG(n) if (sig == n) return #n;
#ifdef SIGHUP
    AILP_SIG(SIGHUP)
#endif
#ifdef SIGINT
    AILP_SIG(SIGINT)
#endif
#ifdef SIGQUIT
    AILP_SIG(SIGQUIT)
#endif
#ifdef SIGILL
    AILP_SIG(SIGILL)
#endif
#ifdef SIGTRAP
    AILP_SIG(SIGTRAP)
#endif
#ifdef SIGABRT
    AILP_SIG(SIGABRT)
#endif
#ifdef SIGBUS
    AILP_SIG(SIGBUS)
#endif
#ifdef SIGFPE
    AILP_SIG(SIGFPE)
#endif
#ifdef SIGKILL
    AILP_SIG(SIGKILL)
#endif
#ifdef SIGUSR1
    AILP_SIG(SIGUSR1)
#endif
#ifdef SIGSEGV
    AILP_SIG(SIGSEGV)
#endif
#ifdef SIGUSR2
    AILP_SIG(SIGUSR2)
#endif
#ifdef SIGPIPE
    AILP_SIG(SIGPIPE)
#endif
#ifdef SIGALRM
    AILP_SIG(SIGALRM)
#endif
#ifdef SIGTERM
    AILP_SIG(SIGTERM)
#endif
#ifdef SIGSTKFLT
    AILP_SIG(SIGSTKFLT)
#endif
#ifdef SIGCHLD
    AILP_SIG(SIGCHLD)
#endif
#ifdef SIGCONT
    AILP_SIG(SIGCONT)
#endif
#ifdef SIGSTOP
    AILP_SIG(SIGSTOP)
#endif
#ifdef SIGTSTP
    AILP_SIG(SIGTSTP)
#endif
#ifdef SIGTTIN
    AILP_SIG(SIGTTIN)
#endif
#ifdef SIGTTOU
    AILP_SIG(SIGTTOU)
#endif
#ifdef SIGURG
    AILP_SIG(SIGURG)
#endif
#ifdef SIGXCPU
    AILP_SIG(SIGXCPU)
#endif
#ifdef SIGXFSZ
    AILP_SIG(SIGXFSZ)
#endif
#ifdef SIGVTALRM
    AILP_SIG(SIGVTALRM)
#endif
#ifdef SIGPROF
    AILP_SIG(SIGPROF)
#endif
#ifdef SIGWINCH
    AILP_SIG(SIGWINCH)
#endif
#ifdef SIGIO
    AILP_SIG(SIGIO)
#endif
#ifdef SIGPWR
    AILP_SIG(SIGPWR)
#endif
#ifdef SIGSYS
    AILP_SIG(SIGSYS)
#endif
#ifdef SIGEMT
    AILP_SIG(SIGEMT)
#endif
#ifdef SIGINFO
    AILP_SIG(SIGINFO)
#endif
#undef AILP_SIG
#if defined(__linux__)
    if (sig == 34) return "SIGRTMIN";
    if (sig == 64) return "SIGRTMAX";
#endif
    return "";
}

/* str(exception) of the last error, as CPython words it */
static int ailp_err_msg(ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    char num[48];
    if (ailp_put_cstr(out, "Command '") || ailp_put_cmd_repr(out)) return -1;
    if (ailp_last.kind == 2) {
        if (ailp_put_cstr(out, "' timed out after ") || ailp_put_cstr(out, ailp_last.timeout) || ailp_put_cstr(out, " seconds")) return -1;
        return 0;
    }
    if (ailp_last.rc < 0) {
        const char *name = ailp_signal_name((int)-ailp_last.rc);
        if (*name) {
            snprintf(num, sizeof num, ": %lld>.", (long long)-ailp_last.rc);
            if (ailp_put_cstr(out, "' died with <Signals.") || ailp_put_cstr(out, name) || ailp_put_cstr(out, num)) return -1;
        } else {
            snprintf(num, sizeof num, "%lld.", (long long)-ailp_last.rc);
            if (ailp_put_cstr(out, "' died with unknown signal ") || ailp_put_cstr(out, num)) return -1;
        }
        return 0;
    }
    snprintf(num, sizeof num, "%lld.", (long long)ailp_last.rc);
    if (ailp_put_cstr(out, "' returned non-zero exit status ") || ailp_put_cstr(out, num)) return -1;
    return 0;
}

/* ------------------------------------------------------------------ float repr (the remaining time) */

static void ailp_float_repr(double d, char *out, size_t cap) {
    char t[40];
    int p;
    for (p = 1; p <= 17; p++) {
        snprintf(t, sizeof t, "%.*e", p - 1, d);
        if (strtod(t, NULL) == d) break;
    }
    if (p > 17) p = 17;
    snprintf(t, sizeof t, "%.*e", p - 1, d);
    /* t = d[.ddd]e[+-]xx */
    char digits[24]; int nd = 0;
    char *e = strchr(t, 'e');
    for (char *c = t; c < e; c++) if (*c >= '0' && *c <= '9') digits[nd++] = *c;
    digits[nd] = 0;
    int exp10 = atoi(e + 1);
    int decpt = exp10 + 1;
    char buf[80]; int o = 0;
    if (d < 0) buf[o++] = '-';
    if (decpt > -4 && decpt <= 16) {
        if (decpt <= 0) {
            buf[o++] = '0'; buf[o++] = '.';
            for (int i = 0; i < -decpt; i++) buf[o++] = '0';
            for (int i = 0; i < nd; i++) buf[o++] = digits[i];
        } else {
            for (int i = 0; i < decpt; i++) buf[o++] = i < nd ? digits[i] : '0';
            buf[o++] = '.';
            if (nd > decpt) { for (int i = decpt; i < nd; i++) buf[o++] = digits[i]; }
            else buf[o++] = '0';
        }
    } else {
        buf[o++] = digits[0];
        if (nd > 1) { buf[o++] = '.'; for (int i = 1; i < nd; i++) buf[o++] = digits[i]; }
        o += snprintf(buf + o, 12, "e%c%02d", exp10 < 0 ? '-' : '+', exp10 < 0 ? -exp10 : exp10);
    }
    buf[o] = 0;
    snprintf(out, cap, "%s", buf);
}

/* ------------------------------------------------------------------ subprocess.list2cmdline */

/* The command line CreateProcess is given, quoted by subprocess.list2cmdline (bit for bit).
   `args` holds `n` NUL-terminated UTF-8 elements back to back. */
static int ailp_list2cmdline(const uint8_t *args, int64_t n, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    const uint8_t *p = args;
    for (int64_t i = 0; i < n; i++) {
        int64_t len = (int64_t)strlen((const char *)p);
        int needquote = len == 0;
        for (int64_t k = 0; k < len; k++) if (p[k] == ' ' || p[k] == '\t') needquote = 1;
        if (i && ailf_buf_putc(out, ' ')) return -1;
        if (needquote && ailf_buf_putc(out, '"')) return -1;
        int64_t bs = 0;
        for (int64_t k = 0; k < len; k++) {
            uint8_t c = p[k];
            if (c == '\\') bs++;
            else if (c == '"') {
                for (int64_t j = 0; j < bs * 2; j++) if (ailf_buf_putc(out, '\\')) return -1;
                bs = 0;
                if (ailf_buf_putc(out, '\\') || ailf_buf_putc(out, '"')) return -1;
            } else {
                for (int64_t j = 0; j < bs; j++) if (ailf_buf_putc(out, '\\')) return -1;
                bs = 0;
                if (ailf_buf_putc(out, c)) return -1;
            }
        }
        /* list2cmdline extends the pending backslashes, then again when the argument is quoted */
        for (int64_t j = 0; j < bs; j++) if (ailf_buf_putc(out, '\\')) return -1;
        if (needquote) {
            for (int64_t j = 0; j < bs; j++) if (ailf_buf_putc(out, '\\')) return -1;
            if (ailf_buf_putc(out, '"')) return -1;
        }
        p += len + 1;
    }
    return 0;
}

#ifndef _WIN32
/* ------------------------------------------------------------------ POSIX */

static int64_t ailp_now(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}
/* a close-on-exec pipe whose ends are both >= 3, so that wiring them to 0, 1, 2 never overwrites one */
static int ailp_pipe(int fd[2]) {
    int r;
#if defined(__linux__) && defined(SYS_pipe2)
    r = (int)syscall(SYS_pipe2, fd, O_CLOEXEC);
#else
    r = pipe(fd);
    if (r == 0) { fcntl(fd[0], F_SETFD, FD_CLOEXEC); fcntl(fd[1], F_SETFD, FD_CLOEXEC); }
#endif
    if (r) return -1;
    for (int i = 0; i < 2; i++) {
        if (fd[i] < 3) {
            int n = fcntl(fd[i], F_DUPFD_CLOEXEC, 3);
            if (n < 0) { int e = errno; close(fd[0]); close(fd[1]); errno = e; return -1; }
            close(fd[i]); fd[i] = n;
        }
    }
    return 0;
}
static int ailp_devnull(void) {
    int fd = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (fd >= 0 && fd < 3) { int n = fcntl(fd, F_DUPFD_CLOEXEC, 3); close(fd); fd = n; }
    return fd;
}
static void ailp_closefd(int *fd) { if (*fd >= 0) { close(*fd); *fd = -1; } }

/* everything the child needs, prepared before the fork (the child may only call async-signal-safe functions) */
typedef struct {
    char **argv; char **cands; int ncands; char **envp; const char *cwd;
    int in_fd, out_fd, err_fd, errpipe;      /* -1: leave the descriptor alone */
} ailp_exec_t;

static void ailp_child_fail(int errpipe, int err, int stage) {
    int rep[2]; rep[0] = err; rep[1] = stage;
    ssize_t w = write(errpipe, rep, sizeof rep);
    (void)w;
    _exit(255);
}
static void ailp_child(const ailp_exec_t *x) {
    if (x->in_fd >= 0 && dup2(x->in_fd, 0) < 0) ailp_child_fail(x->errpipe, errno, 0);
    if (x->out_fd >= 0 && dup2(x->out_fd, 1) < 0) ailp_child_fail(x->errpipe, errno, 0);
    if (x->err_fd >= 0 && dup2(x->err_fd, 2) < 0) ailp_child_fail(x->errpipe, errno, 0);
    if (x->cwd && chdir(x->cwd) < 0) ailp_child_fail(x->errpipe, errno, 1);
    signal(SIGPIPE, SIG_DFL);                /* restore_signals */
#ifdef SIGXFSZ
    signal(SIGXFSZ, SIG_DFL);
#endif
    /* close_fds: everything above 2 except the error pipe */
#if defined(__linux__) && defined(SYS_close_range)
    {
        int lo = x->errpipe;
        long r1 = lo > 3 ? syscall(SYS_close_range, 3u, (unsigned)(lo - 1), 0u) : 0;
        long r2 = syscall(SYS_close_range, (unsigned)(lo + 1), ~0u, 0u);
        if (r1 < 0 || r2 < 0) goto slow;
        goto closed;
    }
slow:
#endif
    {
        long maxfd = sysconf(_SC_OPEN_MAX);
        if (maxfd < 0 || maxfd > 65536) maxfd = 65536;
        for (int fd = 3; fd < maxfd; fd++) if (fd != x->errpipe) close(fd);
    }
#if defined(__linux__) && defined(SYS_close_range)
closed:
#endif
    {
        int saved = 0;
        for (int i = 0; i < x->ncands; i++) {
            execve(x->cands[i], x->argv, x->envp);
            if (errno != ENOENT && errno != ENOTDIR && saved == 0) saved = errno;
        }
        ailp_child_fail(x->errpipe, saved ? saved : errno, 2);
    }
}

static void ailp_free_strs(char **v, int n) { if (v) { for (int i = 0; i < n; i++) free(v[i]); free(v); } }

static int ailp_wait_status(pid_t pid, int *status, int blocking) {
    for (;;) {
        pid_t r = waitpid(pid, status, blocking ? 0 : WNOHANG);
        if (r == pid) return 1;
        if (r == 0) return 0;
        if (errno == EINTR) continue;
        if (errno == ECHILD) { *status = 0; return 1; }
        return -1;
    }
}
static int64_t ailp_rc_of(int status) {
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return -WTERMSIG(status);
    return status;
}

static int64_t ailp_run(int64_t flags, int64_t timeout_us) {
    ailp_req_t *q = &ailp_req;
    if (q->nargs < 1) return ailf_fail(AILF_E_VALUE, "empty command");
    int64_t rh = -1;
    char **argv = NULL, **cands = NULL, **envp = NULL; int ncands = 0, nargv = 0, nenvp = 0;
    int in_r = -1, in_w = -1, out_r = -1, out_w = -1, err_r = -1, err_w = -1, ep[2] = {-1, -1};
    int devnull = -1;
    int fail = 0;

    /* argv */
    argv = (char **)calloc((size_t)q->nargs + 1, sizeof *argv);
    if (!argv) return ailf_fail(AILF_E_NOMEM, "out of memory");
    { const char *p = (const char *)q->argv.p;
      for (int64_t i = 0; i < q->nargs; i++) { argv[i] = strdup(p); if (!argv[i]) { fail = 1; break; } nargv++; p += strlen(p) + 1; } }
    const char *prog = (const char *)q->argv.p;
    /* the candidate files: the program itself, or one per directory of the PATH of the child */
    if (!fail) {
        if (strchr(prog, '/')) {
            cands = (char **)calloc(1, sizeof *cands);
            if (cands) { cands[0] = strdup(prog); ncands = cands[0] ? 1 : 0; }
        } else {
            const char *path = NULL;
            if (q->hasenv) {
                const char *p = (const char *)q->env.p;
                for (int64_t i = 0; i < q->nenv; i++) { if (!strncmp(p, "PATH=", 5)) { path = p + 5; break; } p += strlen(p) + 1; }
            } else path = getenv("PATH");
            if (!path) path = "/bin:/usr/bin";
            size_t np = 1;
            for (const char *c = path; *c; c++) if (*c == ':') np++;
            cands = (char **)calloc(np, sizeof *cands);
            const char *s = path;
            for (size_t i = 0; cands && i < np; i++) {
                const char *e = strchr(s, ':'); size_t dl = e ? (size_t)(e - s) : strlen(s);
                size_t pl = strlen(prog);
                char *c = (char *)malloc(dl + pl + 2);
                if (!c) { fail = 1; break; }
                if (dl) { memcpy(c, s, dl); c[dl] = '/'; memcpy(c + dl + 1, prog, pl + 1); }
                else memcpy(c, prog, pl + 1);
                cands[ncands++] = c;
                s = e ? e + 1 : s + dl;
            }
            if (!cands) fail = 1;
        }
        if (!cands || !ncands) fail = 1;
    }
    /* envp */
    if (!fail && q->hasenv) {
        envp = (char **)calloc((size_t)q->nenv + 1, sizeof *envp);
        if (!envp) fail = 1;
        else { const char *p = (const char *)q->env.p;
               for (int64_t i = 0; i < q->nenv; i++) { envp[i] = strdup(p); if (!envp[i]) { fail = 1; break; } nenvp++; p += strlen(p) + 1; } }
    }
    if (fail) { ailp_free_strs(argv, nargv); ailp_free_strs(cands, ncands); ailp_free_strs(envp, nenvp); return ailf_fail(AILF_E_NOMEM, "out of memory"); }

    /* descriptors */
    int want_in = (flags & AILP_PIPE_IN) || q->hasinput, want_out = (flags & AILP_PIPE_OUT) != 0;
    int want_err = (flags & AILP_PIPE_ERR) != 0;
    int err_to_out = (flags & AILP_ERR_TO_OUT) != 0;
    int c_in = -1, c_out = -1, c_err = -1;
    int e = 0;
    if (ailp_pipe(ep)) { e = errno; goto oserr; }
    if (want_in) { int f[2]; if (ailp_pipe(f)) { e = errno; goto oserr; } in_r = f[0]; in_w = f[1]; c_in = in_r; }
    else if (flags & AILP_NULL_IN) { devnull = ailp_devnull(); if (devnull < 0) { e = errno; goto oserr; } c_in = devnull; }
    if (want_out) { int f[2]; if (ailp_pipe(f)) { e = errno; goto oserr; } out_r = f[0]; out_w = f[1]; c_out = out_w; }
    else if (flags & AILP_NULL_OUT) { if (devnull < 0) devnull = ailp_devnull(); if (devnull < 0) { e = errno; goto oserr; } c_out = devnull; }
    if (want_err) { int f[2]; if (ailp_pipe(f)) { e = errno; goto oserr; } err_r = f[0]; err_w = f[1]; c_err = err_w; }
    else if (err_to_out) c_err = c_out >= 0 ? c_out : 1;
    else if (flags & AILP_NULL_ERR) { if (devnull < 0) devnull = ailp_devnull(); if (devnull < 0) { e = errno; goto oserr; } c_err = devnull; }

    {
        ailp_exec_t x;
        x.argv = argv; x.cands = cands; x.ncands = ncands; x.envp = q->hasenv ? envp : environ;
        x.cwd = q->hascwd ? (const char *)q->cwd.p : NULL;
        x.in_fd = c_in; x.out_fd = c_out; x.err_fd = c_err; x.errpipe = ep[1];
        pid_t pid = fork();
        if (pid < 0) { e = errno; goto oserr; }
        if (pid == 0) { ailp_child(&x); _exit(255); }

        /* parent: the child's ends are closed, the error pipe tells whether exec happened */
        ailp_closefd(&ep[1]); ailp_closefd(&in_r); ailp_closefd(&out_w); ailp_closefd(&err_w); ailp_closefd(&devnull);
        int rep[2]; size_t got = 0;
        while (got < sizeof rep) {
            ssize_t r = read(ep[0], (char *)rep + got, sizeof rep - got);
            if (r < 0 && errno == EINTR) continue;
            if (r <= 0) break;
            got += (size_t)r;
        }
        ailp_closefd(&ep[0]);
        if (got > 0) {
            int st; ailp_wait_status(pid, &st, 1);
            ailp_closefd(&in_w); ailp_closefd(&out_r); ailp_closefd(&err_r);
            int err = got == sizeof rep ? rep[0] : EIO, stage = got == sizeof rep ? rep[1] : 0;
            if (stage == 1) ailf_oserr(err, q->cwd.p, q->cwd.n ? q->cwd.n - 1 : 0);
            else if (stage == 2) ailf_oserr(err, q->argv.p, (int64_t)strlen(prog));
            else ailf_oserr(err, NULL, 0);
            goto out_fail;
        }

        /* feed stdin and drain the pipes */
        ailp_res_t *res = NULL; rh = ailp_new_res(&res);
        if (rh < 0) { kill(pid, SIGKILL); int st; ailp_wait_status(pid, &st, 1); ailp_closefd(&in_w); ailp_closefd(&out_r); ailp_closefd(&err_r); goto out_fail; }
        int has_timeout = (flags & AILP_TIMEOUT) != 0;
        int64_t deadline = ailp_now() + timeout_us * 1000;
        int timedout = 0, status = 0, exited = 0;
        double rem0 = 0;                     /* the time left when the wait starts */
        int64_t inpos = 0;
        struct sigaction old_pipe, ign; int pipe_saved = 0;
        if (in_w >= 0) {
            if (q->input.n == 0) ailp_closefd(&in_w);
            else {
                fcntl(in_w, F_SETFL, fcntl(in_w, F_GETFL) | O_NONBLOCK);
                memset(&ign, 0, sizeof ign); ign.sa_handler = SIG_IGN; sigemptyset(&ign.sa_mask);
                sigaction(SIGPIPE, &ign, &old_pipe); pipe_saved = 1;
            }
        }
        if (out_r >= 0) fcntl(out_r, F_SETFL, fcntl(out_r, F_GETFL) | O_NONBLOCK);
        if (err_r >= 0) fcntl(err_r, F_SETFL, fcntl(err_r, F_GETFL) | O_NONBLOCK);
        int had_pipes = in_w >= 0 || out_r >= 0 || err_r >= 0;
        static uint8_t chunk[65536];
        int io_error = 0;
        while (in_w >= 0 || out_r >= 0 || err_r >= 0) {
            int to = -1;
            if (has_timeout) {
                int64_t rem = deadline - ailp_now();
                if (rem < 0) { timedout = 1; break; }
                to = (int)((rem + 999999) / 1000000);
            }
            struct pollfd pf[3]; int n = 0, wi = -1, wo = -1, we = -1;
            if (in_w >= 0) { pf[n].fd = in_w; pf[n].events = POLLOUT; pf[n].revents = 0; wi = n++; }
            if (out_r >= 0) { pf[n].fd = out_r; pf[n].events = POLLIN; pf[n].revents = 0; wo = n++; }
            if (err_r >= 0) { pf[n].fd = err_r; pf[n].events = POLLIN; pf[n].revents = 0; we = n++; }
            int pr = poll(pf, (nfds_t)n, to);
            if (pr < 0) { if (errno == EINTR) continue; io_error = errno; break; }
            if (has_timeout && ailp_now() > deadline) { timedout = 1; break; }
            if (wi >= 0 && pf[wi].revents) {
                if (pf[wi].revents & (POLLERR | POLLHUP | POLLNVAL)) ailp_closefd(&in_w);
                else {
                    int64_t left = q->input.n - inpos;
                    ssize_t w = write(in_w, q->input.p + inpos, (size_t)(left > 65536 ? 65536 : left));
                    if (w > 0) { inpos += w; if (inpos >= q->input.n) ailp_closefd(&in_w); }
                    else if (w < 0 && errno != EINTR && errno != EAGAIN) ailp_closefd(&in_w);   /* EPIPE: the child stopped reading */
                }
            }
            for (int k = 0; k < 2; k++) {
                int idx = k == 0 ? wo : we; int *fd = k == 0 ? &out_r : &err_r; ailf_buf *dst = k == 0 ? &res->out : &res->err;
                if (idx < 0 || !pf[idx].revents) continue;
                ssize_t r = read(*fd, chunk, sizeof chunk);
                if (r > 0) { if (ailf_buf_put(dst, chunk, r)) { io_error = ENOMEM; } }
                else if (r == 0 || (errno != EINTR && errno != EAGAIN)) ailp_closefd(fd);
            }
            if (io_error) break;
        }
        if (pipe_saved) sigaction(SIGPIPE, &old_pipe, NULL);
        ailp_closefd(&in_w); ailp_closefd(&out_r); ailp_closefd(&err_r);
        if (!timedout && !io_error) {
            if (!has_timeout) { ailp_wait_status(pid, &status, 1); exited = 1; }
            else {
                double delay = 0.0005;
                rem0 = (double)(deadline - ailp_now()) / 1e9;
                for (;;) {
                    int w = ailp_wait_status(pid, &status, 0);
                    if (w != 0) { exited = 1; break; }
                    double remaining = (double)(deadline - ailp_now()) / 1e9;
                    if (remaining <= 0) { timedout = 1; break; }
                    delay = delay * 2; if (delay > remaining) delay = remaining; if (delay > 0.05) delay = 0.05;
                    struct timespec ts; ts.tv_sec = (time_t)delay; ts.tv_nsec = (long)((delay - (double)ts.tv_sec) * 1e9);
                    nanosleep(&ts, NULL);
                }
            }
        }
        if (!exited) { kill(pid, SIGKILL); ailp_wait_status(pid, &status, 1); }
        if (io_error) { ailp_free(rh); rh = -1; ailf_oserr(io_error, NULL, 0); goto out_fail; }
        res->rc = ailp_rc_of(status); res->timedout = timedout;
        res->argv = q->argv; res->nargs = q->nargs;
        memset(&q->argv, 0, sizeof q->argv); q->nargs = 0;
        if (timedout && !had_pipes) {
            /* a wait without pipes reports the time that was left, not the timeout that was given */
            ailp_float_repr(rem0, res->tsrc, sizeof res->tsrc);
        }
        ailp_free_strs(argv, nargv); ailp_free_strs(cands, ncands); ailp_free_strs(envp, nenvp);
        return rh;
    }
oserr:
    ailf_oserr(e, NULL, 0);
out_fail:
    ailp_closefd(&ep[0]); ailp_closefd(&ep[1]); ailp_closefd(&in_r); ailp_closefd(&in_w); ailp_closefd(&out_r);
    ailp_closefd(&out_w); ailp_closefd(&err_r); ailp_closefd(&err_w); ailp_closefd(&devnull);
    ailp_free_strs(argv, nargv); ailp_free_strs(cands, ncands); ailp_free_strs(envp, nenvp);
    return -1;
}

#else  /* _WIN32 */
/* ------------------------------------------------------------------ Windows */

typedef struct { HANDLE h; ailf_buf *dst; } ailp_reader_t;
static DWORD WINAPI ailp_reader_main(LPVOID arg) {
    ailp_reader_t *r = (ailp_reader_t *)arg;
    uint8_t chunk[65536]; DWORD got;
    while (ReadFile(r->h, chunk, sizeof chunk, &got, NULL) && got) {
        if (ailf_buf_put(r->dst, chunk, got)) break;
    }
    return 0;
}
typedef struct { HANDLE h; const uint8_t *p; int64_t n; } ailp_writer_t;
static DWORD WINAPI ailp_writer_main(LPVOID arg) {
    ailp_writer_t *w = (ailp_writer_t *)arg;
    int64_t pos = 0;
    while (pos < w->n) {
        DWORD put = 0, want = (DWORD)(w->n - pos > 65536 ? 65536 : w->n - pos);
        if (!WriteFile(w->h, w->p + pos, want, &put, NULL)) break;      /* the child closed its stdin */
        pos += put;
    }
    CloseHandle(w->h); w->h = NULL;
    return 0;
}
static int ailp_make_pipe(HANDLE *rd, HANDLE *wr, int child_reads) {
    SECURITY_ATTRIBUTES sa; sa.nLength = sizeof sa; sa.lpSecurityDescriptor = NULL; sa.bInheritHandle = TRUE;
    if (!CreatePipe(rd, wr, &sa, 0)) return -1;
    /* the parent's end is not inherited */
    SetHandleInformation(child_reads ? *wr : *rd, HANDLE_FLAG_INHERIT, 0);
    return 0;
}
static void ailp_winfail(DWORD code, const char *what) {
    char text[512]; DWORD n = FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, code, 0, text, sizeof text - 1, NULL);
    while (n && (text[n - 1] == '\r' || text[n - 1] == '\n' || text[n - 1] == ' ' || text[n - 1] == '.')) n--;
    text[n] = 0;
    ailf_e.kind = AILF_E_OS;
    ailf_e.err = (code == ERROR_FILE_NOT_FOUND || code == ERROR_PATH_NOT_FOUND) ? ENOENT
               : (code == ERROR_ACCESS_DENIED) ? EACCES : (code == ERROR_DIRECTORY) ? ENOTDIR : EINVAL;
    ailf_e.has_fn1 = ailf_e.has_fn2 = 0; ailf_e.fn1[0] = ailf_e.fn2[0] = 0;
    snprintf(ailf_e.msg, sizeof ailf_e.msg, "[WinError %lu] %s", (unsigned long)code, n ? text : what);
}
static int64_t ailp_now(void) {
    LARGE_INTEGER f, c; QueryPerformanceFrequency(&f); QueryPerformanceCounter(&c);
    return (int64_t)((double)c.QuadPart / (double)f.QuadPart * 1e9);
}

static int64_t ailp_run(int64_t flags, int64_t timeout_us) {
    ailp_req_t *q = &ailp_req;
    if (q->nargs < 1) return ailf_fail(AILF_E_VALUE, "empty command");
    ailf_buf cmd8 = {0};
    if (ailp_list2cmdline(q->argv.p, q->nargs, &cmd8)) return -1;
    ailf_buf_putc(&cmd8, 0);
    ailf_pchar *cmdw = ailf_path(cmd8.p, cmd8.n - 1);
    ailf_buf_free(&cmd8);
    if (!cmdw) return -1;
    ailf_pchar *cwdw = NULL;
    if (q->hascwd) { cwdw = ailf_path(q->cwd.p, q->cwd.n - 1); if (!cwdw) { free(cmdw); return -1; } }
    wchar_t *envw = NULL;
    if (q->hasenv) {
        /* the environment block: UTF-16 "k=v" entries, an extra 0 at the end */
        size_t cap = 4; const char *p = (const char *)q->env.p;
        for (int64_t i = 0; i < q->nenv; i++) { cap += strlen(p) + 2; p += strlen(p) + 1; }
        envw = (wchar_t *)calloc(cap * 2, sizeof(wchar_t));
        size_t o = 0; p = (const char *)q->env.p;
        for (int64_t i = 0; i < q->nenv; i++) {
            ailf_pchar *w = ailf_path((const uint8_t *)p, (int64_t)strlen(p));
            size_t l = wcslen(w); memcpy(envw + o, w, l * sizeof(wchar_t)); o += l + 1; free(w);
            p += strlen(p) + 1;
        }
        if (!q->nenv) o = 1;
        envw[o] = 0;
    }
    int want_in = (flags & AILP_PIPE_IN) || q->hasinput, want_out = (flags & AILP_PIPE_OUT) != 0;
    int want_err = (flags & AILP_PIPE_ERR) != 0, err_to_out = (flags & AILP_ERR_TO_OUT) != 0;
    HANDLE in_r = NULL, in_w = NULL, out_r = NULL, out_w = NULL, err_r = NULL, err_w = NULL, nul = INVALID_HANDLE_VALUE;
    SECURITY_ATTRIBUTES sa; sa.nLength = sizeof sa; sa.lpSecurityDescriptor = NULL; sa.bInheritHandle = TRUE;
    int64_t rh = -1;
    STARTUPINFOW si; PROCESS_INFORMATION pi; memset(&si, 0, sizeof si); memset(&pi, 0, sizeof pi);
    si.cb = sizeof si; si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE); si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE); si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    if (want_in && ailp_make_pipe(&in_r, &in_w, 1)) goto winerr;
    if (want_out && ailp_make_pipe(&out_r, &out_w, 0)) goto winerr;
    if (want_err && ailp_make_pipe(&err_r, &err_w, 0)) goto winerr;
    if ((flags & (AILP_NULL_IN | AILP_NULL_OUT | AILP_NULL_ERR))) {
        nul = CreateFileW(L"NUL", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, NULL);
        if (nul == INVALID_HANDLE_VALUE) goto winerr;
    }
    if (want_in) si.hStdInput = in_r; else if (flags & AILP_NULL_IN) si.hStdInput = nul;
    if (want_out) si.hStdOutput = out_w; else if (flags & AILP_NULL_OUT) si.hStdOutput = nul;
    if (want_err) si.hStdError = err_w; else if (err_to_out) si.hStdError = si.hStdOutput;
    else if (flags & AILP_NULL_ERR) si.hStdError = nul;
    /* standard handles that the parent hands on must be inheritable */
    if (si.hStdInput) SetHandleInformation(si.hStdInput, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    if (si.hStdOutput) SetHandleInformation(si.hStdOutput, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    if (si.hStdError) SetHandleInformation(si.hStdError, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT);
    if (!CreateProcessW(NULL, cmdw, NULL, NULL, TRUE, CREATE_UNICODE_ENVIRONMENT, envw, cwdw, &si, &pi)) {
        DWORD code = GetLastError();
        ailp_winfail(code, "CreateProcess failed");
        goto fail_close;
    }
    CloseHandle(pi.hThread);
    if (in_r) { CloseHandle(in_r); in_r = NULL; }
    if (out_w) { CloseHandle(out_w); out_w = NULL; }
    if (err_w) { CloseHandle(err_w); err_w = NULL; }
    if (nul != INVALID_HANDLE_VALUE) { CloseHandle(nul); nul = INVALID_HANDLE_VALUE; }
    {
        ailp_res_t *res = NULL; rh = ailp_new_res(&res);
        if (rh < 0) { TerminateProcess(pi.hProcess, 1); CloseHandle(pi.hProcess); goto fail_close; }
        ailp_reader_t ro = {out_r, &res->out}, re = {err_r, &res->err};
        ailp_writer_t wr = {in_w, q->input.p, q->input.n};
        HANDLE threads[3]; int nt = 0, to = -1, te = -1;
        if (out_r) { threads[nt] = CreateThread(NULL, 0, ailp_reader_main, &ro, 0, NULL); to = nt++; }
        if (err_r) { threads[nt] = CreateThread(NULL, 0, ailp_reader_main, &re, 0, NULL); te = nt++; }
        if (in_w) { threads[nt] = CreateThread(NULL, 0, ailp_writer_main, &wr, 0, NULL); nt++; }
        (void)to; (void)te;
        int has_timeout = (flags & AILP_TIMEOUT) != 0;
        int64_t deadline = ailp_now() + timeout_us * 1000;
        int timedout = 0;
        DWORD ms = INFINITE;
        double rem0 = (double)(deadline - ailp_now()) / 1e9;        /* what a wait without pipes reports */
        if (has_timeout) { int64_t rem = deadline - ailp_now(); ms = rem <= 0 ? 0 : (DWORD)((rem + 999999) / 1000000); }
        if (nt) {
            DWORD r = WaitForMultipleObjects((DWORD)nt, threads, TRUE, ms);
            if (r == WAIT_TIMEOUT) timedout = 1;
        }
        if (!timedout) {
            if (has_timeout) { int64_t rem = deadline - ailp_now(); ms = rem <= 0 ? 0 : (DWORD)((rem + 999999) / 1000000); }
            if (WaitForSingleObject(pi.hProcess, ms) == WAIT_TIMEOUT) timedout = 1;
        }
        if (timedout) {
            TerminateProcess(pi.hProcess, 1);
            WaitForSingleObject(pi.hProcess, INFINITE);
            /* CPython's Windows run() then drains the pipes once more */
            if (nt) WaitForMultipleObjects((DWORD)nt, threads, TRUE, INFINITE);
        }
        DWORD code = 0; GetExitCodeProcess(pi.hProcess, &code);
        CloseHandle(pi.hProcess);
        for (int i = 0; i < nt; i++) CloseHandle(threads[i]);
        if (out_r) CloseHandle(out_r);
        if (err_r) CloseHandle(err_r);
        res->rc = (int64_t)code;
        res->timedout = timedout;
        if (timedout && !nt) ailp_float_repr(rem0, res->tsrc, sizeof res->tsrc);
        res->argv = q->argv; res->nargs = q->nargs;
        memset(&q->argv, 0, sizeof q->argv); q->nargs = 0;
        free(cmdw); free(cwdw); free(envw);
        return rh;
    }
winerr:
    ailp_winfail(GetLastError(), "pipe failed");
fail_close:
    if (in_r) CloseHandle(in_r);
    if (in_w) CloseHandle(in_w);
    if (out_r) CloseHandle(out_r);
    if (out_w) CloseHandle(out_w);
    if (err_r) CloseHandle(err_r);
    if (err_w) CloseHandle(err_w);
    if (nul != INVALID_HANDLE_VALUE) CloseHandle(nul);
    free(cmdw); free(cwdw); free(envw);
    return -1;
}
#endif /* _WIN32 */

#endif /* AILPROC_CORE_H */
