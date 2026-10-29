# -*- coding: utf-8 -*-
"""unirt.py -- the C behind unilower.py: unicodedata.name / category / normalize, over ailuni_core.h.

One data core (generated from CPython 3.12 / Unicode 15.0 by tools/gen_unicodedata.py) and two thin
adapter sets: UNI for the general path (ail_obj / ail_st, UTF-16 strings) and TYPED_UNI for the typed
path (ail_str UTF-8, arena strings). The core is pure C and allocates its work array with malloc.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _core():
    with open(os.path.join(HERE, 'ailuni_core.h'), 'r', encoding='utf-8') as handle:
        return handle.read()


UNI = '\n/* ---- unicodedata.name / category / normalize (unirt.py UNI; the core is ailuni_core.h) ---- */\n' \
    + _core() + r'''
static inline const char *ail2u_typename(uint8_t tag) {
    return tag == AIL_T_NONE ? "None" : ail_type_name(tag);
}
static inline uint32_t ail2u_point(ail_str s, int64_t *i) {
    uint32_t c = ail_chr(s, *i);
    if (c >= 0xD800 && c < 0xDC00 && *i + 1 < s.n) {
        uint32_t d = ail_chr(s, *i + 1);
        if (d >= 0xDC00 && d < 0xE000) { *i += 2; return 0x10000u + ((c - 0xD800u) << 10) + (d - 0xDC00u); }
    }
    *i += 1;
    return c;
}
static ail_st ail2u_char(ail_ctx *cx, ail_obj so, int namearg, uint32_t *out) {
    int64_t i = 0;
    uint32_t c;
    ail_str s;
    char msg[128];
    if (so.tag != AIL_T_STR) {
        if (namearg)
            snprintf(msg, sizeof msg, "name() argument 1 must be a unicode character, not %s", ail2u_typename(so.tag));
        else
            snprintf(msg, sizeof msg, "category() argument must be a unicode character, not %s", ail2u_typename(so.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);
    }
    s = ail_view_to_str(so);
    c = s.n ? ail2u_point(s, &i) : 0;
    if (s.n == 0 || i != s.n) {
        if (namearg)
            snprintf(msg, sizeof msg, "name() argument 1 must be a unicode character, not str");
        else
            snprintf(msg, sizeof msg, "category() argument must be a unicode character, not str");
        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);
    }
    *out = c;
    return AIL_OK;
}
static ail_st ail2u_name1(ail_ctx *cx, ail_obj *out, ail_obj so) {
    uint32_t cp;
    char name[128];
    ail_st st = ail2u_char(cx, so, 1, &cp);
    if (st != AIL_OK) return st;
    if (!ailuni_name(cp, name, sizeof name)) return ail_raise_c(cx, AIL_B_VALUEERROR, "no such name");
    *out = ail_str_from_cstr(cx, name);
    return AIL_OK;
}
static ail_st ail2u_name2(ail_ctx *cx, ail_obj *out, ail_obj so, ail_obj fallback) {
    uint32_t cp;
    char name[128];
    ail_st st = ail2u_char(cx, so, 1, &cp);
    if (st != AIL_OK) return st;
    if (!ailuni_name(cp, name, sizeof name)) { *out = fallback; return AIL_OK; }
    *out = ail_str_from_cstr(cx, name);
    return AIL_OK;
}
static ail_st ail2u_category(ail_ctx *cx, ail_obj *out, ail_obj so) {
    uint32_t cp;
    ail_st st = ail2u_char(cx, so, 0, &cp);
    if (st != AIL_OK) return st;
    *out = ail_str_from_cstr(cx, ailuni_category(cp));
    return AIL_OK;
}
static int ail2u_form(ail_obj o, const char *want) {
    ail_str s = ail_view_to_str(o);
    int64_t n = (int64_t)strlen(want);
    if (s.n != n) return 0;
    for (int64_t i = 0; i < n; i++) if (ail_chr(s, i) != (uint16_t)(unsigned char)want[i]) return 0;
    return 1;
}
static uint32_t *ail2u_cps(ail_str s, int64_t *n) {
    uint32_t *out = (uint32_t *)malloc((size_t)(s.n > 0 ? s.n : 1) * sizeof(uint32_t));
    if (!out) return NULL;
    int64_t k = 0;
    for (int64_t i = 0; i < s.n; ) out[k++] = ail2u_point(s, &i);
    *n = k;
    return out;
}
static ail_st ail2u_normalize(ail_ctx *cx, ail_obj *out, ail_obj form, ail_obj so) {
    int which = -1;
    char msg[128];
    int64_t n = 0, rn = 0, o = 0;
    uint32_t *in, *res = NULL;
    ail_strbuild bu;
    ail_str s;
    if (form.tag != AIL_T_STR) {
        snprintf(msg, sizeof msg, "normalize() argument 1 must be str, not %s", ail2u_typename(form.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);
    }
    if (so.tag != AIL_T_STR) {
        snprintf(msg, sizeof msg, "normalize() argument 2 must be str, not %s", ail2u_typename(so.tag));
        return ail_raise_c(cx, AIL_B_TYPEERROR, msg);
    }
    if (ail2u_form(form, "NFC")) which = 0;
    else if (ail2u_form(form, "NFD")) which = 1;
    else if (ail2u_form(form, "NFKC")) which = 2;
    else if (ail2u_form(form, "NFKD")) which = 3;
    if (which < 0) return ail_raise_c(cx, AIL_B_VALUEERROR, "invalid normalization form");
    s = ail_view_to_str(so);
    in = ail2u_cps(s, &n);
    if (!in) return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory");
    if (!ailuni_normalize(which, in, n, &res, &rn)) {
        free(in);
        return ail_raise_c(cx, AIL_B_VALUEERROR, "out of memory");
    }
    bu = ail_str_buf(cx, rn);
    for (int64_t i = 0; i < rn; i++) {
        uint32_t c = res[i];
        if (c >= 0x10000) {
            c -= 0x10000;
            bu.buf[o++] = (uint16_t)(0xD800 + (c >> 10));
            bu.buf[o++] = (uint16_t)(0xDC00 + (c & 0x3FF));
        } else {
            bu.buf[o++] = (uint16_t)c;
        }
    }
    free(in);
    free(res);
    *out = ail_str_buf_done(bu, o);
    return AIL_OK;
}
'''

TYPED_UNI = '\n/* ---- unicodedata typed adapters (unirt.py TYPED_UNI; the core is ailuni_core.h) ---- */\n' \
    + _core() + r'''
static void ailt_uni_raise(const char *text) {
    ail_raise_value_adopt(ail_exception_new(AIL_EXC_VALUE, (const uint8_t *)text, (int64_t)strlen(text), 1));
}
static ail_str ailt_uni_text(ail_sarena *A, const char *s) {
    int64_t n = (int64_t)strlen(s);
    uint8_t *q = ail_sarena_alloc(A, n + 1);
    memcpy(q, s, (size_t)n);
    return (ail_str){q, n, 1};
}
static uint32_t ailt_uni_point(ail_str s, int64_t *i) {
    uint32_t c = ail_str_point(s, *i);
    *i = ail_str_next_unit(s, *i);
    return c;
}
static uint32_t ailt_uni_char(ail_str s, int namearg) {
    int64_t i = 0;
    uint32_t c;
    if (s.n == 0) {
        if (namearg) ailt_uni_raise("name() argument 1 must be a unicode character, not str");
        ailt_uni_raise("category() argument must be a unicode character, not str");
    }
    c = ailt_uni_point(s, &i);
    if (i != s.n) {
        if (namearg) ailt_uni_raise("name() argument 1 must be a unicode character, not str");
        ailt_uni_raise("category() argument must be a unicode character, not str");
    }
    return c;
}
static ail_str ailt_uni_name1(ail_sarena *A, ail_str s) {
    char name[128];
    uint32_t cp = ailt_uni_char(s, 1);
    if (!ailuni_name(cp, name, sizeof name)) ailt_uni_raise("no such name");
    return ailt_uni_text(A, name);
}
static ail_str ailt_uni_name2(ail_sarena *A, ail_str s, ail_str fallback) {
    char name[128];
    uint32_t cp = ailt_uni_char(s, 1);
    if (!ailuni_name(cp, name, sizeof name)) return fallback;
    return ailt_uni_text(A, name);
}
static ail_str ailt_uni_category(ail_sarena *A, ail_str s) {
    uint32_t cp = ailt_uni_char(s, 0);
    return ailt_uni_text(A, ailuni_category(cp));
}
static int ailt_uni_form(ail_str s, const char *want) {
    int64_t n = (int64_t)strlen(want);
    if (s.n != n) return 0;
    for (int64_t i = 0; i < n; i++)
        if (ail_str_point(s, i) != (uint32_t)(unsigned char)want[i]) return 0;
    return 1;
}
static ail_str ailt_uni_normalize(ail_sarena *A, ail_str form, ail_str s) {
    int which = -1;
    if (ailt_uni_form(form, "NFC")) which = 0;
    else if (ailt_uni_form(form, "NFD")) which = 1;
    else if (ailt_uni_form(form, "NFKC")) which = 2;
    else if (ailt_uni_form(form, "NFKD")) which = 3;
    if (which < 0) ailt_uni_raise("invalid normalization form");
    uint32_t *in = (uint32_t *)malloc((size_t)(s.n > 0 ? s.n : 1) * sizeof(uint32_t));
    if (!in) ailt_uni_raise("out of memory");
    int64_t n = 0;
    for (int64_t i = 0; i < s.n; ) in[n++] = ailt_uni_point(s, &i);
    uint32_t *res = NULL;
    int64_t rn = 0;
    if (!ailuni_normalize(which, in, n, &res, &rn)) {
        free(in);
        ailt_uni_raise("out of memory");
    }
    free(in);
    uint8_t *q = ail_sarena_alloc(A, rn * 4 + 1);
    int64_t o = 0;
    _Bool ascii = 1;
    for (int64_t i = 0; i < rn; i++) {
        if (res[i] >= 0x80) ascii = 0;
        o += ail_utf8_put(q + o, res[i]);
    }
    free(res);
    return (ail_str){q, o, ascii};
}
'''

PRIMS = {
    '_ail_uni_name1': ('ail2u_name1(cx, &{t}, {a0})', 1, 'uni'),
    '_ail_uni_name2': ('ail2u_name2(cx, &{t}, {a0}, {a1})', 2, 'uni'),
    '_ail_uni_category': ('ail2u_category(cx, &{t}, {a0})', 1, 'uni'),
    '_ail_uni_normalize': ('ail2u_normalize(cx, &{t}, {a0}, {a1})', 2, 'uni'),
}
