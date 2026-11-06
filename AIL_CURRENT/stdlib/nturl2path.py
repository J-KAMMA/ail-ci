"""Convert a NT pathname to a file URL and vice versa.

This module only exists to provide OS-specific code for urllib.requests, thus do not use directly.

This is CPython 3.12's Lib/nturl2path.py as AIL source.  The two functions keep CPython's logic
and error texts exactly.

Two changes are forced by this compiler:

* CPython imports `urllib.parse` inside each function; an import inside a function or block is
  refused, so CPython's version cannot be used as written.  Moving `import urllib.parse` to the
  top of the file still does not work here: urllib is built on the typed path only, so a program
  built with `AIL_UNIFIED_FORCE=1` (the general path) refuses the whole module.  The two calls
  needed, `urllib.parse.quote` (UTF-8, safe '/') and `urllib.parse.unquote` (UTF-8,
  errors='replace'), are therefore implemented below as `_quote` and `_unquote` over plain str
  operations.  They hold CPython's rules: always-safe bytes A-Za-z0-9_.-~ plus `safe` stay
  unescaped, every other byte becomes %XX in upper case, a '%' not followed by two hex digits is
  literal, and the decoded bytes are read as UTF-8 with one U+FFFD per maximal ill-formed part.
* CPython rebinds its `url` and `p` parameters; the typed path refuses that, so each function
  copies the argument into a local and rebinds the local.
"""

_HEX_DIGITS = "0123456789ABCDEF"
_ALWAYS_SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~"
_ASCII_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _utf8_bytes(ch: str) -> list[int]:
    cp: int = ord(ch)
    out: list[int] = []
    if cp < 0x80:
        out.append(cp)
    elif cp < 0x800:
        out.append(0xC0 + (cp >> 6))
        out.append(0x80 + (cp & 0x3F))
    elif cp < 0x10000:
        out.append(0xE0 + (cp >> 12))
        out.append(0x80 + ((cp >> 6) & 0x3F))
        out.append(0x80 + (cp & 0x3F))
    else:
        out.append(0xF0 + (cp >> 18))
        out.append(0x80 + ((cp >> 12) & 0x3F))
        out.append(0x80 + ((cp >> 6) & 0x3F))
        out.append(0x80 + (cp & 0x3F))
    return out


def _hex_value(ch: str) -> int:
    if ch >= "0" and ch <= "9":
        return ord(ch) - 48
    if ch >= "A" and ch <= "F":
        return ord(ch) - 55
    if ch >= "a" and ch <= "f":
        return ord(ch) - 87
    return -1


def _quote(text: str, safe: str) -> str:
    out: str = ""
    i: int = 0
    while i < len(text):
        ch: str = text[i]
        cp: int = ord(ch)
        if cp < 0x80 and ch in _ALWAYS_SAFE + safe:
            out = out + ch
        else:
            for b in _utf8_bytes(ch):
                out = out + "%" + _HEX_DIGITS[b >> 4] + _HEX_DIGITS[b & 15]
        i += 1
    return out


def _utf8_decode(data: list[int]) -> str:
    out: str = ""
    i: int = 0
    n: int = len(data)
    while i < n:
        b: int = data[i]
        if b < 0x80:
            out = out + chr(b)
            i += 1
            continue
        need: int = 0
        cp: int = 0
        low: int = 0x80
        high: int = 0xBF
        if b >= 0xC2 and b <= 0xDF:
            need = 1
            cp = b & 0x1F
        elif b == 0xE0:
            need = 2
            cp = b & 0x0F
            low = 0xA0
        elif (b >= 0xE1 and b <= 0xEC) or (b >= 0xEE and b <= 0xEF):
            need = 2
            cp = b & 0x0F
        elif b == 0xED:
            need = 2
            cp = b & 0x0F
            high = 0x9F
        elif b == 0xF0:
            need = 3
            cp = b & 0x07
            low = 0x90
        elif b >= 0xF1 and b <= 0xF3:
            need = 3
            cp = b & 0x07
        elif b == 0xF4:
            need = 3
            cp = b & 0x07
            high = 0x8F
        else:
            out = out + "\ufffd"
            i += 1
            continue
        used: int = 1
        while used <= need:
            if i + used >= n:
                break
            c: int = data[i + used]
            if used == 1:
                if c < low or c > high:
                    break
            elif c < 0x80 or c > 0xBF:
                break
            cp = (cp << 6) | (c & 0x3F)
            used += 1
        if used == need + 1:
            out = out + chr(cp)
            i += need + 1
        else:
            out = out + "\ufffd"
            i += used
    return out


def _unquote(text: str) -> str:
    if not '%' in text:
        return text
    raw: list[int] = []
    i: int = 0
    while i < len(text):
        ch: str = text[i]
        if ch == '%' and i + 2 < len(text):
            hi: int = _hex_value(text[i + 1])
            lo: int = _hex_value(text[i + 2])
            if hi >= 0 and lo >= 0:
                raw.append(hi * 16 + lo)
                i += 3
                continue
        for b in _utf8_bytes(ch):
            raw.append(b)
        i += 1
    return _utf8_decode(raw)


def url2pathname(url: str) -> str:
    """OS-specific conversion from a relative URL of the 'file' scheme
    to a file system path; not recommended for general use."""
    # e.g.
    #   ///C|/foo/bar/spam.foo
    # and
    #   ///C:/foo/bar/spam.foo
    # become
    #   C:\foo\bar\spam.foo
    # Windows itself uses ":" even in URLs.
    text: str = url.replace(':', '|')
    if not '|' in text:
        # No drive specifier, just convert slashes
        if text[:4] == '////':
            # path is something like ////host/path/on/remote/host
            # convert this to \\host\path\on\remote\host
            # (notice halving of slashes at the start of the path)
            text = text[2:]
        components: list[str] = text.split('/')
        # make sure not to convert quoted slashes :-)
        return _unquote('\\'.join(components))
    comp: list[str] = text.split('|')
    if len(comp) != 2 or comp[0][-1] not in _ASCII_LETTERS:
        error = 'Bad URL: ' + text
        raise OSError(error)
    drive: str = comp[0][-1].upper()
    components: list[str] = comp[1].split('/')
    path: str = drive + ':'
    for part in components:
        if part:
            path = path + '\\' + _unquote(part)
    # Issue #11474 - handing url such as |c/|
    if path.endswith(':') and text.endswith('/'):
        path += '\\'
    return path


def pathname2url(p: str) -> str:
    """OS-specific conversion from a file system path to a relative URL
    of the 'file' scheme; not recommended for general use."""
    # e.g.
    #   C:\foo\bar\spam.foo
    # becomes
    #   ///C:/foo/bar/spam.foo
    # First, clean up some special forms. We are going to sacrifice
    # the additional information anyway
    text: str = p
    if text[:4] == '\\\\?\\':
        text = text[4:]
        if text[:4].upper() == 'UNC\\':
            text = '\\' + text[4:]
        elif text[1:2] != ':':
            raise OSError('Bad path: ' + text)
    if not ':' in text:
        # No drive specifier, just convert slashes and quote the name
        if text[:2] == '\\\\':
            # path is something like \\host\path\on\remote\host
            # convert this to ////host/path/on/remote/host
            # (notice doubling of slashes at the start of the path)
            text = '\\\\' + text
        components: list[str] = text.split('\\')
        return _quote('/'.join(components), '/')
    comp: list[str] = text.split(':', maxsplit=2)
    if len(comp) != 2 or len(comp[0]) > 1:
        error = 'Bad path: ' + text
        raise OSError(error)

    drive: str = _quote(comp[0].upper(), '/')
    components: list[str] = comp[1].split('\\')
    path: str = '///' + drive + ':'
    for part in components:
        if part:
            path = path + '/' + _quote(part, '/')
    return path
