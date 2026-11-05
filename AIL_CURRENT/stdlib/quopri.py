"""Conversions to/from quoted-printable transport encoding as per RFC 1521.

Derived from CPython 3.12 Lib/quopri.py; PSF License, see stdlib/LICENSE-PSF.txt.
This is CPython 3.12's Lib/quopri.py rewritten as AIL source.  The optional `from binascii import
a2b_qp, b2a_qp` accelerator is not imported and the `main()` command-line tool is omitted
(programs import this module, they do not run it as a script).

CPython's installed quopri uses the binascii accelerator, whose output differs from the pure-Python
fallback in a few places (CR/CRLF handling, trailing whitespace at end of line, a trailing `=` on
decode).  To print what `python3` prints, `encodestring` and `decodestring` below reproduce the
accelerator's documented behaviour (binascii's b2a_qp with istext=True and a2b_qp).  `io.BytesIO`
is not built by this compiler, so CPython's file-object functions `encode` and `decode` are left
out; the string functions do their own line handling instead.

CPython is Copyright (c) 2001 Python Software Foundation; All Rights Reserved, and is
distributed under the PSF License Agreement (see https://docs.python.org/3/license.html).
"""

__all__ = ["encodestring", "decodestring"]

ESCAPE = b'='
MAXLINESIZE = 76
HEX = b'0123456789ABCDEF'
EMPTYSTRING = b''


def needsquoting(c, quotetabs, header):
    """Decide whether a particular byte ordinal needs to be quoted.

    The 'quotetabs' flag indicates whether embedded tabs and spaces should be
    quoted.  Note that line-ending tabs and spaces are always encoded, as per
    RFC 1521.
    """
    assert isinstance(c, bytes)
    if c in b' \t':
        return quotetabs
    # if header, we have to escape _ because _ is used to escape space
    if c == b'_':
        return header
    return c == ESCAPE or not (b' ' <= c <= b'~')


def quote(c):
    """Quote a single character."""
    assert isinstance(c, bytes) and len(c) == 1
    n = c[0]
    return ESCAPE + bytes((HEX[n // 16], HEX[n % 16]))


def ishex(c):
    """Return true if the byte ordinal 'c' is a hexadecimal digit in ASCII."""
    assert isinstance(c, bytes)
    return b'0' <= c <= b'9' or b'a' <= c <= b'f' or b'A' <= c <= b'F'


def unhex(s):
    """Get the integer value of a hexadecimal number."""
    bits = 0
    for c in s:
        c = bytes((c,))
        if b'0' <= c <= b'9':
            i = ord('0')
        elif b'a' <= c <= b'f':
            i = ord('a') - 10
        elif b'A' <= c <= b'F':
            i = ord('A') - 10
        else:
            assert False, "non-hex digit " + repr(c)
        bits = bits * 16 + (c[0] - i)
    return bits


def _ishexbyte(c):
    return ((c >= 48 and c <= 57) or (c >= 65 and c <= 70) or (c >= 97 and c <= 102))


def _hexval(c):
    if c >= 48 and c <= 57:
        return c - 48
    if c >= 65 and c <= 70:
        return c - 55
    return c - 87


def _hexpair(c):
    return bytes((HEX[c // 16], HEX[c % 16]))


def encodestring(s, quotetabs=False, header=False):
    datalen = len(s)
    if datalen == 0:
        return b''
    # See if this string is using CRLF line ends, as binascii's b2a_qp does.
    first_nl = s.find(b'\n')
    crlf = 0
    if first_nl > 0 and s[first_nl - 1] == 13:
        crlf = 1

    result = b''
    linelen = 0
    i = 0
    while i < datalen:
        c = s[i]
        quoting = (c > 126 or c == 61 or (header and c == 95) or
                   (c == 46 and linelen == 0 and
                    (i + 1 == datalen or s[i + 1] == 10 or s[i + 1] == 13 or s[i + 1] == 0)) or
                   ((c == 9 or c == 32) and i + 1 == datalen) or
                   (c < 33 and c != 13 and c != 10 and
                    (quotetabs or (c != 9 and c != 32))))
        if quoting:
            if linelen + 3 >= MAXLINESIZE:
                if crlf:
                    result = result + b'=\r\n'
                else:
                    result = result + b'=\n'
                linelen = 0
            result = result + b'=' + _hexpair(c)
            linelen = linelen + 3
            i = i + 1
        elif c == 10 or (i + 1 < datalen and c == 13 and s[i + 1] == 10):
            # A line end.  Protect whitespace that ended up at the end of the line.
            linelen = 0
            if len(result) > 0 and (result[-1] == 32 or result[-1] == 9):
                ch = result[-1]
                result = result[:-1] + b'=' + _hexpair(ch)
            if crlf:
                result = result + b'\r\n'
            else:
                result = result + b'\n'
            if c == 13:
                i = i + 2
            else:
                i = i + 1
        else:
            if i + 1 != datalen and s[i + 1] != 10 and linelen + 1 >= MAXLINESIZE:
                if crlf:
                    result = result + b'=\r\n'
                else:
                    result = result + b'=\n'
                linelen = 0
            linelen = linelen + 1
            if header and c == 32:
                result = result + b'_'
            else:
                result = result + bytes((c,))
            i = i + 1
    return result


def decodestring(s, header=False):
    result = b''
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if c == 61:  # '='
            i = i + 1
            if i >= n:
                break
            d = s[i]
            if d == 10 or d == 13:
                # Soft line break; a CR skips through to the following LF.
                if d != 10:
                    while i < n and s[i] != 10:
                        i = i + 1
                if i < n:
                    i = i + 1
            elif d == 61:
                result = result + b'='
                i = i + 1
            elif i + 1 < n and _ishexbyte(d) and _ishexbyte(s[i + 1]):
                hi = _hexval(d)
                i = i + 1
                lo = _hexval(s[i])
                i = i + 1
                result = result + bytes(((hi << 4) | lo,))
            else:
                result = result + b'='
        elif header and c == 95:  # '_'
            result = result + b' '
            i = i + 1
        else:
            result = result + bytes((c,))
            i = i + 1
    return result
