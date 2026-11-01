# -*- coding: utf-8 -*-
# prelude_fnmatch.py -- `fnmatch.fnmatch`, `fnmatchcase`, `filter` and `translate` as Python source
# (stdtop.py injects it).
#
# The translation is CPython 3.12's fnmatch.translate, character for character (the same STAR
# compression, the same bracket chunking and the same (?s:...)\Z wrapper), and matching uses the
# classic star-backtracking walk over the same pattern tokens.  Plain Python in the subset the
# general path builds, and a module CPython imports as it stands.

_AIL_FNM_SPECIAL = "()[]{}?*+-|^$\\.&~# \t\n\r\v\f"


def _ail_fnm_tname(x) -> str:
    if x is None:
        return "NoneType"
    return type(x).__name__


def _ail_fnm_escape(c: str) -> str:
    if not isinstance(c, str):
        # re.escape's own error, which fnmatch.translate(bytes) reaches: a bytes pattern indexes to ints
        raise TypeError("decoding to str: need a bytes-like object, %s found" % _ail_fnm_tname(c))
    if c in _AIL_FNM_SPECIAL:
        return "\\" + c
    return c


def _ail_fnm_class_stuff(pat: str, i: int, j: int) -> str:
    # the bracket content as CPython's translate makes it, before the [ ] and the ! / ^ / [ head
    stuff = pat[i:j]
    if "-" not in stuff:
        stuff = stuff.replace("\\", "\\\\")
    else:
        chunks: list[str] = []
        k = i + 2 if pat[i] == "!" else i + 1
        while True:
            k = pat.find("-", k, j)
            if k < 0:
                break
            chunks.append(pat[i:k])
            i = k + 1
            k = k + 3
        chunk = pat[i:j]
        if len(chunk) > 0:
            chunks.append(chunk)
        else:
            chunks[len(chunks) - 1] = chunks[len(chunks) - 1] + "-"
        k = len(chunks) - 1
        while k > 0:
            prev = chunks[k - 1]
            if prev[len(prev) - 1] > chunks[k][0]:
                chunks[k - 1] = prev[:len(prev) - 1] + chunks[k][1:]
                chunks.pop(k)
            k = k - 1
        parts: list[str] = []
        for s in chunks:
            parts.append(s.replace("\\", "\\\\").replace("-", "\\-"))
        stuff = "-".join(parts)
    out = ""
    for c in stuff:
        if c == "&" or c == "~" or c == "|":
            out = out + "\\" + c
        else:
            out = out + c
    return out


def _ail_fnm_class_spec(stuff: str) -> str:
    if stuff[0] == "!":
        return "!" + stuff[1:]
    if stuff[0] == "^" or stuff[0] == "[":
        return "\\" + stuff
    return stuff


def _ail_fnm_match_one(kind: int, spec: str, ch: str) -> bool:
    if kind == 1:
        return True
    if kind == 3:
        return False
    if kind == 0:
        return ch == spec
    neg = False
    body = spec
    if body[0] == "!":
        neg = True
        body = body[1:]
    kinds: list[int] = []
    vals: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        c = body[i]
        if c == "\\":
            i = i + 1
            if i < n:
                kinds.append(0)
                vals.append(body[i])
                i = i + 1
            else:
                kinds.append(0)
                vals.append("\\")
        elif c == "-":
            kinds.append(1)
            vals.append("-")
            i = i + 1
        else:
            kinds.append(0)
            vals.append(c)
            i = i + 1
    code = ord(ch)
    hit = False
    k = 0
    while k < len(kinds):
        if kinds[k] == 1:
            if k > 0 and k + 1 < len(kinds) and kinds[k - 1] == 0 and kinds[k + 1] == 0:
                lo = ord(vals[k - 1])
                hi = ord(vals[k + 1])
                if lo <= code and code <= hi:
                    hit = True
                k = k + 2
            else:
                if code == ord("-"):
                    hit = True
                k = k + 1
        else:
            if code == ord(vals[k]):
                hit = True
            k = k + 1
    if neg:
        return not hit
    return hit


def _ail_fnm_match(name: str, pat: str) -> bool:
    kinds: list[int] = []
    specs: list[str] = []
    i = 0
    n = len(pat)
    while i < n:
        c = pat[i]
        i = i + 1
        if c == "*":
            if len(kinds) == 0 or kinds[len(kinds) - 1] != 2:
                kinds.append(2)
                specs.append("")
        elif c == "?":
            kinds.append(1)
            specs.append("")
        elif c == "[":
            j = i
            if j < n and pat[j] == "!":
                j = j + 1
            if j < n and pat[j] == "]":
                j = j + 1
            while j < n and pat[j] != "]":
                j = j + 1
            if j >= n:
                kinds.append(0)
                specs.append("[")
            else:
                stuff = _ail_fnm_class_stuff(pat, i, j)
                i = j + 1
                if len(stuff) == 0:
                    kinds.append(3)
                    specs.append("")
                elif stuff == "!":
                    kinds.append(1)
                    specs.append("")
                else:
                    kinds.append(4)
                    specs.append(_ail_fnm_class_spec(stuff))
        else:
            kinds.append(0)
            specs.append(c)
    ni = 0
    ti = 0
    star_t = -1
    star_n = -1
    while ni < len(name):
        if ti < len(kinds) and kinds[ti] != 2:
            if _ail_fnm_match_one(kinds[ti], specs[ti], name[ni]):
                ni = ni + 1
                ti = ti + 1
                continue
        if ti < len(kinds) and kinds[ti] == 2:
            star_t = ti
            star_n = ni
            ti = ti + 1
            continue
        if star_t >= 0:
            star_n = star_n + 1
            ni = star_n
            ti = star_t + 1
            continue
        return False
    while ti < len(kinds) and kinds[ti] == 2:
        ti = ti + 1
    return ti == len(kinds)


def _ail_fnmatch_case(name, pat):
    if not isinstance(pat, (str, bytes)):
        # CPython's _compile_pattern is lru_cache'd, so an unhashable pattern is refused before its length
        try:
            hash(pat)
        except TypeError:
            raise TypeError("unhashable type: %r" % type(pat).__name__)
        try:
            pat = list(pat)
        except TypeError:
            raise TypeError("object of type %r has no len()" % _ail_fnm_tname(pat))
    if isinstance(name, (bytearray, memoryview)):
        if not isinstance(pat, bytes):
            raise TypeError("cannot use a string pattern on a bytes-like object")
        name = bytes(name)
    if not isinstance(name, (str, bytes)):
        raise TypeError("expected string or bytes-like object, got %r" % _ail_fnm_tname(name))
    if isinstance(pat, bytes):
        if not isinstance(name, bytes):
            raise TypeError("cannot use a bytes pattern on a string-like object")
        return _ail_fnm_match(name.decode("latin-1"), pat.decode("latin-1"))
    if isinstance(name, bytes):
        raise TypeError("cannot use a string pattern on a bytes-like object")
    return _ail_fnm_match(name, pat)


def _ail_fnmatch_fn(name, pat):
    if not isinstance(name, (str, bytes)):
        raise TypeError("expected str, bytes or os.PathLike object, not %s" % _ail_fnm_tname(name))
    if not isinstance(pat, (str, bytes)):
        raise TypeError("expected str, bytes or os.PathLike object, not %s" % _ail_fnm_tname(pat))
    return _ail_fnmatch_case(name, pat)


def _ail_fnmatch_filter(names, pat):
    if not isinstance(pat, (str, bytes)):
        raise TypeError("expected str, bytes or os.PathLike object, not %s" % _ail_fnm_tname(pat))
    if names is None:
        raise TypeError("'NoneType' object is not iterable")
    if isinstance(names, (int, float, bool)):
        raise TypeError("%r object is not iterable" % _ail_fnm_tname(names))
    result: list = []
    for name in names:
        if _ail_fnmatch_case(name, pat):
            result.append(name)
    return result


def _ail_fnmatch_translate(pat):
    n = len(pat)
    res: list[str] = []
    i = 0
    while i < n:
        c = pat[i]
        i = i + 1
        if c == "*":
            if len(res) == 0 or res[len(res) - 1] != "*":
                res.append("*")
        elif c == "?":
            res.append(".")
        elif c == "[":
            j = i
            if j < n and pat[j] == "!":
                j = j + 1
            if j < n and pat[j] == "]":
                j = j + 1
            while j < n and pat[j] != "]":
                j = j + 1
            if j >= n:
                res.append("\\[")
            else:
                stuff = _ail_fnm_class_stuff(pat, i, j)
                i = j + 1
                if len(stuff) == 0:
                    res.append("(?!)")
                elif stuff == "!":
                    res.append(".")
                else:
                    if stuff[0] == "!":
                        stuff = "^" + stuff[1:]
                    elif stuff[0] == "^" or stuff[0] == "[":
                        stuff = "\\" + stuff
                    res.append("[" + stuff + "]")
        else:
            res.append(_ail_fnm_escape(c))
    inp = res
    res = []
    i = 0
    n = len(inp)
    while i < n and inp[i] != "*":
        res.append(inp[i])
        i = i + 1
    while i < n:
        i = i + 1
        if i == n:
            res.append(".*")
            break
        fixed: list[str] = []
        while i < n and inp[i] != "*":
            fixed.append(inp[i])
            i = i + 1
        joined = "".join(fixed)
        if i == n:
            res.append(".*")
            res.append(joined)
        else:
            res.append("(?>.*?" + joined + ")")
    return "(?s:" + "".join(res) + ")\\Z"
