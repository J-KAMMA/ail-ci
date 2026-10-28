# prelude_struct.py -- `struct` packing of integers, bytes, chars and bools as Python source (structlib.py injects it).
# Supported formats: x c b B ? h H i I l L q Q n N P s, with the byte orders @ = < > !, native alignment, zero
# repeat counts, str/bytes formats and bytearray values or buffers. Native ('@', the default) sizes and alignment
# are those of the 64-bit little-endian target. The float formats f / d / e and the Pascal string p are refused at
# compile time for a constant format and by name at run time for a computed one.


class _AilStructError(Exception):
    pass


class _AilStructIndexProbe:
    def __index__(self) -> int:
        return 0


def _ail_struct_order(prefix: str) -> str:
    if prefix == ">" or prefix == "!":
        return "big"
    return "little"


def _ail_struct_unit(code: str, prefix: str) -> int:
    if code == "x" or code == "c" or code == "?" or code == "s" or code == "b" or code == "B":
        return 1
    if code == "h" or code == "H":
        return 2
    if code == "i" or code == "I":
        return 4
    if code == "l" or code == "L":
        if prefix == "@":
            return 8
        return 4
    if code == "q" or code == "Q" or code == "n" or code == "N" or code == "P":
        return 8
    raise _AilStructError("bad char in struct format")


def _ail_struct_signed(code: str) -> bool:
    if code == "b" or code == "h" or code == "i" or code == "l" or code == "q" or code == "n":
        return True
    return False


def _ail_struct_count(token: str) -> int:
    n = 0
    i = 0
    while i < len(token):
        c = token[i]
        if "0" <= c and c <= "9":
            n = n * 10 + ord(c) - 48
            i = i + 1
        else:
            return n
    return n


def _ail_struct_code(token: str) -> str:
    i = 0
    while i < len(token) and "0" <= token[i] and token[i] <= "9":
        i = i + 1
    return token[i]


def _ail_struct_format(fmt):
    if isinstance(fmt, str):
        return fmt
    if isinstance(fmt, bytes):
        text = ""
        i = 0
        while i < len(fmt):
            text = text + chr(fmt[i])
            i = i + 1
        return text
    raise TypeError("Struct() argument 1 must be a str or bytes object, not " + type(fmt).__name__)


def _ail_struct_tokens(fmt: str) -> list[str]:
    fmt = _ail_struct_format(fmt)
    tokens = []
    prefix = "@"
    i = 0
    if len(fmt) > 0:
        first = fmt[0]
        if first == "@" or first == "=" or first == "<" or first == ">" or first == "!":
            prefix = first
            i = 1
    tokens.append(prefix)
    while i < len(fmt):
        c = fmt[i]
        if c == " " or c == "\t" or c == "\n" or c == "\r" or c == "\v" or c == "\f":
            i = i + 1
            continue
        count = 0
        seen = False
        while i < len(fmt):
            c = fmt[i]
            if "0" <= c and c <= "9":
                count = count * 10 + ord(c) - 48
                i = i + 1
                seen = True
            else:
                break
        if not seen:
            count = 1
        if i >= len(fmt):
            raise _AilStructError("repeat count given without format specifier")
        c = fmt[i]
        i = i + 1
        if c == "f" or c == "d" or c == "e":
            raise _AilStructError("the '" + c + "' format (floating point) is not built")
        if c == "p":
            raise _AilStructError("the 'p' format (Pascal string) is not built")
        if c != "x" and c != "c" and c != "b" and c != "B" and c != "?" and c != "h" and c != "H" \
                and c != "i" and c != "I" and c != "l" and c != "L" and c != "q" and c != "Q" \
                and c != "n" and c != "N" and c != "P" and c != "s":
            raise _AilStructError("bad char in struct format")
        if prefix != "@" and (c == "n" or c == "N" or c == "P"):
            raise _AilStructError("bad char in struct format")
        tokens.append(str(count) + c)
    return tokens


def _ail_struct_align(offset: int, code: str, prefix: str) -> int:
    if prefix != "@":
        return offset
    if code == "x" or code == "c" or code == "?" or code == "s":
        return offset
    a = _ail_struct_unit(code, prefix)
    r = offset % a
    if r != 0:
        return offset + a - r
    return offset


def _ail_struct_total(tokens: list[str]) -> int:
    prefix = tokens[0]
    offset = 0
    i = 1
    while i < len(tokens):
        token = tokens[i]
        n = _ail_struct_count(token)
        code = _ail_struct_code(token)
        if code == "s" or code == "x":
            offset = offset + n
        else:
            offset = _ail_struct_align(offset, code, prefix)
            offset = offset + n * _ail_struct_unit(code, prefix)
        i = i + 1
    return offset


def _ail_struct_expected(tokens: list[str]) -> int:
    total = 0
    i = 1
    while i < len(tokens):
        token = tokens[i]
        n = _ail_struct_count(token)
        code = _ail_struct_code(token)
        if code == "s":
            total = total + 1
        elif code != "x":
            total = total + n
        i = i + 1
    return total


def _ail_struct_limits(code: str, size: int, signed: bool) -> list[int]:
    m = 1
    i = 0
    while i < size * 8:
        m = m * 2
        i = i + 1
    if signed:
        return [-(m // 2), m // 2 - 1]
    return [0, m - 1]


def _ail_struct_value(value, code: str, size: int, signed: bool) -> int:
    if isinstance(value, bool):
        v = 0
        if value:
            v = 1
    elif isinstance(value, int):
        v = value
    else:
        if isinstance(value, float) or isinstance(value, str) or isinstance(value, bytes) \
                or isinstance(value, bytearray) or isinstance(value, list) or isinstance(value, tuple) \
                or isinstance(value, dict) or isinstance(value, set) or value is None:
            raise _AilStructError("required argument is not an integer")
        try:
            v = getattr(value, "__index__")()
        except AttributeError:
            raise _AilStructError("required argument is not an integer")
        if isinstance(v, bool):
            if v:
                v = 1
            else:
                v = 0
        elif not isinstance(v, int):
            raise TypeError("__index__ returned non-int (type " + type(v).__name__ + ")")
    if code == "P":
        if v < 0 - 9223372036854775807 - 1 or v > _ail_struct_limits(code, size, False)[1]:
            raise _AilStructError("int too large to convert")
        return v
    limits = _ail_struct_limits(code, size, signed)
    if v < limits[0] or v > limits[1]:
        raise _AilStructError("'" + code + "' format requires " + str(limits[0]) + " <= number <= " + str(limits[1]))
    return v


def _ail_struct_extend(out: list[int], data: bytes) -> None:
    i = 0
    while i < len(data):
        out.append(data[i])
        i = i + 1


def _ail_struct_pad(out: list[int], stop: int) -> None:
    while len(out) < stop:
        out.append(0)


def _ail_struct_to_bytes(value: int, size: int, order: str) -> list[int]:
    out = []
    v = value
    if v < 0:
        m = 1
        i = 0
        while i < size * 8:
            m = m * 2
            i = i + 1
        v = v + m
    i = 0
    while i < size:
        out.append(v % 256)
        v = v // 256
        i = i + 1
    if order == "big":
        out.reverse()
    return out


def _ail_struct_from_bytes(data: bytes, start: int, size: int, order: str, signed: bool) -> int:
    v = 0
    if order == "little":
        i = size - 1
        while i >= 0:
            v = v * 256 + data[start + i]
            i = i - 1
    else:
        i = 0
        while i < size:
            v = v * 256 + data[start + i]
            i = i + 1
    if signed:
        m = 1
        i = 0
        while i < size * 8:
            m = m * 2
            i = i + 1
        if v >= m // 2:
            v = v - m
    return v


def _ail_struct_pack_list(fmt: str, values: list) -> bytes:
    tokens = _ail_struct_tokens(fmt)
    expected = _ail_struct_expected(tokens)
    if len(values) != expected:
        raise _AilStructError("pack expected " + str(expected) + " items for packing (got " + str(len(values)) + ")")
    prefix = tokens[0]
    order = _ail_struct_order(prefix)
    out = []
    k = 0
    i = 1
    while i < len(tokens):
        token = tokens[i]
        n = _ail_struct_count(token)
        code = _ail_struct_code(token)
        if code == "x":
            _ail_struct_pad(out, len(out) + n)
        elif code == "s":
            value = values[k]
            k = k + 1
            if not (isinstance(value, bytes) or isinstance(value, bytearray)):
                raise _AilStructError("argument for 's' must be a bytes object")
            part = value[:n]
            _ail_struct_extend(out, part)
            _ail_struct_pad(out, len(out) - len(part) + n)
        else:
            _ail_struct_pad(out, _ail_struct_align(len(out), code, prefix))
            if code == "c":
                j = 0
                while j < n:
                    value = values[k]
                    k = k + 1
                    if not isinstance(value, bytes) or len(value) != 1:
                        raise _AilStructError("char format requires a bytes object of length 1")
                    out.append(value[0])
                    j = j + 1
            elif code == "?":
                j = 0
                while j < n:
                    value = values[k]
                    k = k + 1
                    if value:
                        out.append(1)
                    else:
                        out.append(0)
                    j = j + 1
            else:
                size = _ail_struct_unit(code, prefix)
                signed = _ail_struct_signed(code)
                j = 0
                while j < n:
                    v = _ail_struct_value(values[k], code, size, signed)
                    k = k + 1
                    _ail_struct_extend(out, bytes(_ail_struct_to_bytes(v, size, order)))
                    j = j + 1
        i = i + 1
    return bytes(out)


def _ail_struct_calcsize(fmt: str) -> int:
    return _ail_struct_total(_ail_struct_tokens(fmt))


def _ail_struct_buffer(data):
    if isinstance(data, bytes) or isinstance(data, bytearray):
        return data
    raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")


def _ail_struct_read(tokens: list[str], data: bytes, start: int) -> list:
    prefix = tokens[0]
    order = _ail_struct_order(prefix)
    out = []
    offset = start
    i = 1
    while i < len(tokens):
        token = tokens[i]
        n = _ail_struct_count(token)
        code = _ail_struct_code(token)
        if code == "x":
            offset = offset + n
        elif code == "s":
            out.append(bytes(data[offset:offset + n]))
            offset = offset + n
        else:
            offset = _ail_struct_align(offset - start, code, prefix) + start
            if code == "c":
                j = 0
                while j < n:
                    out.append(bytes(data[offset:offset + 1]))
                    offset = offset + 1
                    j = j + 1
            elif code == "?":
                j = 0
                while j < n:
                    out.append(data[offset] != 0)
                    offset = offset + 1
                    j = j + 1
            else:
                size = _ail_struct_unit(code, prefix)
                signed = _ail_struct_signed(code)
                j = 0
                while j < n:
                    out.append(_ail_struct_from_bytes(data, offset, size, order, signed))
                    offset = offset + size
                    j = j + 1
        i = i + 1
    return out


def _ail_struct_unpack_list(fmt: str, data: bytes) -> list:
    tokens = _ail_struct_tokens(fmt)
    data = _ail_struct_buffer(data)
    total = _ail_struct_total(tokens)
    if len(data) != total:
        raise _AilStructError("unpack requires a buffer of " + str(total) + " bytes")
    return _ail_struct_read(tokens, data, 0)


def _ail_struct_unpack_from_list(fmt: str, data: bytes, offset: int = 0) -> list:
    tokens = _ail_struct_tokens(fmt)
    data = _ail_struct_buffer(data)
    total = _ail_struct_total(tokens)
    if offset < 0:
        if len(data) >= total:
            if offset < -len(data):
                raise _AilStructError("offset " + str(offset) + " out of range for " + str(len(data))
                                      + "-byte buffer")
        elif offset <= -total:
            raise _AilStructError("offset " + str(offset) + " out of range for " + str(len(data))
                                  + "-byte buffer")
        start = len(data) + offset
        if start + total > len(data):
            raise _AilStructError("not enough data to unpack " + str(total) + " bytes at offset " + str(offset))
        return _ail_struct_read(tokens, data, start)
    if len(data) < offset + total:
        raise _AilStructError("unpack_from requires a buffer of at least " + str(offset + total)
                              + " bytes for unpacking " + str(total) + " bytes at offset " + str(offset)
                              + " (actual buffer size is " + str(len(data)) + ")")
    return _ail_struct_read(tokens, data, offset)
