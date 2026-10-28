"""Runtime text for the json lowering (jsonlib.py appends the parts a program uses to the program).

Python-subset source, valid CPython as it stands (the tests run it there too): the scanner mirrors
CPython 3.12's _json.c error messages and positions, and the typed parsers assume a document that
the scanner accepted."""

LOADS = r'''
class _AilJp:
    def __init__(self, b: bytes):
        self.b = b
        self.i = 0
        self.kind = 0


def _ail_js_fail(p: _AilJp, msg: str, pos: int) -> int:
    b = p.b
    k = 0
    chars = 0
    line = 1
    last = -1
    while k < pos:
        c = b[k]
        if c < 128 or c >= 192:
            if c == 10:
                line += 1
                last = chars
            chars += 1
        k += 1
    col = chars + 1
    if line > 1:
        col = chars - last
    text = msg + ": line " + str(line) + " column " + str(col) + " (char " + str(chars) + ")"
    raise ValueError(text)
    return 0


def _ail_js_ws(p: _AilJp, start: int) -> int:
    b = p.b
    n = len(b)
    i = start
    while i < n:
        c = b[i]
        if c == 32 or c == 10 or c == 13 or c == 9:
            i += 1
        else:
            break
    return i


def _ail_js_numend(p: _AilJp, i: int) -> int:
    b = p.b
    n = len(b)
    j = i
    if j < n and b[j] == 45:
        j += 1
    if j >= n:
        return -1
    c = b[j]
    if c == 48:
        j += 1
    elif c >= 49 and c <= 57:
        j += 1
        while j < n and b[j] >= 48 and b[j] <= 57:
            j += 1
    else:
        return -1
    p.kind = 1
    if j + 1 < n and b[j] == 46 and b[j + 1] >= 48 and b[j + 1] <= 57:
        j += 2
        while j < n and b[j] >= 48 and b[j] <= 57:
            j += 1
        p.kind = 2
    if j < n and (b[j] == 101 or b[j] == 69):
        k = j + 1
        if k < n and (b[k] == 43 or b[k] == 45):
            k += 1
        if k < n and b[k] >= 48 and b[k] <= 57:
            while k < n and b[k] >= 48 and b[k] <= 57:
                k += 1
            j = k
            p.kind = 2
    return j


def _ail_js_hexv(c: int) -> int:
    if c >= 48 and c <= 57:
        return c - 48
    if c >= 97 and c <= 102:
        return c - 87
    if c >= 65 and c <= 70:
        return c - 55
    return -1


def _ail_js_hex4(p: _AilJp, u: int) -> int:
    # the four hex digits after the 'u' at index u; -1 when one is not a hex digit
    b = p.b
    v = 0
    k = u + 1
    while k < u + 5:
        d = _ail_js_hexv(b[k])
        if d < 0:
            return -1
        v = v * 16 + d
        k += 1
    return v


def _ail_js_strend(p: _AilJp, begin: int) -> int:
    b = p.b
    n = len(b)
    i = begin + 1
    while True:
        if i >= n:
            _ail_js_fail(p, "Unterminated string starting at", begin)
        c = b[i]
        if c == 34:
            return i + 1
        if c < 32:
            _ail_js_fail(p, "Invalid control character at", i)
        if c == 92:
            i += 1
            if i >= n:
                _ail_js_fail(p, "Unterminated string starting at", begin)
            e = b[i]
            if e == 117:
                if i + 5 >= n:
                    _ail_js_fail(p, "Invalid \\uXXXX escape", i)
                v = _ail_js_hex4(p, i)
                if v < 0:
                    _ail_js_fail(p, "Invalid \\uXXXX escape", i)
                i += 5
                if v >= 55296 and v < 56320 and i + 6 < n and b[i] == 92 and b[i + 1] == 117:
                    w = _ail_js_hex4(p, i + 1)
                    if w < 0:
                        _ail_js_fail(p, "Invalid \\uXXXX escape", i + 1)
                    if w >= 56320 and w < 57344:
                        i += 6
            elif e == 34 or e == 92 or e == 47 or e == 98 or e == 102 or e == 110 or e == 114 or e == 116:
                i += 1
            else:
                _ail_js_fail(p, "Invalid \\escape", i - 1)
        else:
            i += 1
    return 0


def _ail_js_chk(p: _AilJp, start: int) -> int:
    # validates the value starting at index start (no leading whitespace); returns the index after it
    b = p.b
    n = len(b)
    i = start
    if i >= n:
        _ail_js_fail(p, "Expecting value", i)
    c = b[i]
    if c == 34:
        return _ail_js_strend(p, i)
    if c == 123:
        i = _ail_js_ws(p, i + 1)
        if i < n and b[i] == 125:
            return i + 1
        while True:
            if i >= n or b[i] != 34:
                _ail_js_fail(p, "Expecting property name enclosed in double quotes", i)
            i = _ail_js_strend(p, i)
            i = _ail_js_ws(p, i)
            if i >= n or b[i] != 58:
                _ail_js_fail(p, "Expecting ':' delimiter", i)
            i = _ail_js_ws(p, i + 1)
            i = _ail_js_chk(p, i)
            i = _ail_js_ws(p, i)
            if i < n and b[i] == 125:
                return i + 1
            if i >= n or b[i] != 44:
                _ail_js_fail(p, "Expecting ',' delimiter", i)
            i = _ail_js_ws(p, i + 1)
    if c == 91:
        i = _ail_js_ws(p, i + 1)
        if i < n and b[i] == 93:
            return i + 1
        while True:
            i = _ail_js_chk(p, i)
            i = _ail_js_ws(p, i)
            if i < n and b[i] == 93:
                return i + 1
            if i >= n or b[i] != 44:
                _ail_js_fail(p, "Expecting ',' delimiter", i)
            i = _ail_js_ws(p, i + 1)
    if c == 110 and b[i:i + 4] == b"null":
        return i + 4
    if c == 116 and b[i:i + 4] == b"true":
        return i + 4
    if c == 102 and b[i:i + 5] == b"false":
        return i + 5
    if c == 78 and b[i:i + 3] == b"NaN":
        return i + 3
    if c == 73 and b[i:i + 8] == b"Infinity":
        return i + 8
    if c == 45 and b[i:i + 9] == b"-Infinity":
        return i + 9
    e = _ail_js_numend(p, i)
    if e < 0:
        _ail_js_fail(p, "Expecting value", i)
    return e
    return 0


def _ail_js_check(s: str) -> _AilJp:
    # validates the whole document as json.loads does and returns the cursor positioned at its value
    if s.startswith("﻿"):
        raise ValueError("Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)")
    p = _AilJp(s.encode())
    n = len(p.b)
    i = _ail_js_ws(p, 0)
    start = i
    e = _ail_js_chk(p, i)
    e = _ail_js_ws(p, e)
    if e != n:
        _ail_js_fail(p, "Extra data", e)
    p.i = start
    return p


def _ail_js_found(p: _AilJp) -> str:
    b = p.b
    c = b[p.i]
    if c == 34:
        return "a str"
    if c == 123:
        return "an object"
    if c == 91:
        return "an array"
    if c == 110:
        return "null"
    if c == 116 or c == 102:
        return "a bool"
    if c == 78 or c == 73:
        return "a float"
    if c == 45 and b[p.i + 1] == 73:
        return "a float"
    _ail_js_numend(p, p.i)
    if p.kind == 1:
        return "an int"
    return "a float"


def _ail_js_mismatch(p: _AilJp, want: str) -> int:
    b = p.b
    k = 0
    chars = 0
    while k < p.i:
        c = b[k]
        if c < 128 or c >= 192:
            chars += 1
        k += 1
    text = "json.loads: found " + _ail_js_found(p) + " at char " + str(chars) + " but the declared type needs " + want
    text += " (CPython would give a value of another type; declare the type of the data or use values of that type)"
    raise RuntimeError(text)
    return 0


def _ail_js_pv_int(p: _AilJp) -> int:
    b = p.b
    i = p.i
    c = b[i]
    if c == 45 or (c >= 48 and c <= 57):
        e = _ail_js_numend(p, i)
        if e > 0 and p.kind == 1:
            p.i = e
            v = 0
            try:
                w = int(b[i:e].decode())
                if w > 9223372036854775807 or w < -9223372036854775807 - 1:
                    _ail_js_mismatch(p, "an int within 64 bits")
                v = w
            except OverflowError:
                _ail_js_mismatch(p, "an int within 64 bits")
            except ValueError:
                _ail_js_mismatch(p, "an int within 64 bits")
            return v
    _ail_js_mismatch(p, "an int")
    return 0


def _ail_js_pv_float(p: _AilJp) -> float:
    b = p.b
    i = p.i
    c = b[i]
    if c == 45 or (c >= 48 and c <= 57):
        e = _ail_js_numend(p, i)
        if e > 0 and p.kind == 2:
            p.i = e
            return float(b[i:e].decode())
    if c == 78:
        p.i = i + 3
        return float("nan")
    if c == 73:
        p.i = i + 8
        return float("inf")
    if c == 45 and b[i + 1] == 73:
        p.i = i + 9
        return float("-inf")
    _ail_js_mismatch(p, "a float (write 1.0, not 1)")
    return 0.0


def _ail_js_pv_bool(p: _AilJp) -> bool:
    b = p.b
    i = p.i
    c = b[i]
    if c == 116:
        p.i = i + 4
        return True
    if c == 102:
        p.i = i + 5
        return False
    _ail_js_mismatch(p, "a bool")
    return False


def _ail_js_pv_str(p: _AilJp) -> str:
    b = p.b
    i = p.i
    if b[i] != 34:
        _ail_js_mismatch(p, "a str")
    i += 1
    start = i
    while True:
        c = b[i]
        if c == 34:
            p.i = i + 1
            return b[start:i].decode()
        if c == 92:
            break
        i += 1
    out = b[start:i].decode()
    while True:
        c = b[i]
        if c == 34:
            p.i = i + 1
            return out
        if c == 92:
            i += 1
            e = b[i]
            if e == 117:
                v = _ail_js_hex4(p, i)
                i += 5
                if v >= 55296 and v < 56320 and b[i] == 92 and b[i + 1] == 117:
                    w = _ail_js_hex4(p, i + 1)
                    if w >= 56320 and w < 57344:
                        v = 65536 + ((v - 55296) << 10) + (w - 56320)
                        i += 6
                if v >= 55296 and v < 57344:
                    raise RuntimeError("json.loads: a lone surrogate \\u" + str(v) + " cannot be held in a str here")
                out += chr(v)
            else:
                if e == 110:
                    out += "\n"
                elif e == 116:
                    out += "\t"
                elif e == 114:
                    out += "\r"
                elif e == 98:
                    out += "\b"
                elif e == 102:
                    out += "\f"
                elif e == 34:
                    out += '"'
                elif e == 92:
                    out += "\\"
                else:
                    out += "/"
                i += 1
        else:
            j = i
            while b[j] != 34 and b[j] != 92:
                j += 1
            out += b[i:j].decode()
            i = j
    return out
'''

DUMPS = r'''
class _AilJo:
    def __init__(self, pad: str, pretty: int, isep: str, ksep: str, asc: int, srt: int, nan: int):
        self.pad = pad
        self.pretty = pretty
        self.isep = isep
        self.ksep = ksep
        self.asc = asc
        self.srt = srt
        self.nan = nan


def _ail_jd_pad(unit: str, n: int) -> str:
    out = ""
    k = 0
    while k < n:
        out += unit
        k += 1
    return out


def _ail_jd_hex(c: int) -> str:
    digits = "0123456789abcdef"
    return "\\u" + digits[(c >> 12) & 15] + digits[(c >> 8) & 15] + digits[(c >> 4) & 15] + digits[c & 15]


def _ail_jd_str(s: str, o: _AilJo) -> str:
    out = '"'
    for ch in s:
        c = ord(ch)
        if c == 34:
            out += '\\"'
        elif c == 92:
            out += "\\\\"
        elif c >= 32 and c < 127:
            out += ch
        elif c == 10:
            out += "\\n"
        elif c == 13:
            out += "\\r"
        elif c == 9:
            out += "\\t"
        elif c == 8:
            out += "\\b"
        elif c == 12:
            out += "\\f"
        elif c < 32:
            out += _ail_jd_hex(c)
        elif o.asc == 0:
            out += ch
        elif c < 65536:
            out += _ail_jd_hex(c)
        else:
            v = c - 65536
            out += _ail_jd_hex(55296 + (v >> 10)) + _ail_jd_hex(56320 + (v & 1023))
    return out + '"'


def _ail_jd_float(x: float, o: _AilJo) -> str:
    if x != x:
        if o.nan == 0:
            raise ValueError("Out of range float values are not JSON compliant: nan")
        return "NaN"
    if x > 1.7976931348623157e308:
        if o.nan == 0:
            raise ValueError("Out of range float values are not JSON compliant: inf")
        return "Infinity"
    if x < -1.7976931348623157e308:
        if o.nan == 0:
            raise ValueError("Out of range float values are not JSON compliant: -inf")
        return "-Infinity"
    return str(x)


def _ail_jd_bad(st: int) -> int:
    # a float that allow_nan=False refuses, met by the C appender (status 1 nan, 2 inf, 3 -inf)
    _ail_jdc_begin()
    if st == 1:
        raise ValueError("Out of range float values are not JSON compliant: nan")
    if st == 2:
        raise ValueError("Out of range float values are not JSON compliant: inf")
    raise ValueError("Out of range float values are not JSON compliant: -inf")
    return 0
'''


# ---- the C fast path of json.loads (cruntime parts JFCORE, JFINTS, ... registered at the end of cruntime.py) ----
#
# One pass over the text's bytes, straight into the declared container, for the documents that are
# plain: strict RFC 8259 syntax, every value of the declared type, ints within 64 bits, no lone
# surrogate. Anything else -- a syntax error, a value of another type, NaN / Infinity, an integer
# beyond int64 -- returns 0 with nothing built, and the caller runs the scanner and typed parsers
# above, which produce CPython's error message and position (or the RuntimeError for a type
# mismatch). So the fast path never has to reproduce an error: it only has to accept a subset of
# what the slow path accepts, with the value the slow path would build.

FAST_CORE = r'''
/* json.loads fast path (jsonlib.py): the scanner helpers shared by every declared type. */
typedef struct { uint8_t *p; int64_t cap; } ail_jf_buf;
static inline const uint8_t *ail_jf_ws(const uint8_t *p, const uint8_t *e) {
    while (p < e && (*p == 32 || *p == 10 || *p == 13 || *p == 9)) p++;
    return p;
}
/* list[list[T]] is read one row at a time (the typed loader appends each row to its result): the opener
   returns the offset of the first row, -1 when the text is not a plain array, -2 for an empty array that
   ends the text; a row reader returns (offset of the next row) * 2 + 1, or (end of the text) * 2 + 0 after
   the last row, or -1. */
static int64_t ail_jf_rows_open(ail_str s) {
    const uint8_t *e = s.p + s.n, *p = ail_jf_ws(s.p, e);
    if (p >= e || *p != '[') return -1;
    p = ail_jf_ws(p + 1, e);
    if (p < e && *p == ']') return ail_jf_ws(p + 1, e) == e ? -2 : -1;
    return p - s.p;
}
/* After a row: whitespace, then ',' (more rows follow) or the closing ']' and the end of the text. */
static inline int64_t ail_jf_row_next(ail_str s, const uint8_t *p) {
    const uint8_t *e = s.p + s.n;
    p = ail_jf_ws(p, e);
    if (p < e && *p == ',') return (((ail_jf_ws(p + 1, e) - s.p)) << 1) | 1;
    if (p < e && *p == ']' && ail_jf_ws(p + 1, e) == e) return (e - s.p) << 1;
    return -1;
}
static int ail_jf_hex4(const uint8_t *q, uint32_t *out) {
    uint32_t v = 0;
    for (int k = 0; k < 4; k++) {
        uint8_t c = q[k];
        uint32_t d = (unsigned)(c - '0') < 10 ? c - '0' : (unsigned)(c - 'a') < 6 ? c - 'a' + 10
                   : (unsigned)(c - 'A') < 6 ? c - 'A' + 10 : 99;
        if (d > 15) return 0;
        v = v * 16 + d;
    }
    *out = v;
    return 1;
}
/* A string with escapes: `s` is the first byte after the opening quote, `q` the first backslash.
   Decodes into buf (valid until the next call). 0 when the string is not plain (a bad escape, a
   control character, a lone surrogate, no closing quote). */
static const uint8_t *ail_jf_string_esc(const uint8_t *s, const uint8_t *q, const uint8_t *e,
                                        ail_str *out, ail_jf_buf *buf) {
    const uint8_t *r = q;
    while (r < e && *r != '"') r += (*r == '\\' && r + 1 < e) ? 2 : 1;
    if (r >= e) return 0;
    int64_t need = (r - s) + 1;
    if (buf->cap < need) {
        int64_t cap = need < 256 ? 256 : need;
        uint8_t *b = (uint8_t *)realloc(buf->p, (size_t)cap);
        if (!b) ail_die("out of memory");
        buf->p = b; buf->cap = cap;
    }
    uint8_t *o = buf->p;
    uint8_t acc = 0;
    const uint8_t *i = s;
    while (i < r) {
        uint8_t c = *i;
        if (c < 32) return 0;
        if (c != '\\') { acc |= c; *o++ = c; i++; continue; }
        if (i + 1 >= r) return 0;
        uint8_t x = i[1];
        i += 2;
        switch (x) {
        case '"': *o++ = '"'; break;
        case '\\': *o++ = '\\'; break;
        case '/': *o++ = '/'; break;
        case 'b': *o++ = 8; break;
        case 'f': *o++ = 12; break;
        case 'n': *o++ = 10; break;
        case 'r': *o++ = 13; break;
        case 't': *o++ = 9; break;
        case 'u': {
            uint32_t v, w;
            if (i + 4 > r || !ail_jf_hex4(i, &v)) return 0;
            i += 4;
            if (v >= 0xD800 && v < 0xDC00) {
                if (i + 6 > r || i[0] != '\\' || i[1] != 'u' || !ail_jf_hex4(i + 2, &w) || w < 0xDC00 || w >= 0xE000) return 0;
                v = 0x10000u + ((v - 0xD800u) << 10) + (w - 0xDC00u);
                i += 6;
            } else if (v >= 0xDC00 && v < 0xE000) return 0;
            if (v < 0x80) *o++ = (uint8_t)v;
            else {
                acc |= 0x80;
                if (v < 0x800) { *o++ = 0xC0 | (v >> 6); *o++ = 0x80 | (v & 63); }
                else if (v < 0x10000) { *o++ = 0xE0 | (v >> 12); *o++ = 0x80 | ((v >> 6) & 63); *o++ = 0x80 | (v & 63); }
                else { *o++ = 0xF0 | (v >> 18); *o++ = 0x80 | ((v >> 12) & 63); *o++ = 0x80 | ((v >> 6) & 63); *o++ = 0x80 | (v & 63); }
            }
            break;
        }
        default: return 0;
        }
    }
    out->p = buf->p; out->n = o - buf->p; out->bytes = !(acc & 0x80);
    return r + 1;
}
/* A string at p (p[0] is the opening quote): the byte after the closing quote, and the text as a
   view into the input (no escapes) or into buf. */
static inline const uint8_t *ail_jf_string(const uint8_t *p, const uint8_t *e, ail_str *out, ail_jf_buf *buf) {
    const uint8_t *s = ++p;
    uint8_t acc = 0;
    for (; p < e; p++) {
        uint8_t c = *p;
        if (c == '"') { out->p = s; out->n = p - s; out->bytes = !(acc & 0x80); return p + 1; }
        if (c < 32) return 0;
        if (c == '\\') return ail_jf_string_esc(s, p, e, out, buf);
        acc |= c;
    }
    return 0;
}
/* -?(0|[1-9][0-9]*) within int64 and not followed by anything that would continue a number. */
static inline const uint8_t *ail_jf_int(const uint8_t *p, const uint8_t *e, int64_t *out) {
    int neg = 0;
    if (p < e && *p == '-') { neg = 1; p++; }
    if (p >= e) return 0;
    uint64_t v;
    const uint8_t *s = p;
    if (*p == '0') { v = 0; p++; }
    else if ((unsigned)(*p - '1') < 9) {
        v = *p++ - '0';
        while (p < e && (unsigned)(*p - '0') < 10) { v = v * 10 + (*p - '0'); p++; }
        if (p - s > 19) return 0;
        if (neg ? v > 9223372036854775808ull : v > 9223372036854775807ull) return 0;
    } else return 0;
    if (p < e && ((unsigned)(*p - '0') < 10 || *p == '.' || *p == 'e' || *p == 'E')) return 0;
    *out = neg ? (int64_t)(0 - v) : (int64_t)v;
    return p;
}
/* A number with a fraction or an exponent (an int literal is a type mismatch: 0). */
static inline const uint8_t *ail_jf_float(const uint8_t *p, const uint8_t *e, double *out) {
    const uint8_t *s = p;
    if (p < e && *p == '-') p++;
    if (p >= e) return 0;
    if (*p == '0') p++;
    else if ((unsigned)(*p - '1') < 9) { do p++; while (p < e && (unsigned)(*p - '0') < 10); }
    else return 0;
    int is_float = 0;
    if (p < e && *p == '.') {
        const uint8_t *q = p + 1;
        if (q >= e || (unsigned)(*q - '0') >= 10) return 0;
        do q++; while (q < e && (unsigned)(*q - '0') < 10);
        p = q; is_float = 1;
    }
    if (p < e && (*p == 'e' || *p == 'E')) {
        const uint8_t *q = p + 1;
        if (q < e && (*q == '+' || *q == '-')) q++;
        if (q < e && (unsigned)(*q - '0') < 10) {
            do q++; while (q < e && (unsigned)(*q - '0') < 10);
            p = q; is_float = 1;
        }
    }
    if (!is_float) return 0;
    if (p < e && ((unsigned)(*p - '0') < 10 || *p == '.' || *p == 'e' || *p == 'E')) return 0;
    char small[64];
    int64_t len = p - s;
    char *tmp = small;
    if (len >= (int64_t)sizeof small) {
        tmp = (char *)malloc((size_t)len + 1);
        if (!tmp) ail_die("out of memory");
    }
    memcpy(tmp, s, (size_t)len);
    tmp[len] = 0;
    *out = strtod(tmp, 0);
    if (tmp != small) free(tmp);
    return p;
}
'''

FAST_INTS = r'''
/* p at '[': the ints of the array appended to L; the byte after the ']' (0: not handled). */
static const uint8_t *ail_jf_arr_int(const uint8_t *p, const uint8_t *e, ail_list *L) {
    p = ail_jf_ws(p + 1, e);
    if (p < e && *p == ']') return p + 1;
    for (;;) {
        int64_t v;
        p = ail_jf_int(p, e, &v);
        if (!p) return 0;
        ail_list_push(L, v);
        p = ail_jf_ws(p, e);
        if (p >= e) return 0;
        if (*p == ',') { p = ail_jf_ws(p + 1, e); continue; }
        if (*p == ']') return p + 1;
        return 0;
    }
}
static int ail_jf_ints(ail_str s, ail_list *out) {
    const uint8_t *e = s.p + s.n, *p = ail_jf_ws(s.p, e);
    ail_list L = {0};
    if (p < e && *p == '[' && (p = ail_jf_arr_int(p, e, &L)) && ail_jf_ws(p, e) == e) {
        ail_list_free(out);
        *out = L;
        return 1;
    }
    free(L.p);
    return 0;
}
static int64_t ail_jf_row_ints(ail_str s, int64_t pos, ail_list *L) {
    const uint8_t *e = s.p + s.n, *p = s.p + pos;
    if (pos < 0 || pos >= s.n || *p != '[') return -1;
    L->n = 0;
    p = ail_jf_arr_int(p, e, L);
    return p ? ail_jf_row_next(s, p) : -1;
}
'''

FAST_FLOATS = r'''
static const uint8_t *ail_jf_arr_flt(const uint8_t *p, const uint8_t *e, ail_flist *L) {
    p = ail_jf_ws(p + 1, e);
    if (p < e && *p == ']') return p + 1;
    for (;;) {
        double v;
        p = ail_jf_float(p, e, &v);
        if (!p) return 0;
        ail_flist_push(L, v);
        p = ail_jf_ws(p, e);
        if (p >= e) return 0;
        if (*p == ',') { p = ail_jf_ws(p + 1, e); continue; }
        if (*p == ']') return p + 1;
        return 0;
    }
}
static int ail_jf_floats(ail_str s, ail_flist *out) {
    const uint8_t *e = s.p + s.n, *p = ail_jf_ws(s.p, e);
    ail_flist L = {0};
    if (p < e && *p == '[' && (p = ail_jf_arr_flt(p, e, &L)) && ail_jf_ws(p, e) == e) {
        ail_flist_free(out);
        *out = L;
        return 1;
    }
    free(L.p);
    return 0;
}
static int64_t ail_jf_row_floats(ail_str s, int64_t pos, ail_flist *L) {
    const uint8_t *e = s.p + s.n, *p = s.p + pos;
    if (pos < 0 || pos >= s.n || *p != '[') return -1;
    L->n = 0;
    p = ail_jf_arr_flt(p, e, L);
    return p ? ail_jf_row_next(s, p) : -1;
}
'''

FAST_STRS = r'''
/* The strings of a list[str] (or of every row of a list[list[str]]) are copied into one block of the
   function's string arena: the decoded text is never longer than the raw one, so the rest of the
   document bounds the block. */
static const uint8_t *ail_jf_arr_str(const uint8_t *p, const uint8_t *e, ail_slist *L, uint8_t **top,
                                     ail_jf_buf *buf) {
    p = ail_jf_ws(p + 1, e);
    if (p < e && *p == ']') return p + 1;
    for (;;) {
        ail_str t;
        if (p >= e || *p != '"' || !(p = ail_jf_string(p, e, &t, buf))) return 0;
        if (t.n) memcpy(*top, t.p, (size_t)t.n);
        ail_slist_push(L, (ail_str){*top, t.n, t.bytes});
        *top += t.n;
        p = ail_jf_ws(p, e);
        if (p >= e) return 0;
        if (*p == ',') { p = ail_jf_ws(p + 1, e); continue; }
        if (*p == ']') return p + 1;
        return 0;
    }
}
static int ail_jf_strs(ail_str s, ail_slist *out, ail_sarena *A) {
    const uint8_t *e = s.p + s.n, *p = ail_jf_ws(s.p, e);
    ail_slist L = {0};
    ail_jf_buf buf = {0};
    if (p < e && *p == '[') {
        uint8_t *top = ail_sarena_alloc(A, e - p + 1);
        p = ail_jf_arr_str(p, e, &L, &top, &buf);
    } else p = 0;
    free(buf.p);
    if (p && ail_jf_ws(p, e) == e) {
        ail_slist_free(out);
        *out = L;
        return 1;
    }
    free(L.p);
    return 0;
}
static int ail_jf_nest_strs(ail_str s, ail_slist *flat, ail_list *offs, ail_sarena *A) {
    const uint8_t *e = s.p + s.n, *p = ail_jf_ws(s.p, e);
    ail_slist F = {0};
    ail_list O = {0};
    ail_jf_buf buf = {0};
    if (p < e && *p == '[') {
        uint8_t *top = ail_sarena_alloc(A, e - p + 1);
        p = ail_jf_ws(p + 1, e);
        if (p < e && *p == ']') p++;
        else for (;;) {
            if (p >= e || *p != '[' || !(p = ail_jf_arr_str(p, e, &F, &top, &buf))) { p = 0; break; }
            ail_list_push(&O, F.n);
            p = ail_jf_ws(p, e);
            if (p < e && *p == ',') { p = ail_jf_ws(p + 1, e); continue; }
            if (p < e && *p == ']') { p++; break; }
            p = 0; break;
        }
    } else p = 0;
    free(buf.p);
    if (p && ail_jf_ws(p, e) == e) {
        ail_slist_free(flat); ail_list_free(offs);
        *flat = F; *offs = O;
        return 1;
    }
    free(F.p); free(O.p);
    return 0;
}
'''

FAST_DICT_BODY = r'''
static int NAME(ail_str s, DICT *out) {
    const uint8_t *e = s.p + s.n, *p = ail_jf_ws(s.p, e);
    DICT d = {0};
    ail_jf_buf buf = {0};
    EXTRA_DECL
    int ok = 0;
    if (p < e && *p == '{') {
        p = ail_jf_ws(p + 1, e);
        if (p < e && *p == '}') { p++; ok = 1; }
        else for (;;) {
            ail_str k;
            VALUE_DECL
            if (p >= e || *p != '"' || !(p = ail_jf_string(p, e, &k, &buf))) break;
            p = ail_jf_ws(p, e);
            if (p >= e || *p != ':') break;
            p = ail_jf_ws(p + 1, e);
            if (!(p = PARSE_VALUE)) break;
            STORE
            p = ail_jf_ws(p, e);
            if (p < e && *p == ',') { p = ail_jf_ws(p + 1, e); continue; }
            if (p < e && *p == '}') { p++; ok = 1; }
            break;
        }
    }
    free(buf.p);
    EXTRA_FREE
    if (ok && ail_jf_ws(p, e) == e) {
        REPLACE(out, d);
        return 1;
    }
    DROP(&d);
    return 0;
}
'''


def _dict_fast(name, dtype, value_decl, parse_value, store, replace, drop, extra_decl='', extra_free=''):
    return (FAST_DICT_BODY.replace('NAME', name).replace('DICT', dtype).replace('EXTRA_DECL', extra_decl)
            .replace('EXTRA_FREE', extra_free).replace('VALUE_DECL', value_decl)
            .replace('PARSE_VALUE', parse_value).replace('STORE', store).replace('REPLACE', replace)
            .replace('DROP', drop))


FAST_DICT_INT = _dict_fast(
    'ail_jf_dict_int', 'ail_sdict', 'int64_t v;', 'ail_jf_int(p, e, &v)',
    '{ int64_t slot; ail_sdict_upsert(&d, k, &slot); d.table.val[slot] = v; }',
    'ail_sdict_replace', 'ail_sdict_free')

FAST_DICT_FLOAT = _dict_fast(
    'ail_jf_dict_float', 'ail_fdict', 'double v;', 'ail_jf_float(p, e, &v)',
    '{ int64_t slot; ail_sdict_upsert(&d, k, &slot); d.table.val[slot] = ail_fdict_pack(v); }',
    'ail_fdict_replace', 'ail_fdict_free')

FAST_DICT_STR = _dict_fast(
    'ail_jf_dict_str', 'ail_smap', 'ail_str v;', '(p < e && *p == 0x22 ? ail_jf_string(p, e, &v, &vbuf) : 0)',
    'ail_smap_put(&d, k, v);',
    'ail_smap_replace', 'ail_smap_free', 'ail_jf_buf vbuf = {0};', 'free(vbuf.p);')


# ---- the C side of json.dumps (cruntime parts JDCORE, JDINTS, ... registered at the end of cruntime.py) ----
#
# The text is built in one growing buffer per thread: begin, any number of appends (a container's
# elements, or a literal piece from the typed wrapper), take (the buffer becomes a string of the
# caller's arena). The bytes are exactly the ones the typed helpers in DUMPS above produce: CPython's
# separators, ensure_ascii escapes (lower-case hex, surrogate pairs), float repr, NaN / Infinity.
# The float functions return 0, or 1 / 2 / 3 for nan / inf / -inf met with allow_nan false (the
# wrapper raises CPython's ValueError after dropping the partial text).

DUMP_CORE = r'''
typedef struct { uint8_t *p; int64_t n, cap; uint8_t hi; } ail_jd_buf;
AIL_LINK_STATE(_Thread_local ail_jd_buf, ail_jd_g, = {0});
typedef struct { ail_str pad; int64_t pretty; ail_str isep, ksep; int64_t asc, srt, nan; } ail_jd_opt;
static void ail_jd_grow(int64_t need) {
    int64_t cap = ail_jd_g.cap ? ail_jd_g.cap : 4096;
    while (cap < need) {
        if (cap > INT64_MAX / 2) ail_die("allocation too large");
        cap *= 2;
    }
    uint8_t *q = (uint8_t *)realloc(ail_jd_g.p, (size_t)cap);
    if (!q) ail_die("out of memory");
    ail_jd_g.p = q; ail_jd_g.cap = cap;
}
/* The write position, with room for `extra` more bytes and the closing NUL. */
static inline uint8_t *ail_jd_room(int64_t extra) {
    if (ail_jd_g.n + extra + 1 > ail_jd_g.cap) ail_jd_grow(ail_jd_g.n + extra + 1);
    return ail_jd_g.p + ail_jd_g.n;
}
static void ail_jd_begin(void) { ail_jd_g.n = 0; ail_jd_g.hi = 0; }
static inline void ail_jd_lit(const char *s, int64_t n) {
    memcpy(ail_jd_room(n), s, (size_t)n);
    ail_jd_g.n += n;
}
static inline void ail_jd_put(ail_str s) {
    if (s.n) { memcpy(ail_jd_room(s.n), s.p, (size_t)s.n); ail_jd_g.n += s.n; }
    if (!s.bytes) ail_jd_g.hi = 0x80;
}
/* The text so far as an owned str (a malloc'd block, as ail_str_return_owned makes one): what a typed
   `-> str` function returns, without a second copy; the buffer starts empty again. */
static ail_str ail_jd_take_owned(void) {
    if (!ail_jd_g.n) return (ail_str){NULL, 0, 1};
    ail_jd_g.p[ail_jd_g.n] = 0;
    ail_str s = {ail_jd_g.p, ail_jd_g.n, !(ail_jd_g.hi & 0x80)};
    ail_jd_g.p = 0; ail_jd_g.n = ail_jd_g.cap = 0; ail_jd_g.hi = 0;
    return s;
}
/* "\n" and `lvl` copies of the indent unit. */
static void ail_jd_nl(const ail_jd_opt *o, int64_t lvl) {
    int64_t unit = o->pad.n;
    uint8_t *w = ail_jd_room(1 + unit * lvl);
    *w++ = 10;
    for (int64_t k = 0; k < lvl; k++, w += unit) memcpy(w, o->pad.p, (size_t)unit);
    ail_jd_g.n += 1 + unit * lvl;
    if (unit && !o->pad.bytes) ail_jd_g.hi = 0x80;
}
static inline void ail_jd_sep(const ail_jd_opt *o, int64_t lvl) {
    ail_jd_put(o->isep);
    if (o->pretty) ail_jd_nl(o, lvl);
}
static const char ail_jd_digits2[] =
    "00010203040506070809101112131415161718192021222324252627282930313233343536373839"
    "40414243444546474849505152535455565758596061626364656667686970717273747576777879"
    "8081828384858687888990919293949596979899";
static inline void ail_jd_int(int64_t v) {
    uint8_t *w = ail_jd_room(20);
    char tmp[24];
    int k = 24;
    uint64_t u = v < 0 ? 0 - (uint64_t)v : (uint64_t)v;
    while (u >= 100) {
        unsigned r = (unsigned)(u % 100);
        u /= 100;
        k -= 2;
        tmp[k] = ail_jd_digits2[2 * r]; tmp[k + 1] = ail_jd_digits2[2 * r + 1];
    }
    if (u >= 10) { k -= 2; tmp[k] = ail_jd_digits2[2 * u]; tmp[k + 1] = ail_jd_digits2[2 * u + 1]; }
    else tmp[--k] = (char)('0' + u);
    if (v < 0) tmp[--k] = '-';
    memcpy(w, tmp + k, (size_t)(24 - k));
    ail_jd_g.n += 24 - k;
}
static inline void ail_jd_hex4(uint8_t *w, uint32_t c) {
    static const char d[] = "0123456789abcdef";
    w[0] = '\\'; w[1] = 'u';
    w[2] = d[(c >> 12) & 15]; w[3] = d[(c >> 8) & 15]; w[4] = d[(c >> 4) & 15]; w[5] = d[c & 15];
}
/* A string as JSON: quotes, escapes. ensure_ascii escapes every non-ASCII character (and DEL). */
static void ail_jd_string(ail_str s, int64_t asc) {
    const uint8_t *p = s.p, *e = s.p + s.n;
    uint8_t *w = ail_jd_room(s.n * 6 + 2);
    int64_t base = ail_jd_g.n;
    uint8_t *start = w;
    *w++ = '"';
    while (p < e) {
        const uint8_t *run = p;
        while (p < e && *p >= 32 && *p < 127 && *p != '"' && *p != '\\') p++;
        if (p > run) { memcpy(w, run, (size_t)(p - run)); w += p - run; }
        if (p >= e) break;
        uint8_t c = *p;
        if (c == '"') { *w++ = '\\'; *w++ = '"'; p++; }
        else if (c == '\\') { *w++ = '\\'; *w++ = '\\'; p++; }
        else if (c == 10) { *w++ = '\\'; *w++ = 'n'; p++; }
        else if (c == 13) { *w++ = '\\'; *w++ = 'r'; p++; }
        else if (c == 9) { *w++ = '\\'; *w++ = 't'; p++; }
        else if (c == 8) { *w++ = '\\'; *w++ = 'b'; p++; }
        else if (c == 12) { *w++ = '\\'; *w++ = 'f'; p++; }
        else if (c < 32) { ail_jd_hex4(w, c); w += 6; p++; }
        else if (c == 127) {
            if (asc) { ail_jd_hex4(w, c); w += 6; } else *w++ = c;
            p++;
        } else if (!asc) {
            int64_t k = ail__utf8_w(c, e - p);
            memcpy(w, p, (size_t)k); w += k; p += k;
            ail_jd_g.hi = 0x80;
        } else {
            uint32_t cp;
            int64_t k = ail__utf8_w(c, e - p);
            if (k == 2) cp = ((c & 0x1Fu) << 6) | (p[1] & 0x3Fu);
            else if (k == 3) cp = ((c & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu);
            else cp = ((c & 0x07u) << 18) | ((p[1] & 0x3Fu) << 12) | ((p[2] & 0x3Fu) << 6) | (p[3] & 0x3Fu);
            p += k;
            if (cp < 0x10000) { ail_jd_hex4(w, cp); w += 6; }
            else {
                uint32_t v = cp - 0x10000;
                ail_jd_hex4(w, 0xD800 + (v >> 10)); ail_jd_hex4(w + 6, 0xDC00 + (v & 1023)); w += 12;
            }
        }
    }
    *w++ = '"';
    (void)base;
    ail_jd_g.n += w - start;
}
/* The entry numbers of a dict's n keys in code point order (UTF-8 byte order is code point order). */
static int64_t *ail_jd_sorted(const ail_str *keys, int64_t n) {
    int64_t *a = (int64_t *)malloc((size_t)(n ? n : 1) * sizeof *a);
    int64_t *b = (int64_t *)malloc((size_t)(n ? n : 1) * sizeof *b);
    uint64_t *pre = (uint64_t *)malloc((size_t)(n ? n : 1) * sizeof *pre);
    if (!a || !b || !pre) ail_die("out of memory");
    for (int64_t i = 0; i < n; i++) {
        uint8_t t[8] = {0};
        int64_t m = keys[i].n < 8 ? keys[i].n : 8;
        if (m) memcpy(t, keys[i].p, (size_t)m);
        uint64_t v;
        memcpy(&v, t, 8);
        pre[i] = __builtin_bswap64(v);
        a[i] = i;
    }
    for (int64_t w = 1; w < n; w *= 2) {
        for (int64_t lo = 0; lo < n; lo += 2 * w) {
            int64_t mid = lo + w < n ? lo + w : n, hi = lo + 2 * w < n ? lo + 2 * w : n;
            int64_t i = lo, j = mid, o = lo;
            while (i < mid && j < hi) {
                int64_t x = a[i], y = a[j];
                int le;
                if (pre[x] != pre[y]) le = pre[x] < pre[y];
                else le = ail_str_cmp(keys[x], keys[y]) <= 0;
                b[o++] = le ? a[i++] : a[j++];
            }
            while (i < mid) b[o++] = a[i++];
            while (j < hi) b[o++] = a[j++];
        }
        int64_t *t = a; a = b; b = t;
    }
    free(b); free(pre);
    return a;
}
'''

DUMP_BOOLS_INTS = r'''
/* A list of ints / bools (`bools`: true / false by truthiness). */
static void ail_jd_ints(ail_list L, int64_t bools, const ail_jd_opt *o, int64_t lvl) {
    if (L.n == 0) { ail_jd_lit("[]", 2); return; }
    ail_jd_lit("[", 1);
    if (o->pretty) ail_jd_nl(o, lvl + 1);
    for (int64_t i = 0; i < L.n; i++) {
        if (i) ail_jd_sep(o, lvl + 1);
        if (bools) { if (L.p[i]) ail_jd_lit("true", 4); else ail_jd_lit("false", 5); }
        else ail_jd_int(L.p[i]);
    }
    if (o->pretty) ail_jd_nl(o, lvl);
    ail_jd_lit("]", 1);
}
'''

def _ryu_tables():
    """The C tables of the shortest-digits float printer below: 5^i cut to 125 bits (326 entries) and the
    125-bit reciprocals 2^j / 5^i + 1 (342 entries), as pairs of 64-bit words, low word first."""
    bits = 125
    pos, inv = [], []
    for i in range(326):
        p = 5 ** i
        j = p.bit_length() - bits
        v = p >> j if j >= 0 else p << -j
        pos.append((v & (2 ** 64 - 1), v >> 64))
    for i in range(342):
        p = 5 ** i
        v = (1 << (p.bit_length() - 1 + bits)) // p + 1
        inv.append((v & (2 ** 64 - 1), v >> 64))

    def table(name, rows):
        return 'static const uint64_t %s[%d][2] = {\n%s\n};\n' % (
            name, len(rows), ',\n'.join('{ %du, %du }' % row for row in rows))
    return table('ail_ryu_pow5_inv_split', inv) + table('ail_ryu_pow5_split', pos)


# repr(float) by Ryu (Ulf Adams, 2018): the shortest digits that read back as the same double, which is the
# string ail_fmt_float finds by its search over printf precisions -- for every double whose rounding
# interval is symmetric (a power of two has a lopsided one: those, 2046 doubles, and a platform without
# 128-bit integers take ail_fmt_float itself). Checked against ail_fmt_float on tens of millions of doubles.
DUMP_REPR = _ryu_tables() + r'''
#if defined(__SIZEOF_INT128__)
#define AIL_RYU_BITS 125
static inline uint32_t ail_ryu_pow5bits(int32_t e) { return (uint32_t)(((uint32_t)e * 1217359u) >> 19) + 1u; }
static inline uint32_t ail_ryu_log10pow2(int32_t e) { return ((uint32_t)e * 78913u) >> 18; }
static inline uint32_t ail_ryu_log10pow5(int32_t e) { return ((uint32_t)e * 732923u) >> 20; }
static inline uint32_t ail_ryu_pow5factor(uint64_t v) {
    uint32_t n = 0;
    for (;;) {
        uint64_t q = v / 5;
        if (v != q * 5) return n;
        v = q;
        n++;
    }
}
static inline uint64_t ail_ryu_mulshift(uint64_t m, const uint64_t *mul, int32_t j) {
    unsigned __int128 b0 = (unsigned __int128)m * mul[0];
    unsigned __int128 b2 = (unsigned __int128)m * mul[1];
    return (uint64_t)(((b0 >> 64) + b2) >> (j - 64));
}
/* The shortest digits (m, no trailing zeros left to remove) and exponent e with value = m * 10^e that
   round to the finite nonzero double with these fields. Not for a power of two (mantissa 0, exponent > 1:
   the interval is lopsided there and the caller takes the slow path). */
static void ail_ryu_d2d(uint64_t ieee_m, uint32_t ieee_e, uint64_t *out_m, int32_t *out_e) {
    int32_t e2;
    uint64_t m2;
    if (ieee_e == 0) { e2 = 1 - 1023 - 52 - 2; m2 = ieee_m; }
    else { e2 = (int32_t)ieee_e - 1023 - 52 - 2; m2 = (1ull << 52) | ieee_m; }
    int accept = (m2 & 1) == 0;
    uint64_t mv = 4 * m2;
    uint32_t mm_shift = ieee_m != 0 || ieee_e <= 1;
    uint64_t vr, vp, vm;
    int32_t e10;
    int vm_tz = 0, vr_tz = 0;
    if (e2 >= 0) {
        uint32_t q = ail_ryu_log10pow2(e2) - (e2 > 3);
        e10 = (int32_t)q;
        int32_t k = AIL_RYU_BITS + (int32_t)ail_ryu_pow5bits((int32_t)q) - 1;
        int32_t i = -e2 + (int32_t)q + k;
        const uint64_t *mul = ail_ryu_pow5_inv_split[q];
        vr = ail_ryu_mulshift(4 * m2, mul, i);
        vp = ail_ryu_mulshift(4 * m2 + 2, mul, i);
        vm = ail_ryu_mulshift(4 * m2 - 1 - mm_shift, mul, i);
        if (q <= 21) {
            uint32_t mv_mod5 = (uint32_t)(mv - 5 * (mv / 5));
            if (mv_mod5 == 0) vr_tz = ail_ryu_pow5factor(mv) >= q;
            else if (accept) vm_tz = ail_ryu_pow5factor(mv - 1 - mm_shift) >= q;
            else vp -= ail_ryu_pow5factor(mv + 2) >= q;
        }
    } else {
        uint32_t q = ail_ryu_log10pow5(-e2) - (-e2 > 1);
        e10 = (int32_t)q + e2;
        int32_t i = -e2 - (int32_t)q;
        int32_t k = (int32_t)ail_ryu_pow5bits(i) - AIL_RYU_BITS;
        int32_t j = (int32_t)q - k;
        const uint64_t *mul = ail_ryu_pow5_split[i];
        vr = ail_ryu_mulshift(4 * m2, mul, j);
        vp = ail_ryu_mulshift(4 * m2 + 2, mul, j);
        vm = ail_ryu_mulshift(4 * m2 - 1 - mm_shift, mul, j);
        if (q <= 1) {
            vr_tz = 1;
            if (accept) vm_tz = mm_shift == 1;
            else --vp;
        } else if (q < 63) {
            vr_tz = (mv & ((1ull << q) - 1)) == 0;
        }
    }
    int32_t removed = 0;
    uint8_t last = 0;
    uint64_t output;
    if (vm_tz || vr_tz) {
        for (;;) {
            uint64_t vp10 = vp / 10, vm10 = vm / 10;
            if (vp10 <= vm10) break;
            uint32_t vm_mod = (uint32_t)(vm - 10 * vm10);
            uint64_t vr10 = vr / 10;
            uint32_t vr_mod = (uint32_t)(vr - 10 * vr10);
            vm_tz &= vm_mod == 0;
            vr_tz &= last == 0;
            last = (uint8_t)vr_mod;
            vr = vr10; vp = vp10; vm = vm10;
            ++removed;
        }
        if (vm_tz) {
            for (;;) {
                uint64_t vm10 = vm / 10;
                uint32_t vm_mod = (uint32_t)(vm - 10 * vm10);
                if (vm_mod != 0) break;
                uint64_t vp10 = vp / 10, vr10 = vr / 10;
                uint32_t vr_mod = (uint32_t)(vr - 10 * vr10);
                vr_tz &= last == 0;
                last = (uint8_t)vr_mod;
                vr = vr10; vp = vp10; vm = vm10;
                ++removed;
            }
        }
        if (vr_tz && last == 5 && vr % 2 == 0) last = 4;
        output = vr + ((vr == vm && (!accept || !vm_tz)) || last >= 5);
    } else {
        int round_up = 0;
        uint64_t vp100 = vp / 100, vm100 = vm / 100;
        if (vp100 > vm100) {
            uint64_t vr100 = vr / 100;
            uint32_t vr_mod = (uint32_t)(vr - 100 * vr100);
            round_up = vr_mod >= 50;
            vr = vr100; vp = vp100; vm = vm100;
            removed += 2;
        }
        for (;;) {
            uint64_t vp10 = vp / 10, vm10 = vm / 10;
            if (vp10 <= vm10) break;
            uint64_t vr10 = vr / 10;
            uint32_t vr_mod = (uint32_t)(vr - 10 * vr10);
            round_up = vr_mod >= 5;
            vr = vr10; vp = vp10; vm = vm10;
            ++removed;
        }
        output = vr + (vr == vm || round_up);
    }
    *out_m = output;
    *out_e = e10 + removed;
}
#endif
/* repr(x) of a finite double into out (at most 24 bytes): CPython's float repr, the bytes ail_fmt_float
   writes. 1 when written. */
static int ail_jd_repr(double x, char *out) {
#if defined(__SIZEOF_INT128__)
    uint64_t bits;
    memcpy(&bits, &x, 8);
    uint64_t ieee_m = bits & ((1ull << 52) - 1);
    uint32_t ieee_e = (uint32_t)((bits >> 52) & 0x7FF);
    int neg = (int)(bits >> 63);
    char *w = out;
    if (neg) *w++ = '-';
    if (ieee_e == 0 && ieee_m == 0) { *w++ = '0'; *w++ = '.'; *w++ = '0'; *w = 0; return (int)(w - out); }
    if (ieee_m == 0 && ieee_e > 1) return 0;          /* a power of two: the slow path */
    uint64_t m;
    int32_t e;
    ail_ryu_d2d(ieee_m, ieee_e, &m, &e);
    char digits[24];
    int nd = 0;
    while (m) { digits[nd++] = (char)('0' + m % 10); m /= 10; }
    for (int a = 0, b = nd - 1; a < b; a++, b--) { char t = digits[a]; digits[a] = digits[b]; digits[b] = t; }
    int exp10 = e + nd - 1;
    while (nd > 1 && digits[nd - 1] == '0') nd--;
    if (exp10 >= -4 && exp10 < 16) {
        if (exp10 >= 0) {
            for (int i = 0; i <= exp10; i++) *w++ = i < nd ? digits[i] : '0';
            *w++ = '.';
            if (nd > exp10 + 1) for (int i = exp10 + 1; i < nd; i++) *w++ = digits[i];
            else *w++ = '0';
        } else {
            *w++ = '0'; *w++ = '.';
            for (int i = 0; i < -exp10 - 1; i++) *w++ = '0';
            for (int i = 0; i < nd; i++) *w++ = digits[i];
        }
    } else {
        *w++ = digits[0];
        if (nd > 1) { *w++ = '.'; for (int i = 1; i < nd; i++) *w++ = digits[i]; }
        *w++ = 'e';
        *w++ = exp10 < 0 ? '-' : '+';
        int ax = exp10 < 0 ? -exp10 : exp10;
        if (ax >= 100) { *w++ = (char)('0' + ax / 100); ax %= 100; }
        *w++ = (char)('0' + ax / 10);
        *w++ = (char)('0' + ax % 10);
    }
    *w = 0;
    return (int)(w - out);
#else
    (void)x; (void)out;
    return 0;
#endif
}
'''


DUMP_FLOATS = r'''
static int ail_jd_float(double x, const ail_jd_opt *o) {
    if (x != x) { if (!o->nan) return 1; ail_jd_lit("NaN", 3); return 0; }
    if (x > 1.7976931348623157e308) { if (!o->nan) return 2; ail_jd_lit("Infinity", 8); return 0; }
    if (x < -1.7976931348623157e308) { if (!o->nan) return 3; ail_jd_lit("-Infinity", 9); return 0; }
    char tmp[64];
    int n = ail_jd_repr(x, tmp);
    if (!n) { ail_fmt_float(tmp, sizeof tmp, x); n = (int)strlen(tmp); }
    ail_jd_lit(tmp, n);
    return 0;
}
static int ail_jd_floats(ail_flist L, const ail_jd_opt *o, int64_t lvl) {
    if (L.n == 0) { ail_jd_lit("[]", 2); return 0; }
    ail_jd_lit("[", 1);
    if (o->pretty) ail_jd_nl(o, lvl + 1);
    for (int64_t i = 0; i < L.n; i++) {
        if (i) ail_jd_sep(o, lvl + 1);
        int st = ail_jd_float(L.p[i], o);
        if (st) return st;
    }
    if (o->pretty) ail_jd_nl(o, lvl);
    ail_jd_lit("]", 1);
    return 0;
}
'''

DUMP_STRS = r'''
static void ail_jd_strs(ail_slist L, const ail_jd_opt *o, int64_t lvl) {
    if (L.n == 0) { ail_jd_lit("[]", 2); return; }
    ail_jd_lit("[", 1);
    if (o->pretty) ail_jd_nl(o, lvl + 1);
    for (int64_t i = 0; i < L.n; i++) {
        if (i) ail_jd_sep(o, lvl + 1);
        ail_jd_string(L.p[i], o->asc);
    }
    if (o->pretty) ail_jd_nl(o, lvl);
    ail_jd_lit("]", 1);
}
'''

DUMP_DICT_BODY = r'''
static int NAME(const DICT *D, const ail_jd_opt *o, int64_t lvl) {
    DENSE
    int64_t n = D->table.n;
    if (n == 0) { ail_jd_lit("{}", 2); return 0; }
    const ail_str *keys = D->table.order;
    int64_t *order = o->srt ? ail_jd_sorted(keys, n) : 0;
    int st = 0;
    ail_jd_lit("{", 1);
    if (o->pretty) ail_jd_nl(o, lvl + 1);
    for (int64_t i = 0; i < n && !st; i++) {
        int64_t e = order ? order[i] : i;
        if (i) ail_jd_sep(o, lvl + 1);
        ail_jd_string(keys[e], o->asc);
        ail_jd_put(o->ksep);
        VALUE
    }
    free(order);
    if (st) return st;
    if (o->pretty) ail_jd_nl(o, lvl);
    ail_jd_lit("}", 1);
    return 0;
}
'''


def _dump_dict(name, dtype, value, dense='ail_stab_dense(&D->table);'):
    return DUMP_DICT_BODY.replace('NAME', name).replace('DICT', dtype).replace('DENSE', dense).replace('VALUE', value)


DUMP_DICT_INT = _dump_dict('ail_jd_dict_int', 'ail_sdict', 'ail_jd_int(D->table.val[e]);')
DUMP_DICT_FLOAT = _dump_dict('ail_jd_dict_float', 'ail_fdict', 'st = ail_jd_float(ail_fdict_unpack(D->table.val[e]), o);')
DUMP_DICT_STR = _dump_dict('ail_jd_dict_str', 'ail_smap', 'ail_jd_string(D->values[D->table.val[e]], o->asc);',
                           'ail_smap_dense(D);')
