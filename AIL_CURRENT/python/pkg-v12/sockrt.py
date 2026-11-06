# -*- coding: utf-8 -*-
"""sockrt.py -- runtime parts of ffsock1 (the Python `socket` module).

`ailsock_core.h` is the shared C core. Here:

  TYPED       the typed-path adapters: one `ailt_sp_sock_*` function per primitive of
              socklib.SOCKS, raising ConnectionRefusedError / ConnectionResetError /
              BrokenPipeError / TimeoutError (codes 32..35) or OSError.
  GENERAL_C   the same adapters for the general path: values are ail_obj, strings arrive as
              UTF-8 text and the socket payload is carried as a latin-1 string.
  install()   adds the two parts to cruntime's tables and patches the exception table and the
              handler codes for the four socket classes; it does nothing to a program that does
              not import socket, so other programs keep their C byte for byte.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, 'ailsock_core.h'), 'r', encoding='utf-8') as _f:
    CORE = _f.read()

# exception codes reserved for this module; the DIE block gains these names only in a socket program
SOCK_CODES = {'ConnectionRefusedError': 32, 'ConnectionResetError': 33,
              'BrokenPipeError': 34, 'TimeoutError': 35, 'BlockingIOError': 36}
LAST_CODE = 36

TYPED = r'''
/* ---- ffsock1 typed adapters: the socket primitives of socklib.SOCKS over ailsock_core.h ---- */
#define AIL_EXC_CONNREFUSED 32
#define AIL_EXC_CONNRESET 33
#define AIL_EXC_BROKENPIPE 34
#define AIL_EXC_TIMEOUT 35
#define AIL_EXC_BLOCKING 36
static void ailt_sockraise(void) {
    if (ailsk_raisecode == 10) {
        ail_raise_value_adopt(ail_exception_new(10, (const uint8_t *)ailf_e.msg, (int64_t)strlen(ailf_e.msg), 1));
    }
    if (ailsk_raisecode == 36) {
        int err = ailf_e.err ? ailf_e.err : EAGAIN;
        const char *why = strerror(err);
        ail_exception *value = ail_exception_new_os(err, (ail_str){(const uint8_t *)why, (int64_t)strlen(why), 0});
        value->code = AIL_EXC_BLOCKING;
        ail_raise_value_adopt(value);
    }
    if (ailsk_timedout) {
        static const char m[] = "timed out";
        ail_raise_value_adopt(ail_exception_new(AIL_EXC_TIMEOUT, (const uint8_t *)m, (int64_t)sizeof m - 1, 1));
    }
    int err = ailf_e.err;
    int code = AIL_EXC_OS;
    switch (err) {
    case ECONNREFUSED: code = AIL_EXC_CONNREFUSED; break;
    case ECONNRESET: case ECONNABORTED: code = AIL_EXC_CONNRESET; break;
    case EPIPE: case ESHUTDOWN: code = AIL_EXC_BROKENPIPE; break;
    case ETIMEDOUT: code = AIL_EXC_TIMEOUT; break;
    default: break;
    }
    const char *why = strerror(err);
    ail_exception *value = ail_exception_new_os(err, (ail_str){(const uint8_t *)why, (int64_t)strlen(why), 0});
    value->code = code;
    ail_raise_value_adopt(value);
}
#define AILT_SOCKCHECK(call) do { if ((call) < 0) ailt_sockraise(); } while (0)
static int64_t ailt_sp_sock_new(int64_t d, int64_t t) { int64_t r = ailsk_new(d, t); if (r < 0) ailt_sockraise(); return r; }
static int64_t ailt_sp_sock_bind(int64_t h, ail_str host, int64_t port) { AILT_SOCKCHECK(ailsk_bind(h, host.p, host.n, port)); return 0; }
static int64_t ailt_sp_sock_listen(int64_t h, int64_t backlog) { AILT_SOCKCHECK(ailsk_listen(h, backlog)); return 0; }
static int64_t ailt_sp_sock_accept(int64_t h) { int64_t r = ailsk_accept(h); if (r < 0) ailt_sockraise(); return r; }
static int64_t ailt_sp_sock_connect(int64_t h, ail_str host, int64_t port) { AILT_SOCKCHECK(ailsk_connect(h, host.p, host.n, port)); return 0; }
static int64_t ailt_sp_sock_close(int64_t h) { AILT_SOCKCHECK(ailsk_close(h)); return 0; }
static int64_t ailt_sp_sock_shutdown(int64_t h, int64_t how) { AILT_SOCKCHECK(ailsk_shutdown(h, how)); return 0; }
static int64_t ailt_sp_sock_settimeout(int64_t h, int64_t us) { AILT_SOCKCHECK(ailsk_settimeout(h, us)); return 0; }
static int64_t ailt_sp_sock_gettimeout(int64_t h) { int64_t us = 0; if (ailsk_gettimeout(h, &us) < 0) ailt_sockraise(); return us; }
static int64_t ailt_sp_sock_addr_count(int64_t h) { int64_t r = ailsk_addr_count(h); if (r < 0) ailt_sockraise(); return r; }
static int64_t ailt_sp_sock_setsockopt(int64_t h, int64_t level, int64_t opt, int64_t value) { AILT_SOCKCHECK(ailsk_setsockopt(h, level, opt, value)); return 0; }
static ail_str ailt_sp_sock_recv(ail_sarena *A, int64_t h, int64_t n) {
    ailf_buf b = {0}; int64_t r = ailsk_recv_text(h, n, &b);
    if (r < 0) { free(b.p); ailt_sockraise(); }
    return ailt_adopt_str(A, &b);
}
static int64_t ailt_sp_sock_send(int64_t h, ail_str data) {
    uint8_t *p = NULL; int64_t n = 0;
    if (ailsk_text_bytes(data.p, data.n, &p, &n) < 0) { free(p); ailt_sockraise(); }
    int64_t r = ailsk_send(h, p, n); free(p);
    if (r < 0) ailt_sockraise();
    return r;
}
static int64_t ailt_sp_sock_sendall(int64_t h, ail_str data) {
    uint8_t *p = NULL; int64_t n = 0;
    if (ailsk_text_bytes(data.p, data.n, &p, &n) < 0) { free(p); ailt_sockraise(); }
    int64_t r = ailsk_sendall(h, p, n); free(p);
    if (r < 0) ailt_sockraise();
    return r;
}
static int64_t ailt_sp_sock_sendb(int64_t h, ail_bytes d) {
    int64_t r = ailsk_send(h, d.p, d.n);
    if (r < 0) ailt_sockraise();
    return r;
}
static int64_t ailt_sp_sock_sendallb(int64_t h, ail_bytes d) {
    int64_t r = ailsk_sendall(h, d.p, d.n);
    if (r < 0) ailt_sockraise();
    return r;
}
static ail_bytes ailt_sp_sock_recvb(ail_barena *A, int64_t h, int64_t n) {
    ailf_buf b = {0}; int64_t r = ailsk_recv_bin(h, n, &b);
    if (r < 0) { free(b.p); ailt_sockraise(); }
    return ailt_adopt_bytes(A, &b);
}
static ail_str ailt_sp_sock_local_host(ail_sarena *A, int64_t h) {
    ailf_buf b = {0}; int64_t r = ailsk_local_host(h, &b);
    if (r < 0) { free(b.p); ailt_sockraise(); }
    return ailt_adopt_str(A, &b);
}
static int64_t ailt_sp_sock_local_port(int64_t h) { int64_t r = ailsk_local_port(h); if (r < 0) ailt_sockraise(); return r; }
static ail_str ailt_sp_sock_peer_host(ail_sarena *A, int64_t h) {
    ailf_buf b = {0}; int64_t r = ailsk_peer_host(h, &b);
    if (r < 0) { free(b.p); ailt_sockraise(); }
    return ailt_adopt_str(A, &b);
}
static int64_t ailt_sp_sock_peer_port(int64_t h) { int64_t r = ailsk_peer_port(h); if (r < 0) ailt_sockraise(); return r; }
static ail_str ailt_sp_sock_gethostname(ail_sarena *A) {
    ailf_buf b = {0}; int64_t r = ailsk_gethostname(&b);
    if (r < 0) { free(b.p); ailt_sockraise(); }
    return ailt_adopt_str(A, &b);
}
static ail_str ailt_sp_sock_gethostbyname(ail_sarena *A, ail_str name) {
    ailf_buf b = {0}; int64_t r = ailsk_gethostbyname(name.p, name.n, &b);
    if (r < 0) { free(b.p); ailt_sockraise(); }
    return ailt_adopt_str(A, &b);
}
'''

# ---- general path adapters ----------------------------------------------------------------
GENERAL_C = r'''
/* ---- ffsock1 general adapters: the socket primitives of socklib.SOCKS over ailsock_core.h ---- */
static ail_st ailo_sockfail(ail_ctx *cx) {
    if (ailsk_raisecode == 10) return ail_raise_c(cx, AIL_B_OVERFLOWERROR, ailf_e.msg);
    if (ailsk_raisecode == 36) return ail_raise_oserror(cx, ailf_e.err ? ailf_e.err : EAGAIN);
    if (ailsk_timedout) return ail_raise_c(cx, AIL_B_TIMEOUTERROR, "timed out");
    return ailo_fail(cx);
}
static ail_st ailo_sp_sock_new(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0, i1 = 0; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a1, &i1); if (st != AIL_OK) return st;
    int64_t r = ailsk_new(i0, i1); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(r); return AIL_OK;
}
static ail_st ailo_sp_sock_bind(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1, ail_obj a2) {
    int64_t i0 = 0, i2 = 0; ailf_buf s1 = {0}; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_utf8_arg(cx, a1, &s1); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a2, &i2); if (st != AIL_OK) { free(s1.p); return st; }
    int64_t r = ailsk_bind(i0, s1.p, s1.n, i2); free(s1.p);
    if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_listen(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0, i1 = 0; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a1, &i1); if (st != AIL_OK) return st;
    int64_t r = ailsk_listen(i0, i1); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_accept(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    int64_t r = ailsk_accept(i0); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(r); return AIL_OK;
}
static ail_st ailo_sp_sock_connect(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1, ail_obj a2) {
    int64_t i0 = 0, i2 = 0; ailf_buf s1 = {0}; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_utf8_arg(cx, a1, &s1); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a2, &i2); if (st != AIL_OK) { free(s1.p); return st; }
    int64_t r = ailsk_connect(i0, s1.p, s1.n, i2); free(s1.p);
    if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_close(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    int64_t r = ailsk_close(i0); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_shutdown(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0, i1 = 0; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a1, &i1); if (st != AIL_OK) return st;
    int64_t r = ailsk_shutdown(i0, i1); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_settimeout(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0, i1 = 0; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a1, &i1); if (st != AIL_OK) return st;
    int64_t r = ailsk_settimeout(i0, i1); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_gettimeout(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    int64_t us = 0; if (ailsk_gettimeout(i0, &us) < 0) return ailo_sockfail(cx);
    *out = ail_box_int(us); return AIL_OK;
}
static ail_st ailo_sp_sock_addr_count(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    int64_t r = ailsk_addr_count(i0); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(r); return AIL_OK;
}
static ail_st ailo_sp_sock_setsockopt(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1, ail_obj a2, ail_obj a3) {
    int64_t i0 = 0, i1 = 0, i2 = 0, i3 = 0; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a1, &i1); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a2, &i2); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a3, &i3); if (st != AIL_OK) return st;
    int64_t r = ailsk_setsockopt(i0, i1, i2, i3); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_recv(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0, i1 = 0; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_int_arg(cx, a1, &i1); if (st != AIL_OK) return st;
    ailf_buf b = {0}; int64_t r = ailsk_recv_text(i0, i1, &b);
    if (r < 0) { free(b.p); return ailo_sockfail(cx); }
    *out = ail_bi_str_from_utf8(cx, (const char *)(b.p ? b.p : (uint8_t *)""), b.n);
    free(b.p); return AIL_OK;
}
static ail_st ailo_sp_sock_send(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0; ailf_buf s1 = {0}; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_utf8_arg(cx, a1, &s1); if (st != AIL_OK) return st;
    uint8_t *p = NULL; int64_t n = 0;
    if (ailsk_text_bytes(s1.p ? s1.p : (const uint8_t *)"", s1.n, &p, &n) < 0) { free(s1.p); return ailo_sockfail(cx); }
    int64_t r = ailsk_send(i0, p, n); free(p); free(s1.p);
    if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(r); return AIL_OK;
}
static ail_st ailo_sp_sock_sendall(ail_ctx *cx, ail_obj *out, ail_obj a0, ail_obj a1) {
    int64_t i0 = 0; ailf_buf s1 = {0}; ail_st st;
    st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    st = ailo_utf8_arg(cx, a1, &s1); if (st != AIL_OK) return st;
    uint8_t *p = NULL; int64_t n = 0;
    if (ailsk_text_bytes(s1.p ? s1.p : (const uint8_t *)"", s1.n, &p, &n) < 0) { free(s1.p); return ailo_sockfail(cx); }
    int64_t r = ailsk_sendall(i0, p, n); free(p); free(s1.p);
    if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(0); return AIL_OK;
}
static ail_st ailo_sp_sock_local_host(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    ailf_buf b = {0}; int64_t r = ailsk_local_host(i0, &b);
    if (r < 0) { free(b.p); return ailo_sockfail(cx); }
    *out = ail_bi_str_from_utf8(cx, (const char *)(b.p ? b.p : (uint8_t *)""), b.n);
    free(b.p); return AIL_OK;
}
static ail_st ailo_sp_sock_local_port(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    int64_t r = ailsk_local_port(i0); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(r); return AIL_OK;
}
static ail_st ailo_sp_sock_peer_host(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    ailf_buf b = {0}; int64_t r = ailsk_peer_host(i0, &b);
    if (r < 0) { free(b.p); return ailo_sockfail(cx); }
    *out = ail_bi_str_from_utf8(cx, (const char *)(b.p ? b.p : (uint8_t *)""), b.n);
    free(b.p); return AIL_OK;
}
static ail_st ailo_sp_sock_peer_port(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    int64_t i0 = 0; ail_st st = ailo_int_arg(cx, a0, &i0); if (st != AIL_OK) return st;
    int64_t r = ailsk_peer_port(i0); if (r < 0) return ailo_sockfail(cx);
    *out = ail_box_int(r); return AIL_OK;
}
static ail_st ailo_sp_sock_gethostname(ail_ctx *cx, ail_obj *out) {
    ailf_buf b = {0}; int64_t r = ailsk_gethostname(&b);
    if (r < 0) { free(b.p); return ailo_sockfail(cx); }
    *out = ail_bi_str_from_utf8(cx, (const char *)(b.p ? b.p : (uint8_t *)""), b.n);
    free(b.p); return AIL_OK;
}
static ail_st ailo_sp_sock_gethostbyname(ail_ctx *cx, ail_obj *out, ail_obj a0) {
    ailf_buf s0 = {0}; ail_st st = ailo_utf8_arg(cx, a0, &s0); if (st != AIL_OK) return st;
    ailf_buf b = {0}; int64_t r = ailsk_gethostbyname(s0.p ? s0.p : (const uint8_t *)"", s0.n, &b);
    free(s0.p);
    if (r < 0) { free(b.p); return ailo_sockfail(cx); }
    *out = ail_bi_str_from_utf8(cx, (const char *)(b.p ? b.p : (uint8_t *)""), b.n);
    free(b.p); return AIL_OK;
}
'''

_NAME_RE = re.compile(r'(static const char \*ail_exception_name\(int code\) \{\n\s*static const char \*names\[\] =\s*\{)(.*?)(\};)', re.S)


def patch_die(text):
    """Extend the DIE block's exception names table with the four socket classes (codes 32..35)."""
    found = _NAME_RE.search(text)
    if not found:
        raise AssertionError('DIE block changed; update sockrt.patch_die (names)')
    names = re.findall(r'"([^"]*)"', found.group(2))
    if len(names) > 32:
        # user exception classes already occupy 32..: refuse rather than overwrite them
        raise AssertionError('socket exceptions and user exception classes share codes')
    names += [''] * (32 - len(names))
    names += [n for n in ('ConnectionRefusedError', 'ConnectionResetError', 'BrokenPipeError',
                          'TimeoutError', 'BlockingIOError')]
    text = text[:found.start()] + found.group(1) + ', '.join('"%s"' % n for n in names) + found.group(3) + text[found.end():]
    for old, new in ((r'return code >= 1 && code <= \d+ \? names\[code\]',
                      'return code >= 1 && code <= %d ? names[code]' % LAST_CODE),
                     (r'if \(code < 1 \|\| code > \d+ \|\| n < 0', 'if (code < 1 || code > %d || n < 0' % LAST_CODE),
                     (r'if \(code < 1 \|\| code > \d+\) code = AIL_EXC_RUNTIME;',
                      'if (code < 1 || code > %d) code = AIL_EXC_RUNTIME;' % LAST_CODE)):
        text, count = re.subn(old, new, text)
        if count != 1:
            raise AssertionError('DIE block changed; update sockrt.patch_die: ' + old)
    return text


_INSTALLED = False


def install():
    """Add the socket parts and exception codes to the compiler tables (once)."""
    global _INSTALLED
    if _INSTALLED:
        return
    import cruntime
    if 'SOCKCORE' not in cruntime.SOURCE:
        cruntime.ORDER.insert(cruntime.ORDER.index('PROCCORE') + 1, 'SOCKCORE')
        cruntime.SOURCE['SOCKCORE'] = CORE
        cruntime.REQUIRES['SOCKCORE'] = ['FILECORE']
        cruntime.ORDER.insert(cruntime.ORDER.index('PROCIO') + 1, 'SOCKIO')
        cruntime.SOURCE['SOCKIO'] = TYPED
        cruntime.REQUIRES['SOCKIO'] = ['SOCKCORE', 'FILEIO', 'OSEXC']
    _INSTALLED = True
