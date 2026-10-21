# -*- coding: utf-8 -*-
"""safetyrt.py -- run-time pieces the general (boxed) path appends to a program only when it uses them
(branch safetynet). A program that uses none of them gets the C it always had.

* STRPRED2: str.isalpha / isalnum / isupper / islower / istitle over all of Unicode (CPython 3.12's tables,
  cruntime.STRPRED), for the v2 string units (UTF-16, a surrogate pair is one code point). The core's
  ASCII-only versions stopped the program on a non-ASCII character.
"""
import cruntime
import randrt
import jsonbrt
import statbrt
import rebrt


def _strpred_tables():
    text = cruntime.STRPRED
    start = text.index('static const uint16_t ail__sp_idx')
    end = text.index('/* Walk the code points of s')
    return text[start:end]


STRPRED2 = '''
/* ---- str predicates over all of Unicode (safetyrt.py STRPRED2) ---- */
''' + _strpred_tables() + r'''
static inline uint32_t ail2p_point(ail_str s, int64_t *i) {
    uint32_t c = ail_chr(s, *i);
    if (c >= 0xD800 && c < 0xDC00 && *i + 1 < s.n) {
        uint32_t d = ail_chr(s, *i + 1);
        if (d >= 0xDC00 && d < 0xE000) { *i += 2; return 0x10000u + ((c - 0xD800u) << 10) + (d - 0xDC00u); }
    }
    *i += 1;
    return c;
}
static inline int ail2p_all(ail_obj so, unsigned mask) {
    ail_str s = ail_view_to_str(so);
    if (s.n == 0) return 0;
    for (int64_t i = 0; i < s.n; ) if (!(ail__sp(ail2p_point(s, &i)) & mask)) return 0;
    return 1;
}
static inline int ail2p_isalpha(ail_obj s) { return ail2p_all(s, 1u); }
static inline int ail2p_isalnum(ail_obj s) { return ail2p_all(s, 15u); }
static inline int ail2p_isupper(ail_obj so) {
    ail_str s = ail_view_to_str(so); int cased = 0;
    for (int64_t i = 0; i < s.n; ) { unsigned f = ail__sp(ail2p_point(s, &i)); if (f & 16u) return 0; if (f & 64u) cased = 1; }
    return cased;
}
static inline int ail2p_islower(ail_obj so) {
    ail_str s = ail_view_to_str(so); int cased = 0;
    for (int64_t i = 0; i < s.n; ) { unsigned f = ail__sp(ail2p_point(s, &i)); if (f & 32u) return 0; if (f & 128u) cased = 1; }
    return cased;
}
static inline int ail2p_istitle(ail_obj so) {
    ail_str s = ail_view_to_str(so); int cased = 0, prev = 0;
    for (int64_t i = 0; i < s.n; ) {
        unsigned f = ail__sp(ail2p_point(s, &i));
        if (f & 32u) { if (prev) return 0; prev = 1; cased = 1; }
        else if (f & 128u) { if (!prev) return 0; prev = 1; cased = 1; }
        else prev = 0;
    }
    return cased;
}
/* `s.NAME()` for one of the predicates: a receiver that is not a str raises AttributeError as CPython does */
static inline ail_st ail2p_method(ail_ctx *cx, ail_obj *out, ail_obj s, int which, const char *name) {
    if (s.tag != AIL_T_STR) {
        char buf[128]; snprintf(buf, sizeof buf, "'%s' object has no attribute '%s'", ail_type_name(s.tag), name);
        return ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, buf);
    }
    int r = which == 0 ? ail2p_isalpha(s) : which == 1 ? ail2p_isalnum(s) : which == 2 ? ail2p_isupper(s)
          : which == 3 ? ail2p_islower(s) : ail2p_istitle(s);
    *out = ail_box_bool(r);
    return AIL_OK;
}
'''

SLICE = r'''
/* ---- slice objects, slices of instances, slice assignment (safetyrt.py SLICE) ---- */
static inline ail_st ail2s_bound(ail_ctx *cx, ail_obj v, int *has, int64_t *out) {
    if (v.tag == AIL_T_NONE || v.tag == AIL_T_UNBOUND) { *has = 0; *out = 0; return AIL_OK; }
    if (v.tag == AIL_T_INT || v.tag == AIL_T_BOOL) { *has = 1; *out = v.i; return AIL_OK; }
    return ail_raise_c(cx, AIL_B_TYPEERROR, "slice indices must be integers or None or have an __index__ method");
}
/* c[lo:hi:step] with bounds that may be None at run time */
static inline ail_st ail2s_getslice(ail_ctx *cx, ail_obj *out, ail_obj c, ail_obj lo, ail_obj hi, ail_obj step) {
    int hl, hh, hs; int64_t l, h, s; ail_st st;
    if ((st = ail2s_bound(cx, lo, &hl, &l)) != AIL_OK) return st;
    if ((st = ail2s_bound(cx, hi, &hh, &h)) != AIL_OK) return st;
    if ((st = ail2s_bound(cx, step, &hs, &s)) != AIL_OK) return st;
    return ail_op_getslice(cx, out, c, hl, l, hh, h, hs, s);
}
static int64_t ail2s_ids[3];
static inline ail_st ail2s_fields(ail_ctx *cx, ail_obj k, ail_obj *lo, ail_obj *hi, ail_obj *step) {
    if (!ail2s_ids[0]) { ail2s_ids[0] = ail_intern(cx, "start"); ail2s_ids[1] = ail_intern(cx, "stop"); ail2s_ids[2] = ail_intern(cx, "step"); }
    ail_st st;
    if ((st = ail_inst_getattr(cx, lo, k, ail2s_ids[0], "start")) != AIL_OK) return st;
    if ((st = ail_inst_getattr(cx, hi, k, ail2s_ids[1], "stop")) != AIL_OK) return st;
    return ail_inst_getattr(cx, step, k, ail2s_ids[2], "step");
}
static inline int ail2s_is_slice(ail_obj k, ail_obj cls) {
    return k.tag == AIL_T_INST && ail_class_is_or_subclass(((ail_instobj *)k.o)->cls, cls);
}
/* c[key] where key may be a slice object: a str / list / tuple is sliced, anything else is indexed with it */
static inline ail_st ail2s_getitem(ail_ctx *cx, ail_obj *out, ail_obj c, ail_obj key, ail_obj cls) {
    if (c.tag != AIL_T_INST && ail2s_is_slice(key, cls)) {
        ail_obj lo, hi, step; ail_st st = ail2s_fields(cx, key, &lo, &hi, &step);
        if (st != AIL_OK) return st;
        return ail2s_getslice(cx, out, c, lo, hi, step);
    }
    return ail_op_getitem(cx, out, c, key);
}
/* c[key] = v / del c[key] where key may be a slice object */
static inline ail_st ail2s_setslice(ail_ctx *cx, ail_obj c, ail_obj lo, ail_obj hi, ail_obj step, ail_obj value, int del);
static inline ail_st ail2s_setitem(ail_ctx *cx, ail_obj c, ail_obj key, ail_obj v, ail_obj cls, int del) {
    if (c.tag != AIL_T_INST && ail2s_is_slice(key, cls)) {
        ail_obj lo, hi, step; ail_st st = ail2s_fields(cx, key, &lo, &hi, &step);
        if (st != AIL_OK) return st;
        return ail2s_setslice(cx, c, lo, hi, step, v, del);
    }
    return del ? ail_op_delitem(cx, c, key) : ail_op_setitem(cx, c, key, v);
}
/* slice.indices(n) */
static inline ail_st ail2s_indices(ail_ctx *cx, ail_obj *out, ail_obj lo, ail_obj hi, ail_obj step, ail_obj n) {
    int hl, hh, hs; int64_t l, h, s; ail_st st;
    if ((st = ail2s_bound(cx, lo, &hl, &l)) != AIL_OK) return st;
    if ((st = ail2s_bound(cx, hi, &hh, &h)) != AIL_OK) return st;
    if ((st = ail2s_bound(cx, step, &hs, &s)) != AIL_OK) return st;
    if (n.tag != AIL_T_INT && n.tag != AIL_T_BOOL) return ail_raise_c(cx, AIL_B_TYPEERROR, "'str' object cannot be interpreted as an integer");
    if (n.i < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "length should not be negative");
    ail_slice_idx r; if ((st = ail__slice_resolve(cx, &r, n.i, hl, l, hh, h, hs, s)) != AIL_OK) return st;
    ail_obj items[3] = { ail_box_int(r.start), ail_box_int(r.stop), ail_box_int(r.step) };
    *out = ail_tuple_new(cx, items, 3); return AIL_OK;
}
/* lst[lo:hi:step] = value and del lst[lo:hi:step] (CPython's list_ass_subscript) */
static inline ail_st ail2s_setslice(ail_ctx *cx, ail_obj c, ail_obj lo, ail_obj hi, ail_obj step, ail_obj value, int del) {
    if (c.tag != AIL_T_LIST) {
        char buf[96];
        snprintf(buf, sizeof buf, del ? "'%s' object does not support item deletion" : "'%s' object does not support item assignment", ail_type_name(c.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
    }
    int hl, hh, hs; int64_t l, h, s; ail_st st;
    if ((st = ail2s_bound(cx, lo, &hl, &l)) != AIL_OK) return st;
    if ((st = ail2s_bound(cx, hi, &hh, &h)) != AIL_OK) return st;
    if ((st = ail2s_bound(cx, step, &hs, &s)) != AIL_OK) return st;
    ail_vecobj *v = (ail_vecobj *)c.o;
    ail_slice_idx r; if ((st = ail__slice_resolve(cx, &r, v->n, hl, l, hh, h, hs, s)) != AIL_OK) return st;
    ail_obj *src = NULL; int64_t m = 0; ail_obj *copy = NULL;
    if (!del) {
        ail_obj seq = value;
        if (value.tag != AIL_T_LIST && value.tag != AIL_T_TUPLE) {
            if ((st = ail_bi_list_from_iter(cx, &seq, value)) != AIL_OK) {
                if (st == AIL_EXC && ail_exc_matches_b(cx, AIL_B_TYPEERROR)) {
                    ail_exc_clear(cx);
                    return ail_raise_c(cx, AIL_B_TYPEERROR, r.step == 1 ? "can only assign an iterable" : "must assign iterable to extended slice");
                }
                return st;
            }
        }
        ail_vecobj *sv = (ail_vecobj *)seq.o;
        m = sv->n;
        copy = (ail_obj *)ail_xmalloc((size_t)(m ? m : 1) * sizeof(ail_obj));
        if (m) memcpy(copy, sv->p, (size_t)m * sizeof(ail_obj));
        src = copy;
    }
    if (r.step == 1) {
        int64_t start = r.start, stop = r.stop < r.start ? r.start : r.stop, old = stop - start;
        int64_t nn = v->n - old + m;
        if (nn > v->n) ail_vec_reserve(cx, v, nn);
        memmove(v->p + start + m, v->p + stop, (size_t)(v->n - stop) * sizeof(ail_obj));
        if (m) memcpy(v->p + start, src, (size_t)m * sizeof(ail_obj));
        v->n = nn;
        free(copy);
        return AIL_OK;
    }
    if (del) {
        int64_t len = r.len;
        if (len == 0) return AIL_OK;
        int64_t lo_i = r.step > 0 ? r.start : r.start + (len - 1) * r.step, stp = r.step > 0 ? r.step : -r.step;
        int64_t w = lo_i;
        for (int64_t i = lo_i, k = 0; i < v->n; i++) {
            if (k < len && i == lo_i + k * stp) { k++; continue; }
            v->p[w++] = v->p[i];
        }
        v->n = w;
        return AIL_OK;
    }
    if (m != r.len) {
        free(copy);
        char buf[128]; snprintf(buf, sizeof buf, "attempt to assign sequence of size %lld to extended slice of size %lld", (long long)m, (long long)r.len);
        return ail_raise_c(cx, AIL_B_VALUEERROR, buf);
    }
    for (int64_t k = 0; k < m; k++) v->p[r.start + k * r.step] = src[k];
    free(copy);
    return AIL_OK;
}
'''

BYTES = r'''
/* ---- bytes and bytearray on the general path (safetyrt.py BYTES) ----
   A bytes value is an instance of the prelude class `bytes` (prelude_bytes.py) holding a str whose
   units are the bytes, 0..255; the C below works on such strs. */
static inline ail_obj ail2b_from_buf(ail_ctx *cx, const unsigned char *p, int64_t n) {
    ail_strback *b = ail_strback_alloc(cx, n);
    for (int64_t i = 0; i < n; i++) b->data[i] = p[i];
    return ail_str_view((ail_gcobj *)b, 0, n);
}
static inline ail_st ail2b_need(ail_ctx *cx, ail_obj s) {
    if (s.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "a bytes-like object is required");
    return AIL_OK;
}
/* sys.stdin.buffer.read(n): n < 0 reads to the end */
static inline ail_st ail2b_stdin(ail_ctx *cx, ail_obj *out, ail_obj n) {
    ail_st st = ail2_stdin_flush(cx);
    if (st != AIL_OK) return st;
    int64_t limit = (n.tag == AIL_T_INT || n.tag == AIL_T_BOOL) ? n.i : -1;
    size_t cap = 65536, len = 0;
    unsigned char *buf = (unsigned char *)ail_xmalloc(cap);
    for (;;) {
        if (limit >= 0 && (int64_t)len >= limit) break;
        if (len == cap) { cap *= 2; unsigned char *nb = (unsigned char *)ail_xmalloc(cap); memcpy(nb, buf, len); free(buf); buf = nb; }
        size_t want = cap - len;
        if (limit >= 0 && (int64_t)want > limit - (int64_t)len) want = (size_t)(limit - (int64_t)len);
        errno = 0;
        size_t got = fread(buf + len, 1, want, stdin);
        int saved = errno;
        len += got;
        if (ferror(stdin)) { clearerr(stdin); if (saved == EINTR) continue; free(buf); return ail_raise_oserror(cx, saved); }
        if (feof(stdin)) break;
    }
    *out = ail2b_from_buf(cx, buf, (int64_t)len);
    free(buf);
    return AIL_OK;
}
/* sys.stdout.buffer.write(b): the bytes as they are */
static inline ail_st ail2b_write(ail_ctx *cx, ail_obj *out, ail_obj s) {
    ail_st st = ail2b_need(cx, s); if (st != AIL_OK) return st;
    ail_str v = ail_view_to_str(s);
    char tmp[4096]; int64_t k = 0;
    for (int64_t i = 0; i < v.n; i++) {
        tmp[k++] = (char)(unsigned char)ail_chr(v, i);
        if (k == (int64_t)sizeof tmp) { ail_out_write(cx, tmp, (size_t)k); k = 0; }
    }
    if (k) ail_out_write(cx, tmp, (size_t)k);
    *out = ail_box_int(v.n);
    return AIL_OK;
}
/* the last encode/decode error: kind 1 UnicodeEncodeError, 2 UnicodeDecodeError, 3 LookupError */
static char ail2b_err[256]; static int ail2b_errkind;
static inline ail_st ail2b_lasterr(ail_ctx *cx, ail_obj *out) { *out = ail_str_from_cstr(cx, ail2b_err); return AIL_OK; }
static inline ail_st ail2b_errkind_get(ail_ctx *cx, ail_obj *out) { (void)cx; *out = ail_box_int(ail2b_errkind); return AIL_OK; }
static inline void ail2b_chrname(char *b, size_t n, uint32_t c) {
    if (c < 0x100) snprintf(b, n, "'\\x%02x'", c);
    else if (c < 0x10000) snprintf(b, n, "'\\u%04x'", c);
    else snprintf(b, n, "'\\U%08x'", c);
}
/* encoding: 0 utf-8, 1 ascii, 2 latin-1; errors: 0 strict, 1 ignore, 2 replace */
static inline ail_st ail2b_encode(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj enc, ail_obj err) {
    if (so.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "expected str");
    ail_str s = ail_view_to_str(so);
    int e = (int)enc.i, eh = (int)err.i;
    static const char *names[3] = {"utf-8", "ascii", "latin-1"};
    unsigned char *buf = (unsigned char *)ail_xmalloc((size_t)(s.n * 3 + 1));
    int64_t k = 0, pos = 0;
    for (int64_t i = 0; i < s.n; pos++) {
        uint32_t c = ail_chr(s, i); int64_t start = i; i++;
        if (c >= 0xD800 && c < 0xDC00 && i < s.n) {
            uint32_t d = ail_chr(s, i);
            if (d >= 0xDC00 && d < 0xE000) { c = 0x10000 + ((c - 0xD800) << 10) + (d - 0xDC00); i++; }
        }
        (void)start;
        int bad = e == 0 ? (c >= 0xD800 && c < 0xE000) : e == 1 ? c >= 0x80 : c >= 0x100;
        if (bad) {
            if (eh == 1) continue;
            if (eh == 2) { buf[k++] = '?'; continue; }
            /* strict: CPython reports the run of characters the codec cannot encode */
            int64_t endpos = pos + 1, j = i;
            while (j < s.n) {
                uint32_t c2 = ail_chr(s, j); int64_t j2 = j + 1;
                if (c2 >= 0xD800 && c2 < 0xDC00 && j2 < s.n) {
                    uint32_t d2 = ail_chr(s, j2);
                    if (d2 >= 0xDC00 && d2 < 0xE000) { c2 = 0x10000 + ((c2 - 0xD800) << 10) + (d2 - 0xDC00); j2++; }
                }
                int bad2 = e == 0 ? (c2 >= 0xD800 && c2 < 0xE000) : e == 1 ? c2 >= 0x80 : c2 >= 0x100;
                if (!bad2) break;
                endpos++; j = j2;
            }
            const char *why = e == 0 ? "surrogates not allowed" : e == 1 ? "ordinal not in range(128)" : "ordinal not in range(256)";
            if (endpos - pos == 1) {
                char nm[16]; ail2b_chrname(nm, sizeof nm, c);
                snprintf(ail2b_err, sizeof ail2b_err, "'%s' codec can't encode character %s in position %lld: %s", names[e], nm, (long long)pos, why);
            } else
                snprintf(ail2b_err, sizeof ail2b_err, "'%s' codec can't encode characters in position %lld-%lld: %s", names[e], (long long)pos, (long long)(endpos - 1), why);
            ail2b_errkind = 1;
            free(buf); *out = ail_box_none(); return AIL_OK;
        }
        if (e != 0 || c < 0x80) buf[k++] = (unsigned char)c;
        else if (c < 0x800) { buf[k++] = (unsigned char)(0xC0 | (c >> 6)); buf[k++] = (unsigned char)(0x80 | (c & 0x3F)); }
        else if (c < 0x10000) { buf[k++] = (unsigned char)(0xE0 | (c >> 12)); buf[k++] = (unsigned char)(0x80 | ((c >> 6) & 0x3F)); buf[k++] = (unsigned char)(0x80 | (c & 0x3F)); }
        else { buf[k++] = (unsigned char)(0xF0 | (c >> 18)); buf[k++] = (unsigned char)(0x80 | ((c >> 12) & 0x3F)); buf[k++] = (unsigned char)(0x80 | ((c >> 6) & 0x3F)); buf[k++] = (unsigned char)(0x80 | (c & 0x3F)); }
    }
    *out = ail2b_from_buf(cx, buf, k);
    free(buf);
    return AIL_OK;
}
/* one UTF-8 sequence at p[i]: its code point, or the length of the invalid part (CPython's maximal subpart) and why */
static inline int64_t ail2b_utf8_step(const uint16_t *p, int64_t n, int64_t i, uint32_t *cp, const char **why) {
    uint32_t c = p[i];
    if (c < 0x80) { *cp = c; return 1; }
    int need; uint32_t lo = 0x80, hi = 0xBF;
    if (c < 0xC2) { *why = "invalid start byte"; return -1; }
    else if (c < 0xE0) { need = 1; *cp = c & 0x1F; }
    else if (c < 0xF0) { need = 2; *cp = c & 0x0F; if (c == 0xE0) lo = 0xA0; if (c == 0xED) hi = 0x9F; }
    else if (c < 0xF5) { need = 3; *cp = c & 0x07; if (c == 0xF0) lo = 0x90; if (c == 0xF4) hi = 0x8F; }
    else { *why = "invalid start byte"; return -1; }
    for (int k = 1; k <= need; k++) {
        if (i + k >= n) { *why = "unexpected end of data"; return -(int64_t)k; }
        uint32_t d = p[i + k];
        if (d < lo || d > hi) { *why = "invalid continuation byte"; return -(int64_t)k; }
        lo = 0x80; hi = 0xBF;
        *cp = (*cp << 6) | (d & 0x3F);
    }
    return need + 1;
}
static inline ail_st ail2b_decode(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj enc, ail_obj err) {
    if (so.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "expected bytes");
    ail_str s = ail_view_to_str(so);
    int e = (int)enc.i, eh = (int)err.i;
    static const char *names[3] = {"utf-8", "ascii", "latin-1"};
    /* the units of a bytes str are bytes; a view's buffer is uint16_t unless it is pure ASCII */
    uint16_t *p = (uint16_t *)ail_xmalloc((size_t)(s.n + 1) * sizeof(uint16_t));
    for (int64_t i = 0; i < s.n; i++) p[i] = ail_chr(s, i);
    ail_strbuild bu = ail_str_buf(cx, s.n);
    int64_t o = 0;
    for (int64_t i = 0; i < s.n; ) {
        uint32_t cp = 0; const char *why = NULL; int64_t len;
        if (e == 2) { cp = p[i]; len = 1; }
        else if (e == 1) { cp = p[i]; if (cp < 0x80) len = 1; else { len = -1; why = "ordinal not in range(128)"; } }
        else len = ail2b_utf8_step(p, s.n, i, &cp, &why);
        if (len > 0) {
            if (cp > 0xFFFF) ail_die("decode: a code point above U+FFFF in the 16-bit v2 runtime");
            bu.buf[o++] = (uint16_t)cp; i += len; continue;
        }
        int64_t bad = -len;
        if (eh == 1) { i += bad; continue; }
        if (eh == 2) { bu.buf[o++] = 0xFFFD; i += bad; continue; }
        if (bad == 1)
            snprintf(ail2b_err, sizeof ail2b_err, "'%s' codec can't decode byte 0x%02x in position %lld: %s", names[e], (unsigned)p[i], (long long)i, why);
        else
            snprintf(ail2b_err, sizeof ail2b_err, "'%s' codec can't decode bytes in position %lld-%lld: %s", names[e], (long long)i, (long long)(i + bad - 1), why);
        ail2b_errkind = 2;
        free(p); *out = ail_box_none(); return AIL_OK;
    }
    free(p);
    *out = ail_str_buf_done(bu, o);
    return AIL_OK;
}
/* bytes(iterable of int) */
static inline ail_st ail2b_from_ints(ail_ctx *cx, ail_obj *out, ail_obj src) {
    AIL_FRAME_ENTER(cx, fr, 2);
    ail_st st = AIL_OK;
    if (src.tag == AIL_T_LIST || src.tag == AIL_T_TUPLE) fr.slots[0] = src;
    else if ((st = ail_bi_list_from_iter(cx, &fr.slots[0], src)) != AIL_OK) {
        if (st == AIL_EXC && ail_exc_matches_b(cx, AIL_B_TYPEERROR)) {
            ail_exc_clear(cx);
            char buf[96]; snprintf(buf, sizeof buf, "cannot convert '%s' object to bytes", ail_type_name(src.tag));
            st = ail_raise_c(cx, AIL_B_TYPEERROR, buf);
        }
        AIL_FRAME_LEAVE(cx, fr); return st;
    }
    ail_vecobj *v = (ail_vecobj *)fr.slots[0].o;
    for (int64_t i = 0; i < v->n; i++) {
        ail_obj x = v->p[i];
        if (x.tag != AIL_T_INT && x.tag != AIL_T_BOOL) {
            char buf[96]; snprintf(buf, sizeof buf, "'%s' object cannot be interpreted as an integer", ail_type_name(x.tag));
            st = ail_raise_c(cx, AIL_B_TYPEERROR, buf); AIL_FRAME_LEAVE(cx, fr); return st;
        }
        if (x.i < 0 || x.i > 255) { st = ail_raise_c(cx, AIL_B_VALUEERROR, "bytes must be in range(0, 256)"); AIL_FRAME_LEAVE(cx, fr); return st; }
    }
    ail_strback *b = ail_strback_alloc(cx, v->n);
    v = (ail_vecobj *)fr.slots[0].o;
    for (int64_t i = 0; i < v->n; i++) b->data[i] = (uint16_t)v->p[i].i;
    *out = ail_str_view((ail_gcobj *)b, 0, v->n);
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/* the bytes of a str as a list of int */
static inline ail_st ail2b_ints(ail_ctx *cx, ail_obj *out, ail_obj so) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    AIL_FRAME_ENTER(cx, fr, 2);
    fr.slots[0] = so;
    fr.slots[1] = ail_list_new(cx);
    ail_str s = ail_view_to_str(fr.slots[0]);
    ail_vecobj *v = (ail_vecobj *)fr.slots[1].o;
    ail_vec_reserve(cx, v, s.n);
    for (int64_t i = 0; i < s.n; i++) v->p[i] = ail_box_int(ail_chr(s, i));
    v->n = s.n;
    *out = fr.slots[1];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/* repr(b) without the leading b: CPython's quoting */
static inline ail_st ail2b_repr(ail_ctx *cx, ail_obj *out, ail_obj so) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    int sq = 0, dq = 0;
    for (int64_t i = 0; i < s.n; i++) { uint16_t c = ail_chr(s, i); if (c == '\'') sq = 1; else if (c == '"') dq = 1; }
    uint16_t q = (sq && !dq) ? '"' : '\'';
    ail_strbuild bu = ail_str_buf1(cx, s.n * 4 + 2, so);
    int64_t o = 0;
    bu.buf[o++] = q;
    for (int64_t i = 0; i < s.n; i++) {
        uint16_t c = ail_chr(s, i);
        if (c == q || c == '\\') { bu.buf[o++] = '\\'; bu.buf[o++] = c; }
        else if (c == '\t') { bu.buf[o++] = '\\'; bu.buf[o++] = 't'; }
        else if (c == '\n') { bu.buf[o++] = '\\'; bu.buf[o++] = 'n'; }
        else if (c == '\r') { bu.buf[o++] = '\\'; bu.buf[o++] = 'r'; }
        else if (c < 0x20 || c >= 0x7f) {
            static const char hx[] = "0123456789abcdef";
            bu.buf[o++] = '\\'; bu.buf[o++] = 'x'; bu.buf[o++] = hx[(c >> 4) & 15]; bu.buf[o++] = hx[c & 15];
        } else bu.buf[o++] = c;
    }
    bu.buf[o++] = q;
    *out = ail_str_buf_done(bu, o);
    return AIL_OK;
}
static inline int ail2b_isspace(uint16_t c) { return c == ' ' || (c >= 9 && c <= 13); }
static inline int ail2b_isupper(uint16_t c) { return c >= 'A' && c <= 'Z'; }
static inline int ail2b_islower(uint16_t c) { return c >= 'a' && c <= 'z'; }
static inline int ail2b_isdigit(uint16_t c) { return c >= '0' && c <= '9'; }
/* upper / lower / swapcase / title / capitalize, ASCII only: 0..4 */
static inline ail_st ail2b_case(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj which) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    ail_strbuild bu = ail_str_buf1(cx, s.n, so);
    int w = (int)which.i, prev = 0;
    for (int64_t i = 0; i < s.n; i++) {
        uint16_t c = ail_chr(s, i), r = c;
        int up = ail2b_isupper(c), lo = ail2b_islower(c);
        if (w == 0) { if (lo) r = c - 32; }
        else if (w == 1) { if (up) r = c + 32; }
        else if (w == 2) { if (lo) r = c - 32; else if (up) r = c + 32; }
        else if (w == 3) { if (prev) { if (up) r = c + 32; } else if (lo) r = c - 32; prev = up || lo; }
        else { if (i == 0) { if (lo) r = c - 32; } else if (up) r = c + 32; }
        bu.buf[i] = r;
    }
    *out = ail_str_buf_done(bu, s.n);
    return AIL_OK;
}
/* isalnum isalpha isascii isdigit islower isspace istitle isupper: 0..7 */
static inline ail_st ail2b_pred(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj which) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    int w = (int)which.i, r;
    if (w == 2) { r = 1; for (int64_t i = 0; i < s.n; i++) if (ail_chr(s, i) >= 0x80) { r = 0; break; } *out = ail_box_bool(r); return AIL_OK; }
    if (s.n == 0) { *out = ail_box_bool(0); return AIL_OK; }
    if (w == 4 || w == 7) {
        int cased = 0; r = 1;
        for (int64_t i = 0; i < s.n; i++) {
            uint16_t c = ail_chr(s, i);
            if (w == 4 ? ail2b_isupper(c) : ail2b_islower(c)) { r = 0; break; }
            if (w == 4 ? ail2b_islower(c) : ail2b_isupper(c)) cased = 1;
        }
        *out = ail_box_bool(r && cased); return AIL_OK;
    }
    if (w == 6) {
        int cased = 0, prev = 0; r = 1;
        for (int64_t i = 0; i < s.n; i++) {
            uint16_t c = ail_chr(s, i);
            if (ail2b_isupper(c)) { if (prev) { r = 0; break; } prev = 1; cased = 1; }
            else if (ail2b_islower(c)) { if (!prev) { r = 0; break; } prev = 1; cased = 1; }
            else prev = 0;
        }
        *out = ail_box_bool(r && cased); return AIL_OK;
    }
    r = 1;
    for (int64_t i = 0; i < s.n && r; i++) {
        uint16_t c = ail_chr(s, i);
        int a = ail2b_isupper(c) || ail2b_islower(c), d = ail2b_isdigit(c);
        r = w == 0 ? (a || d) : w == 1 ? a : w == 3 ? d : ail2b_isspace(c);
    }
    *out = ail_box_bool(r);
    return AIL_OK;
}
/* split() / rsplit() on ASCII whitespace, at most maxsplit times (< 0: no limit) */
static inline ail_st ail2b_split_ws(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj maxsplit, ail_obj right) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    AIL_FRAME_ENTER(cx, fr, 2);
    fr.slots[0] = so; fr.slots[1] = ail_list_new(cx);
    ail_str s = ail_view_to_str(so);
    int64_t ms = maxsplit.i, n = s.n, cnt = 0;
    if (!right.i) {
        int64_t i = 0;
        for (;;) {
            while (i < n && ail2b_isspace(ail_chr(s, i))) i++;
            if (i >= n) break;
            int64_t j = i;
            if (ms >= 0 && cnt >= ms) { j = n; while (j > i && ail2b_isspace(ail_chr(s, j - 1))) j--; }
            else while (j < n && !ail2b_isspace(ail_chr(s, j))) j++;
            ail_list_append(cx, fr.slots[1], ail_str_view(so.sv.backing, so.sv.off + i, j - i));
            cnt++; i = j;
        }
    } else {
        int64_t j = n;
        AIL_FRAME_ENTER(cx, f2, 1);
        f2.slots[0] = ail_list_new(cx);
        for (;;) {
            while (j > 0 && ail2b_isspace(ail_chr(s, j - 1))) j--;
            if (j <= 0) break;
            int64_t i = j;
            if (ms >= 0 && cnt >= ms) { i = 0; while (i < j && ail2b_isspace(ail_chr(s, i))) i++; }
            else while (i > 0 && !ail2b_isspace(ail_chr(s, i - 1))) i--;
            ail_list_append(cx, f2.slots[0], ail_str_view(so.sv.backing, so.sv.off + i, j - i));
            cnt++; j = i;
        }
        ail_vecobj *v = (ail_vecobj *)f2.slots[0].o;
        for (int64_t k = v->n - 1; k >= 0; k--) ail_list_append(cx, fr.slots[1], v->p[k]);
        AIL_FRAME_LEAVE(cx, f2);
    }
    *out = fr.slots[1];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/* strip() / lstrip() / rstrip() of ASCII whitespace: 0 both, 1 left, 2 right */
static inline ail_st ail2b_strip_ws(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj which) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    int64_t i = 0, j = s.n;
    if (which.i != 2) while (i < j && ail2b_isspace(ail_chr(s, i))) i++;
    if (which.i != 1) while (j > i && ail2b_isspace(ail_chr(s, j - 1))) j--;
    *out = ail_str_view(so.sv.backing, so.sv.off + i, j - i);
    return AIL_OK;
}
/* splitlines(keepends): \n, \r and \r\n only */
static inline ail_st ail2b_splitlines(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj keep) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    AIL_FRAME_ENTER(cx, fr, 2);
    fr.slots[0] = so; fr.slots[1] = ail_list_new(cx);
    ail_str s = ail_view_to_str(so);
    int64_t i = 0, n = s.n;
    while (i < n) {
        int64_t j = i;
        while (j < n && ail_chr(s, j) != '\n' && ail_chr(s, j) != '\r') j++;
        int64_t e = j;
        if (j < n) { if (ail_chr(s, j) == '\r' && j + 1 < n && ail_chr(s, j + 1) == '\n') j += 2; else j++; }
        ail_list_append(cx, fr.slots[1], ail_str_view(so.sv.backing, so.sv.off + i, (keep.i ? j : e) - i));
        i = j;
    }
    *out = fr.slots[1];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
/* translate(table, delete): table is None or a 256-unit str */
static inline ail_st ail2b_translate(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj table, ail_obj del) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    unsigned char drop[256]; memset(drop, 0, sizeof drop);
    if (del.tag == AIL_T_STR) { ail_str d = ail_view_to_str(del); for (int64_t i = 0; i < d.n; i++) drop[ail_chr(d, i) & 255] = 1; }
    uint16_t map[256];
    for (int i = 0; i < 256; i++) map[i] = (uint16_t)i;
    if (table.tag == AIL_T_STR) {
        ail_str t = ail_view_to_str(table);
        if (t.n != 256) return ail_raise_c(cx, AIL_B_VALUEERROR, "translation table must be 256 characters long");
        for (int i = 0; i < 256; i++) map[i] = ail_chr(t, i);
    }
    ail_strbuild bu = ail_str_buf1(cx, s.n, so);
    int64_t o = 0;
    s = ail_view_to_str(so);
    for (int64_t i = 0; i < s.n; i++) { uint16_t c = ail_chr(s, i) & 255; if (!drop[c]) bu.buf[o++] = map[c]; }
    *out = ail_str_buf_done(bu, o);
    return AIL_OK;
}
/* hex(): two lower-case digits a byte */
static inline ail_st ail2b_hex(ail_ctx *cx, ail_obj *out, ail_obj so) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    ail_strbuild bu = ail_str_buf1(cx, s.n * 2, so);
    static const char hx[] = "0123456789abcdef";
    for (int64_t i = 0; i < s.n; i++) { uint16_t c = ail_chr(s, i); bu.buf[2 * i] = hx[(c >> 4) & 15]; bu.buf[2 * i + 1] = hx[c & 15]; }
    *out = ail_str_buf_done(bu, s.n * 2);
    return AIL_OK;
}
/* bytes.fromhex(s): None and ail2b_err on a bad digit */
static inline int ail2b_hexval(uint16_t c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static inline ail_st ail2b_fromhex(ail_ctx *cx, ail_obj *out, ail_obj so) {
    if (so.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "fromhex() argument must be str");
    ail_str s = ail_view_to_str(so);
    ail_strbuild bu = ail_str_buf1(cx, s.n / 2 + 1, so);
    int64_t o = 0, i = 0;
    while (i < s.n) {
        uint16_t c = ail_chr(s, i);
        if (c == ' ' || (c >= 9 && c <= 13)) { i++; continue; }
        int hi = ail2b_hexval(c);
        if (hi < 0 || i + 1 >= s.n || ail2b_hexval(ail_chr(s, i + 1)) < 0) {
            int64_t at = hi < 0 ? i : i + 1;
            if (hi >= 0 && i + 1 >= s.n) at = i + 1;
            snprintf(ail2b_err, sizeof ail2b_err, "non-hexadecimal number found in fromhex() arg at position %lld", (long long)at);
            ail2b_errkind = 4; *out = ail_box_none(); return AIL_OK;
        }
        bu.buf[o++] = (uint16_t)(hi * 16 + ail2b_hexval(ail_chr(s, i + 1)));
        i += 2;
    }
    *out = ail_str_buf_done(bu, o);
    return AIL_OK;
}
/* 1 when every unit of s is ASCII and none is one of the separators int()/float() of a str would skip but
   of bytes would not (0x1c..0x1f) */
static inline ail_st ail2b_numsafe(ail_ctx *cx, ail_obj *out, ail_obj so) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    int r = 1;
    for (int64_t i = 0; i < s.n; i++) { uint16_t c = ail_chr(s, i); if (c >= 0x80 || (c >= 0x1c && c <= 0x1f)) { r = 0; break; } }
    *out = ail_box_bool(r);
    return AIL_OK;
}
'''

BYTESFILE = r'''
/* ---- binary files on the general path (safetyrt.py BYTESFILE): filelib's primitives over ailfile_core.h ---- */
static ail_st ail2bf_read(ail_ctx *cx, ail_obj *out, ail_obj h, ail_obj n, int which) {
    int64_t hi = 0, ni = 0; ail_st st;
    if ((st = ailo_int_arg(cx, h, &hi)) != AIL_OK) return st;
    if (which != 2 && (st = ailo_int_arg(cx, n, &ni)) != AIL_OK) return st;
    ailf_buf b; b.p = NULL; b.n = b.cap = 0;
    int r = which == 0 ? ailf_bread(hi, ni, &b) : which == 1 ? ailf_breadline(hi, ni, &b) : ailf_bnext(hi, &b);
    if (r < 0) { free(b.p); return ailo_fail(cx); }
    *out = ail2b_from_buf(cx, b.p ? (const unsigned char *)b.p : (const unsigned char *)"", b.n);
    free(b.p);
    return AIL_OK;
}
static ail_st ail2bf_write(ail_ctx *cx, ail_obj *out, ail_obj h, ail_obj data) {
    int64_t hi = 0; ail_st st;
    if ((st = ailo_int_arg(cx, h, &hi)) != AIL_OK) return st;
    if ((st = ail2b_need(cx, data)) != AIL_OK) return st;
    ail_str v = ail_view_to_str(data);
    uint8_t *p = (uint8_t *)ail_xmalloc((size_t)(v.n ? v.n : 1));
    for (int64_t i = 0; i < v.n; i++) p[i] = (uint8_t)ail_chr(v, i);
    int64_t r = ailf_bwrite(hi, p, v.n);
    free(p);
    if (r < 0) return ailo_fail(cx);
    *out = ail_box_int(r);
    return AIL_OK;
}
'''

FMT = r'''
/* ---- format specs and %-formatting over all the standard types (safetyrt.py FMT) ----
   CPython 3.12's format() mini-language for int, bool, float and str, and printf-style `%` with a
   format or arguments known only at run time. */
typedef struct { uint16_t *p; int64_t n, cap; } ail2f_buf;
static inline void ail2f_put(ail2f_buf *b, uint16_t c) {
    if (b->n == b->cap) { b->cap = b->cap ? b->cap * 2 : 64; b->p = (uint16_t *)realloc(b->p, (size_t)b->cap * sizeof(uint16_t)); if (!b->p) ail_die("out of memory"); }
    b->p[b->n++] = c;
}
static inline void ail2f_puts(ail2f_buf *b, const char *s) { while (*s) ail2f_put(b, (unsigned char)*s++); }
static inline ail_obj ail2f_done(ail_ctx *cx, ail2f_buf *b) {
    ail_strbuild bu = ail_str_buf(cx, b->n);
    if (b->n) memcpy(bu.buf, b->p, (size_t)b->n * sizeof(uint16_t));
    free(b->p); b->p = NULL;
    return ail_str_buf_done(bu, b->n);
}
typedef struct { uint16_t fill; char align, sign; int alt, zero, fill_given, has_width, has_prec; int64_t width, prec; char group, type; } ail2f_spec;
/* 0, or -1 with the ValueError text in msg */
static inline int ail2f_parse(ail_str s, ail2f_spec *f, char *msg, size_t msz) {
    memset(f, 0, sizeof *f); f->fill = ' ';
    int64_t i = 0, n = s.n;
    #define AIL2F_ALIGN(c) ((c) == '<' || (c) == '>' || (c) == '=' || (c) == '^')
    if (n >= 2 && AIL2F_ALIGN(ail_chr(s, 1))) { f->fill = ail_chr(s, 0); f->align = (char)ail_chr(s, 1); f->fill_given = 1; i = 2; }
    else if (n >= 1 && AIL2F_ALIGN(ail_chr(s, 0))) { f->align = (char)ail_chr(s, 0); i = 1; }
    if (i < n && (ail_chr(s, i) == '+' || ail_chr(s, i) == '-' || ail_chr(s, i) == ' ')) f->sign = (char)ail_chr(s, i++);
    if (i < n && ail_chr(s, i) == 'z') i++;
    if (i < n && ail_chr(s, i) == '#') { f->alt = 1; i++; }
    /* CPython's '0' flag: the padding fills with zeros, but only where the spec did not write a
       fill character -- `{:<06d}` is '420000' and `{:*<06d}` is '42****' (there the '0' is the
       first digit of the width). The '=' alignment the flag implies is added by the padding code
       (ail2f_pad_num), not here: a written alignment must stay visible to the str checks. */
    if (i < n && ail_chr(s, i) == '0') { f->zero = 1; if (!f->fill_given) f->fill = '0'; i++; }
    while (i < n && ail_chr(s, i) >= '0' && ail_chr(s, i) <= '9') {
        f->has_width = 1;
        if (f->width > 100000000) { snprintf(msg, msz, "Too many decimal digits in format string"); return -1; }
        f->width = f->width * 10 + (ail_chr(s, i++) - '0');
    }
    if (i < n && (ail_chr(s, i) == ',' || ail_chr(s, i) == '_')) f->group = (char)ail_chr(s, i++);
    if (i < n && (ail_chr(s, i) == ',' || ail_chr(s, i) == '_')) { snprintf(msg, msz, "Cannot specify both ',' and '_'."); return -1; }
    if (i < n && ail_chr(s, i) == '.') {
        i++;
        if (!(i < n && ail_chr(s, i) >= '0' && ail_chr(s, i) <= '9')) { snprintf(msg, msz, "Format specifier missing precision"); return -1; }
        f->has_prec = 1;
        while (i < n && ail_chr(s, i) >= '0' && ail_chr(s, i) <= '9') {
            if (f->prec > 100000000) { snprintf(msg, msz, "Too many decimal digits in format string"); return -1; }
            f->prec = f->prec * 10 + (ail_chr(s, i++) - '0');
        }
    }
    if (n - i > 1) { snprintf(msg, msz, "Invalid format specifier"); return -1; }
    if (i < n) {
        uint16_t t = ail_chr(s, i);
        if (t > 127) { snprintf(msg, msz, "Invalid format specifier"); return -1; }
        f->type = (char)t;
    }
    return 0;
}
/* The fill in effect: the '0' flag fills with zeros only where no fill character was written
   (`{:*<06d}` has fill '*' -- its '0' is the first digit of the width). */
static inline uint16_t ail2f_zfill(ail2f_spec *f) {
    return (f->zero && !f->fill_given) ? (uint16_t)'0' : f->fill;
}
/* body is the digits (and point / exponent) without sign; prefix is "0x" etc. Numbers: default align '>' */
static inline ail_obj ail2f_pad_num(ail_ctx *cx, const char *sign, const char *prefix, const char *body, ail2f_spec *f) {
    /* numbers default to '>' alignment, or to '=' when the '0' flag asked for zero padding */
    char align = f->align ? f->align : (f->zero ? '=' : '>');
    uint16_t fill = ail2f_zfill(f);
    /* grouping of the integer digits */
    char grouped[512]; const char *b = body;
    if (f->group) {
        int64_t blen = (int64_t)strlen(body), ip = 0;
        while (ip < blen && ((body[ip] >= '0' && body[ip] <= '9') || ((f->type == 'x' || f->type == 'X' || f->type == 'b' || f->type == 'o')
               && ((body[ip] >= 'a' && body[ip] <= 'f') || (body[ip] >= 'A' && body[ip] <= 'F'))))) ip++;
        int every = (f->type == 'x' || f->type == 'X' || f->type == 'b' || f->type == 'o') ? 4 : 3;
        int64_t o = 0;
        int64_t zero_width = 0;
        if (align == '=' && fill == '0') {
            /* '=' alignment with a zero fill: the grouping covers the padding zeros too
               (CPython: '{:08,d}'.format(1234) is '0,001,234', '{:<08,d}' is '1,234000') */
            zero_width = f->width - (int64_t)strlen(sign) - (int64_t)strlen(prefix) - (blen - ip);
        }
        int64_t digits = ip, total = digits;
        if (zero_width > 0) {
            /* the smallest digit count whose grouped width reaches zero_width */
            while (total + (total - 1) / every < zero_width) total++;
        }
        for (int64_t k = 0; k < total; k++) {
            int64_t from_right = total - k;
            if (k > 0 && from_right % every == 0 && o < 500) grouped[o++] = f->group;
            int64_t src = k - (total - digits);
            if (o < 500) grouped[o++] = src >= 0 ? body[src] : '0';
        }
        for (int64_t k = ip; k < blen && o < 510; k++) grouped[o++] = body[k];
        grouped[o] = 0;
        b = grouped;
    }
    int64_t len = (int64_t)strlen(sign) + (int64_t)strlen(prefix) + (int64_t)strlen(b);
    int64_t pad = f->width > len ? f->width - len : 0;
    int64_t left = align == '>' ? pad : align == '^' ? pad / 2 : 0;
    int64_t right = align == '<' ? pad : align == '^' ? pad - pad / 2 : 0;
    int64_t mid = align == '=' ? pad : 0;
    ail2f_buf o = {0, 0, 0};
    for (int64_t k = 0; k < left; k++) ail2f_put(&o, fill);
    ail2f_puts(&o, sign); ail2f_puts(&o, prefix);
    for (int64_t k = 0; k < mid; k++) ail2f_put(&o, fill);
    ail2f_puts(&o, b);
    for (int64_t k = 0; k < right; k++) ail2f_put(&o, fill);
    return ail2f_done(cx, &o);
}
static inline ail_obj ail2f_pad_str(ail_ctx *cx, ail_str s, int64_t len, ail2f_spec *f, char dflt) {
    char align = f->align ? f->align : dflt;
    uint16_t fill = ail2f_zfill(f);
    int64_t pad = f->width > len ? f->width - len : 0;
    int64_t left = align == '>' ? pad : align == '^' ? pad / 2 : 0;
    ail2f_buf o = {0, 0, 0};
    for (int64_t k = 0; k < left; k++) ail2f_put(&o, fill);
    for (int64_t k = 0; k < len; k++) ail2f_put(&o, ail_chr(s, k));
    for (int64_t k = 0; k < pad - left; k++) ail2f_put(&o, fill);
    return ail2f_done(cx, &o);
}
static inline const char *ail2f_signstr(int neg, char sign) { return neg ? "-" : sign == '+' ? "+" : sign == ' ' ? " " : ""; }
/* the digits of a float in one of e E f F g G % or the repr form (type 0) */
static inline void ail2f_float_body(char *out, size_t osz, double v, ail2f_spec *f, char type) {
    if (isinf(v) || isnan(v)) {
        const char *t = isnan(v) ? "nan" : "inf";
        int up = type == 'E' || type == 'F' || type == 'G';
        snprintf(out, osz, "%s", up ? (isnan(v) ? "NAN" : "INF") : t);
        if (type == '%') snprintf(out, osz, "%s%%", t);
        return;
    }
    int64_t prec = f->has_prec ? f->prec : 6;
    if (prec > 300) prec = 300;
    char fmt[16];
    if (type == 0 && !f->has_prec) {
        ail_fmt_float(out, osz, v);
        return;
    }
    if (type == 0) {
        int p = prec < 1 ? 1 : (int)prec;
        char e[400]; snprintf(e, sizeof e, "%.*e", p - 1, v);
        char *ep = strchr(e, 'e'); int x = atoi(ep + 1);
        if (x < -4 || x >= p - 1) {
            /* exponent form: the digits without trailing zeros (unless #) */
            *ep = 0;
            if (!f->alt && strchr(e, '.')) { size_t L = strlen(e); while (L && e[L - 1] == '0') e[--L] = 0; if (L && e[L - 1] == '.') e[--L] = 0; }
            snprintf(out, osz, "%se%c%02d", e, x < 0 ? '-' : '+', x < 0 ? -x : x);
        } else {
            snprintf(out, osz, "%.*f", p - 1 - x < 0 ? 0 : p - 1 - x, v);
            if (!f->alt && strchr(out, '.')) { size_t L = strlen(out); while (L && out[L - 1] == '0') out[--L] = 0; }
            size_t L = strlen(out);
            if (L && out[L - 1] == '.') { out[L] = '0'; out[L + 1] = 0; }
            else if (!strchr(out, '.')) strcat(out, ".0");
        }
        return;
    }
    if (type == 'n') type = 'g';
    if (type == '%') { snprintf(fmt, sizeof fmt, "%%%s.*f", f->alt ? "#" : ""); snprintf(out, osz - 1, fmt, (int)prec, v * 100.0); strcat(out, "%"); return; }
    snprintf(fmt, sizeof fmt, "%%%s.*%c", f->alt ? "#" : "", type);
    snprintf(out, osz, fmt, (int)prec, v);
}
static inline ail_st ail2f_format(ail_ctx *cx, ail_obj *out, ail_obj x, ail_obj specobj) {
    if (specobj.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "format() argument 2 must be str");
    ail_str spec = ail_view_to_str(specobj);
    if (spec.n == 0) { *out = ail_obj_str(cx, x); return AIL_OK; }
    ail2f_spec f; char msg[160];
    if (ail2f_parse(spec, &f, msg, sizeof msg)) return ail_raise_c(cx, AIL_B_VALUEERROR, msg);
    char type = f.type;
    if (f.group && type) {
        /* CPython checks the grouping against the type before it looks at the value */
        if (type == 'n' || type == 's' || type == 'c' || (f.group == ',' && (type == 'b' || type == 'o' || type == 'x' || type == 'X'))) {
            snprintf(msg, sizeof msg, "Cannot specify '%c' with '%c'.", f.group, type);
            return ail_raise_c(cx, AIL_B_VALUEERROR, msg);
        }
    }
    if (x.tag == AIL_T_STR) {
        if (type && type != 's') { snprintf(msg, sizeof msg, "Unknown format code '%c' for object of type 'str'", type); return ail_raise_c(cx, AIL_B_VALUEERROR, msg); }
        if (f.sign) return ail_raise_c(cx, AIL_B_VALUEERROR, "Sign not allowed in string format specifier");
        if (f.alt) return ail_raise_c(cx, AIL_B_VALUEERROR, "Alternate form (#) not allowed in string format specifier");
        if (f.align == '=') return ail_raise_c(cx, AIL_B_VALUEERROR, "'=' alignment not allowed in string format specifier");
        if (f.group) { snprintf(msg, sizeof msg, "Cannot specify '%c' with 's'.", f.group); return ail_raise_c(cx, AIL_B_VALUEERROR, msg); }
        ail_str s = ail_view_to_str(x);
        int64_t len = s.n;
        if (f.has_prec && f.prec < len) len = f.prec;
        *out = ail2f_pad_str(cx, s, len, &f, '<');
        return AIL_OK;
    }
    if (x.tag == AIL_T_INT || x.tag == AIL_T_BOOL) {
        if (type == 'e' || type == 'E' || type == 'f' || type == 'F' || type == 'g' || type == 'G' || type == '%') {
            char body[400]; double d = (double)x.i;
            ail2f_float_body(body, sizeof body, fabs(d), &f, type);
            *out = ail2f_pad_num(cx, ail2f_signstr(d < 0, f.sign), "", body, &f); return AIL_OK;
        }
        if (type && type != 'd' && type != 'n' && type != 'b' && type != 'o' && type != 'x' && type != 'X' && type != 'c') {
            snprintf(msg, sizeof msg, "Unknown format code '%c' for object of type '%s'", type, x.tag == AIL_T_BOOL ? "bool" : "int");
            return ail_raise_c(cx, AIL_B_VALUEERROR, msg);
        }
        if (f.has_prec) return ail_raise_c(cx, AIL_B_VALUEERROR, "Precision not allowed in integer format specifier");
        if (type == 'c') {
            if (f.sign) return ail_raise_c(cx, AIL_B_VALUEERROR, "Sign not allowed with integer format specifier 'c'");
            if (f.alt) return ail_raise_c(cx, AIL_B_VALUEERROR, "Alternate form (#) not allowed with integer format specifier 'c'");
            if (x.i < 0 || x.i > 0x10FFFF) return ail_raise_c(cx, AIL_B_OVERFLOWERROR, "%c arg not in range(0x110000)");
            if (x.i > 0xFFFF) ail_die("format 'c': a code point above U+FFFF in the 16-bit v2 runtime");
            uint16_t c = (uint16_t)x.i; ail_str s; s.p = &c; s.n = 1; s.bytes = 0;
            *out = ail2f_pad_str(cx, s, 1, &f, '>'); return AIL_OK;
        }
        if (f.group == ',' && (type == 'b' || type == 'o' || type == 'x' || type == 'X')) {
            snprintf(msg, sizeof msg, "Cannot specify ',' with '%c'.", type); return ail_raise_c(cx, AIL_B_VALUEERROR, msg);
        }
        if (f.group && type == 'n') { snprintf(msg, sizeof msg, "Cannot specify '%c' with 'n'.", f.group); return ail_raise_c(cx, AIL_B_VALUEERROR, msg); }
        uint64_t m = x.i < 0 ? (uint64_t)0 - (uint64_t)x.i : (uint64_t)x.i;
        char body[80]; int base = type == 'b' ? 2 : type == 'o' ? 8 : (type == 'x' || type == 'X') ? 16 : 10;
        const char *dig = type == 'X' ? "0123456789ABCDEF" : "0123456789abcdef";
        char tmp[80]; int k = 0;
        do { tmp[k++] = dig[m % (uint64_t)base]; m /= (uint64_t)base; } while (m);
        for (int i = 0; i < k; i++) body[i] = tmp[k - 1 - i];
        body[k] = 0;
        const char *prefix = !f.alt ? "" : base == 2 ? "0b" : base == 8 ? "0o" : type == 'X' ? "0X" : base == 16 ? "0x" : "";
        *out = ail2f_pad_num(cx, ail2f_signstr(x.i < 0, f.sign), prefix, body, &f);
        return AIL_OK;
    }
    if (x.tag == AIL_T_FLOAT) {
        if (type && type != 'e' && type != 'E' && type != 'f' && type != 'F' && type != 'g' && type != 'G' && type != '%' && type != 'n') {
            snprintf(msg, sizeof msg, "Unknown format code '%c' for object of type 'float'", type);
            return ail_raise_c(cx, AIL_B_VALUEERROR, msg);
        }
        if (f.group && type == 'n') { snprintf(msg, sizeof msg, "Cannot specify '%c' with 'n'.", f.group); return ail_raise_c(cx, AIL_B_VALUEERROR, msg); }
        double d = ail_float_val(x);
        char body[400];
        int neg = signbit(d) && !isnan(d);
        ail2f_float_body(body, sizeof body, fabs(d), &f, type);
        *out = ail2f_pad_num(cx, ail2f_signstr(neg, f.sign), "", body, &f);
        return AIL_OK;
    }
    if (x.tag == AIL_T_NONE) return ail_raise_c(cx, AIL_B_TYPEERROR, "unsupported format string passed to NoneType.__format__");
    /* anything else formats its str() as a string would, the way object.__format__ does for an empty spec only */
    const char *tn = ail_type_name(x.tag);
    char nb[80];
    if ((x.tag == AIL_T_INST || x.tag == AIL_T_EXC) && ((ail_instobj *)x.o)->cls.tag == AIL_T_CLASS) {   /* the class's own name */
        ail_str cs = ail_view_to_str(((ail_classobj *)((ail_instobj *)x.o)->cls.o)->name);
        size_t k = 0;
        for (int64_t i = 0; i < cs.n && k + 1 < sizeof nb; i++) { uint32_t ch = (uint32_t)ail_chr(cs, i); nb[k++] = ch < 128 ? (char)ch : '?'; }
        nb[k] = 0; tn = nb;
    }
    snprintf(msg, sizeof msg, "unsupported format string passed to %s.__format__", tn);
    return ail_raise_c(cx, AIL_B_TYPEERROR, msg);
}
/* fmt % args at run time (printf-style formatting, CPython's PyUnicode_Format) */
static inline ail_st ail2f_percent(ail_ctx *cx, ail_obj *out, ail_obj fmtobj, ail_obj args) {
    if (fmtobj.tag != AIL_T_STR) {
        char m[96]; snprintf(m, sizeof m, "unsupported operand type(s) for %%: '%s' and '%s'", ail_type_name(fmtobj.tag), ail_type_name(args.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, m);
    }
    AIL_FRAME_ENTER(cx, fr, 4);
    fr.slots[0] = fmtobj; fr.slots[1] = args;
    ail_str s = ail_view_to_str(fmtobj);
    int is_tuple = args.tag == AIL_T_TUPLE;
    int64_t nargs = is_tuple ? ((ail_vecobj *)args.o)->n : 1, ai = 0;
    int is_map = args.tag == AIL_T_DICT, used_map = 0;
    ail2f_buf o = {0, 0, 0};
    ail_st st = AIL_OK; char msg[160];
    for (int64_t i = 0; i < s.n; i++) {
        uint16_t c = ail_chr(s, i);
        if (c != '%') { ail2f_put(&o, c); continue; }
        int64_t start = i;
        i++;
        if (i >= s.n) { st = ail_raise_c(cx, AIL_B_VALUEERROR, "incomplete format"); goto fail; }
        ail_obj arg; int have = 0;
        if (ail_chr(s, i) == '(') {
            if (!is_map) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "format requires a mapping"); goto fail; }
            int64_t depth = 1, k0 = ++i;
            while (i < s.n && depth) { if (ail_chr(s, i) == '(') depth++; else if (ail_chr(s, i) == ')') depth--; if (depth) i++; }
            if (i >= s.n) { st = ail_raise_c(cx, AIL_B_VALUEERROR, "incomplete format key"); goto fail; }
            fr.slots[2] = ail_str_view(fmtobj.sv.backing, fmtobj.sv.off + k0, i - k0);
            i++;
            if ((st = ail_dict_getitem(cx, &fr.slots[3], args, fr.slots[2])) != AIL_OK) goto fail;
            arg = fr.slots[3]; have = 1; used_map = 1;
        }
        ail2f_spec f; memset(&f, 0, sizeof f); f.fill = ' ';
        int left = 0;
        for (; i < s.n; i++) {
            uint16_t q = ail_chr(s, i);
            if (q == '-') left = 1; else if (q == '+') f.sign = '+'; else if (q == ' ') { if (f.sign != '+') f.sign = ' '; }
            else if (q == '#') f.alt = 1; else if (q == '0') f.zero = 1; else break;
        }
        if (i < s.n && ail_chr(s, i) == '*') {
            if (!is_tuple || ai >= nargs) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "not enough arguments for format string"); goto fail; }
            ail_obj w = ((ail_vecobj *)args.o)->p[ai++];
            if (w.tag != AIL_T_INT && w.tag != AIL_T_BOOL) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "* wants int"); goto fail; }
            f.width = w.i; if (f.width < 0) { left = 1; f.width = -f.width; }
            i++;
        } else while (i < s.n && ail_chr(s, i) >= '0' && ail_chr(s, i) <= '9') f.width = f.width * 10 + (ail_chr(s, i++) - '0');
        if (i < s.n && ail_chr(s, i) == '.') {
            i++; f.has_prec = 1;
            if (i < s.n && ail_chr(s, i) == '*') {
                if (!is_tuple || ai >= nargs) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "not enough arguments for format string"); goto fail; }
                ail_obj w = ((ail_vecobj *)args.o)->p[ai++];
                if (w.tag != AIL_T_INT && w.tag != AIL_T_BOOL) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "* wants int"); goto fail; }
                f.prec = w.i < 0 ? 0 : w.i; i++;
            } else while (i < s.n && ail_chr(s, i) >= '0' && ail_chr(s, i) <= '9') f.prec = f.prec * 10 + (ail_chr(s, i++) - '0');
        }
        while (i < s.n && (ail_chr(s, i) == 'h' || ail_chr(s, i) == 'l' || ail_chr(s, i) == 'L')) i++;
        if (i >= s.n) { st = ail_raise_c(cx, AIL_B_VALUEERROR, "incomplete format"); goto fail; }
        uint16_t t = ail_chr(s, i);
        if (t == '%') { ail2f_put(&o, '%'); continue; }
        if (!have) {
            if (is_tuple) {
                if (ai >= nargs) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "not enough arguments for format string"); goto fail; }
                arg = ((ail_vecobj *)args.o)->p[ai++];
            } else {
                if (ai >= 1) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "not enough arguments for format string"); goto fail; }
                arg = args; ai++;
            }
        }
        /* '-' and '0' together: CPython's %-formatting IGNORES the '0' flag next to '-'
           ("%-08d" % 255 is '255     '), so the padding is spaces there. */
        if (left) { f.align = '<'; f.zero = 0; } else f.align = '>';
        if (f.zero) { f.align = 0; }
        f.has_width = f.width > 0;
        ail_obj piece;
        if (t == 's' || t == 'r' || t == 'a') {
            fr.slots[2] = t == 's' ? ail_obj_str(cx, arg) : ail_obj_repr(cx, arg);
            ail_str v = ail_view_to_str(fr.slots[2]);
            int64_t len = v.n; if (f.has_prec && f.prec < len) len = f.prec;
            f.zero = 0; if (!f.align) f.align = '>';
            piece = ail2f_pad_str(cx, v, len, &f, '>');
        } else if (t == 'd' || t == 'i' || t == 'u' || t == 'o' || t == 'x' || t == 'X') {
            int64_t iv;
            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) iv = arg.i;
            else if (arg.tag == AIL_T_FLOAT && (t == 'd' || t == 'i' || t == 'u')) {
                double d = ail_float_val(arg);
                if (isnan(d)) { st = ail_raise_c(cx, AIL_B_VALUEERROR, "cannot convert float NaN to integer"); goto fail; }
                if (isinf(d)) { st = ail_raise_c(cx, AIL_B_OVERFLOWERROR, "cannot convert float infinity to integer"); goto fail; }
                if (d >= 9223372036854775808.0 || d < -9223372036854775808.0) { st = ail_hit_limit(cx, "integer overflow", "int64"); goto fail; }
                iv = (int64_t)d;
            } else {
                if (t == 'd' || t == 'i' || t == 'u') snprintf(msg, sizeof msg, "%%%c format: a real number is required, not %s", (char)t, ail_type_name(arg.tag));
                else snprintf(msg, sizeof msg, "%%%c format: an integer is required, not %s", (char)t, ail_type_name(arg.tag));
                st = ail_raise_c(cx, AIL_B_TYPEERROR, msg); goto fail;
            }
            uint64_t m = iv < 0 ? (uint64_t)0 - (uint64_t)iv : (uint64_t)iv;
            int base = t == 'o' ? 8 : (t == 'x' || t == 'X') ? 16 : 10;
            const char *dig = t == 'X' ? "0123456789ABCDEF" : "0123456789abcdef";
            char tmp[80], body[200]; int k = 0;
            do { tmp[k++] = dig[m % (uint64_t)base]; m /= (uint64_t)base; } while (m);
            int z = 0;
            if (f.has_prec) while (k + z < f.prec && k + z < 150) body[z++] = '0';
            for (int q = 0; q < k; q++) body[z + q] = tmp[k - 1 - q];
            body[z + k] = 0;
            const char *prefix = !f.alt ? "" : base == 8 ? "0o" : t == 'X' ? "0X" : base == 16 ? "0x" : "";
            f.type = 'd'; f.has_prec = 0;
            piece = ail2f_pad_num(cx, ail2f_signstr(iv < 0, f.sign), prefix, body, &f);
        } else if (t == 'e' || t == 'E' || t == 'f' || t == 'F' || t == 'g' || t == 'G') {
            double d;
            if (arg.tag == AIL_T_FLOAT) d = ail_float_val(arg);
            else if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) d = (double)arg.i;
            else { snprintf(msg, sizeof msg, "must be real number, not %s", ail_type_name(arg.tag)); st = ail_raise_c(cx, AIL_B_TYPEERROR, msg); goto fail; }
            char body[400];
            if (!f.has_prec) { f.has_prec = 1; f.prec = 6; }
            ail2f_float_body(body, sizeof body, fabs(d), &f, (char)t);
            f.type = (char)t; f.has_prec = 0;
            piece = ail2f_pad_num(cx, ail2f_signstr(signbit(d) && !isnan(d), f.sign), "", body, &f);
        } else if (t == 'c') {
            uint16_t ch;
            if (arg.tag == AIL_T_INT || arg.tag == AIL_T_BOOL) {
                if (arg.i < 0 || arg.i > 0x10FFFF) { st = ail_raise_c(cx, AIL_B_OVERFLOWERROR, "%c arg not in range(0x110000)"); goto fail; }
                if (arg.i > 0xFFFF) ail_die("%c: a code point above U+FFFF in the 16-bit v2 runtime");
                ch = (uint16_t)arg.i;
            } else if (arg.tag == AIL_T_STR && ail_view_to_str(arg).n == 1) ch = ail_chr(ail_view_to_str(arg), 0);
            else { st = ail_raise_c(cx, AIL_B_TYPEERROR, "%c requires int or char"); goto fail; }
            ail_str v; v.p = &ch; v.n = 1; v.bytes = 0;
            f.zero = 0; if (!f.align) f.align = '>';
            piece = ail2f_pad_str(cx, v, 1, &f, '>');
        } else {
            if (t >= 32 && t < 127) snprintf(msg, sizeof msg, "unsupported format character '%c' (0x%x) at index %lld", (char)t, (unsigned)t, (long long)i);
            else snprintf(msg, sizeof msg, "unsupported format character '\\x%x' (0x%x) at index %lld", (unsigned)t, (unsigned)t, (long long)i);
            st = ail_raise_c(cx, AIL_B_VALUEERROR, msg); goto fail;
        }
        (void)start;
        ail_str pv = ail_view_to_str(piece);
        for (int64_t k = 0; k < pv.n; k++) ail2f_put(&o, ail_chr(pv, k));
    }
    if (!used_map && !is_map && ai < nargs) { st = ail_raise_c(cx, AIL_B_TYPEERROR, "not all arguments converted during string formatting"); goto fail; }
    *out = ail2f_done(cx, &o);
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
fail:
    free(o.p);
    AIL_FRAME_LEAVE(cx, fr);
    return st;
}
'''

GEN = r'''
/* ---- generator functions on the general path (safetyrt.py GEN) ----
   A generator runs its body on a C stack of its own (ucontext; fibers on Windows). `yield` switches back to
   the caller with the value, next()/send() switches in again. The frames of a suspended generator and of the
   callers waiting for a running one are not on cx->frames, so the collector reaches them through the hook
   below: a suspended generator's frames are marked only when its object is, and a generator nobody can
   reach any more gives its stack back. */
#ifdef _WIN32
#include <windows.h>
#else
#include <ucontext.h>
#include <sys/mman.h>
#endif
#if defined(__x86_64__) && defined(__linux__)
/* glibc's swapcontext saves the signal mask with two system calls a switch; a switch here only needs the
   callee-saved registers and the stack pointer (System V AMD64) */
#define AIL2G_ASM 1
void ail2g_switch(void **from, void *to);
__asm__(".text\n.globl ail2g_switch\n.hidden ail2g_switch\n.type ail2g_switch,@function\nail2g_switch:\n"
        "  pushq %rbp\n  pushq %rbx\n  pushq %r12\n  pushq %r13\n  pushq %r14\n  pushq %r15\n"
        "  movq %rsp, (%rdi)\n  movq %rsi, %rsp\n"
        "  popq %r15\n  popq %r14\n  popq %r13\n  popq %r12\n  popq %rbx\n  popq %rbp\n  ret\n"
        ".size ail2g_switch, .-ail2g_switch\n");
#endif
typedef ail_st (*ail2g_body)(ail_ctx *, ail_obj *, ail_obj);
enum { AIL2G_NEW, AIL2G_SUSPENDED, AIL2G_RUNNING, AIL2G_DONE };
typedef struct ail2g {
    int state, scanned;
    ail2g_body body;
    ail_gcobj *inst;            /* the generator object (not owned: the collector decides) */
    ail_obj args;               /* while NEW: the call's arguments (also an attribute of the object) */
    ail_frame *top;             /* the frames of the body while it is suspended */
    ail_obj value, sent;
    ail_st status;
    const char *name;
#ifdef _WIN32
    LPVOID fiber, caller;
#else
    ucontext_t ctx, caller;
    void *stack; size_t stack_size;
    void *sp, *caller_sp;
#endif
} ail2g;
typedef struct ail2g_wait { ail_frame *top; struct ail2g_wait *next; } ail2g_wait;
static ail2g **ail2g_tab; static int64_t ail2g_n, ail2g_cap;
static ail2g *ail2g_current;
static ail2g_wait *ail2g_waiting;    /* the callers' frames while a generator runs */
static ail_ctx *ail2g_cx;
static int64_t ail2g_id_h, ail2g_id_a;
#define AIL2G_STACK ((size_t)8 << 20)

#ifndef _WIN32
/* stacks given back are kept for the next generator: no mapping and no first-touch faults per generator */
static void *ail2g_pool[256]; static int ail2g_pooled;
#endif
/* every 256 new stacks the collector runs, so generators left unfinished are found and their stacks
   reused before many pile up */
static int64_t ail2g_fresh;
static void ail2g_free_stack(ail2g *g) {
#ifdef _WIN32
    if (g->fiber) { DeleteFiber(g->fiber); g->fiber = NULL; }
#else
    if (g->stack) {
        if (ail2g_pooled < 256) ail2g_pool[ail2g_pooled++] = g->stack;
        else munmap(g->stack, g->stack_size);
        g->stack = NULL;
    }
#endif
}
static inline void ail2g_mark_chain(ail_frame *f) {
    for (; f; f = f->prev) for (int32_t i = 0; i < f->n; i++) ail_gc_mark_value(f->slots[i]);
}
static void ail2g_gc_hook(ail_ctx *cx) {
    (void)cx;
    for (ail2g_wait *w = ail2g_waiting; w; w = w->next) ail2g_mark_chain(w->top);
    for (int64_t i = 0; i < ail2g_n; i++) if (ail2g_tab[i]) {
        ail2g *g = ail2g_tab[i];
        g->scanned = 0;
        if (g->state == AIL2G_RUNNING) { g->scanned = 1; ail_gc_mark_value(g->sent); }
    }
    for (int changed = 1; changed; ) {
        changed = 0;
        for (int64_t i = 0; i < ail2g_n; i++) {
            ail2g *g = ail2g_tab[i];
            if (!g || g->scanned || !g->inst->mark) continue;
            g->scanned = 1; changed = 1;
            ail_gc_mark_value(g->args); ail_gc_mark_value(g->value); ail_gc_mark_value(g->sent);
            if (g->state == AIL2G_SUSPENDED) ail2g_mark_chain(g->top);
        }
    }
    for (int64_t i = 0; i < ail2g_n; i++) {
        ail2g *g = ail2g_tab[i];
        if (g && !g->scanned && !g->inst->mark) { ail2g_free_stack(g); free(g); ail2g_tab[i] = NULL; }
    }
}
#ifdef _WIN32
static void CALLBACK ail2g_entry(LPVOID p) {
#else
static void ail2g_entry(void) {
    void *p = ail2g_current;
#endif
    ail2g *g = (ail2g *)p;
    ail_ctx *cx = ail2g_cx;
    AIL_FRAME_ENTER(cx, fr, 1);
    fr.slots[0] = g->args;
    g->args = ail_box_none();
    ail_obj r;
    g->status = g->body(cx, &r, fr.slots[0]);
    AIL_FRAME_LEAVE(cx, fr);
    g->state = AIL2G_DONE;
    g->top = NULL;
#ifdef _WIN32
    SwitchToFiber(g->caller);
#elif defined(AIL2G_ASM)
    ail2g_switch(&g->sp, g->caller_sp);
#else
    setcontext(&g->caller);
#endif
}
static inline ail_st ail2g_make(ail_ctx *cx, ail_obj *out, ail_obj cls, ail_obj args, ail2g_body body, const char *name) {
    if (!ail2g_id_h) { ail2g_id_h = ail_intern(cx, "_h"); ail2g_id_a = ail_intern(cx, "_a"); }
    ail2g_cx = cx;
    AIL_FRAME_ENTER(cx, fr, 2);
    fr.slots[0] = args;
    fr.slots[1] = ail_inst_new(cx, cls);
    ail2g *g = (ail2g *)ail_xcalloc(sizeof *g);
    g->state = AIL2G_NEW; g->body = body; g->inst = fr.slots[1].o; g->args = args; g->name = name;
    g->value = g->sent = ail_box_none();
    int64_t h = -1;
    for (int64_t i = 0; i < ail2g_n; i++) if (!ail2g_tab[i]) { h = i; break; }
    if (h < 0) {
        if (ail2g_n == ail2g_cap) { ail2g_cap = ail2g_cap ? ail2g_cap * 2 : 16; ail2g_tab = (ail2g **)realloc(ail2g_tab, (size_t)ail2g_cap * sizeof *ail2g_tab); if (!ail2g_tab) ail_die("out of memory"); }
        h = ail2g_n++;
    }
    ail2g_tab[h] = g;
    ail_inst_setattr(cx, fr.slots[1], ail2g_id_a, args);
    ail_inst_setattr(cx, fr.slots[1], ail2g_id_h, ail_box_int(h));
    *out = fr.slots[1];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
static inline ail_st ail2g_of(ail_ctx *cx, ail_obj inst, ail2g **out) {
    ail_obj h; ail_st st = ail_inst_getattr(cx, &h, inst, ail2g_id_h, "_h");
    if (st != AIL_OK) return st;
    if (h.tag != AIL_T_INT || h.i < 0 || h.i >= ail2g_n || !ail2g_tab[h.i]) ail_die("generator: lost handle");
    *out = ail2g_tab[h.i];
    return AIL_OK;
}
/* next(g) / g.send(v) */
static inline ail_st ail2g_resume(ail_ctx *cx, ail_obj *out, ail_obj inst, ail_obj sendv) {
    ail2g *g; ail_st st = ail2g_of(cx, inst, &g);
    if (st != AIL_OK) return st;
    if (g->state == AIL2G_DONE) return ail_raise_c(cx, AIL_B_STOPITERATION, "");
    if (g->state == AIL2G_RUNNING) return ail_raise_c(cx, AIL_B_VALUEERROR, "generator already executing");
    if (g->state == AIL2G_NEW && sendv.tag != AIL_T_NONE)
        return ail_raise_c(cx, AIL_B_TYPEERROR, "can't send non-None value to a just-started generator");
    ail2g_wait w; w.top = cx->frames; w.next = ail2g_waiting; ail2g_waiting = &w;
    ail2g *outer = ail2g_current;
    ail2g_current = g;
    g->sent = sendv;
    int fresh = g->state == AIL2G_NEW;
    if (fresh && ++ail2g_fresh >= 256) { ail2g_fresh = 0; ail_gc_collect(cx); }
    cx->frames = fresh ? NULL : g->top;
    g->state = AIL2G_RUNNING;
#ifdef _WIN32
    if (fresh) {
        g->fiber = CreateFiber(AIL2G_STACK, ail2g_entry, g);
        if (!g->fiber) ail_die("generator: no stack");
    }
    LPVOID me = GetCurrentFiber();
    if (me == (LPVOID)0x1E00 || me == NULL) me = ConvertThreadToFiber(NULL);
    g->caller = me;
    SwitchToFiber(g->fiber);
#else
    if (fresh) {
        g->stack_size = AIL2G_STACK;
        if (ail2g_pooled) g->stack = ail2g_pool[--ail2g_pooled];
        else {
            g->stack = mmap(NULL, g->stack_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
            if (g->stack == MAP_FAILED) { g->stack = NULL; ail_die("generator: no stack"); }
            mprotect(g->stack, 4096, PROT_NONE);
        }
#ifdef AIL2G_ASM
        /* a frame ail2g_switch returns from into ail2g_entry, with the stack aligned as after a call */
        uintptr_t top = ((uintptr_t)g->stack + g->stack_size) & ~(uintptr_t)15;
        void **p = (void **)(top - 8);
        p[0] = 0;
        p[-1] = (void *)ail2g_entry;
        for (int k = 2; k <= 7; k++) p[-k] = 0;
        g->sp = (void *)&p[-7];
#else
        if (getcontext(&g->ctx)) ail_die("generator: getcontext");
        g->ctx.uc_stack.ss_sp = g->stack; g->ctx.uc_stack.ss_size = g->stack_size; g->ctx.uc_link = NULL;
        makecontext(&g->ctx, ail2g_entry, 0);
#endif
    }
#ifdef AIL2G_ASM
    ail2g_switch(&g->caller_sp, g->sp);
#else
    swapcontext(&g->caller, &g->ctx);
#endif
#endif
    ail2g_current = outer;
    ail2g_waiting = w.next;
    cx->frames = w.top;
    if (g->state == AIL2G_SUSPENDED) { *out = g->value; g->value = ail_box_none(); return AIL_OK; }
    ail2g_free_stack(g);
    if (g->status == AIL_OK) return ail_raise_c(cx, AIL_B_STOPITERATION, "");
    if (g->status == AIL_EXC && ail_exc_matches_b(cx, AIL_B_STOPITERATION)) {
        ail_exc_clear(cx);
        return ail_raise_c(cx, AIL_B_RUNTIMEERROR, "generator raised StopIteration");
    }
    return g->status;
}
/* `yield value` inside the body: the value goes out, the sent one comes back */
static inline ail_st ail2g_yield(ail_ctx *cx, ail_obj *sent, ail_obj value) {
    ail2g *g = ail2g_current;
    if (!g) ail_die("yield outside a generator");
    g->value = value;
    g->top = cx->frames;
    g->state = AIL2G_SUSPENDED;
#ifdef _WIN32
    SwitchToFiber(g->caller);
#elif defined(AIL2G_ASM)
    ail2g_switch(&g->sp, g->caller_sp);
#else
    swapcontext(&g->ctx, &g->caller);
#endif
    *sent = g->sent;
    g->sent = ail_box_none();
    return AIL_OK;
}
/* g.close(): a generator that has not finished is finished (its finally blocks do not run) */
static inline ail_st ail2g_close(ail_ctx *cx, ail_obj *out, ail_obj inst) {
    ail2g *g; ail_st st = ail2g_of(cx, inst, &g);
    if (st != AIL_OK) return st;
    if (g->state == AIL2G_RUNNING) return ail_raise_c(cx, AIL_B_VALUEERROR, "generator already executing");
    if (g->state != AIL2G_DONE) { g->state = AIL2G_DONE; g->top = NULL; ail2g_free_stack(g); }
    *out = ail_box_none();
    return AIL_OK;
}
static inline ail_st ail2g_name(ail_ctx *cx, ail_obj *out, ail_obj inst) {
    ail2g *g; ail_st st = ail2g_of(cx, inst, &g);
    if (st != AIL_OK) return st;
    *out = ail_str_from_cstr(cx, g->name);
    return AIL_OK;
}
'''

ATTR = r'''
/* ---- getattr / hasattr / setattr / vars with a name known at run time (safetyrt.py ATTR) ---- */
static inline ail_st ail2a_cname(ail_ctx *cx, ail_obj name, char *buf, size_t n) {
    if (name.tag != AIL_T_STR) {
        char m[120]; snprintf(m, sizeof m, "attribute name must be string, not '%s'", ail_type_name(name.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, m);
    }
    ail_str s = ail_view_to_str(name);
    size_t k = 0;
    for (int64_t i = 0; i < s.n; i++) {
        uint32_t c = ail_chr(s, i);
        if (c < 0x80) { if (k + 1 < n) buf[k++] = (char)c; }
        else if (c < 0x800) { if (k + 2 < n) { buf[k++] = (char)(0xC0 | (c >> 6)); buf[k++] = (char)(0x80 | (c & 0x3F)); } }
        else if (k + 3 < n) { buf[k++] = (char)(0xE0 | (c >> 12)); buf[k++] = (char)(0x80 | ((c >> 6) & 0x3F)); buf[k++] = (char)(0x80 | (c & 0x3F)); }
    }
    buf[k] = 0;
    return AIL_OK;
}
static inline int ail2a_streq(ail_obj s, const char *lit) {
    if (s.tag != AIL_T_STR) return 0;
    ail_str v = ail_view_to_str(s);
    int64_t n = (int64_t)strlen(lit);
    if (v.n != n) return 0;
    for (int64_t i = 0; i < n; i++) if (ail_chr(v, i) != (unsigned char)lit[i]) return 0;
    return 1;
}
static inline int ail2a_find(ail_ctx *cx, ail_obj obj, const char *name, ail_obj *out) {
    ail_instobj *o = (ail_instobj *)obj.o;
    for (int64_t i = 0; i < o->n; i++) {
        int64_t nid = o->attrs[i].name_id;
        if (nid >= 0 && nid < cx->intern_n && strcmp(cx->intern_tab[nid], name) == 0) { *out = o->attrs[i].val; return 1; }
    }
    return 0;
}
static inline ail_st ail2a_need_inst(ail_ctx *cx, ail_obj obj, const char *fn) {
    if (obj.tag == AIL_T_INST || obj.tag == AIL_T_EXC) return AIL_OK;
    char m[160]; snprintf(m, sizeof m, "%s() on a '%s' value is not built on the general path (only instances of the program's classes)", fn, ail_type_name(obj.tag));
    return ail_raise_c(cx, AIL_B_NOTIMPLEMENTEDERROR, m);
}
/* getattr(obj, name[, default]); is_method: the class of obj has a method of that name */
static inline ail_st ail2a_getattr(ail_ctx *cx, ail_obj *out, ail_obj obj, ail_obj name, int has_dflt, ail_obj dflt) {
    char buf[256]; ail_st st = ail2a_cname(cx, name, buf, sizeof buf); if (st != AIL_OK) return st;
    if ((st = ail2a_need_inst(cx, obj, "getattr")) != AIL_OK) return st;
    if (ail2a_find(cx, obj, buf, out)) return AIL_OK;
    if (has_dflt) { *out = dflt; return AIL_OK; }
    char m[320]; snprintf(m, sizeof m, "'%s' object has no attribute '%s'", ail_type_name(obj.tag), buf);
    if (obj.tag == AIL_T_INST && ((ail_instobj *)obj.o)->cls.tag == AIL_T_CLASS) {
        ail_str cn = ail_view_to_str(((ail_classobj *)((ail_instobj *)obj.o)->cls.o)->name);
        char cb[100]; size_t k = 0;
        for (int64_t i = 0; i < cn.n && k + 1 < sizeof cb; i++) cb[k++] = (char)ail_chr(cn, i);
        cb[k] = 0;
        snprintf(m, sizeof m, "'%s' object has no attribute '%s'", cb, buf);
    }
    return ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, m);
}
static inline ail_st ail2a_hasattr(ail_ctx *cx, ail_obj *out, ail_obj obj, ail_obj name, int is_method) {
    char buf[256]; ail_st st = ail2a_cname(cx, name, buf, sizeof buf); if (st != AIL_OK) return st;
    if (is_method) { *out = ail_box_bool(1); return AIL_OK; }
    if ((st = ail2a_need_inst(cx, obj, "hasattr")) != AIL_OK) return st;
    ail_obj v; *out = ail_box_bool(ail2a_find(cx, obj, buf, &v));
    return AIL_OK;
}
static inline ail_st ail2a_setattr(ail_ctx *cx, ail_obj *out, ail_obj obj, ail_obj name, ail_obj v) {
    char buf[256]; ail_st st = ail2a_cname(cx, name, buf, sizeof buf); if (st != AIL_OK) return st;
    if ((st = ail2a_need_inst(cx, obj, "setattr")) != AIL_OK) return st;
    int64_t id = -1;
    for (int64_t i = 0; i < cx->intern_n; i++) if (strcmp(cx->intern_tab[i], buf) == 0) { id = i; break; }
    if (id < 0) { char *dup = (char *)ail_xmalloc(strlen(buf) + 1); strcpy(dup, buf); id = ail_intern(cx, dup); }
    ail_inst_setattr(cx, obj, id, v);
    *out = ail_box_none();
    return AIL_OK;
}
static inline ail_st ail2a_vars(ail_ctx *cx, ail_obj *out, ail_obj obj) {
    ail_st st = ail2a_need_inst(cx, obj, "vars"); if (st != AIL_OK) return st;
    AIL_FRAME_ENTER(cx, fr, 2);
    fr.slots[0] = ail_dict_new(cx);
    ail_instobj *o = (ail_instobj *)obj.o;
    for (int64_t i = 0; i < o->n; i++) {
        int64_t nid = o->attrs[i].name_id;
        if (nid < 0 || nid >= cx->intern_n) continue;
        const char *nm = cx->intern_tab[nid];
        if (nm[0] == '_' && nm[1] == '_' ) continue;
        fr.slots[1] = ail_bi_str_from_utf8(cx, nm, (int64_t)strlen(nm));
        st = ail_dict_set(cx, fr.slots[0], fr.slots[1], o->attrs[i].val);
        if (st != AIL_OK) { AIL_FRAME_LEAVE(cx, fr); return st; }
        o = (ail_instobj *)obj.o;
    }
    *out = fr.slots[0];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_OK;
}
'''

EXC = r'''
/* ---- exception objects of the program's exception classes (safetyrt.py EXC) ----
   An instance of a class derived from a builtin exception carries `args` (what it was built with, or what its
   __init__ handed to super().__init__) and, once complete, the text str(e) shows (the class's __str__, else
   the args as BaseException.__str__ writes them); it is then an exception value like the ones the run time
   makes, which `except ... as e`, print(e) and the traceback read. */
static int64_t ail2x_args_id;
static inline ail_st ail2x_message(ail_ctx *cx, ail_obj *out, ail_obj inst) {
    ail_instobj *ii = (ail_instobj *)inst.o;
    for (ail_obj k = ii->cls; k.tag == AIL_T_CLASS; k = ((ail_classobj *)k.o)->base) {
        ail_classobj *kc = (ail_classobj *)k.o;
        if (kc->str_fn) {
            ail_obj self = inst; self.tag = AIL_T_INST;
            ail_st st = kc->str_fn(cx, out, self);
            if (st != AIL_OK) return st;
            if (out->tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "__str__ returned non-string");
            return AIL_OK;
        }
    }
    ail_obj args = ail_box_none();
    for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == ail2x_args_id) args = ii->attrs[i].val;
    if (args.tag != AIL_T_TUPLE) { *out = ail_str_from_cstr(cx, ""); return AIL_OK; }
    ail_vecobj *v = (ail_vecobj *)args.o;
    if (v->n == 0) *out = ail_str_from_cstr(cx, "");
    else if (v->n == 1) *out = ail_class_is_or_subclass(ii->cls, cx->builtin_cls[AIL_B_KEYERROR]) ? ail_obj_repr(cx, v->p[0]) : ail_obj_str(cx, v->p[0]);
    else *out = ail_obj_repr(cx, args);
    return AIL_OK;
}
/* the instance is complete: its message, and the tag of an exception value */
static inline ail_st ail2x_finish(ail_ctx *cx, ail_obj *inst) {
    if (!ail2x_args_id) ail2x_args_id = ail_intern(cx, "args");
    AIL_FRAME_ENTER(cx, fr, 2);
    fr.slots[0] = *inst;
    ail_instobj *ii = (ail_instobj *)inst->o;
    int has = 0;
    for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == ail2x_args_id) has = 1;
    if (!has) ail_inst_setattr(cx, fr.slots[0], ail2x_args_id, ail_tuple_new(cx, NULL, 0));
    ail_st st = ail2x_message(cx, &fr.slots[1], fr.slots[0]);
    if (st == AIL_OK) {
        ail_inst_setattr(cx, fr.slots[0], AIL_ATTR_MESSAGE, fr.slots[1]);
        inst->tag = AIL_T_EXC;
    }
    AIL_FRAME_LEAVE(cx, fr);
    return st;
}
static inline ail_st ail2x_setargs(ail_ctx *cx, ail_obj inst, ail_obj args) {
    if (!ail2x_args_id) ail2x_args_id = ail_intern(cx, "args");
    ail_inst_setattr(cx, inst, ail2x_args_id, args);
    return AIL_OK;
}
/* raise v: an exception instance (complete or not) */
static inline ail_st ail2x_raise(ail_ctx *cx, ail_obj v) {
    if (v.tag == AIL_T_INST) { ail_st st = ail2x_finish(cx, &v); if (st != AIL_OK) return st; }
    if (v.tag != AIL_T_EXC) return ail_raise_c(cx, AIL_B_TYPEERROR, "exceptions must derive from BaseException");
    ail_instobj *ii = (ail_instobj *)v.o;
    ail_obj msg = ail_str_from_cstr(cx, "");
    for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == AIL_ATTR_MESSAGE) msg = ii->attrs[i].val;
    ail_raise(cx, ii->cls, msg);
    cx->exc.value = v;
    return AIL_EXC;
}
/* raise of a builtin exception class with arguments, in a program that reads e.args: the value carries them */
static inline ail_st ail2x_raise_builtin(ail_ctx *cx, ail_obj cls, ail_obj msg, ail_obj *args, int64_t n) {
    if (!ail2x_args_id) ail2x_args_id = ail_intern(cx, "args");
    AIL_FRAME_ENTER(cx, fr, 3);
    fr.slots[0] = msg;
    fr.slots[1] = ail_tuple_new(cx, args, n);
    fr.slots[2] = ail_inst_new(cx, cls);
    fr.slots[2].tag = AIL_T_EXC;
    ail_inst_setattr(cx, fr.slots[2], AIL_ATTR_MESSAGE, fr.slots[0]);
    ail_inst_setattr(cx, fr.slots[2], ail2x_args_id, fr.slots[1]);
    ail_raise(cx, cls, fr.slots[0]);
    cx->exc.value = fr.slots[2];
    AIL_FRAME_LEAVE(cx, fr);
    return AIL_EXC;
}
/* e.args of any exception value: what it carries, else (message,) as CPython's builtins hold it */
static inline ail_st ail2x_args(ail_ctx *cx, ail_obj *out, ail_obj e) {
    if (e.tag != AIL_T_EXC && e.tag != AIL_T_INST) {
        char m[120]; snprintf(m, sizeof m, "'%s' object has no attribute 'args'", ail_type_name(e.tag));
        return ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, m);
    }
    if (!ail2x_args_id) ail2x_args_id = ail_intern(cx, "args");
    ail_instobj *ii = (ail_instobj *)e.o;
    for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == ail2x_args_id) { *out = ii->attrs[i].val; return AIL_OK; }
    if (e.tag == AIL_T_INST) return ail_raise_c(cx, AIL_B_ATTRIBUTEERROR, "object has no attribute 'args'");
    for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == AIL_ATTR_MESSAGE) {
        ail_obj m = ii->attrs[i].val;
        if (m.tag == AIL_T_STR && ail_view_to_str(m).n == 0) { *out = ail_tuple_new(cx, NULL, 0); return AIL_OK; }
        AIL_FRAME_ENTER(cx, fr, 1); fr.slots[0] = m;
        ail_obj items[1] = { m };
        *out = ail_tuple_new(cx, items, 1);
        AIL_FRAME_LEAVE(cx, fr);
        return AIL_OK;
    }
    *out = ail_tuple_new(cx, NULL, 0);
    return AIL_OK;
}
'''

DDICT = r'''
/* ---- defaultdict with a factory function (safetyrt.py DDICT, with patch_defaultdict) ---- */
static inline ail_st ail2d_call(ail_ctx *cx, ail_obj *out, ail_mapobj *m) {
    ail_obj f = m->dd_fn;
    if (f.tag != AIL_T_FUNC) ail_die("defaultdict: the factory is not a function");
    ail_funcobj *fo = (ail_funcobj *)f.o;
    return fo->fn(cx, out, ail_box_none(), fo->cells);
}
'''

MISC = r'''
/* ---- small primitives (safetyrt.py MISC) ---- */
/* the two values are instances of one class (a dataclass's __eq__ compares only those) */
static inline ail_st ail2e_same_class(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {
    (void)cx;
    int r = (a.tag == AIL_T_INST || a.tag == AIL_T_EXC) && (b.tag == AIL_T_INST || b.tag == AIL_T_EXC)
            && ((ail_instobj *)a.o)->cls.o == ((ail_instobj *)b.o)->cls.o;
    *out = ail_box_bool(r);
    return AIL_OK;
}
/* the class name of an instance or exception (what `type(e).__name__` is) */
static inline ail_st ail2e_exc_name(ail_ctx *cx, ail_obj *out, ail_obj a) {
    if (a.tag != AIL_T_INST && a.tag != AIL_T_EXC) return ail_raise_c(cx, AIL_B_TYPEERROR, "_ail_exc_name: not an instance");
    ail_obj c = ((ail_instobj *)a.o)->cls;
    if (c.tag != AIL_T_CLASS) return ail_raise_c(cx, AIL_B_TYPEERROR, "_ail_exc_name: no class");
    *out = ((ail_classobj *)c.o)->name;
    return AIL_OK;
}
/* print(..., file=sys.stderr): the text, UTF-8, straight to stderr */
static inline ail_st ail2e_write(ail_ctx *cx, ail_obj *out, ail_obj s) {
    (void)cx;
    if (s.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "expected str");
    ail_str_write(ail_view_to_str(s), stderr);
    *out = ail_box_none();
    return AIL_OK;
}
'''

def _hash_core():
    import os
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ailhash_core.h'), 'r', encoding='utf-8') as handle:
        return handle.read()


HASH = '\n/* ---- hashlib, hmac, secrets and base64 on the general path (safetyrt.py HASH; the core is ailhash_core.h) ---- */\n' \
    + _hash_core() + r'''
/* a bytes str (units 0..255) as malloc'd bytes */
static inline ail_st ail2h_get(ail_ctx *cx, ail_obj so, uint8_t **p, int64_t *n) {
    ail_st st = ail2b_need(cx, so); if (st != AIL_OK) return st;
    ail_str s = ail_view_to_str(so);
    uint8_t *b = (uint8_t *)malloc((size_t)s.n + 1);
    if (!b) return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory");
    for (int64_t i = 0; i < s.n; i++) b[i] = (uint8_t)ail_chr(s, i);
    *p = b; *n = s.n;
    return AIL_OK;
}
static inline ail_st ail2h_algo(ail_ctx *cx, ail_obj *out, ail_obj name) {
    if (name.tag != AIL_T_STR) return ail_raise_c(cx, AIL_B_TYPEERROR, "expected str");
    ail_str s = ail_view_to_str(name);
    uint8_t b[32];
    int64_t n = s.n > 31 ? 31 : s.n;
    for (int64_t i = 0; i < n; i++) { uint16_t c = ail_chr(s, i); b[i] = c < 0x80 ? (uint8_t)c : 0xff; }
    *out = ail_box_int(s.n > 31 ? -1 : ailhs_algo_of(b, n));
    return AIL_OK;
}
static inline ail_st ail2h_new(ail_ctx *cx, ail_obj *out, ail_obj algo, ail_obj size, ail_obj key, ail_obj salt, ail_obj person) {
    uint8_t *k = NULL, *sl = NULL, *pe = NULL; int64_t kn = 0, sn = 0, pn = 0; ail_st st;
    if ((st = ail2h_get(cx, key, &k, &kn)) != AIL_OK) return st;
    if ((st = ail2h_get(cx, salt, &sl, &sn)) != AIL_OK) { free(k); return st; }
    if ((st = ail2h_get(cx, person, &pe, &pn)) != AIL_OK) { free(k); free(sl); return st; }
    uint8_t blob[AILHS_BLOB1];
    ailhs_new(blob, (int)algo.i, size.i, k, kn, sl, sn, pe, pn);
    free(k); free(sl); free(pe);
    *out = ail2b_from_buf(cx, blob, AILHS_BLOB1);
    return AIL_OK;
}
static inline ail_st ail2h_hmac(ail_ctx *cx, ail_obj *out, ail_obj algo, ail_obj key) {
    uint8_t *k = NULL; int64_t kn = 0; ail_st st;
    if ((st = ail2h_get(cx, key, &k, &kn)) != AIL_OK) return st;
    uint8_t blob[AILHS_BLOB2];
    ailhs_hmac_new(blob, (int)algo.i, k, kn);
    free(k);
    *out = ail2b_from_buf(cx, blob, AILHS_BLOB2);
    return AIL_OK;
}
static inline ail_st ail2h_update(ail_ctx *cx, ail_obj *out, ail_obj state, ail_obj data) {
    uint8_t *s = NULL, *d = NULL; int64_t sn = 0, dn = 0; ail_st st;
    if ((st = ail2h_get(cx, state, &s, &sn)) != AIL_OK) return st;
    if ((st = ail2h_get(cx, data, &d, &dn)) != AIL_OK) { free(s); return st; }
    uint8_t blob[AILHS_BLOB2];
    int bad = ailhs_feed(blob, s, sn, d, dn);
    free(s); free(d);
    if (bad) return ail_raise_c(cx, AIL_B_VALUEERROR, "not a hash state");
    *out = ail2b_from_buf(cx, blob, sn);
    return AIL_OK;
}
static inline ail_st ail2h_digest(ail_ctx *cx, ail_obj *out, ail_obj state) {
    uint8_t *s = NULL; int64_t sn = 0; ail_st st;
    if ((st = ail2h_get(cx, state, &s, &sn)) != AIL_OK) return st;
    int64_t n = ailhs_info(s, sn, 0);
    uint8_t d[64];
    int bad = n < 0 || ailhs_digest_of(d, s, sn);
    free(s);
    if (bad) return ail_raise_c(cx, AIL_B_VALUEERROR, "not a hash state");
    *out = ail2b_from_buf(cx, d, n);
    return AIL_OK;
}
static inline ail_st ail2h_info(ail_ctx *cx, ail_obj *out, ail_obj state, ail_obj which) {
    uint8_t *s = NULL; int64_t sn = 0; ail_st st;
    if ((st = ail2h_get(cx, state, &s, &sn)) != AIL_OK) return st;
    int64_t r = ailhs_info(s, sn, which.i);
    free(s);
    if (r < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "not a hash state");
    *out = ail_box_int(r);
    return AIL_OK;
}
static inline ail_st ail2h_pbkdf2(ail_ctx *cx, ail_obj *out, ail_obj algo, ail_obj pw, ail_obj salt, ail_obj iters, ail_obj dklen) {
    uint8_t *p = NULL, *sl = NULL; int64_t pn = 0, sn = 0; ail_st st;
    if ((st = ail2h_get(cx, pw, &p, &pn)) != AIL_OK) return st;
    if ((st = ail2h_get(cx, salt, &sl, &sn)) != AIL_OK) { free(p); return st; }
    uint8_t *o = (uint8_t *)malloc((size_t)dklen.i + 1);
    if (!o) { free(p); free(sl); return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory"); }
    ailhs_pbkdf2(o, dklen.i, (int)algo.i, p, pn, sl, sn, iters.i);
    free(p); free(sl);
    *out = ail2b_from_buf(cx, o, dklen.i);
    free(o);
    return AIL_OK;
}
static inline ail_st ail2h_cmp(ail_ctx *cx, ail_obj *out, ail_obj a, ail_obj b) {
    uint8_t *x = NULL, *y = NULL; int64_t xn = 0, yn = 0; ail_st st;
    if ((st = ail2h_get(cx, a, &x, &xn)) != AIL_OK) return st;
    if ((st = ail2h_get(cx, b, &y, &yn)) != AIL_OK) { free(x); return st; }
    *out = ail_box_int(ailhs_cmp(x, xn, y, yn));
    free(x); free(y);
    return AIL_OK;
}
static inline ail_st ail2h_rand(ail_ctx *cx, ail_obj *out, ail_obj n) {
    uint8_t *o = (uint8_t *)malloc((size_t)(n.i > 0 ? n.i : 0) + 1);
    if (!o) return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory");
    if (n.i > 0 && ailhs_random(o, (size_t)n.i) < 0) { free(o); return ail_raise_c(cx, AIL_B_VALUEERROR, "cannot read random bytes from the operating system"); }
    *out = ail2b_from_buf(cx, o, n.i > 0 ? n.i : 0);
    free(o);
    return AIL_OK;
}
static inline ail_st ail2h_bits(ail_ctx *cx, ail_obj *out, ail_obj k) {
    int64_t r = ailhs_randbits(k.i);
    if (r < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "cannot read random bytes from the operating system");
    *out = ail_box_int(r);
    return AIL_OK;
}
static inline ail_st ail2h_b64e(ail_ctx *cx, ail_obj *out, ail_obj data, ail_obj urlsafe) {
    uint8_t *d = NULL; int64_t dn = 0; ail_st st;
    if ((st = ail2h_get(cx, data, &d, &dn)) != AIL_OK) return st;
    int64_t n = ailhs_b64e_len(dn);
    uint8_t *o = (uint8_t *)malloc((size_t)n + 1);
    if (!o) { free(d); return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory"); }
    ailhs_b64e(o, d, dn, (int)urlsafe.i);
    free(d);
    *out = ail2b_from_buf(cx, o, n);
    free(o);
    return AIL_OK;
}
static inline ail_st ail2h_b64d(ail_ctx *cx, ail_obj *out, ail_obj data, ail_obj mode) {
    uint8_t *d = NULL; int64_t dn = 0; ail_st st;
    if ((st = ail2h_get(cx, data, &d, &dn)) != AIL_OK) return st;
    uint8_t *o = (uint8_t *)malloc((size_t)(3 * ((dn + 3) / 4) + 3));
    if (!o) { free(d); return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory"); }
    int64_t n = ailhs_b64d(o, d, dn, (int)mode.i);
    free(d);
    *out = ail2b_from_buf(cx, o, n > 0 ? n : 0);
    free(o);
    return AIL_OK;
}
static inline ail_st ail2h_b64err(ail_ctx *cx, ail_obj *out) { (void)cx; *out = ail_box_int(ailhs_b64_err); return AIL_OK; }
static inline ail_st ail2h_b64n(ail_ctx *cx, ail_obj *out) { (void)cx; *out = ail_box_int(ailhs_b64_n); return AIL_OK; }
'''

# ba_u: only under AIL_UNIFIED=1 (unified.py): the element of a prelude bytearray instance read without the method call
BA_U = r'''
static inline int ail2u_ba_get(ail_obj c, ail_obj idx, ail_obj cls, ail_obj *r, int64_t attr) {
    if (c.tag != AIL_T_INST || idx.tag != AIL_T_INT || ((ail_instobj *)c.o)->cls.o != cls.o) return 0;
    ail_instobj *o = (ail_instobj *)c.o;
    for (int64_t j = 0; j < o->n; j++) {
        if (o->attrs[j].name_id == attr) {
            ail_obj l = o->attrs[j].val;
            if (l.tag != AIL_T_LIST) return 0;
            ail_vecobj *v = (ail_vecobj *)l.o;
            if ((uint64_t)idx.i < (uint64_t)v->n && v->p[idx.i].tag == AIL_T_INT) { *r = v->p[idx.i]; return 1; }
            return 0;
        }
    }
    return 0;
}
'''

# str_u: only under AIL_UNIFIED=1 (unified.py): `s == s[::-1]` of a str, read in place
STR_U = r'''
static inline int ail2u_palindrome(ail_obj s) {
    if (s.sv.len < 2) return 1;
    ail_str v = ail_view_to_str(s);
    for (int64_t i = 0, j = v.n - 1; i < j; i++, j--)
        if (ail_chr(v, i) != ail_chr(v, j)) return 0;
    return 1;
}
'''

FRAGMENTS = {'strpred': STRPRED2, 'slice': SLICE, 'bytes': BYTES, 'bytesfile': BYTESFILE, 'fmt': FMT, 'gen': GEN,
             'misc': MISC, 'ddict': DDICT, 'attr': ATTR, 'exc': EXC, 'hash': HASH, 'rng': randrt.RNG,
             'rng_u': randrt.RNG_U,      # rng_u: only under AIL_UNIFIED=1 (unified.py)
             'ba_u': BA_U, 'str_u': STR_U,
             'jsn': jsonbrt.JSN, 'sta': statbrt.STA, 'rex': rebrt.REX}
ORDER = ['strpred', 'slice', 'bytes', 'bytesfile', 'fmt', 'gen', 'misc', 'ddict', 'attr', 'exc', 'hash', 'rng', 'rng_u', 'ba_u', 'str_u', 'jsn', 'sta', 'rex']

GEN_PRELUDE = '''
class generator:
    def __iter__(self):
        return self

    def __next__(self):
        return _ail_gen_resume(self, None)

    def send(self, value):
        return _ail_gen_resume(self, value)

    def close(self):
        return _ail_gen_close(self)

    def __repr__(self):
        return "<generator object " + _ail_gen_name(self) + ">"
'''



def patch_gcpool(c_text):
    """AIL_UNIFIED=1 only (docs/design/UNIFIED_IR.md section 12): a size-class free list under the collector.
    `ail_gc_alloc` takes a header-only-or-payload-free block of up to 128 bytes from the list of its class (sizes
    rounded up to 16) and zeroes it as calloc would; the sweep puts such a block on the list instead of free().
    The collection schedule is unchanged (gc_bytes is charged and credited exactly as before), so the program
    cannot tell. The lists hold at most the collector's own threshold (1.5 x cx->gc_threshold: 8 MB or twice the live set, plus the size-class rounding), the
    most one cycle can free; they are file statics (not in ail_ctx), so the blocks stay reachable for leak
    checkers. Not used with threads."""
    def one(text, old, new):
        if text.count(old) != 1:
            raise AssertionError('safetyrt: no place for the gc pool: %r' % old[:60])
        return text.replace(old, new)
    c_text = one(c_text, '''static inline void *ail_gc_alloc(ail_ctx *cx, uint8_t kind, size_t sz) {
    ail_gc_maybe_collect(cx, sz);
    ail_gcobj *o = (ail_gcobj *)ail_xcalloc(sz);
''', '''#define AIL2U_POOL_MAX 128
static ail_gcobj *ail2u_pool[AIL2U_POOL_MAX / 16 + 1];
static size_t ail2u_pool_bytes;
static inline void *ail_gc_alloc(ail_ctx *cx, uint8_t kind, size_t sz) {
    ail_gc_maybe_collect(cx, sz);
    ail_gcobj *o;
    if (sz <= AIL2U_POOL_MAX && sz > 0) {
        size_t c = (sz + 15) >> 4;
        o = ail2u_pool[c];
        if (o) { ail2u_pool[c] = o->gcnext; ail2u_pool_bytes -= c << 4; memset(o, 0, sz); }
        else o = (ail_gcobj *)ail_xcalloc(c << 4);
    } else o = (ail_gcobj *)ail_xcalloc(sz);
''')
    c_text = one(c_text, '''            cx->gc_bytes -= o->size;
            ail__free_payload(o);
            free(o);
''', '''            cx->gc_bytes -= o->size;
            ail__free_payload(o);
            if (o->size <= AIL2U_POOL_MAX && o->size > 0 && ail2u_pool_bytes < cx->gc_threshold + cx->gc_threshold / 2) {
                size_t c = ((size_t)o->size + 15) >> 4;
                o->gcnext = ail2u_pool[c]; ail2u_pool[c] = o; ail2u_pool_bytes += c << 4;
            } else free(o);
''')
    return c_text


SORT_PRIM = r'''
/* AIL_UNIFIED only (docs/design/UNIFIED_IR.md section 15): a sort whose keys are all floats (no NaN) or all ints is done on
   (key, index) records with a natural merge sort (runs found first, so two ordered lists put side by side cost one
   merge); the elements are then moved once. Stable, like the general merge sort; same result for any such keys. */
typedef struct { double k; int64_t i; } ail2u_recf;
typedef struct { int64_t k; int64_t i; } ail2u_reci;
#define AIL2U_SORTGEN(NAME, REC) \
static void NAME##_merge(const REC *s, REC *d, int64_t lo, int64_t mid, int64_t hi) { \
    int64_t i = lo, j = mid, k = lo; \
    if (!(s[mid].k < s[mid - 1].k)) { memcpy(d + lo, s + lo, (size_t)(hi - lo) * sizeof(REC)); return; } \
    while (i < mid && j < hi) { if (s[j].k < s[i].k) d[k++] = s[j++]; else d[k++] = s[i++]; } \
    while (i < mid) d[k++] = s[i++]; \
    while (j < hi) d[k++] = s[j++]; \
} \
static void NAME##_sort(REC *a, REC *b, int64_t n) { \
    int64_t *bd = (int64_t *)ail_xmalloc((size_t)(n / 8 + 3) * sizeof(int64_t)); \
    int64_t nr = 0, s = 0; bd[0] = 0; \
    while (s < n) { \
        int64_t e = s + 1; \
        if (e < n) { \
            if (a[e].k < a[e - 1].k) { while (e < n && a[e].k < a[e - 1].k) e++; \
                for (int64_t x = s, y = e - 1; x < y; x++, y--) { REC t = a[x]; a[x] = a[y]; a[y] = t; } } \
            else while (e < n && !(a[e].k < a[e - 1].k)) e++; \
        } \
        while (e - s < 8 && e < n) { REC t = a[e]; int64_t y = e; while (y > s && t.k < a[y - 1].k) { a[y] = a[y - 1]; y--; } a[y] = t; e++; } \
        bd[++nr] = e; s = e; \
    } \
    REC *src = a, *dst = b; \
    while (nr > 1) { \
        int64_t m = 0, r = 0; \
        for (; r + 1 < nr; r += 2) { NAME##_merge(src, dst, bd[r], bd[r + 1], bd[r + 2]); bd[++m] = bd[r + 2]; } \
        if (r < nr) { memcpy(dst + bd[r], src + bd[r], (size_t)(bd[r + 1] - bd[r]) * sizeof(REC)); bd[++m] = bd[r + 1]; } \
        nr = m; { REC *t = src; src = dst; dst = t; } \
    } \
    if (src != a) memcpy(a, src, (size_t)n * sizeof(REC)); \
    free(bd); \
}
AIL2U_SORTGEN(ail2u_sf, ail2u_recf)
AIL2U_SORTGEN(ail2u_si, ail2u_reci)
/* p: the elements, keys: their keys (n of each), tmp: scratch of n objects. Returns 0 (nothing done) unless the keys are all floats or all ints. */
static int ail2u_sort_prim(ail_obj *p, ail_obj *keys, ail_obj *tmp, int64_t n) {
    uint8_t tg = keys[0].tag;
    if (tg != AIL_T_FLOAT && tg != AIL_T_INT) return 0;
    for (int64_t i = 0; i < n; i++) {
        if (keys[i].tag != tg) return 0;
        if (tg == AIL_T_FLOAT) { double v = ail_float_val(keys[i]); if (v != v) return 0; }
    }
    _Static_assert(sizeof(ail_obj) >= 32, "two arrays of 16-byte records are laid over the scratch objects");
    if (tg == AIL_T_FLOAT) {
        ail2u_recf *a = (ail2u_recf *)tmp, *b = a + n;
        for (int64_t i = 0; i < n; i++) { a[i].k = ail_float_val(keys[i]); a[i].i = i; }
        ail2u_sf_sort(a, b, n);
        for (int64_t i = 0; i < n; i++) keys[i] = p[a[i].i];
    } else {
        ail2u_reci *a = (ail2u_reci *)tmp, *b = a + n;
        for (int64_t i = 0; i < n; i++) { a[i].k = keys[i].i; a[i].i = i; }
        ail2u_si_sort(a, b, n);
        for (int64_t i = 0; i < n; i++) keys[i] = p[a[i].i];
    }
    memcpy(p, keys, (size_t)n * sizeof(ail_obj));
    return 1;
}
'''


def patch_sortprim(c_text):
    """AIL_UNIFIED only (docs/design/UNIFIED_IR.md section 15): `ail_list_sort` sorts (key, index) records with a natural merge
    sort when every key is a float (none NaN) or every key is an int, and moves the elements once. Any other key goes the old way
    (the same merge sort as before). Stable, so the order is the same as the general sort's for these keys; the scratch is the
    `tmp` array that was already allocated, and the old key-side scratch is only allocated when it is needed."""
    head = 'static inline ail_st ail_list_sort(ail_ctx *cx, ail_obj lst, ail_obj key_fn_or_none, int reverse) {'
    if c_text.count(head) != 1:
        return c_text            # a program without the runtime's sort: nothing to do
    out = c_text.replace(head, SORT_PRIM + head)
    for old, new in (
            ('    ail_obj *ktmp = (ail_obj *)ail_xmalloc((size_t)n * sizeof(ail_obj));\n    AIL_ROOT1(cx, frl, lst);',
             '    ail_obj *ktmp = NULL;\n    AIL_ROOT1(cx, frl, lst);'),
            ('    if (st == AIL_OK) st = ail__vec_merge_sort(cx, v->p, keys, tmp, ktmp, 0, n);\n',
             '    if (st == AIL_OK && !ail2u_sort_prim(v->p, keys, tmp, n)) { ktmp = (ail_obj *)ail_xmalloc((size_t)n * sizeof(ail_obj)); '
             'st = ail__vec_merge_sort(cx, v->p, keys, tmp, ktmp, 0, n); }\n')):
        if out.count(old) != 1:
            raise AssertionError('safetyrt: the runtime sort changed shape: %r' % old[:60])
        out = out.replace(old, new)
    return out


def patch_tuples(c_text):
    """AIL_UNIFIED only (section 15): a tuple of at most 8 items is one allocation (the header, then the items), not a header and
    a separate 8-item (256-byte) array. `p` points past the header; the places that free or grow `p` know that block is not theirs.
    The collector's byte count now includes the items (it did not count the array before), so a program that makes many tuples
    collects a little sooner and holds less."""
    old_new = (
        ('''    ail_vecobj *v = ail_vec_new(cx);
    AIL_FRAME_LEAVE(cx, fr);
    ail_vec_reserve(cx, v, n);
    for (int64_t i = 0; i < n; i++) v->p[v->n++] = items[i];
    ail_obj r; r.tag = AIL_T_TUPLE;''',
         '''    ail_vecobj *v = (ail_vecobj *)ail_gc_alloc(cx, AIL_K_LIST, sizeof(ail_vecobj) + (n <= 8 ? (size_t)n * sizeof(ail_obj) : 0));
    AIL_FRAME_LEAVE(cx, fr);
    if (n > 0 && n <= 8) { v->p = (ail_obj *)(v + 1); v->cap = n; }
    else ail_vec_reserve(cx, v, n);
    for (int64_t i = 0; i < n; i++) v->p[v->n++] = items[i];
    ail_obj r; r.tag = AIL_T_TUPLE;'''),
        ('    free(v->p);\n    v->p = np; v->cap = nc;',
         '    if (v->p != (ail_obj *)(v + 1)) free(v->p);   /* an inline tuple block is part of the header\'s allocation */\n    v->p = np; v->cap = nc;'),
        ('case AIL_K_LIST: case AIL_K_TUPLE: free(((ail_vecobj *)o)->p); break;',
         'case AIL_K_LIST: case AIL_K_TUPLE: if (((ail_vecobj *)o)->p != (ail_obj *)((ail_vecobj *)o + 1)) free(((ail_vecobj *)o)->p); break;'),
    )
    out = c_text
    for old, new in old_new:
        if out.count(old) != 1:
            if 'ail_tuple_new(ail_ctx' not in out:
                return c_text
            raise AssertionError('safetyrt: the runtime tuple code changed shape: %r' % old[:60])
        out = out.replace(old, new)
    return out


def patch_defaultdict(c_text):
    """A defaultdict whose factory is a function (`defaultdict(lambda: [0, 0])`, `defaultdict(dict)`): the dict
    carries the function (dd_factory 5, dd_fn), the collector marks it, and a missing key calls it."""
    def one(text, old, new):
        if text.count(old) != 1:
            raise AssertionError('safetyrt: no place for the defaultdict factory: %r' % old[:60])
        return text.replace(old, new)
    c_text = one(c_text, 'int8_t dd_factory; /* defaultdict marker: 0 plain dict, 1 int, 2 list, 3 set, 4 str (2026-09-16) */ } ail_mapobj;',
                 'int8_t dd_factory; /* defaultdict marker: 0 plain dict, 1 int, 2 list, 3 set, 4 str (2026-09-16) */\n'
                 '                 ail_obj dd_fn; /* dd_factory 5: the factory function (safetyrt.patch_defaultdict) */ } ail_mapobj;\n'
                 'static inline ail_st ail2d_call(ail_ctx *cx, ail_obj *out, ail_mapobj *m);')
    c_text = one(c_text, '            ail_mapobj *m = (ail_mapobj *)o;\n'
                 '            for (int64_t i = 0; i < m->n; i++) { ail_gc_mark_value(m->entries[i].key); ail_gc_mark_value(m->entries[i].val); }',
                 '            ail_mapobj *m = (ail_mapobj *)o;\n'
                 '            ail_gc_mark_value(m->dd_fn);\n'
                 '            for (int64_t i = 0; i < m->n; i++) { ail_gc_mark_value(m->entries[i].key); ail_gc_mark_value(m->entries[i].val); }')
    c_text = one(c_text, '        ail_obj dflt = fac == 1 ? ail_box_int(0) : fac == 2 ? ail_list_new(cx) : fac == 3 ? ail_set_new(cx) : ail_str_from_cstr(cx, "");',
                 '        ail_obj dflt;\n'
                 '        if (fac == 5) { st = ail2d_call(cx, &dflt, (ail_mapobj *)d.o); if (st != AIL_OK) return st; }\n'
                 '        else dflt = fac == 1 ? ail_box_int(0) : fac == 2 ? ail_list_new(cx) : fac == 3 ? ail_set_new(cx) : ail_str_from_cstr(cx, "");')
    c_text = one(c_text, '            ail_obj dflt = fac == 1 ? ail_box_int(0) : fac == 2 ? ail_list_new(cx)\n'
                 '                         : fac == 3 ? ail_set_new(cx) : ail_str_from_cstr(cx, "");',
                 '            ail_obj dflt;\n'
                 '            if (fac == 5) { st = ail2d_call(cx, &dflt, m); if (st != AIL_OK) return st; }\n'
                 '            else dflt = fac == 1 ? ail_box_int(0) : fac == 2 ? ail_list_new(cx)\n'
                 '                         : fac == 3 ? ail_set_new(cx) : ail_str_from_cstr(cx, "");')
    c_text = one(c_text, '/*DD5REPR*/',
                 'if (m->dd_fn.tag == AIL_T_FUNC) {   /* a function factory: its label, or <function NAME at 0x...> (the address varies run to run, as in CPython) */\n'
                 '                        const char *nm = ((ail_funcobj *)m->dd_fn.o)->name;\n'
                 '                        if (nm && !strncmp(nm, "<class ", 7)) fputs(nm, f);\n'
                 '                        else fprintf(f, "<function %s at %p>", nm ? nm : "<lambda>", (void *)m->dd_fn.o);\n'
                 '                    }')
    c_text = one(c_text, '/*DD5COPY*/',
                 'if (m->dd_factory == 5) { ((ail_mapobj *)r.o)->dd_factory = 5; ((ail_mapobj *)r.o)->dd_fn = m->dd_fn; }')
    return c_text


NI_PRELUDE = '''
class _AilNotImplementedType:
    def __repr__(self):
        return "NotImplemented"


_AIL_NOTIMPLEMENTED = _AilNotImplementedType()
'''

NI_DECLS = r'''/* NotImplemented (safetyrt.patch_notimplemented): the one instance of _AilNotImplementedType */
static ail_obj ail2n_cls;
static inline int ail2n_is(ail_obj x) {
    return x.tag == AIL_T_INST && ail2n_cls.tag == AIL_T_CLASS && ((ail_instobj *)x.o)->cls.o == ail2n_cls.o;
}
static void ail2n_tname(char *buf, size_t n, ail_obj x) {
    if (x.tag == AIL_T_INST && ((ail_instobj *)x.o)->cls.tag == AIL_T_CLASS) {
        ail_str s = ail_view_to_str(((ail_classobj *)((ail_instobj *)x.o)->cls.o)->name);
        size_t k = 0;
        for (int64_t i = 0; i < s.n && k + 1 < n; i++) { uint32_t ch = (uint32_t)ail_chr(s, i); buf[k++] = ch < 128 ? (char)ch : '?'; }
        buf[k] = 0; return;
    }
    snprintf(buf, n, "%s", ail_type_name(x.tag));
}
__attribute__((noinline, cold)) static ail_st ail2n_lt_error(ail_ctx *cx, ail_obj a, ail_obj b) {
    char buf[240], na[80], nb[80];
    ail2n_tname(na, sizeof na, a); ail2n_tname(nb, sizeof nb, b);
    snprintf(buf, sizeof buf, "'<' not supported between instances of '%s' and '%s'", na, nb);
    return ail_raise_c(cx, AIL_B_TYPEERROR, buf);
}
'''


def patch_notimplemented(c_text):
    """A method that returns NotImplemented: the other operand's reflected method is tried next (+, -, ...,
    ==, !=), equality falls back to identity and an ordering to TypeError, as in CPython."""
    def one(text, old, new):
        if text.count(old) != 1:
            raise AssertionError('safetyrt: no place for NotImplemented: %r' % old[:70])
        return text.replace(old, new)
    # before the first of these places (dunderrt's functions come before the core's comparison)
    marks = [m for m in ('/* ---- operator special methods on instances (dunderrt.py) ---- */',
                         'static inline ail_st ail_obj_cmp(ail_ctx *cx, int64_t *out, ail_obj a, ail_obj b) {') if m in c_text]
    first = min(marks, key=c_text.index)
    c_text = c_text.replace(first, NI_DECLS + first, 1)
    c_text = one(c_text, 'ail_obj r; ail_st st = kc->lt_fn(cx, &r, a, b); if (st != AIL_OK) return st;',
                 'ail_obj r; ail_st st = kc->lt_fn(cx, &r, a, b); if (st != AIL_OK) return st;\n'
                 '            if (ail2n_is(r)) return ail2n_lt_error(cx, a, b);')
    c_text = one(c_text, 'if (b.tag == AIL_T_INST) { st = kc->lt_fn(cx, &r, b, a); if (st != AIL_OK) return st; if (ail_obj_truthy(r)) { *out = 1; return AIL_OK; } }',
                 'if (b.tag == AIL_T_INST) { st = kc->lt_fn(cx, &r, b, a); if (st != AIL_OK) return st; if (!ail2n_is(r) && ail_obj_truthy(r)) { *out = 1; return AIL_OK; } }')
    c_text = one(c_text, '    ail_d2_fn f = ail_dun2(a, fwd);\n    if (f) return f(cx, out, a, b);\n    f = ail_dun2(b, rev);\n    if (f) return f(cx, out, b, a);\n',
                 '    ail_d2_fn f = ail_dun2(a, fwd); ail_st nst;\n'
                 '    if (f) { nst = f(cx, out, a, b); if (nst != AIL_OK || !ail2n_is(*out)) return nst; }\n'
                 '    f = ail_dun2(b, rev);\n'
                 '    if (f) { nst = f(cx, out, b, a); if (nst != AIL_OK || !ail2n_is(*out)) return nst; }\n')
    c_text = one(c_text, '        if (ne && (f = ail_dun2(x, AIL_D2_NE))) return f(cx, out, x, y);\n'
                 '        if ((f = ail_dun2(x, AIL_D2_EQ))) {\n'
                 '            st = f(cx, &r, x, y); if (st != AIL_OK) return st;\n',
                 '        if (ne && (f = ail_dun2(x, AIL_D2_NE))) { st = f(cx, out, x, y); if (st != AIL_OK || !ail2n_is(*out)) return st; continue; }\n'
                 '        if ((f = ail_dun2(x, AIL_D2_EQ))) {\n'
                 '            st = f(cx, &r, x, y); if (st != AIL_OK) return st;\n'
                 '            if (ail2n_is(r)) continue;\n')
    old = '        if (est != AIL_OK) { if (ail__eq_scope) ail__eq_err = est; return 0; }\n        return ail_obj_truthy(r);\n'
    if c_text.count(old) != 2:
        raise AssertionError('safetyrt: no place for NotImplemented in ail_dun_eq_raw')
    c_text = c_text.replace(old, '        if (est != AIL_OK) { if (ail__eq_scope) ail__eq_err = est; return 0; }\n'
                                 '        if (!ail2n_is(r)) return ail_obj_truthy(r);\n')
    c_text = one(c_text, '    if (ail_obj_truthy(r)) { *out = 1; *stp = AIL_OK; return 1; }\n    return 0;',
                 '    if (!ail2n_is(r) && ail_obj_truthy(r)) { *out = 1; *stp = AIL_OK; return 1; }\n    return 0;')
    c_text = one(c_text, 'if (gf) { *stp = gf(cx, &r, b, a); if (*stp != AIL_OK) return 1; if (ail_obj_truthy(r))',
                 'if (gf) { *stp = gf(cx, &r, b, a); if (*stp != AIL_OK) return 1; if (!ail2n_is(r) && ail_obj_truthy(r))')
    c_text = one(c_text, '        *stp = kc->lt_fn(cx, &r, b, a); if (*stp != AIL_OK) return 1;\n        if (ail_obj_truthy(r)) {',
                 '        *stp = kc->lt_fn(cx, &r, b, a); if (*stp != AIL_OK) return 1;\n'
                 '        if (ail2n_is(r)) { *stp = ail2n_lt_error(cx, a, b); return 1; }\n        if (ail_obj_truthy(r)) {')
    return c_text


def patch_exc(c_text):
    """repr() of an exception value that carries args shows them (ClassName(arg, ...)), as for every exception in
    CPython, not only the run time's OS errors."""
    old = ('            if (ail_class_is_or_subclass(ii->cls, cx->builtin_cls[AIL_B_OSERROR])) {\n'
           '                int64_t args_id = ail_intern(cx, "args");')
    if c_text.count(old) != 1:
        raise AssertionError('safetyrt: no place for exception args in repr')
    c_text = c_text.replace(old, '            {\n                int64_t args_id = ail_intern(cx, "args");')
    # an exception raised with no argument (`raise ValueError`) shows as ValueError()
    old = ('            for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == AIL_ATTR_MESSAGE) {\n'
           '                ail_obj r = ail_str_repr(cx, ii->attrs[i].val); ail_str_write(ail_view_to_str(r), f);\n')
    if c_text.count(old) != 1:
        raise AssertionError('safetyrt: no place for an empty exception message in repr')
    return c_text.replace(old, '            for (int64_t i = 0; i < ii->n; i++) if (ii->attrs[i].name_id == AIL_ATTR_MESSAGE\n'
                               '                    && !(ii->attrs[i].val.tag == AIL_T_STR && ii->attrs[i].val.sv.len == 0)) {\n'
                               '                ail_obj r = ail_str_repr(cx, ii->attrs[i].val); ail_str_write(ail_view_to_str(r), f);\n')


def patch_generators(c_text):
    """The collector of a program with generators also marks the frames of suspended generators and of the
    callers waiting for one (GEN's ail2g_gc_hook)."""
    head = 'static inline void ail_gc_collect(ail_ctx *cx) {\n    for (ail_frame *f = cx->frames; f; f = f->prev)'
    mark = ('    for (int i = 0; i < AIL_B_COUNT; i++) ail_gc_mark_value(cx->builtin_cls[i]);\n\n'
            '    ail_gcobj **link = &cx->gc_all;')
    if c_text.count(head) != 1 or c_text.count(mark) != 1:
        raise AssertionError('safetyrt: the collector has no place for the generator hook')
    c_text = c_text.replace(head, 'static void ail2g_gc_hook(ail_ctx *cx);\n' + head)
    return c_text.replace(mark, mark.replace('\n\n', '\n    ail2g_gc_hook(cx);\n\n'))

# names of the bytes prelude a program must not define itself for the prelude to be added
BYTES_NAMES = frozenset(('bytes', 'bytearray', 'read_stdin_bytes', 'read_bytes', 'write_stdout_bytes', 'UnicodeError',
                         'UnicodeDecodeError', 'UnicodeEncodeError', 'LookupError'))
# a program that mentions one of these uses bytes
BYTES_WORDS = frozenset(('bytes', 'bytearray', 'read_stdin_bytes', 'read_bytes', 'write_stdout_bytes', 'UnicodeError',
                         'UnicodeDecodeError', 'UnicodeEncodeError'))
ENCODINGS = {'utf-8', 'utf8', 'u8', 'utf', 'cp65001', 'ascii', 'us-ascii', '646', 'us', 'latin-1', 'latin1',
             'iso-8859-1', 'iso8859-1', '8859', 'cp819', 'l1', 'latin', 'iso-ir-100'}
ERROR_HANDLERS = {'strict', 'ignore', 'replace'}
READ_BYTES = '''
def read_bytes(path):
    f = open(path, "rb")
    data = f.read()
    f.close()
    return data
'''

# the class of slice objects, compiled with the program on the general path when it needs one
SLICE_PRELUDE = '''
class slice:
    def __init__(self, start, stop, step):
        self.start = start
        self.stop = stop
        self.step = step

    def __repr__(self):
        return "slice(" + repr(self.start) + ", " + repr(self.stop) + ", " + repr(self.step) + ")"

    def __eq__(self, other):
        if not isinstance(other, slice):
            return False
        return (self.start, self.stop, self.step) == (other.start, other.stop, other.step)

    def indices(self, n):
        return _ail_slice_indices(self.start, self.stop, self.step, n)
'''

# name -> (C call, argument count, fragment): primitives the preludes call
PRIMS = {
    '_ail_slice_indices': ('ail2s_indices(cx, &{t}, {a0}, {a1}, {a2}, {a3})', 4, 'slice'),
    '_ail_slice_get': ('ail2s_getslice(cx, &{t}, {a0}, {a1}, {a2}, {a3})', 4, 'slice'),
    '_ail_b_stdin': ('ail2b_stdin(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_write': ('ail2b_write(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_lasterr': ('ail2b_lasterr(cx, &{t})', 0, 'bytes'),
    '_ail_b_errkind': ('ail2b_errkind_get(cx, &{t})', 0, 'bytes'),
    '_ail_b_encode': ('ail2b_encode(cx, &{t}, {a0}, {a1}, {a2})', 3, 'bytes'),
    '_ail_b_decode': ('ail2b_decode(cx, &{t}, {a0}, {a1}, {a2})', 3, 'bytes'),
    '_ail_b_from_ints': ('ail2b_from_ints(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_ints': ('ail2b_ints(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_repr': ('ail2b_repr(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_case': ('ail2b_case(cx, &{t}, {a0}, {a1})', 2, 'bytes'),
    '_ail_b_pred': ('ail2b_pred(cx, &{t}, {a0}, {a1})', 2, 'bytes'),
    '_ail_b_split_ws': ('ail2b_split_ws(cx, &{t}, {a0}, {a1}, {a2})', 3, 'bytes'),
    '_ail_b_strip_ws': ('ail2b_strip_ws(cx, &{t}, {a0}, {a1})', 2, 'bytes'),
    '_ail_b_splitlines': ('ail2b_splitlines(cx, &{t}, {a0}, {a1})', 2, 'bytes'),
    '_ail_b_translate': ('ail2b_translate(cx, &{t}, {a0}, {a1}, {a2})', 3, 'bytes'),
    '_ail_b_hex': ('ail2b_hex(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_fromhex': ('ail2b_fromhex(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_b_numsafe': ('ail2b_numsafe(cx, &{t}, {a0})', 1, 'bytes'),
    '_ail_hs_algo': ('ail2h_algo(cx, &{t}, {a0})', 1, 'hash'),
    '_ail_hs_new': ('ail2h_new(cx, &{t}, {a0}, {a1}, {a2}, {a3}, {a4})', 5, 'hash'),
    '_ail_hs_hmac': ('ail2h_hmac(cx, &{t}, {a0}, {a1})', 2, 'hash'),
    '_ail_hs_update': ('ail2h_update(cx, &{t}, {a0}, {a1})', 2, 'hash'),
    '_ail_hs_digest': ('ail2h_digest(cx, &{t}, {a0})', 1, 'hash'),
    '_ail_hs_info': ('ail2h_info(cx, &{t}, {a0}, {a1})', 2, 'hash'),
    '_ail_hs_pbkdf2': ('ail2h_pbkdf2(cx, &{t}, {a0}, {a1}, {a2}, {a3}, {a4})', 5, 'hash'),
    '_ail_hs_cmp': ('ail2h_cmp(cx, &{t}, {a0}, {a1})', 2, 'hash'),
    '_ail_hs_rand': ('ail2h_rand(cx, &{t}, {a0})', 1, 'hash'),
    '_ail_hs_bits': ('ail2h_bits(cx, &{t}, {a0})', 1, 'hash'),
    '_ail_hs_b64e': ('ail2h_b64e(cx, &{t}, {a0}, {a1})', 2, 'hash'),
    '_ail_hs_b64d': ('ail2h_b64d(cx, &{t}, {a0}, {a1})', 2, 'hash'),
    '_ail_hs_b64err': ('ail2h_b64err(cx, &{t})', 0, 'hash'),
    '_ail_hs_b64n': ('ail2h_b64n(cx, &{t})', 0, 'hash'),
    '_ail_pct': ('ail2f_percent(cx, &{t}, {a0}, {a1})', 2, 'fmt'),
    '_ail_format': ('ail2f_format(cx, &{t}, {a0}, {a1})', 2, 'fmt'),
    '_ail_gen_resume': ('ail2g_resume(cx, &{t}, {a0}, {a1})', 2, 'gen'),
    '_ail_gen_close': ('ail2g_close(cx, &{t}, {a0})', 1, 'gen'),
    '_ail_gen_name': ('ail2g_name(cx, &{t}, {a0})', 1, 'gen'),
    '_ail_stderr_write': ('ail2e_write(cx, &{t}, {a0})', 1, 'misc'),
    '_ail_same_class': ('ail2e_same_class(cx, &{t}, {a0}, {a1})', 2, 'misc'),
    '_ail_exc_name': ('ail2e_exc_name(cx, &{t}, {a0})', 1, 'misc'),
}
PRIMS.update({name: (cfn, count, 'rng') for name, (cfn, count) in randrt.PRIMS.items()})   # random.Random (randrt.py)
PRIMS.update({name: (cfn, count, 'jsn') for name, (cfn, count) in jsonbrt.PRIMS.items()})   # json's loops (jsonbrt.py)
PRIMS.update({name: (cfn, count, 'sta') for name, (cfn, count) in statbrt.PRIMS.items()})   # statistics' loops (statbrt.py)
PRIMS.update({name: (cfn, count, 'rex') for name, (cfn, count) in rebrt.PRIMS.items()})   # re's Pike VM and DFA (rebrt.py)

# The read-only methods bytes and bytearray share: name, parameters, arguments of the `_ail_bm_` function or
# primitive (on the str `S`), and what the result is: `b` one bytes-like value, `L` a list of them, `T` a
# 3-tuple of them, `v` a plain value.
_CASES = ('upper', 'lower', 'swapcase', 'title', 'capitalize')
_PREDS = ('isalnum', 'isalpha', 'isascii', 'isdigit', 'islower', 'isspace', 'istitle', 'isupper')
SHARED_METHODS = [
    ('split', 'sep=None, maxsplit=-1', '_ail_bm_split(S, sep, maxsplit)', 'L'),
    ('rsplit', 'sep=None, maxsplit=-1', '_ail_bm_rsplit(S, sep, maxsplit)', 'L'),
    ('splitlines', 'keepends=False', '_ail_b_splitlines(S, keepends)', 'L'),
    ('strip', 'chars=None', '_ail_bm_strip(S, chars)', 'b'),
    ('lstrip', 'chars=None', '_ail_bm_lstrip(S, chars)', 'b'),
    ('rstrip', 'chars=None', '_ail_bm_rstrip(S, chars)', 'b'),
    ('startswith', 'prefix, start=None, end=None', '_ail_bm_startswith(S, prefix, start, end)', 'v'),
    ('endswith', 'suffix, start=None, end=None', '_ail_bm_endswith(S, suffix, start, end)', 'v'),
    ('find', 'sub, start=None, end=None', '_ail_bm_find(S, sub, start, end)', 'v'),
    ('rfind', 'sub, start=None, end=None', '_ail_bm_rfind(S, sub, start, end)', 'v'),
    ('index', 'sub, start=None, end=None', '_ail_bm_index(S, sub, start, end)', 'v'),
    ('rindex', 'sub, start=None, end=None', '_ail_bm_rindex(S, sub, start, end)', 'v'),
    ('count', 'sub, start=None, end=None', '_ail_bm_count(S, sub, start, end)', 'v'),
    ('replace', 'old, new, count=-1', '_ail_bm_replace(S, old, new, count)', 'b'),
    ('join', 'iterable', '_ail_bm_join(S, iterable)', 'b'),
    ('partition', 'sep', '_ail_bm_partition(S, sep)', 'T'),
    ('rpartition', 'sep', '_ail_bm_rpartition(S, sep)', 'T'),
    ('removeprefix', 'prefix', '_ail_bm_removeprefix(S, prefix)', 'b'),
    ('removesuffix', 'suffix', '_ail_bm_removesuffix(S, suffix)', 'b'),
    ('center', 'width, fillchar=None', '_ail_bm_center(S, width, fillchar)', 'b'),
    ('ljust', 'width, fillchar=None', '_ail_bm_ljust(S, width, fillchar)', 'b'),
    ('rjust', 'width, fillchar=None', '_ail_bm_rjust(S, width, fillchar)', 'b'),
    ('zfill', 'width', 'S.zfill(width)', 'b'),
    ('expandtabs', 'tabsize=8', 'S.expandtabs(tabsize)', 'b'),
    ('translate', 'table, delete=None', '_ail_bm_translate(S, table, delete)', 'b'),
    ('decode', 'encoding="utf-8", errors="strict"', '_ail_bm_decode(S, encoding, errors)', 'v'),
    ('hex', '*args', '_ail_bm_hex(S, args)', 'v'),
] + [(m, '', '_ail_b_case(S, %d)' % i, 'b') for i, m in enumerate(_CASES)] \
  + [(m, '', '_ail_b_pred(S, %d)' % i, 'v') for i, m in enumerate(_PREDS)]


def _methods(wrap, raw):
    out = []
    for name, params, call, kind in SHARED_METHODS:
        call = call.replace('S', raw, 1) if call.startswith('S.') else call.replace('(S', '(' + raw, 1)
        if kind == 'b':
            body = 'return %s(%s)' % (wrap, call)
        elif kind == 'L':
            body = 'return [%s(x) for x in %s]' % (wrap, call)
        elif kind == 'T':
            body = '_ail_t = %s\n        return (%s(_ail_t[0]), %s(_ail_t[1]), %s(_ail_t[2]))' % (call, wrap, wrap, wrap)
        else:
            body = 'return %s' % call
        out.append('    def %s(self%s):\n        %s\n' % (name, (', ' + params) if params else '', body))
    return '\n'.join(out)


def bytes_prelude():
    """prelude_bytes.py with the shared methods written into both classes."""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prelude_bytes.py')
    lines = open(path, encoding='utf-8').read().split('\n')
    out = []
    for line in lines:
        if line.startswith('#@METHODS '):
            _, cls, wrap, raw = line.split(' ', 3)
            out.append(_methods(wrap, raw))
        elif line.startswith('#') and not out:
            continue
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


def text(needed):
    """The fragments `needed` names, in a fixed order (so the C does not depend on the order of first use)."""
    return ''.join(FRAGMENTS[k] for k in ORDER if k in needed)
