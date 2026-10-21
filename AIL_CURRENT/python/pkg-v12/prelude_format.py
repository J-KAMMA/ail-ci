# -*- coding: utf-8 -*-
# prelude_format.py -- str.format / str.format_map as Python source (fmtlib.py rewrites `S.format(a, k=v)` to
# `_ail_str_format(S, [a], {"k": v})`). A port of CPython's Objects/stringlib/unicode_format.h: the same parse of a
# replacement field (`{name.attr[key]!r:spec}`), the same automatic / manual numbering rules, a nested replacement field
# in the spec (two levels), and the same error texts. The value is formatted by the builtin format().


def _ail_fmt_int(s: str) -> int:
    # get_integer: the digits of s as an int, -1 when s is empty or not all digits
    if len(s) == 0:
        return -1
    for ch in s:
        if ch < "0" or ch > "9":
            return -1
    return int(s)


def _ail_fmt_ascii(s: str) -> str:
    # ascii(x): repr(x) with every character above 127 written as an escape
    out = []
    for ch in s:
        o = ord(ch)
        if o < 128:
            out.append(ch)
        elif o < 256:
            out.append("\\x" + "%02x" % o)
        elif o < 65536:
            out.append("\\u" + "%04x" % o)
        else:
            out.append("\\U" + "%08x" % o)
    return "".join(out)


def _ail_fmt_tname(x) -> str:
    if x is None:
        return "NoneType"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "list"
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    return "object"


def _ail_fmt_get(field: str, args, kwargs, st, depth):
    # field is the text between the braces of one replacement field (parse_field + the rest of build_string's work)
    n = len(field)
    i = 0
    c = ""
    while i < n:
        c = field[i]
        i += 1
        if c == "{":
            raise ValueError("unexpected '{' in field name")
        if c == "[":
            while i < n and field[i] != "]":
                i += 1
            c = ""
            continue
        if c == "}" or c == ":" or c == "!":
            break
        c = ""
    name_end = n
    conv = ""
    spec = ""
    if c == "!" or c == ":":
        name_end = i - 1
        pos = i
        if c == "!":
            if pos >= n:
                raise ValueError("end of string while looking for conversion specifier")
            conv = field[pos]
            pos += 1
            if pos < n:
                d = field[pos]
                pos += 1
                if d != ":":
                    raise ValueError("expected ':' after conversion specifier")
        spec = field[pos:]
    name = field[:name_end]
    # field_name_split: the first part up to a '.' or '['
    k = 0
    m = len(name)
    while k < m:
        ch = name[k]
        if ch == "{":
            raise ValueError("unexpected '{' in field name")
        if ch == "[" or ch == ".":
            break
        k += 1
    first = name[:k]
    rest = name[k:]
    idx = _ail_fmt_int(first)
    numeric = len(first) == 0 or idx != -1
    if numeric:
        if st[1] == 0:
            if len(first) == 0:
                st[1] = 1
            else:
                st[1] = 2
        if st[1] == 2 and len(first) == 0:
            raise ValueError("cannot switch from manual field specification to automatic field numbering")
        if st[1] == 1 and len(first) != 0:
            raise ValueError("cannot switch from automatic field numbering to manual field specification")
        if len(first) == 0:
            idx = st[0]
            st[0] = st[0] + 1
    if numeric:
        if idx >= len(args):
            raise IndexError("Replacement index " + str(idx) + " out of range for positional args tuple")
        val = args[idx]
    else:
        if first not in kwargs:
            raise KeyError(first)
        val = kwargs[first]
    p = 0
    r = len(rest)
    while p < r:
        ch = rest[p]
        p += 1
        if ch == ".":
            q = p
            while q < r and rest[q] != "." and rest[q] != "[":
                q += 1
            attr = rest[p:q]
            if len(attr) == 0:
                raise ValueError("Empty attribute in format string")
            try:
                val = getattr(val, attr)
            except NotImplementedError:
                raise AttributeError("'" + _ail_fmt_tname(val) + "' object has no attribute '" + attr + "'")
            p = q
        elif ch == "[":
            q = p
            while q < r and rest[q] != "]":
                q += 1
            if q >= r:
                raise ValueError("Missing ']' in format string")
            key = rest[p:q]
            if len(key) == 0:
                raise ValueError("Empty attribute in format string")
            ki = _ail_fmt_int(key)
            if ki != -1:
                val = val[ki]
            else:
                val = val[key]
            p = q + 1
        else:
            raise ValueError("Only '.' or '[' may follow ']' in format field specifier")
    if conv == "r":
        val = repr(val)
    elif conv == "s":
        val = str(val)
    elif conv == "a":
        val = _ail_fmt_ascii(repr(val))
    elif conv != "":
        raise ValueError("Unknown conversion specifier " + conv)
    if "{" in spec:
        spec = _ail_fmt_build(spec, args, kwargs, st, depth - 1)
    return format(val, spec)


def _ail_fmt_build(fmt: str, args, kwargs, st, depth: int) -> str:
    if depth <= 0:
        raise ValueError("Max string recursion exceeded")
    out = []
    n = len(fmt)
    i = 0
    while i < n:
        c = fmt[i]
        if c != "{" and c != "}":
            j = i + 1
            while j < n and fmt[j] != "{" and fmt[j] != "}":
                j += 1
            out.append(fmt[i:j])
            i = j
            continue
        i += 1
        at_end = i >= n
        if c == "}" and (at_end or fmt[i] != "}"):
            raise ValueError("Single '}' encountered in format string")
        if at_end and c == "{":
            raise ValueError("Single '{' encountered in format string")
        if fmt[i] == c:
            out.append(c)
            i += 1
            continue
        # a replacement field: its end is found as parse_field does (nested braces of the spec counted)
        j = i
        level = 0
        in_spec = False
        while j < n:
            d = fmt[j]
            j += 1
            if not in_spec:
                if d == "[":
                    while j < n and fmt[j] != "]":
                        j += 1
                    continue
                if d == "}":
                    level = -1
                    break
                if d == ":" or d == "!":
                    in_spec = True
                    level = 1
                    if d == "!":
                        # the conversion character, then ':' or '}'
                        if j >= n:
                            raise ValueError("end of string while looking for conversion specifier")
                        j += 1
                        if j < n:
                            e = fmt[j]
                            j += 1
                            if e == "}":
                                level = 0
                                break
                            if e != ":":
                                raise ValueError("expected ':' after conversion specifier")
                    continue
                if d == "{":
                    raise ValueError("unexpected '{' in field name")
            else:
                if d == "{":
                    level += 1
                elif d == "}":
                    level -= 1
                    if level == 0:
                        break
        if in_spec:
            if level != 0:
                raise ValueError("unmatched '{' in format spec")
            field = fmt[i:j - 1]
        else:
            if level != -1:
                raise ValueError("expected '}' before end of string")
            field = fmt[i:j - 1]
        out.append(_ail_fmt_get(field, args, kwargs, st, depth))
        i = j
    return "".join(out)


def _ail_str_format(fmt: str, args, kwargs) -> str:
    return _ail_fmt_build(fmt, args, kwargs, [0, 0], 2)


def _ail_fmt_merge(base, *more):
    # f(**a, k=v, **b): the keywords of a call that has several ** unpackings
    out = {}
    for k in base:
        out[k] = base[k]
    for extra in more:
        for k in extra:
            if k in out:
                raise TypeError("format() got multiple values for keyword argument " + repr(k))
            out[k] = extra[k]
    return out
