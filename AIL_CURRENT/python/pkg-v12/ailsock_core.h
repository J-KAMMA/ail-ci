/* ailsock_core.h -- ffsock1: POSIX TCP sockets behind the Python `socket` surface.

   Plain C, no AIL types: it sits after ailfile_core.h in the same translation unit (it uses
   ailf_buf, ailf_e and ailf_oserr there) and is shared by the typed and the general runtime
   (sockrt.py holds the adapters). A program carries it only when it imports socket.

   Handles are small integers into a fixed table. Every descriptor is non-blocking and each
   operation waits in poll() for the socket's timeout, so settimeout() applies to connect,
   accept, recv and send alike. Errors fill ailf_e (CPython's "[Errno N] text") and return -1;
   a wait that expires sets ailsk_timedout instead, which the adapters turn into TimeoutError. */
#ifndef AILSOCK_CORE_H
#define AILSOCK_CORE_H

#include <errno.h>
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#ifdef _WIN32
#error ailsock_core.h is POSIX only (Winsock is a later job)
#else
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <netdb.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#endif

#define AILSK_MAX 256
#define AILSK_HOST 128

typedef struct {
    int used;
    int fd;
    int domain;
    int listener;
    int write_closed;
    int64_t timeout_us;          /* -1 blocking, >= 0 microseconds */
    char lhost[AILSK_HOST];
    int lport;
    char phost[AILSK_HOST];
    int pport;
} ailsk_sock;

static ailsk_sock ailsk_table[AILSK_MAX];
static int ailsk_timedout;

static int ailsk_fail(int err) {
    ailsk_timedout = 0;
    return ailf_oserr(err, NULL, 0);
}
static int ailsk_failmsg(const char *text) {
    ailsk_timedout = 0;
    return ailf_fail(AILF_E_VALUE, text);
}
static void ailsk_timeout(void) {
    ailsk_timedout = 1;
    ailf_e.kind = AILF_E_OS;
    ailf_e.err = 0;
    ailf_e.has_fn1 = ailf_e.has_fn2 = 0;
    snprintf(ailf_e.msg, sizeof ailf_e.msg, "timed out");
}
static ailsk_sock *ailsk_get(int64_t h) {
    if (h < 1 || h >= AILSK_MAX || !ailsk_table[h].used) { ailsk_fail(EBADF); return NULL; }
    return &ailsk_table[h];
}
static int64_t ailsk_slot(ailsk_sock *S) { return (int64_t)(S - ailsk_table); }

static void ailsk_set_nonblock(int fd) {
    int flags;
    do { flags = fcntl(fd, F_GETFL); } while (flags < 0 && errno == EINTR);
    if (flags < 0) return;
    do { flags = fcntl(fd, F_SETFL, flags | O_NONBLOCK); } while (flags < 0 && errno == EINTR);
}

static void ailsk_addr_name(const struct sockaddr_storage *a, char *out, int cap, int *port) {
    out[0] = 0; if (port) *port = 0;
    if (a->ss_family == AF_INET) {
        const struct sockaddr_in *v = (const struct sockaddr_in *)a;
        inet_ntop(AF_INET, &v->sin_addr, out, (socklen_t)cap);
        if (port) *port = (int)ntohs(v->sin_port);
    } else if (a->ss_family == AF_INET6) {
        const struct sockaddr_in6 *v = (const struct sockaddr_in6 *)a;
        inet_ntop(AF_INET6, &v->sin6_addr, out, (socklen_t)cap);
        if (port) *port = (int)ntohs(v->sin6_port);
    }
}
static int ailsk_update_local(ailsk_sock *S) {
    struct sockaddr_storage a; socklen_t n = sizeof a;
    int r;
    do { r = getsockname(S->fd, (struct sockaddr *)&a, &n); } while (r < 0 && errno == EINTR);
    if (r < 0) return -1;
    ailsk_addr_name(&a, S->lhost, (int)sizeof S->lhost, &S->lport);
    return 0;
}
static int ailsk_update_peer(ailsk_sock *S) {
    struct sockaddr_storage a; socklen_t n = sizeof a;
    int r;
    do { r = getpeername(S->fd, (struct sockaddr *)&a, &n); } while (r < 0 && errno == EINTR);
    if (r < 0) return -1;
    ailsk_addr_name(&a, S->phost, (int)sizeof S->phost, &S->pport);
    return 0;
}

static int ailsk_wait(ailsk_sock *S, short events) {
    int timeout = S->timeout_us < 0 ? -1 : (int)((S->timeout_us + 999) / 1000);
    for (;;) {
        struct pollfd p = {S->fd, events, 0};
        int r = poll(&p, 1, timeout);
        if (r < 0) {
            if (errno == EINTR) continue;
            return ailsk_fail(errno);
        }
        if (r == 0) { ailsk_timeout(); return -1; }
        if (p.revents & POLLNVAL) return ailsk_fail(EBADF);
        if (p.revents & (events | POLLHUP | POLLERR)) return 0;
        return ailsk_fail(EIO);
    }
}

static int64_t ailsk_new(int64_t domain, int64_t type) {
    if (domain != AF_INET && domain != AF_INET6) return ailsk_failmsg("only AF_INET and AF_INET6 are built");
    if (type != SOCK_STREAM) return ailsk_failmsg("only SOCK_STREAM is built");
    int fd = socket((int)domain, SOCK_STREAM, 0);
    if (fd < 0) return ailsk_fail(errno);
    ailsk_set_nonblock(fd);
    for (int i = 1; i < AILSK_MAX; i++) {
        if (ailsk_table[i].used) continue;
        memset(&ailsk_table[i], 0, sizeof ailsk_table[i]);
        ailsk_table[i].used = 1;
        ailsk_table[i].fd = fd;
        ailsk_table[i].domain = (int)domain;
        ailsk_table[i].timeout_us = -1;
        return i;
    }
    close(fd);
    return ailsk_failmsg("too many sockets open");
}

static int ailsk_hostname(const uint8_t *host, int64_t n, char *out, int cap) {
    if (n < 0 || n >= cap) return ailsk_failmsg("host name too long");
    if (n && memchr(host, 0, (size_t)n)) return ailsk_failmsg("embedded null byte");
    if (n) memcpy(out, host, (size_t)n);
    out[n] = 0;
    return 0;
}

static int64_t ailsk_bind(int64_t h, const uint8_t *host, int64_t hn, int64_t port) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (port < 0 || port > 65535) return ailsk_failmsg("port must be 0-65535");
    char name[AILSK_HOST];
    if (ailsk_hostname(host, hn, name, (int)sizeof name) < 0) return -1;
    char service[8]; snprintf(service, sizeof service, "%d", (int)port);
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof hints);
    hints.ai_family = S->domain; hints.ai_socktype = SOCK_STREAM; hints.ai_flags = AI_PASSIVE;
    int e = getaddrinfo(hn ? name : NULL, service, &hints, &res);
    if (e) return ailsk_fail(e == EAI_SYSTEM ? errno : EADDRNOTAVAIL);
    int saved = 0;
    for (struct addrinfo *a = res; a; a = a->ai_next) {
        int r;
        do { r = bind(S->fd, a->ai_addr, a->ai_addrlen); } while (r < 0 && errno == EINTR);
        if (!r) { saved = 0; break; }
        saved = errno;
    }
    freeaddrinfo(res);
    if (saved) return ailsk_fail(saved);
    if (ailsk_update_local(S) < 0) return ailsk_fail(errno);
    return 0;
}

static int64_t ailsk_listen(int64_t h, int64_t backlog) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (backlog < 0) return ailsk_failmsg("backlog must be non-negative");
    int r;
    do { r = listen(S->fd, (int)backlog); } while (r < 0 && errno == EINTR);
    if (r < 0) return ailsk_fail(errno);
    S->listener = 1;
    return 0;
}

static int64_t ailsk_accept(int64_t h) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (!S->listener) return ailsk_fail(EINVAL);
    if (ailsk_wait(S, POLLIN) < 0) return -1;
    int fd;
    do { fd = accept(S->fd, NULL, NULL); } while (fd < 0 && errno == EINTR);
    if (fd < 0) return ailsk_fail(errno);
    ailsk_set_nonblock(fd);
    for (int i = 1; i < AILSK_MAX; i++) {
        if (ailsk_table[i].used) continue;
        memset(&ailsk_table[i], 0, sizeof ailsk_table[i]);
        ailsk_table[i].used = 1;
        ailsk_table[i].fd = fd;
        ailsk_table[i].domain = S->domain;
        ailsk_table[i].timeout_us = S->timeout_us;
        ailsk_update_local(&ailsk_table[i]);
        ailsk_update_peer(&ailsk_table[i]);
        return i;
    }
    close(fd);
    return ailsk_failmsg("too many sockets open");
}

static int64_t ailsk_connect(int64_t h, const uint8_t *host, int64_t hn, int64_t port) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (port < 1 || port > 65535) return ailsk_failmsg("port must be 1-65535");
    char name[AILSK_HOST];
    if (ailsk_hostname(host, hn, name, (int)sizeof name) < 0) return -1;
    if (!hn) return ailsk_failmsg("host must not be empty");
    char service[8]; snprintf(service, sizeof service, "%d", (int)port);
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof hints);
    hints.ai_family = S->domain; hints.ai_socktype = SOCK_STREAM;
    int e = getaddrinfo(name, service, &hints, &res);
    if (e) return ailsk_fail(e == EAI_SYSTEM ? errno : EHOSTUNREACH);
    int saved = 0;
    for (struct addrinfo *a = res; a; a = a->ai_next) {
        int fd = S->fd;
        if (a != res) {
            fd = socket(S->domain, SOCK_STREAM, 0);
            if (fd < 0) { saved = errno; continue; }
            ailsk_set_nonblock(fd);
        }
        int r;
        do { r = connect(fd, a->ai_addr, a->ai_addrlen); } while (r < 0 && errno == EINTR);
        if (r < 0 && (errno == EINPROGRESS || errno == EALREADY)) {
            short ev = POLLOUT;
            int timeout = S->timeout_us < 0 ? -1 : (int)((S->timeout_us + 999) / 1000);
            for (;;) {
                struct pollfd p = {fd, ev, 0};
                int w = poll(&p, 1, timeout);
                if (w < 0) {
                    if (errno == EINTR) continue;
                    saved = errno; break;
                }
                if (w == 0) { ailsk_timeout(); if (a != res) close(fd); freeaddrinfo(res); return -1; }
                if (p.revents & POLLNVAL) { saved = EBADF; break; }
                int soerr = 0; socklen_t sl = sizeof soerr;
                if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &soerr, &sl) < 0) { saved = errno; break; }
                if (soerr) { saved = soerr; break; }
                r = 0; break;
            }
        } else if (r < 0) {
            saved = errno;
        }
        if (r == 0) {
            if (a != res) { close(S->fd); S->fd = fd; }
            freeaddrinfo(res);
            if (ailsk_update_local(S) < 0) return ailsk_fail(errno);
            if (ailsk_update_peer(S) < 0) return ailsk_fail(errno);
            return 0;
        }
        if (a != res) close(fd);
    }
    freeaddrinfo(res);
    return ailsk_fail(saved ? saved : ECONNREFUSED);
}

static int64_t ailsk_close(int64_t h) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    int r = 0;
    if (S->fd >= 0) r = close(S->fd);
    S->used = 0; S->fd = -1;
    if (r < 0) return ailsk_fail(errno);
    return 0;
}

static int64_t ailsk_shutdown(int64_t h, int64_t how) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (how < 0 || how > 2) return ailsk_failmsg("invalid shutdown flag");
    int r;
    do { r = shutdown(S->fd, (int)how); } while (r < 0 && errno == EINTR);
    if (r < 0) return ailsk_fail(errno);
    if (how != 0) S->write_closed = 1;
    return 0;
}

static int64_t ailsk_settimeout(int64_t h, int64_t us) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (us < -1) return ailsk_failmsg("Timeout value out of range");
    S->timeout_us = us;
    return 0;
}
static int64_t ailsk_gettimeout(int64_t h, int64_t *us) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    *us = S->timeout_us;
    return 0;
}

static int64_t ailsk_setsockopt(int64_t h, int64_t level, int64_t opt, int64_t value) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    int v = (int)value, r;
    do { r = setsockopt(S->fd, (int)level, (int)opt, &v, sizeof v); } while (r < 0 && errno == EINTR);
    if (r < 0) return ailsk_fail(errno);
    return 0;
}

static int ailsk_recv_raw(ailsk_sock *S, uint8_t *buf, int n) {
    if (n == 0) return 0;
    if (ailsk_wait(S, POLLIN) < 0) return -1;
    ssize_t got;
    do { got = recv(S->fd, buf, (size_t)n, 0); } while (got < 0 && errno == EINTR);
    if (got < 0) return ailsk_fail(errno);
    return (int)got;
}

static int64_t ailsk_recv_text(int64_t h, int64_t n, ailf_buf *out) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (n < 0) return ailsk_failmsg("negative buffersize in recv");
    if (n > 2147483647) n = 2147483647;
    uint8_t *tmp = (uint8_t *)malloc((size_t)(n > 0 ? n : 1));
    if (!tmp) return ailf_fail(AILF_E_NOMEM, "out of memory");
    int got = ailsk_recv_raw(S, tmp, (int)n);
    if (got < 0) { free(tmp); return -1; }
    for (int i = 0; i < got; i++)
        if (ailf_buf_putcp(out, tmp[i])) { free(tmp); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
    free(tmp);
    return got;
}

static int64_t ailsk_recv_bin(int64_t h, int64_t n, ailf_buf *out) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (n < 0) return ailsk_failmsg("negative buffersize in recv");
    if (n > 2147483647) n = 2147483647;
    uint8_t *tmp = (uint8_t *)malloc((size_t)(n > 0 ? n : 1));
    if (!tmp) return ailf_fail(AILF_E_NOMEM, "out of memory");
    int got = ailsk_recv_raw(S, tmp, (int)n);
    if (got < 0) { free(tmp); return -1; }
    if (ailf_buf_put(out, tmp, got)) { free(tmp); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
    free(tmp);
    return got;
}

static int64_t ailsk_text_bytes(const uint8_t *p, int64_t n, uint8_t **out, int64_t *len) {
    uint8_t *q = (uint8_t *)malloc((size_t)(n > 0 ? n : 1));
    if (!q) return ailf_fail(AILF_E_NOMEM, "out of memory");
    int64_t o = 0;
    for (int64_t i = 0; i < n;) {
        uint8_t c = p[i];
        uint32_t cp;
        if (c < 0x80) { cp = c; i++; }
        else if (c < 0xE0 && i + 1 < n) { cp = ((c & 0x1Fu) << 6) | (p[i+1] & 0x3Fu); i += 2; }
        else if (c < 0xF0 && i + 2 < n) { cp = ((c & 0x0Fu) << 12) | ((p[i+1] & 0x3Fu) << 6) | (p[i+2] & 0x3Fu); i += 3; }
        else if (i + 3 < n) { cp = ((c & 0x07u) << 18) | ((p[i+1] & 0x3Fu) << 12) | ((p[i+2] & 0x3Fu) << 6) | (p[i+3] & 0x3Fu); i += 4; }
        else { cp = 0xFFFFFFFF; i = n; }
        if (cp > 255) { free(q); return ailf_fail(AILF_E_VALUE, "embedded null byte"); }
        q[o++] = (uint8_t)cp;
    }
    *out = q; *len = o;
    return 0;
}

static int64_t ailsk_send(int64_t h, const uint8_t *p, int64_t n) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (S->write_closed) return ailsk_fail(EPIPE);
    if (n <= 0) return 0;
    if (ailsk_wait(S, POLLOUT) < 0) return -1;
    ssize_t sent;
    do { sent = send(S->fd, p, (size_t)n, MSG_NOSIGNAL); } while (sent < 0 && errno == EINTR);
    if (sent < 0) return ailsk_fail(errno);
    return (int64_t)sent;
}
static int64_t ailsk_sendall(int64_t h, const uint8_t *p, int64_t n) {
    int64_t off = 0;
    while (off < n) {
        int64_t r = ailsk_send(h, p + off, n - off);
        if (r < 0) return -1;
        if (r == 0) return ailsk_fail(EPIPE);
        off += r;
    }
    return 0;
}

static int64_t ailsk_local_host(int64_t h, ailf_buf *out) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (!S->lhost[0] && ailsk_update_local(S) < 0) return ailsk_fail(errno);
    if (ailf_buf_put(out, (const uint8_t *)S->lhost, (int64_t)strlen(S->lhost)))
        return ailf_fail(AILF_E_NOMEM, "out of memory");
    return 0;
}
static int64_t ailsk_local_port(int64_t h) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (!S->lhost[0] && ailsk_update_local(S) < 0) return ailsk_fail(errno);
    return S->lport;
}
static int64_t ailsk_peer_host(int64_t h, ailf_buf *out) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (!S->phost[0] && ailsk_update_peer(S) < 0) return ailsk_fail(errno);
    if (ailf_buf_put(out, (const uint8_t *)S->phost, (int64_t)strlen(S->phost)))
        return ailf_fail(AILF_E_NOMEM, "out of memory");
    return 0;
}
static int64_t ailsk_peer_port(int64_t h) {
    ailsk_sock *S = ailsk_get(h);
    if (!S) return -1;
    if (!S->phost[0] && ailsk_update_peer(S) < 0) return ailsk_fail(errno);
    return S->pport;
}

static int64_t ailsk_gethostname(ailf_buf *out) {
    char name[256];
    if (gethostname(name, sizeof name) < 0) return ailsk_fail(errno);
    name[sizeof name - 1] = 0;
    if (ailf_buf_put(out, (const uint8_t *)name, (int64_t)strlen(name)))
        return ailf_fail(AILF_E_NOMEM, "out of memory");
    return 0;
}
static int64_t ailsk_gethostbyname(const uint8_t *name, int64_t n, ailf_buf *out) {
    char host[AILSK_HOST];
    if (ailsk_hostname(name, n, host, (int)sizeof host) < 0) return -1;
    struct in_addr v4;
    if (inet_pton(AF_INET, host, &v4) == 1) {
        char text[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &v4, text, (socklen_t)sizeof text);
        if (ailf_buf_put(out, (const uint8_t *)text, (int64_t)strlen(text))) return ailf_fail(AILF_E_NOMEM, "out of memory");
        return 0;
    }
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof hints);
    hints.ai_family = AF_INET; hints.ai_socktype = SOCK_STREAM;
    int e = getaddrinfo(host, NULL, &hints, &res);
    if (e) return ailsk_fail(e == EAI_SYSTEM ? errno : EHOSTUNREACH);
    char text[INET_ADDRSTRLEN]; int ok = 0;
    for (struct addrinfo *a = res; a; a = a->ai_next) {
        if (a->ai_family != AF_INET) continue;
        const struct sockaddr_in *v = (const struct sockaddr_in *)a->ai_addr;
        if (inet_ntop(AF_INET, &v->sin_addr, text, (socklen_t)sizeof text)) { ok = 1; break; }
    }
    freeaddrinfo(res);
    if (!ok) return ailsk_fail(EHOSTUNREACH);
    if (ailf_buf_put(out, (const uint8_t *)text, (int64_t)strlen(text))) return ailf_fail(AILF_E_NOMEM, "out of memory");
    return 0;
}

#endif
