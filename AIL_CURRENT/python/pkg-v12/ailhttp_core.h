/* ailhttp_core.h -- the libcurl layer under urllib.request.urlopen (stage G12, HTTP).

   Plain C, no AIL types: it sits after ailfile_core.h in the same translation unit (it uses ailf_buf
   and the allocation helpers there) and is shared by the typed runtime and a test driver. A program
   carries it, and links -lcurl, only when it reaches urllib.request.

   ONE HOP per call. The redirect, status and error policy of urllib (HTTPRedirectHandler,
   HTTPErrorProcessor, URLError / HTTPError) is Python text in urllib_prelude.py, because that is where
   CPython has it; this file only performs a request and hands back what came on the wire:

     ailh_begin / ailh_hdr / ailh_body   describe the request (method, URL, timeout, header lines in the
                                         order and spelling the caller wants them on the wire, body)
     ailh_perform                        runs it (libcurl easy handle, redirects OFF, HTTP/1.1, one
                                         connection, no automatic decoding, certificate checks ON) and
                                         returns a result handle: the status line, every header line in
                                         order, the whole body; or, when libcurl failed, the reason text
                                         CPython's URLError would carry
     ailh_status / ailh_reason / ailh_nhdr / ailh_hname / ailh_hval / ailh_hget / ailh_read ...
                                         read a result
   HTTPError keeps the response it was raised for in one "last error" record that the handler's
   `e.code`, `e.reason`, `e.headers`, `e.read()` read (ailh_eset / ailh_e*). */
#ifndef AILHTTP_CORE_H
#define AILHTTP_CORE_H

#include <curl/curl.h>
#include <ctype.h>
#ifdef _WIN32
#define strncasecmp _strnicmp
#else
#include <strings.h>
#endif

/* ------------------------------------------------------------------ the request */

typedef struct { char *n, *v; } ailh_hdr;
typedef struct { ailh_hdr *a; int64_t n, cap; } ailh_hdrs;

typedef struct {
    char *method, *url;
    int64_t tmo_us;                          /* < 0: no timeout */
    ailf_buf body; int hasbody;
    ailh_hdrs hdrs;
} ailh_req_t;
static ailh_req_t ailh_rq;

static char *ailh_dup(const uint8_t *s, int64_t n) {
    char *d = (char *)malloc((size_t)n + 1);
    if (!d) return NULL;
    if (n) memcpy(d, s, (size_t)n);
    d[n] = 0;
    return d;
}
static void ailh_hdrs_free(ailh_hdrs *h) {
    for (int64_t i = 0; i < h->n; i++) { free(h->a[i].n); free(h->a[i].v); }
    free(h->a); h->a = NULL; h->n = h->cap = 0;
}
static int ailh_hdrs_add(ailh_hdrs *h, char *n, char *v) {
    if (!n || !v) { free(n); free(v); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
    if (h->n == h->cap) {
        int64_t cap = h->cap ? h->cap * 2 : 16;
        ailh_hdr *q = (ailh_hdr *)realloc(h->a, (size_t)cap * sizeof *q);
        if (!q) { free(n); free(v); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
        h->a = q; h->cap = cap;
    }
    h->a[h->n].n = n; h->a[h->n].v = v; h->n++;
    return 0;
}

static int ailh_begin(const uint8_t *m, int64_t mn, const uint8_t *u, int64_t un, int64_t tmo_us) {
    free(ailh_rq.method); free(ailh_rq.url);
    ailf_buf_free(&ailh_rq.body); ailh_hdrs_free(&ailh_rq.hdrs);
    memset(&ailh_rq, 0, sizeof ailh_rq);
    if (memchr(u, 0, (size_t)un) || memchr(m, 0, (size_t)mn)) return ailf_fail(AILF_E_VALUE, "embedded null byte");
    ailh_rq.method = ailh_dup(m, mn); ailh_rq.url = ailh_dup(u, un);
    if (!ailh_rq.method || !ailh_rq.url) return ailf_fail(AILF_E_NOMEM, "out of memory");
    ailh_rq.tmo_us = tmo_us;
    return 0;
}
static int ailh_hdr_add(const uint8_t *n, int64_t nn, const uint8_t *v, int64_t vn) {
    if (memchr(n, 0, (size_t)nn) || memchr(v, 0, (size_t)vn)) return ailf_fail(AILF_E_VALUE, "embedded null byte");
    return ailh_hdrs_add(&ailh_rq.hdrs, ailh_dup(n, nn), ailh_dup(v, vn));
}
static int ailh_set_body(const uint8_t *p, int64_t n) {
    ailf_buf_free(&ailh_rq.body);
    ailh_rq.hasbody = 1;
    return ailf_buf_put(&ailh_rq.body, p, n);
}

/* ------------------------------------------------------------------ results */

typedef struct {
    int failed;                              /* libcurl could not complete the request */
    int timedout;                            /* ... because the timeout ran out */
    char *errtext;                           /* the reason of the URLError */
    int64_t status; char *reason;
    ailh_hdrs hdrs;
    ailf_buf body; int64_t pos; int closed;
} ailh_res_t;
static ailh_res_t **ailh_slots; static int64_t ailh_nslots;

static int64_t ailh_new_res(ailh_res_t **out) {
    ailh_res_t *r = (ailh_res_t *)calloc(1, sizeof *r);
    if (!r) return ailf_fail(AILF_E_NOMEM, "out of memory");
    int64_t i = 0;
    while (i < ailh_nslots && ailh_slots[i]) i++;
    if (i == ailh_nslots) {
        ailh_res_t **q = (ailh_res_t **)realloc(ailh_slots, (size_t)(ailh_nslots + 8) * sizeof *q);
        if (!q) { free(r); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
        ailh_slots = q;
        for (int64_t k = ailh_nslots; k < ailh_nslots + 8; k++) ailh_slots[k] = NULL;
        ailh_nslots += 8;
    }
    ailh_slots[i] = r; *out = r;
    return i + 1;
}
static ailh_res_t *ailh_res(int64_t h) { return h >= 1 && h <= ailh_nslots ? ailh_slots[h - 1] : NULL; }
static int ailh_free(int64_t h) {
    ailh_res_t *r = ailh_res(h);
    if (!r) return 0;
    free(r->errtext); free(r->reason); ailh_hdrs_free(&r->hdrs); ailf_buf_free(&r->body);
    free(r); ailh_slots[h - 1] = NULL;
    return 0;
}
/* HTTPResponse.close(): the body is gone (read() gives b""), the headers stay */
static int ailh_close(int64_t h) {
    ailh_res_t *r = ailh_res(h);
    if (!r) return 0;
    ailf_buf_free(&r->body); r->pos = 0; r->closed = 1;
    return 0;
}
static int64_t ailh_is_closed(int64_t h) { ailh_res_t *r = ailh_res(h); return r ? r->closed : 1; }

static int ailh_out_cstr(const char *s, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    return ailf_buf_put(out, (const uint8_t *)(s ? s : ""), s ? (int64_t)strlen(s) : 0);
}

/* ------------------------------------------------------------------ one hop */

static size_t ailh_on_body(char *p, size_t sz, size_t nm, void *ud) {
    ailh_res_t *r = (ailh_res_t *)ud;
    size_t n = sz * nm;
    if (ailf_buf_put(&r->body, (const uint8_t *)p, (int64_t)n)) return 0;
    return n;
}
static void ailh_trim_ws(const char **s, size_t *n) {
    while (*n && (**s == ' ' || **s == '\t')) { (*s)++; (*n)--; }
}
static size_t ailh_on_header(char *p, size_t sz, size_t nm, void *ud) {
    ailh_res_t *r = (ailh_res_t *)ud;
    size_t n = sz * nm, total = n;
    while (n && (p[n - 1] == '\r' || p[n - 1] == '\n')) n--;
    if (n >= 5 && memcmp(p, "HTTP/", 5) == 0) {
        /* a new status line (also after a 100 Continue): start over, as the last response is the one that counts */
        ailh_hdrs_free(&r->hdrs); free(r->reason); r->reason = NULL;
        size_t i = 5;
        while (i < n && p[i] != ' ') i++;                 /* version */
        while (i < n && p[i] == ' ') i++;
        while (i < n && p[i] != ' ') i++;                 /* status code */
        while (i < n && (p[i] == ' ' || p[i] == '\t')) i++;
        size_t e = n;
        while (e > i && (p[e - 1] == ' ' || p[e - 1] == '\t')) e--;
        r->reason = ailh_dup((const uint8_t *)p + i, (int64_t)(e - i));
        return r->reason ? total : 0;
    }
    if (n == 0) return total;
    if ((p[0] == ' ' || p[0] == '\t') && r->hdrs.n) {          /* an obsolete folded line continues the last value */
        ailh_hdr *last = &r->hdrs.a[r->hdrs.n - 1];
        const char *s = p; size_t m = n;
        ailh_trim_ws(&s, &m);
        size_t old = strlen(last->v);
        char *q = (char *)realloc(last->v, old + m + 3);
        if (!q) return 0;
        q[old] = '\r'; q[old + 1] = '\n';
        memcpy(q + old + 2, p, n);                          /* CPython keeps the folding as it came, minus the final CRLF */
        q[old + 2 + n] = 0;
        last->v = q;
        return total;
    }
    const char *colon = (const char *)memchr(p, ':', n);
    if (!colon) return total;                                /* not a header line: ignored (as http.client does after the first blank) */
    const char *v = colon + 1; size_t vn = n - (size_t)(colon + 1 - p);
    ailh_trim_ws(&v, &vn);
    if (ailh_hdrs_add(&r->hdrs, ailh_dup((const uint8_t *)p, (int64_t)(colon - p)), ailh_dup((const uint8_t *)v, (int64_t)vn))) return 0;
    return total;
}

static int ailh_inited;

/* the reason text of the URLError CPython raises for the failure libcurl reports (the wording of the OS error
   or of ssl.SSLError as far as libcurl tells it) */
static void ailh_reason_text(CURL *c, CURLcode rc, const char *detail, ailh_res_t *r) {
    char buf[900];
    long en = 0;
    switch (rc) {
    case CURLE_OPERATION_TIMEDOUT:
        r->timedout = 1; snprintf(buf, sizeof buf, "timed out"); break;
    case CURLE_COULDNT_RESOLVE_HOST: case CURLE_COULDNT_RESOLVE_PROXY:
        snprintf(buf, sizeof buf, "[Errno -2] Name or service not known"); break;
    case CURLE_COULDNT_CONNECT:
        curl_easy_getinfo(c, CURLINFO_OS_ERRNO, &en);
        if (en) snprintf(buf, sizeof buf, "[Errno %ld] %s", en, strerror((int)en));
        else snprintf(buf, sizeof buf, "%s", detail && *detail ? detail : curl_easy_strerror(rc));
        break;
    case CURLE_PEER_FAILED_VERIFICATION: case CURLE_SSL_CACERT_BADFILE: case CURLE_SSL_CERTPROBLEM: {
        const char *d = detail ? detail : "";
        const char *why = strstr(d, "SSL certificate problem: ");
        if (why) snprintf(buf, sizeof buf, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: %s (_ssl.c:1006)", why + 25);
        else if (strstr(d, "no alternative certificate subject name matches target host name"))
            snprintf(buf, sizeof buf, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch (_ssl.c:1006)");
        else snprintf(buf, sizeof buf, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:1006)");
        break;
    }
    case CURLE_SSL_CONNECT_ERROR:
        snprintf(buf, sizeof buf, "[SSL] %s (_ssl.c:1006)", detail && *detail ? detail : "handshake failure"); break;
    case CURLE_GOT_NOTHING: case CURLE_RECV_ERROR:
        snprintf(buf, sizeof buf, "[Errno 104] Connection reset by peer"); break;
    default:
        snprintf(buf, sizeof buf, "%s", detail && *detail ? detail : curl_easy_strerror(rc)); break;
    }
    r->errtext = ailh_dup((const uint8_t *)buf, (int64_t)strlen(buf));
}

static int64_t ailh_perform(void) {
    ailh_res_t *r = NULL;
    int64_t h = ailh_new_res(&r);
    if (h < 0) return -1;
    if (!ailh_inited) { curl_global_init(CURL_GLOBAL_DEFAULT); ailh_inited = 1; }
    CURL *c = curl_easy_init();
    if (!c) { ailh_free(h); return ailf_fail(AILF_E_FATAL, "libcurl could not start"); }
    char err[CURL_ERROR_SIZE]; err[0] = 0;
    struct curl_slist *list = NULL;
    const char *m = ailh_rq.method;
    curl_easy_setopt(c, CURLOPT_ERRORBUFFER, err);
    curl_easy_setopt(c, CURLOPT_URL, ailh_rq.url);
    curl_easy_setopt(c, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(c, CURLOPT_FOLLOWLOCATION, 0L);
    curl_easy_setopt(c, CURLOPT_HTTP_VERSION, (long)CURL_HTTP_VERSION_1_1);
    curl_easy_setopt(c, CURLOPT_PATH_AS_IS, 1L);
    curl_easy_setopt(c, CURLOPT_FORBID_REUSE, 1L);
    curl_easy_setopt(c, CURLOPT_FRESH_CONNECT, 1L);
    curl_easy_setopt(c, CURLOPT_SSL_VERIFYPEER, 1L);
    curl_easy_setopt(c, CURLOPT_SSL_VERIFYHOST, 2L);
#if defined(CURL_AT_LEAST_VERSION)
#if CURL_AT_LEAST_VERSION(7, 85, 0)
    curl_easy_setopt(c, CURLOPT_PROTOCOLS_STR, "http,https");
#else
    curl_easy_setopt(c, CURLOPT_PROTOCOLS, (long)(CURLPROTO_HTTP | CURLPROTO_HTTPS));
#endif
#endif
    /* OpenSSL's default_verify_paths, which is what ssl.create_default_context() uses: SSL_CERT_FILE and
       SSL_CERT_DIR replace the default file and directory (the system directory stays trusted) */
    const char *cafile = getenv("SSL_CERT_FILE"), *cadir = getenv("SSL_CERT_DIR");
    if (cafile && *cafile) {
        curl_easy_setopt(c, CURLOPT_CAINFO, cafile);
        if (!(cadir && *cadir)) {
#ifndef _WIN32
            struct stat st;
            if (stat("/etc/ssl/certs", &st) == 0 && S_ISDIR(st.st_mode)) curl_easy_setopt(c, CURLOPT_CAPATH, "/etc/ssl/certs");
#endif
        }
    }
    if (cadir && *cadir) curl_easy_setopt(c, CURLOPT_CAPATH, cadir);
    if (ailh_rq.tmo_us >= 0) {
        long ms = (long)(ailh_rq.tmo_us / 1000);
        if (ms < 1) ms = 1;
        curl_easy_setopt(c, CURLOPT_CONNECTTIMEOUT_MS, ms);
        long secs = (long)((ailh_rq.tmo_us + 999999) / 1000000);
        if (secs < 1) secs = 1;
        curl_easy_setopt(c, CURLOPT_LOW_SPEED_LIMIT, 1L);        /* a socket timeout is "no byte for that long" */
        curl_easy_setopt(c, CURLOPT_LOW_SPEED_TIME, secs);
    }
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION, ailh_on_body);
    curl_easy_setopt(c, CURLOPT_WRITEDATA, r);
    curl_easy_setopt(c, CURLOPT_HEADERFUNCTION, ailh_on_header);
    curl_easy_setopt(c, CURLOPT_HEADERDATA, r);
    /* the verb: GET and POST are libcurl's own, HEAD asks for no body, anything else is spelt as given */
    int is_head = strcmp(m, "HEAD") == 0;
    if (is_head) curl_easy_setopt(c, CURLOPT_NOBODY, 1L);
    if (ailh_rq.hasbody) {
        curl_easy_setopt(c, CURLOPT_POST, 1L);
        curl_easy_setopt(c, CURLOPT_POSTFIELDSIZE_LARGE, (curl_off_t)ailh_rq.body.n);
        curl_easy_setopt(c, CURLOPT_POSTFIELDS, ailh_rq.body.p ? (const char *)ailh_rq.body.p : "");
        if (strcmp(m, "POST") != 0) curl_easy_setopt(c, CURLOPT_CUSTOMREQUEST, m);
    } else if (!is_head && strcmp(m, "GET") != 0) {
        curl_easy_setopt(c, CURLOPT_CUSTOMREQUEST, m);
    }
    /* the header lines exactly as the caller listed them; libcurl's own Accept / Expect / Host / User-Agent
       are switched off by naming them with no value, so the request on the wire is the one urllib sends */
    for (int64_t i = 0; i < ailh_rq.hdrs.n; i++) {
        size_t ln = strlen(ailh_rq.hdrs.a[i].n) + strlen(ailh_rq.hdrs.a[i].v) + 3;
        char *line = (char *)malloc(ln);
        if (!line) { curl_slist_free_all(list); curl_easy_cleanup(c); ailh_free(h); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
        /* libcurl drops "Name:" with nothing after it; "Name;" is its spelling of a header with an empty value */
        if (ailh_rq.hdrs.a[i].v[0]) snprintf(line, ln, "%s: %s", ailh_rq.hdrs.a[i].n, ailh_rq.hdrs.a[i].v);
        else snprintf(line, ln, "%s;", ailh_rq.hdrs.a[i].n);
        list = curl_slist_append(list, line);
        free(line);
    }
    static const char *const off[] = {"Accept:", "Expect:", "User-Agent:", "Transfer-Encoding:", NULL};
    for (int i = 0; off[i]; i++) {
        size_t nl = strlen(off[i]) - 1; int named = 0;
        for (int64_t k = 0; k < ailh_rq.hdrs.n; k++)
            if (strlen(ailh_rq.hdrs.a[k].n) == nl && strncasecmp(ailh_rq.hdrs.a[k].n, off[i], nl) == 0) { named = 1; break; }
        if (!named) list = curl_slist_append(list, off[i]);
    }
    if (list) curl_easy_setopt(c, CURLOPT_HTTPHEADER, list);
    CURLcode rc = curl_easy_perform(c);
    if (rc != CURLE_OK) {
        r->failed = 1;
        ailh_reason_text(c, rc, err, r);
        if (!r->errtext) { curl_slist_free_all(list); curl_easy_cleanup(c); ailh_free(h); return ailf_fail(AILF_E_NOMEM, "out of memory"); }
        ailf_buf_free(&r->body);
    } else {
        long code = 0;
        curl_easy_getinfo(c, CURLINFO_RESPONSE_CODE, &code);
        r->status = code;
        if (!r->reason) r->reason = ailh_dup((const uint8_t *)"", 0);
    }
    curl_slist_free_all(list);
    curl_easy_cleanup(c);
    return h;
}

/* ------------------------------------------------------------------ reading a result */

static int64_t ailh_failed(int64_t h) { ailh_res_t *r = ailh_res(h); return r ? r->failed : 1; }
static int64_t ailh_timedout(int64_t h) { ailh_res_t *r = ailh_res(h); return r ? r->timedout : 0; }
static int ailh_errtext(int64_t h, ailf_buf *out) { ailh_res_t *r = ailh_res(h); return ailh_out_cstr(r ? r->errtext : "", out); }
static int64_t ailh_status(int64_t h) { ailh_res_t *r = ailh_res(h); return r ? r->status : 0; }
static int ailh_reason(int64_t h, ailf_buf *out) { ailh_res_t *r = ailh_res(h); return ailh_out_cstr(r ? r->reason : "", out); }
static int64_t ailh_nhdr(int64_t h) { ailh_res_t *r = ailh_res(h); return r ? r->hdrs.n : 0; }
static int ailh_hname(int64_t h, int64_t i, ailf_buf *out) {
    ailh_res_t *r = ailh_res(h);
    return ailh_out_cstr(r && i >= 0 && i < r->hdrs.n ? r->hdrs.a[i].n : "", out);
}
static int ailh_hval(int64_t h, int64_t i, ailf_buf *out) {
    ailh_res_t *r = ailh_res(h);
    return ailh_out_cstr(r && i >= 0 && i < r->hdrs.n ? r->hdrs.a[i].v : "", out);
}
/* the index of the first header called `name` (case-insensitively), or -1 */
static int64_t ailh_hfind(int64_t h, const uint8_t *name, int64_t nn) {
    ailh_res_t *r = ailh_res(h);
    if (!r) return -1;
    for (int64_t i = 0; i < r->hdrs.n; i++)
        if ((int64_t)strlen(r->hdrs.a[i].n) == nn && strncasecmp(r->hdrs.a[i].n, (const char *)name, (size_t)nn) == 0) return i;
    return -1;
}
/* HTTPResponse.read(amt): amt < 0 reads to the end; a closed response gives b"" */
static int ailh_read(int64_t h, int64_t amt, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    ailh_res_t *r = ailh_res(h);
    if (!r || r->closed) return 0;
    int64_t left = r->body.n - r->pos;
    if (amt < 0 || amt > left) amt = left;
    if (amt > 0 && ailf_buf_put(out, r->body.p + r->pos, amt)) return -1;
    r->pos += amt;
    return 0;
}

/* ------------------------------------------------------------------ the last error (HTTPError / URLError) */

static struct { int64_t kind, code, h; char *url, *reason, *msg; } ailh_last;

static int ailh_eset(int64_t h, int64_t kind, int64_t code, const uint8_t *u, int64_t un,
                     const uint8_t *rs, int64_t rn, const uint8_t *m, int64_t mn) {
    ailh_free(ailh_last.h);
    free(ailh_last.url); free(ailh_last.reason); free(ailh_last.msg);
    memset(&ailh_last, 0, sizeof ailh_last);
    ailh_last.kind = kind; ailh_last.code = code; ailh_last.h = h;
    ailh_last.url = ailh_dup(u, un); ailh_last.reason = ailh_dup(rs, rn); ailh_last.msg = ailh_dup(m, mn);
    if (!ailh_last.url || !ailh_last.reason || !ailh_last.msg) return ailf_fail(AILF_E_NOMEM, "out of memory");
    return 0;
}
static int64_t ailh_ecode(void) { return ailh_last.code; }
static int64_t ailh_eh(void) { return ailh_last.h; }
static int ailh_eurl(ailf_buf *out) { return ailh_out_cstr(ailh_last.url, out); }
static int ailh_ereason(ailf_buf *out) { return ailh_out_cstr(ailh_last.reason, out); }
static int ailh_emsg(ailf_buf *out) { return ailh_out_cstr(ailh_last.msg, out); }

#endif
