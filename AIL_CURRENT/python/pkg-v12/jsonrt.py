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
                v = int(b[i:e].decode())
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
'''
