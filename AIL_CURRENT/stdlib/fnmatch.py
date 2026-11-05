"""Derived from CPython 3.12 Lib/fnmatch.py; PSF License, see stdlib/LICENSE-PSF.txt.

Filename matching with shell patterns.  `fnmatch()` and `filter()` case-normalize their arguments
with `os.path.normcase`, which is the identity on POSIX (this file is POSIX-only), so it is not
called.  CPython compiles `translate()`'s regular expression at run time; this compiler only accepts
a literal pattern in `re.compile`, so matching walks the pattern directly.  `translate()` still
returns CPython's exact regular-expression text.  Bytes patterns and names are matched as
ISO-8859-1 text, as CPython does when it compiles them.
"""

__all__ = ["filter", "fnmatch", "fnmatchcase", "translate"]

import re


def _class_end(pat: str, start: int) -> int:
    n = len(pat)
    j = start + 1
    if j < n and pat[j] == "!":
        j = j + 1
    if j < n and pat[j] == "]":
        j = j + 1
    while j < n and pat[j] != "]":
        j = j + 1
    if j >= n:
        return -1
    return j


def _class_matches(c: str, cls: str) -> bool:
    body = cls[1:-1]
    negate = False
    if body.startswith("!"):
        negate = True
        body = body[1:]
    matched = False
    k = 0
    n = len(body)
    while k < n:
        if k + 2 < n and body[k + 1] == "-":
            lo = body[k]
            hi = body[k + 2]
            if lo <= c and c <= hi:
                matched = True
            k = k + 3
        else:
            if body[k] == c:
                matched = True
            k = k + 1
    if negate:
        return not matched
    return matched


def _match(name: str, pat: str) -> bool:
    ni = 0
    pi = 0
    n = len(name)
    m = len(pat)
    star = -1
    star_ni = 0
    while ni < n:
        if pi < m and pat[pi] == "*":
            star = pi
            pi = pi + 1
            star_ni = ni
        elif pi < m and pat[pi] == "[":
            end = _class_end(pat, pi)
            if end < 0:
                if name[ni] == "[":
                    ni = ni + 1
                    pi = pi + 1
                elif star >= 0:
                    pi = star + 1
                    star_ni = star_ni + 1
                    ni = star_ni
                else:
                    return False
            else:
                cls = pat[pi:end + 1]
                if _class_matches(name[ni], cls):
                    ni = ni + 1
                    pi = end + 1
                elif star >= 0:
                    pi = star + 1
                    star_ni = star_ni + 1
                    ni = star_ni
                else:
                    return False
        elif pi < m and (pat[pi] == "?" or pat[pi] == name[ni]):
            ni = ni + 1
            pi = pi + 1
        elif star >= 0:
            pi = star + 1
            star_ni = star_ni + 1
            ni = star_ni
        else:
            return False
    while pi < m and pat[pi] == "*":
        pi = pi + 1
    return pi == m


def _as_text(value) -> str:
    if isinstance(value, bytes):
        return str(value, "ISO-8859-1")
    return value


def _check_type(name, pat):
    if isinstance(pat, bytes):
        if isinstance(name, str):
            raise TypeError("cannot use a bytes pattern on a string-like object")
    elif isinstance(pat, str):
        if isinstance(name, bytes):
            raise TypeError("cannot use a string pattern on a bytes-like object")
    else:
        raise TypeError("object of type '%s' has no len()"
                        % type(pat).__name__)
    if not isinstance(name, str) and not isinstance(name, bytes):
        raise TypeError("expected string or bytes-like object, got '%s'"
                        % type(name).__name__)


def fnmatch(name, pat):
    """Test whether FILENAME matches PATTERN.

    Patterns are Unix shell style:

    *       matches everything
    ?       matches any single character
    [seq]   matches any character in seq
    [!seq]  matches any char not in seq

    An initial period in FILENAME is not special.
    Both FILENAME and PATTERN are first case-normalized
    if the operating system requires it.
    If you don't want this, use fnmatchcase(FILENAME, PATTERN).
    """
    _check_type(name, pat)
    return fnmatchcase(_as_text(name), _as_text(pat))


def filter(names, pat):
    """Construct a list from those elements of the iterable NAMES that match PAT."""
    result = []
    for name in names:
        if fnmatchcase(name, pat):
            result.append(name)
    return result


def fnmatchcase(name, pat):
    """Test whether FILENAME matches PATTERN, including case.

    This is a version of fnmatch() which doesn't case-normalize
    its arguments.
    """
    _check_type(name, pat)
    return _match(_as_text(name), _as_text(pat))


def translate(pat):
    """Translate a shell PATTERN to a regular expression.

    There is no way to quote meta-characters.
    """

    STAR = None
    res = []
    add = res.append
    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        i = i + 1
        if c == "*":
            if (not res) or res[-1] is not STAR:
                add(STAR)
        elif c == "?":
            add(".")
        elif c == "[":
            j = i
            if j < n and pat[j] == "!":
                j = j + 1
            if j < n and pat[j] == "]":
                j = j + 1
            while j < n and pat[j] != "]":
                j = j + 1
            if j >= n:
                add("\\[")
            else:
                stuff = pat[i:j]
                if "-" not in stuff:
                    stuff = stuff.replace("\\", r"\\")
                else:
                    chunks = []
                    k = i + 2 if pat[i] == "!" else i + 1
                    while True:
                        k = pat.find("-", k, j)
                        if k < 0:
                            break
                        chunks.append(pat[i:k])
                        i = k + 1
                        k = k + 3
                    chunk = pat[i:j]
                    if chunk:
                        chunks.append(chunk)
                    else:
                        chunks[-1] += "-"
                    for k in range(len(chunks) - 1, 0, -1):
                        if chunks[k - 1][-1] > chunks[k][0]:
                            chunks[k - 1] = chunks[k - 1][:-1] + chunks[k][1:]
                            del chunks[k]
                    stuff = "-".join(s.replace("\\", r"\\").replace("-", r"\-")
                                     for s in chunks)
                stuff = re.sub(r"([&~|])", r"\\\1", stuff)
                i = j + 1
                if not stuff:
                    add("(?!)")
                elif stuff == "!":
                    add(".")
                else:
                    if stuff[0] == "!":
                        stuff = "^" + stuff[1:]
                    elif stuff[0] in ("^", "["):
                        stuff = "\\" + stuff
                    add(f"[{stuff}]")
        else:
            if not isinstance(c, str):
                raise TypeError(
                    "decoding to str: need a bytes-like object, int found")
            add(re.escape(c))

    inp = res
    res = []
    add = res.append
    i, n = 0, len(inp)
    while i < n and inp[i] is not STAR:
        add(inp[i])
        i += 1
    while i < n:
        i += 1
        if i == n:
            add(".*")
            break
        fixed = []
        while i < n and inp[i] is not STAR:
            fixed.append(inp[i])
            i += 1
        fixed = "".join(fixed)
        if i == n:
            add(".*")
            add(fixed)
        else:
            add(f"(?>.*?{fixed})")
    res = "".join(res)
    return fr"(?s:{res})\Z"
