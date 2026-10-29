# prelude_struct.py -- struct.pack / struct.unpack / struct.error for the integer formats, as Python source.
class _AilStructError(Exception):
    pass


def _ail_struct_bounds(ch: str) -> list[int]:
    if ch == "b":
        return [1, -128, 127]
    if ch == "B":
        return [1, 0, 255]
    if ch == "h":
        return [2, -32768, 32767]
    if ch == "H":
        return [2, 0, 65535]
    if ch == "i":
        return [4, -2147483648, 2147483647]
    if ch == "I":
        return [4, 0, 4294967295]
    if ch == "l":
        return [4, -2147483648, 2147483647]
    if ch == "L":
        return [4, 0, 4294967295]
    if ch == "q":
        return [8, -9223372036854775808, 9223372036854775807]
    if ch == "Q":
        return [8, 0, -1]
    if ch == "?":
        return [1, 0, 1]
    return [0, 0, 0]


def _ail_struct_range(ch: str, info: list[int]) -> None:
    if ch == "Q":
        raise _AilStructError("'Q' format requires 0 <= number <= 18446744073709551615")
    raise _AilStructError("'" + ch + "' format requires " + str(info[1]) + " <= number <= " + str(info[2]))


def _ail_struct_skip_space(fmt: str, i: int) -> int:
    while i < len(fmt):
        c = fmt[i]
        if c != " " and c != "\t" and c != "\n" and c != "\r":
            break
        i = i + 1
    return i


def _ail_struct_count(fmt: str, i: int) -> list[int]:
    count = 0
    have = False
    while i < len(fmt):
        c = fmt[i]
        if c < "0" or c > "9":
            break
        count = count * 10 + (ord(c) - 48)
        have = True
        i = i + 1
    if not have:
        return [-1, i]
    return [count, i]


def _ail_struct_order(fmt: str) -> str:
    if len(fmt) == 0:
        raise _AilStructError("bad char in struct format")
    c = fmt[0]
    if c == "<":
        return "little"
    if c == ">" or c == "!":
        return "big"
    raise _AilStructError("bad char in struct format")


def _ail_struct_size(fmt: str) -> int:
    order = _ail_struct_order(fmt)
    i = 1
    total = 0
    while i < len(fmt):
        i = _ail_struct_skip_space(fmt, i)
        if i >= len(fmt):
            break
        got = _ail_struct_count(fmt, i)
        count = got[0]
        if count < 0:
            count = 1
        i = got[1]
        if i >= len(fmt):
            raise _AilStructError("repeat count given without format specifier")
        ch = fmt[i]
        i = i + 1
        if ch == "x":
            total = total + count
            continue
        info = _ail_struct_bounds(ch)
        if info[0] == 0:
            raise _AilStructError("bad char in struct format")
        total = total + info[0] * count
    return total


def _ail_struct_pack(fmt: str, values: list[int]) -> bytes:
    order = _ail_struct_order(fmt)
    i = 1
    vi = 0
    expected = 0
    out = bytearray()
    while i < len(fmt):
        i = _ail_struct_skip_space(fmt, i)
        if i >= len(fmt):
            break
        got = _ail_struct_count(fmt, i)
        count = got[0]
        if count < 0:
            count = 1
        i = got[1]
        if i >= len(fmt):
            raise _AilStructError("repeat count given without format specifier")
        ch = fmt[i]
        i = i + 1
        if ch == "x":
            k = 0
            while k < count:
                out.append(0)
                k = k + 1
            continue
        info = _ail_struct_bounds(ch)
        if info[0] == 0:
            raise _AilStructError("bad char in struct format")
        expected = expected + count
        if vi + count > len(values):
            raise _AilStructError("pack expected " + str(expected) + " items for packing (got " + str(len(values)) + ")")
        k = 0
        while k < count:
            v = values[vi]
            vi = vi + 1
            if ch == "?":
                if v:
                    out.append(1)
                else:
                    out.append(0)
            else:
                if not isinstance(v, int):
                    raise _AilStructError("required argument is not an integer")
                if info[2] < 0:
                    if v < info[1]:
                        _ail_struct_range(ch, info)
                    try:
                        out.extend(v.to_bytes(info[0], order, signed=(info[1] < 0)))
                    except Exception:
                        _ail_struct_range(ch, info)
                else:
                    if v < info[1] or v > info[2]:
                        _ail_struct_range(ch, info)
                    out.extend(v.to_bytes(info[0], order, signed=(info[1] < 0)))
            k = k + 1
    if vi != len(values):
        raise _AilStructError("pack expected " + str(expected) + " items for packing (got " + str(len(values)) + ")")
    return bytes(out)


def _ail_struct_unpack(fmt: str, data: bytes) -> list[int]:
    order = _ail_struct_order(fmt)
    total = _ail_struct_size(fmt)
    if not isinstance(data, bytes) and not isinstance(data, bytearray):
        raise _AilStructError("a bytes-like object is required, not '" + type(data).__name__ + "'")
    if len(data) != total:
        raise _AilStructError("unpack requires a buffer of " + str(total) + " bytes")
    i = 1
    pos = 0
    out = []
    while i < len(fmt):
        i = _ail_struct_skip_space(fmt, i)
        if i >= len(fmt):
            break
        got = _ail_struct_count(fmt, i)
        count = got[0]
        if count < 0:
            count = 1
        i = got[1]
        if i >= len(fmt):
            raise _AilStructError("repeat count given without format specifier")
        ch = fmt[i]
        i = i + 1
        if ch == "x":
            pos = pos + count
            continue
        info = _ail_struct_bounds(ch)
        if info[0] == 0:
            raise _AilStructError("bad char in struct format")
        k = 0
        while k < count:
            piece = data[pos:pos + info[0]]
            if ch == "?":
                if piece[0] != 0:
                    out.append(1)
                else:
                    out.append(0)
            else:
                out.append(int.from_bytes(piece, order, signed=(info[1] < 0)))
            pos = pos + info[0]
            k = k + 1
    return out
