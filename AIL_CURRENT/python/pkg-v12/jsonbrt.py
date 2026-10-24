# -*- coding: utf-8 -*-
"""jsonbrt.py -- the hot loops of prelude_genlib.py's json on the general (boxed) path, in C (fragment 'jsn' of
safetyrt.py).

json.dumps / json.loads on the general path are Python source (prelude_genlib.py) that runs on boxed values: the
profile of the gdev programs that use json put 40-60% of their instructions into the character loops of
_ail_json_quote (string escaping), _ail_json_ws (white space) and _ail_json_string (string scanning). Those three
are primitives here, with the control flow of the Python functions line for line:

* _ail_json_quote(s, ascii_only) -> the quoted text;
* _ail_json_ws(s, n, i)          -> the index of the first character that is not white space;
* _ail_json_scan(s, n, end)      -> (text, index after the closing quote), or (None, position, code) where the
  Python wrapper (prelude_genlib._ail_json_string, unchanged by this file's use) raises what code names: 1 invalid
  control character, 2 unterminated string, 3 invalid escape, 4 invalid \\uXXXX escape, 5 a surrogate escape.

Strings are 32-bit code-point units on this path, as in the Python source. A string without escapes comes back as a view of
the text (no copy). A program that does not use json gets the C it always had.
"""

PRIMS = {
    '_ail_json_quote': ('ail2j_quote(cx, &{t}, {a0}, {a1})', 2),
    '_ail_json_ws': ('ail2j_ws(cx, &{t}, {a0}, {a1}, {a2})', 3),
    '_ail_json_scan': ('ail2j_scan(cx, &{t}, {a0}, {a1}, {a2})', 3),
}

# the Python functions these primitives replace, and the wrapper that keeps the name `_ail_json_string`
NATIVE = ('_ail_json_quote', '_ail_json_ws', '_ail_json_string')

SCAN_WRAPPER = '''
def _ail_json_string(s, n, end):
    r = _ail_json_scan(s, n, end)
    if len(r) == 3:
        code = r[2]
        if code == 1:
            _ail_json_fail('Invalid control character at', s, r[1])
        if code == 2:
            _ail_json_fail('Unterminated string starting at', s, r[1])
        if code == 3:
            _ail_json_fail('Invalid \\\\escape', s, r[1])
        if code == 4:
            _ail_json_fail('Invalid \\\\uXXXX escape', s, r[1])
        raise ValueError('a lone surrogate escape in JSON text is not supported on the general path')
    return r
'''

JSN = r'''
/* ---- json on the general path (jsonbrt.py) ---- */
#ifndef AIL2Z_PAUSE
#define AIL2Z_PAUSE(cx) size_t ail2z_saved_ = (cx)->gc_threshold; (cx)->gc_threshold = (size_t)-1 >> 1
#define AIL2Z_RESUME(cx) (cx)->gc_threshold = ail2z_saved_
#endif
static ail_st ail2j_needstr(ail_ctx *cx, ail_obj x) {
    if (x.tag == AIL_T_STR) return AIL_OK;
    char buf[96]; snprintf(buf, sizeof buf, "json: expected str, not %s", ail_type_name(x.tag));
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
static inline int ail2j_isint(ail_obj x) { return x.tag == AIL_T_INT || x.tag == AIL_T_BOOL; }
static const char ail2j_hex[] = "0123456789abcdef";
static inline void ail2j_u(uint32_t *o, uint32_t n) {
    o[0] = '\\'; o[1] = 'u'; o[2] = ail2j_hex[(n >> 12) & 15]; o[3] = ail2j_hex[(n >> 8) & 15];
    o[4] = ail2j_hex[(n >> 4) & 15]; o[5] = ail2j_hex[n & 15];
}
/* _ail_json_quote(s, ascii_only) */
static ail_st ail2j_quote(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj asc) {
    ail_st st = ail2j_needstr(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    int ascii = ail_obj_truthy(asc);
    int64_t len = 2;
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = ail_chr(s, i);
        if (c == '"' || c == '\\' || c == '\n' || c == '\r' || c == '\t' || c == '\b' || c == '\f') len += 2;
        else if (c < 32) len += 6;
        else if (ascii && c > 0xFFFF) len += 12;
        else if (ascii && c > 126) len += 6;
        else len += 1;
    }
    ail_strbuild bu = ail_str_buf(cx, len);
    uint32_t *o = bu.buf;
    int64_t k = 0;
    o[k++] = '"';
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = ail_chr(s, i);
        switch (c) {
            case '"': o[k++] = '\\'; o[k++] = '"'; break;
            case '\\': o[k++] = '\\'; o[k++] = '\\'; break;
            case '\n': o[k++] = '\\'; o[k++] = 'n'; break;
            case '\r': o[k++] = '\\'; o[k++] = 'r'; break;
            case '\t': o[k++] = '\\'; o[k++] = 't'; break;
            case '\b': o[k++] = '\\'; o[k++] = 'b'; break;
            case '\f': o[k++] = '\\'; o[k++] = 'f'; break;
            default:
                if (c < 32) { ail2j_u(o + k, c); k += 6; }
                else if (ascii && c > 0xFFFF) {
                    uint32_t v = c - 0x10000;
                    ail2j_u(o + k, 0xD800 + (v >> 10)); k += 6;
                    ail2j_u(o + k, 0xDC00 + (v & 0x3FF)); k += 6;
                }
                else if (ascii && c > 126) { ail2j_u(o + k, c); k += 6; }
                else o[k++] = c;
        }
    }
    o[k++] = '"';
    *out = ail_str_buf_done(bu, k);
    return AIL_OK;
}
/* _ail_json_ws(s, n, i) */
static ail_st ail2j_ws(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj no, ail_obj io) {
    ail_st st = ail2j_needstr(cx, so); if (st != AIL_OK) return st;
    if (!ail2j_isint(no) || !ail2j_isint(io)) return ail_raise_c(cx, AIL_B_TYPEERROR, "json: an integer index is expected");
    ail_str s = ail_view_to_str(so);
    int64_t n = no.i, i = io.i;
    if (n > s.n) n = s.n;
    if (i < 0) { *out = io; return AIL_OK; }
    while (i < n) {
        uint32_t c = ail_chr(s, i);
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r') i++; else break;
    }
    *out = ail_box_int(i);
    return AIL_OK;
}
static inline int ail2j_hexval(uint32_t c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static ail_st ail2j_fail(ail_ctx *cx, ail_obj *out, int64_t pos, int64_t code) {
    ail_obj it[3]; it[0] = ail_box_none(); it[1] = ail_box_int(pos); it[2] = ail_box_int(code);
    *out = ail_tuple_new(cx, it, 3);
    return AIL_OK;
}
/* _ail_json_scan(s, n, end): the body of _ail_json_string, the control flow unchanged */
static ail_st ail2j_scan(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj no, ail_obj eo) {
    ail_st st = ail2j_needstr(cx, so); if (st != AIL_OK) return st;
    if (!ail2j_isint(no) || !ail2j_isint(eo)) return ail_raise_c(cx, AIL_B_TYPEERROR, "json: an integer index is expected");
    ail_str s = ail_view_to_str(so);
    int64_t n = no.i, end = eo.i, begin = end - 1;
    if (n > s.n) n = s.n;
    if (end < 0 || end > n) return ail_raise_c(cx, AIL_B_INDEXERROR, "string index out of range");
    uint32_t *buf = NULL;            /* built when an escape turns up */
    int64_t bn = 0, first = end;     /* [first, end) is the run copied so far when buf is NULL */
    for (;;) {
        int64_t nxt = end;
        uint32_t c = 0;
        while (nxt < n) {
            c = ail_chr(s, nxt);
            if (c == '"' || c == '\\') break;
            if (c <= 31) { if (buf) free(buf); return ail2j_fail(cx, out, nxt, 1); }
            nxt++;
        }
        if (nxt >= n) { if (buf) free(buf); return ail2j_fail(cx, out, begin, 2); }
        if (nxt > end) {
            if (buf) { memcpy(buf + bn, s.p + end, (size_t)(nxt - end) * sizeof(uint32_t)); bn += nxt - end; }
        }
        nxt++;
        if (c == '"') {
            int64_t stop = nxt - 1;
            ail_obj text;
            AIL2Z_PAUSE(cx);
            if (!buf) {
                /* no escape: a view of the text between the quotes */
                text = ail_str_view(so.sv.backing, so.sv.off + first, stop - first);
            } else {
                ail_strbuild bu = ail_str_buf(cx, bn);
                if (bn) memcpy(bu.buf, buf, (size_t)bn * sizeof(uint32_t));
                text = ail_str_buf_done(bu, bn);
                free(buf);
            }
            ail_obj it[2]; it[0] = text; it[1] = ail_box_int(nxt);
            *out = ail_tuple_new(cx, it, 2);
            AIL2Z_RESUME(cx);
            return AIL_OK;
        }
        if (nxt == n) { if (buf) free(buf); return ail2j_fail(cx, out, begin, 2); }
        if (!buf) {   /* the first escape: copy the run seen so far */
            buf = (uint32_t *)ail_xmalloc((size_t)(n - first + 1) * sizeof(uint32_t));
            bn = nxt - 1 - first;
            if (bn) memcpy(buf, s.p + first, (size_t)bn * sizeof(uint32_t));
        }
        c = ail_chr(s, nxt);
        if (c != 'u') {
            end = nxt + 1;
            switch (c) {
                case '"': case '\\': case '/': buf[bn++] = c; break;
                case 'b': buf[bn++] = '\b'; break;
                case 'f': buf[bn++] = '\f'; break;
                case 'n': buf[bn++] = '\n'; break;
                case 'r': buf[bn++] = '\r'; break;
                case 't': buf[bn++] = '\t'; break;
                default: free(buf); return ail2j_fail(cx, out, end - 2, 3);
            }
        } else {
            nxt++;
            end = nxt + 4;
            if (end >= n) { free(buf); return ail2j_fail(cx, out, nxt - 1, 4); }
            int v = 0;
            for (int j = 0; j < 4; j++) {
                int h = ail2j_hexval(ail_chr(s, nxt + j));
                if (h < 0) { free(buf); return ail2j_fail(cx, out, end - 5, 4); }
                v = v * 16 + h;
            }
            nxt = end;
            if (v >= 0xD800 && v <= 0xDBFF && nxt + 6 <= n
                && ail_chr(s, nxt) == '\\' && ail_chr(s, nxt + 1) == 'u') {
                int v2 = 0, ok = 1;
                for (int j = 0; j < 4; j++) {
                    int h = ail2j_hexval(ail_chr(s, nxt + 2 + j));
                    if (h < 0) { ok = 0; break; }
                    v2 = v2 * 16 + h;
                }
                if (ok && v2 >= 0xDC00 && v2 <= 0xDFFF) {
                    v = 0x10000 + ((v - 0xD800) << 10) + (v2 - 0xDC00);
                    nxt += 6;
                    end = nxt;
                }
            }
            /* A lone surrogate is not a scalar value: refuse it by name, as the base did,
               rather than storing it and later writing invalid UTF-8 from print()/encode(). */
            if (v >= 0xD800 && v <= 0xDFFF) { free(buf); return ail2j_fail(cx, out, 0, 5); }
            buf[bn++] = (uint32_t)v;
        }
    }
}
'''
