/* ailurl_core.h -- the C that urllib.parse (stage G12) adds to ailfile_core.h: unquote and repr. It is
   embedded only into a program that reaches one of them, and needs no library. */
#ifndef AILURL_CORE_H
#define AILURL_CORE_H

static int ailu_hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
/* urllib.parse.unquote(s) / unquote_plus(s): every ASCII run is percent-decoded to bytes and those bytes are
   decoded as UTF-8 with errors='replace'; text outside ASCII is copied as it is */
static int ailu_unquote(const uint8_t *s, int64_t n, int64_t plus, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    int64_t i = 0;
    while (i < n) {
        int64_t j = i;
        if (s[i] >= 0x80) {
            while (j < n && s[j] >= 0x80) j++;
            if (ailf_buf_put(out, s + i, j - i)) return -1;
            i = j; continue;
        }
        while (j < n && s[j] < 0x80) j++;
        ailf_buf raw = {0};
        for (int64_t k = i; k < j; k++) {
            if (s[k] == '%' && k + 2 < j && ailu_hexval(s[k + 1]) >= 0 && ailu_hexval(s[k + 2]) >= 0) {
                if (ailf_buf_putc(&raw, (uint8_t)(ailu_hexval(s[k + 1]) * 16 + ailu_hexval(s[k + 2])))) { ailf_buf_free(&raw); return -1; }
                k += 2;
            } else if (plus && s[k] == '+') {
                if (ailf_buf_putc(&raw, ' ')) { ailf_buf_free(&raw); return -1; }
            } else if (ailf_buf_putc(&raw, s[k])) { ailf_buf_free(&raw); return -1; }
        }
        int64_t used = 0;
        int rc = raw.n ? ailf_decode_stage1(AILF_ENC_UTF8, AILF_ERR_REPLACE, raw.p, raw.n, 1, out, &used) : 0;
        ailf_buf_free(&raw);
        if (rc) return -1;
        i = j;
    }
    return 0;
}
/* repr() of a str, as the messages of ValueError("unknown url type: %r") show it */
static int ailu_repr(const uint8_t *s, int64_t n, ailf_buf *out) {
    out->p = NULL; out->n = out->cap = 0;
    int64_t need = ailf_repr_str(NULL, 0, s, n);
    if (ailf_buf_reserve(out, need + 1)) return -1;
    ailf_repr_str((char *)out->p, need + 1, s, n);
    out->n = need;
    return 0;
}

#endif
