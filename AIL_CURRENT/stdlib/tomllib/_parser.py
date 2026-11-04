# SPDX-License-Identifier: MIT
"""A TOML 1.0 parser that the AIL compiler builds.

This reproduces CPython 3.12's ``tomllib`` behaviour (messages, positions
and results) in the subset of Python that ``ail_chatgpt.py`` compiles.
See ``tomllib/__init__.py`` for the list of rewrites and the refusal each
one answers.
"""

import datetime

from ._re import (
    BARE_KEY_CHARS,
    DIGITS,
    HEXDIGITS,
    WS,
    WS_AND_NEWLINE,
)


class TOMLDecodeError(ValueError):
    """An error raised if a document is not valid TOML."""

    def __init__(self, msg, doc, pos):
        lineno = 1
        line_start = 0
        i = 0
        while i < pos:
            if doc[i] == "\n":
                lineno += 1
                line_start = i + 1
            i += 1
        if pos >= len(doc):
            coord_repr = "end of document"
        else:
            coord_repr = "line " + str(lineno) + ", column " + str(pos - line_start + 1)
        super().__init__(msg + " (at " + coord_repr + ")")


def load(fp, parse_float=0):
    """Parse TOML from a binary file object."""
    b = getattr(fp, "read")()
    if isinstance(b, bytes):
        return loads(b.decode(), parse_float)
    raise TypeError(
        "File must be opened in binary mode, e.g. use `open('foo.toml', 'rb')`"
    )


def loads(s, parse_float=0):
    """Parse TOML from a string."""
    src = s.replace("\r\n", "\n")
    pos = 0
    root = {}
    header = []
    declared = {}
    implicit = {}

    while True:
        pos = _skip_chars(src, pos, WS)
        if pos >= len(src):
            break
        char = src[pos]
        if char == "\n":
            pos += 1
            continue
        if char == "#":
            pos = _skip_comment(src, pos)
        elif char == "[":
            r = _table_header(src, pos, root, declared, implicit)
            pos = r[0]
            header = r[1]
            pos = _skip_chars(src, pos, WS)
        elif char == '"' or char == "'" or char in BARE_KEY_CHARS:
            table = _table_at(root, header)
            if table is None:
                raise TOMLDecodeError("Cannot overwrite a value", src, pos)
            pos = _key_value(src, pos, table, parse_float, header, implicit)
            pos = _skip_chars(src, pos, WS)
        else:
            raise TOMLDecodeError("Invalid statement", src, pos)

        pos = _skip_comment(src, pos)
        if pos < len(src) and src[pos] != "\n":
            raise TOMLDecodeError(
                "Expected newline or end of document after a statement", src, pos
            )
        pos += 1

    return root


def _table_header(src, pos, root, declared, implicit):
    is_list = 0
    if src.startswith("[[", pos):
        is_list = 1
        pos += 2
    else:
        pos += 1
    pos = _skip_chars(src, pos, WS)
    r = _parse_key(src, pos)
    pos = r[0]
    parts = r[1]

    joined = _join_key(parts)
    if joined in implicit:
        raise TOMLDecodeError("Cannot declare " + _key_repr(parts) + " twice", src, pos)
    for key in implicit.keys():
        declared[key] = 1
    implicit.clear()
    if is_list:
        if joined in declared:
            del declared[joined]
    elif joined in declared:
        raise TOMLDecodeError("Cannot declare " + _key_repr(parts) + " twice", src, pos)
    declared[joined] = 1

    if is_list:
        if not src.startswith("]]", pos):
            raise TOMLDecodeError(
                "Expected ']]' at the end of an array declaration", src, pos
            )
        _append_table(root, parts, src, pos)
        return [pos + 2, parts]

    if not src.startswith("]", pos):
        raise TOMLDecodeError("Expected ']' at the end of a table declaration", src, pos)
    _navigate(root, parts, 1, src, pos)
    return [pos + 1, parts]


def _key_value(src, pos, table, parse_float, header, implicit):
    r = _parse_key_value_pair(src, pos, parse_float)
    pos = r[0]
    parts = r[1]
    if len(parts) > 1:
        i = 1
        while i < len(parts):
            prefix = []
            j = 0
            while j < len(header):
                prefix.append(header[j])
                j += 1
            j = 0
            while j < i:
                prefix.append(parts[j])
                j += 1
            implicit[_join_key(prefix)] = 1
            i += 1
    _set_value(table, parts, r[2], src, pos, 0)
    return pos


def _parse_key_value_pair(src, pos, parse_float):
    r = _parse_key(src, pos)
    pos = r[0]
    parts = r[1]
    if pos >= len(src) or src[pos] != "=":
        raise TOMLDecodeError("Expected '=' after a key in a key/value pair", src, pos)
    pos = _skip_chars(src, pos + 1, WS)
    r = _parse_value(src, pos, parse_float)
    return [r[0], parts, r[1]]


def _set_value(table, parts, value, src, pos, inline):
    node = table
    i = 0
    while i < len(parts) - 1:
        k = parts[i]
        if k in node:
            v = node[k]
            if isinstance(v, dict):
                node = v
            elif isinstance(v, list):
                node = v[len(v) - 1]
            else:
                raise TOMLDecodeError("Cannot overwrite a value", src, pos)
        else:
            child = {}
            node[k] = child
            node = child
        i += 1
    last = parts[len(parts) - 1]
    if last in node:
        if inline:
            raise TOMLDecodeError("Duplicate inline table key " + repr(last), src, pos)
        raise TOMLDecodeError("Cannot overwrite a value", src, pos)
    node[last] = value


def _parse_key(src, pos):
    r = _parse_key_part(src, pos)
    pos = r[0]
    parts = []
    parts.append(r[1])
    pos = _skip_chars(src, pos, WS)
    while pos < len(src) and src[pos] == ".":
        pos += 1
        pos = _skip_chars(src, pos, WS)
        r = _parse_key_part(src, pos)
        pos = r[0]
        parts.append(r[1])
        pos = _skip_chars(src, pos, WS)
    return [pos, parts]


def _parse_key_part(src, pos):
    if pos >= len(src):
        raise TOMLDecodeError("Invalid initial character for a key part", src, pos)
    char = src[pos]
    if char in BARE_KEY_CHARS:
        start = pos
        while pos < len(src) and src[pos] in BARE_KEY_CHARS:
            pos += 1
        return [pos, src[start:pos]]
    if char == "'":
        return _parse_literal_str(src, pos)
    if char == '"':
        return _parse_basic_str(src, pos + 1, 0)
    raise TOMLDecodeError("Invalid initial character for a key part", src, pos)


def _parse_array(src, pos, parse_float):
    pos += 1
    values = []
    pos = _skip_comments_and_array_ws(src, pos)
    if pos < len(src) and src[pos] == "]":
        return [pos + 1, values]
    while True:
        r = _parse_value(src, pos, parse_float)
        pos = r[0]
        values.append(r[1])
        pos = _skip_comments_and_array_ws(src, pos)
        if pos < len(src) and src[pos] == "]":
            return [pos + 1, values]
        if pos >= len(src) or src[pos] != ",":
            raise TOMLDecodeError("Unclosed array", src, pos)
        pos += 1
        pos = _skip_comments_and_array_ws(src, pos)
        if pos < len(src) and src[pos] == "]":
            return [pos + 1, values]


def _parse_inline_table(src, pos, parse_float):
    pos += 1
    table = {}
    pos = _skip_chars(src, pos, WS)
    if pos < len(src) and src[pos] == "}":
        return [pos + 1, table]
    while True:
        r = _parse_key_value_pair(src, pos, parse_float)
        pos = r[0]
        _set_value(table, r[1], r[2], src, pos, 1)
        pos = _skip_chars(src, pos, WS)
        if pos < len(src) and src[pos] == "}":
            return [pos + 1, table]
        if pos >= len(src) or src[pos] != ",":
            raise TOMLDecodeError("Unclosed inline table", src, pos)
        pos += 1
        pos = _skip_chars(src, pos, WS)


def _parse_basic_str(src, pos, multiline):
    result = ""
    start_pos = pos
    while True:
        if pos >= len(src):
            raise TOMLDecodeError("Unterminated string", src, pos)
        char = src[pos]
        if char == '"':
            if not multiline:
                return [pos + 1, result + src[start_pos:pos]]
            if src.startswith('"""', pos):
                return [pos + 3, result + src[start_pos:pos]]
            pos += 1
            continue
        if char == "\\":
            result += src[start_pos:pos]
            r = _parse_basic_str_escape(src, pos, multiline)
            pos = r[0]
            result += r[1]
            start_pos = pos
            continue
        if multiline:
            illegal = (
                ord(char) < 32 and char != "\t" and char != "\n"
            ) or ord(char) == 127
        else:
            illegal = (ord(char) < 32 and char != "\t") or ord(char) == 127
        if illegal:
            raise TOMLDecodeError("Illegal character " + repr(char), src, pos)
        pos += 1


def _parse_basic_str_escape(src, pos, multiline):
    escape_id = src[pos : pos + 2]
    pos += 2
    if multiline and (
        escape_id == "\\ " or escape_id == "\\\t" or escape_id == "\\\n"
    ):
        if escape_id != "\\\n":
            pos = _skip_chars(src, pos, WS)
            if pos >= len(src):
                return [pos, ""]
            if src[pos] != "\n":
                raise TOMLDecodeError("Unescaped '\\' in a string", src, pos)
            pos += 1
        pos = _skip_chars(src, pos, WS_AND_NEWLINE)
        return [pos, ""]
    if escape_id == "\\u":
        return _parse_hex_char(src, pos, 4)
    if escape_id == "\\U":
        return _parse_hex_char(src, pos, 8)
    if escape_id == "\\b":
        return [pos, chr(8)]
    if escape_id == "\\t":
        return [pos, "\t"]
    if escape_id == "\\n":
        return [pos, "\n"]
    if escape_id == "\\f":
        return [pos, chr(12)]
    if escape_id == "\\r":
        return [pos, "\r"]
    if escape_id == '\\"':
        return [pos, '"']
    if escape_id == "\\\\":
        return [pos, "\\"]
    raise TOMLDecodeError("Unescaped '\\' in a string", src, pos)


def _parse_hex_char(src, pos, hex_len):
    hex_str = src[pos : pos + hex_len]
    if len(hex_str) != hex_len:
        raise TOMLDecodeError("Invalid hex value", src, pos)
    i = 0
    while i < hex_len:
        if hex_str[i] not in HEXDIGITS:
            raise TOMLDecodeError("Invalid hex value", src, pos)
        i += 1
    pos += hex_len
    hex_int = int(hex_str, 16)
    if not (
        (0 <= hex_int and hex_int <= 55295) or (57344 <= hex_int and hex_int <= 1114111)
    ):
        raise TOMLDecodeError("Escaped character is not a Unicode scalar value", src, pos)
    return [pos, chr(hex_int)]


def _parse_literal_str(src, pos):
    pos += 1
    start_pos = pos
    while True:
        if pos >= len(src):
            raise TOMLDecodeError('Expected "\'"', src, pos)
        char = src[pos]
        if char == "'":
            return [pos + 1, src[start_pos:pos]]
        if (ord(char) < 32 and char != "\t") or ord(char) == 127:
            raise TOMLDecodeError("Found invalid character " + repr(char), src, pos)
        pos += 1


def _parse_multiline_str(src, pos, literal):
    pos += 3
    if pos < len(src) and src[pos] == "\n":
        pos += 1
    if literal:
        delim = "'"
        start_pos = pos
        end_pos = -1
        while True:
            if pos >= len(src):
                raise TOMLDecodeError('Expected "\'\'\'"', src, pos)
            char = src[pos]
            if src.startswith("'''", pos):
                end_pos = pos
                break
            if (ord(char) < 32 and char != "\t" and char != "\n") or ord(char) == 127:
                raise TOMLDecodeError("Found invalid character " + repr(char), src, pos)
            pos += 1
        result = src[start_pos:end_pos]
        pos = end_pos + 3
    else:
        delim = '"'
        r = _parse_basic_str(src, pos, 1)
        pos = r[0]
        result = r[1]

    if not src.startswith(delim, pos):
        return [pos, result]
    pos += 1
    if not src.startswith(delim, pos):
        return [pos, result + delim]
    pos += 1
    return [pos, result + delim + delim]


def _parse_value(src, pos, parse_float):
    if pos >= len(src):
        raise TOMLDecodeError("Invalid value", src, pos)
    char = src[pos]
    if char == '"':
        if src.startswith('"""', pos):
            return _parse_multiline_str(src, pos, 0)
        return _parse_basic_str(src, pos + 1, 0)
    if char == "'":
        if src.startswith("'''", pos):
            return _parse_multiline_str(src, pos, 1)
        return _parse_literal_str(src, pos)
    if char == "t":
        if src.startswith("true", pos):
            value = True
            return [pos + 4, value]
    if char == "f":
        if src.startswith("false", pos):
            value = False
            return [pos + 5, value]
    if char == "[":
        return _parse_array(src, pos, parse_float)
    if char == "{":
        return _parse_inline_table(src, pos, parse_float)

    r = _scan_datetime(src, pos)
    if r[0]:
        return [r[1], r[2]]
    r = _scan_number(src, pos, parse_float)
    if r[0]:
        return [r[1], r[2]]

    if src.startswith("inf", pos):
        return [pos + 3, _to_float("inf", parse_float)]
    if src.startswith("nan", pos):
        return [pos + 3, _to_float("nan", parse_float)]
    if src.startswith("-inf", pos):
        return [pos + 4, _to_float("-inf", parse_float)]
    if src.startswith("+inf", pos):
        return [pos + 4, _to_float("+inf", parse_float)]
    if src.startswith("-nan", pos):
        return [pos + 4, _to_float("-nan", parse_float)]
    if src.startswith("+nan", pos):
        return [pos + 4, _to_float("+nan", parse_float)]

    raise TOMLDecodeError("Invalid value", src, pos)


def _scan_datetime(src, pos):
    date_end = _scan_date(src, pos)
    if date_end >= 0:
        year = int(src[pos : pos + 4])
        month = int(src[pos + 5 : pos + 7])
        day = int(src[pos + 8 : pos + 10])
        if date_end < len(src):
            char = src[date_end]
            if char == "T" or char == "t" or char == " ":
                r = _scan_time(src, date_end + 1)
                if r[0] > 0:
                    off = _scan_offset(src, r[0])
                    try:
                        value = datetime.datetime(
                            year, month, day, r[1], r[2], r[3], r[4]
                        )
                    except ValueError:
                        raise TOMLDecodeError("Invalid date or datetime", src, pos)
                    if off[2] == 1:
                        tz = datetime.timezone(datetime.timedelta(minutes=off[1]))
                        value = value.replace(tzinfo=tz)
                    return [1, off[0], value]
        try:
            value = datetime.date(year, month, day)
        except ValueError:
            raise TOMLDecodeError("Invalid date or datetime", src, pos)
        return [1, date_end, value]

    r = _scan_time(src, pos)
    if r[0] > 0:
        return [1, r[0], src[pos : r[0]]]

    return [0, pos, 0]


def _scan_date(src, pos):
    if pos + 10 > len(src):
        return -1
    i = 0
    while i < 4:
        if src[pos + i] not in DIGITS:
            return -1
        i += 1
    if src[pos + 4] != "-":
        return -1
    month = _two_digits(src, pos + 5)
    if month < 1 or month > 12:
        return -1
    if src[pos + 7] != "-":
        return -1
    day = _two_digits(src, pos + 8)
    if day < 1 or day > 31:
        return -1
    return pos + 10


def _scan_time(src, pos):
    hour = _two_digits(src, pos)
    if hour < 0 or pos + 2 >= len(src) or src[pos + 2] != ":":
        return [0, 0, 0, 0, 0]
    minute = _two_digits(src, pos + 3)
    if minute < 0 or pos + 5 >= len(src) or src[pos + 5] != ":":
        return [0, 0, 0, 0, 0]
    second = _two_digits(src, pos + 6)
    if second < 0:
        return [0, 0, 0, 0, 0]
    if hour > 23 or minute > 59 or second > 59:
        return [0, 0, 0, 0, 0]
    end = pos + 8
    micro = 0
    if end < len(src) and src[end] == ".":
        end += 1
        digits = 0
        while end < len(src) and src[end] in DIGITS:
            if digits < 6:
                micro = micro * 10 + (ord(src[end]) - 48)
            digits += 1
            end += 1
        if digits == 0:
            return [0, 0, 0, 0, 0]
        while digits < 6:
            micro = micro * 10
            digits += 1
    return [end, hour, minute, second, micro]


def _scan_offset(src, pos):
    if pos < len(src) and (src[pos] == "Z" or src[pos] == "z"):
        return [pos + 1, 0, 1]
    if pos < len(src) and (src[pos] == "+" or src[pos] == "-"):
        if pos + 6 > len(src):
            return [pos, 0, 0]
        hour = _two_digits(src, pos + 1)
        if hour < 0 or hour > 23 or src[pos + 3] != ":":
            return [pos, 0, 0]
        minute = _two_digits(src, pos + 4)
        if minute < 0 or minute > 59:
            return [pos, 0, 0]
        total = hour * 60 + minute
        if src[pos] == "-":
            total = -total
        return [pos + 6, total, 1]
    return [pos, 0, 0]


def _two_digits(src, pos):
    if pos + 2 > len(src):
        return -1
    if src[pos] not in DIGITS or src[pos + 1] not in DIGITS:
        return -1
    return int(src[pos : pos + 2])


def _scan_number(src, pos, parse_float):
    if pos + 1 < len(src) and src[pos] == "0":
        char = src[pos + 1]
        if char == "x" or char == "b" or char == "o":
            allowed = HEXDIGITS
            base = 16
            if char == "b":
                allowed = "01"
                base = 2
            elif char == "o":
                allowed = "01234567"
                base = 8
            start = pos + 2
            end = _scan_digit_run(src, start, allowed)
            if end == start:
                return [0, pos, 0]
            return [1, end, int(src[start:end], base)]

    i = pos
    sign = ""
    if i < len(src) and (src[i] == "+" or src[i] == "-"):
        sign = src[i]
        i += 1
    if i >= len(src):
        return [0, pos, 0]
    start = i
    if src[i] == "0":
        i += 1
    elif src[i] in "123456789":
        i = _scan_digit_run(src, i, DIGITS)
    else:
        return [0, pos, 0]

    is_float = 0
    if i < len(src) and src[i] == ".":
        j = i + 1
        if j < len(src) and src[j] in DIGITS:
            i = _scan_digit_run(src, j, DIGITS)
            is_float = 1
    if i < len(src) and (src[i] == "e" or src[i] == "E"):
        j = i + 1
        if j < len(src) and (src[j] == "+" or src[j] == "-"):
            j += 1
        if j < len(src) and src[j] in DIGITS:
            i = _scan_digit_run(src, j, DIGITS)
            is_float = 1

    text = sign + src[start:i]
    if is_float:
        return [1, i, _to_float(text, parse_float)]
    return [1, i, int(text, 10)]


def _scan_digit_run(src, pos, allowed):
    first = 1
    while pos < len(src):
        char = src[pos]
        if char in allowed:
            first = 0
            pos += 1
        elif (
            char == "_"
            and first == 0
            and pos + 1 < len(src)
            and src[pos + 1] in allowed
        ):
            pos += 1
        else:
            break
    return pos


def _to_float(text, parse_float):
    if parse_float == 0:
        return float(text)
    value = parse_float(text)
    if isinstance(value, dict) or isinstance(value, list):
        raise ValueError("parse_float must not return dicts or lists")
    return value


def _skip_chars(src, pos, chars):
    while pos < len(src) and src[pos] in chars:
        pos += 1
    return pos


def _skip_comment(src, pos):
    if pos >= len(src) or src[pos] != "#":
        return pos
    pos += 1
    while pos < len(src):
        char = src[pos]
        if char == "\n":
            return pos
        if (ord(char) < 32 and char != "\t") or ord(char) == 127:
            raise TOMLDecodeError("Found invalid character " + repr(char), src, pos)
        pos += 1
    return pos


def _skip_comments_and_array_ws(src, pos):
    while True:
        before = pos
        pos = _skip_chars(src, pos, WS_AND_NEWLINE)
        pos = _skip_comment(src, pos)
        if pos == before:
            return pos


def _navigate(root, parts, create, src, pos):
    node = root
    i = 0
    while i < len(parts):
        key = parts[i]
        if key in node:
            value = node[key]
            if isinstance(value, list):
                if len(value) == 0:
                    raise TOMLDecodeError("Cannot overwrite a value", src, pos)
                node = value[len(value) - 1]
            elif isinstance(value, dict):
                node = value
            else:
                raise TOMLDecodeError("Cannot overwrite a value", src, pos)
        elif create:
            child = {}
            node[key] = child
            node = child
        else:
            raise TOMLDecodeError("Cannot overwrite a value", src, pos)
        i += 1
    return node


def _append_table(root, parts, src, pos):
    if len(parts) == 1:
        parent = root
    else:
        head = []
        i = 0
        while i < len(parts) - 1:
            head.append(parts[i])
            i += 1
        parent = _navigate(root, head, 1, src, pos)
    last = parts[len(parts) - 1]
    if last in parent:
        current = parent[last]
        if isinstance(current, list):
            current.append({})
        else:
            raise TOMLDecodeError("Cannot overwrite a value", src, pos)
    else:
        parent[last] = [{}]


def _table_at(root, parts):
    node = root
    i = 0
    while i < len(parts):
        key = parts[i]
        if not (key in node):
            return None
        value = node[key]
        if isinstance(value, list):
            if len(value) == 0:
                return None
            node = value[len(value) - 1]
        elif isinstance(value, dict):
            node = value
        else:
            return None
        i += 1
    return node


def _join_key(parts):
    out = ""
    i = 0
    while i < len(parts):
        if i:
            out += "\u0000"
        out += parts[i]
        i += 1
    return out


def _key_repr(parts):
    out = "("
    i = 0
    while i < len(parts):
        if i:
            out += ", "
        out += repr(parts[i])
        i += 1
    if len(parts) == 1:
        out += ","
    return out + ")"
