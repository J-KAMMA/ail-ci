# prelude_struct.py -- `struct.pack` / `unpack` / `unpack_from` / `calcsize` lowered onto bytes.
# structlib.py parses a literal format at compile time and calls these helpers; a format that is not
# a literal, a float code ('e', 'f', 'd') or a 'p' string is refused by name.  The accumulator is a
# bytes value passed through the calls (bytes parameters are read-only, so each helper returns a new
# value), which keeps every packed value inside one expression.
class _ail_struct_error(Exception):
    pass


def _ail_struct_zeros(acc: bytes, n: int) -> bytes:
    out: list[int] = []
    for b in acc:
        out.append(b)
    i = 0
    while i < n:
        out.append(0)
        i += 1
    return bytes(out)


def _ail_struct_num(acc: bytes, v: int, size: int, signed: bool, big: bool, lo: int, hi: int, msg: str) -> bytes:
    if v < lo or v > hi:
        raise _ail_struct_error(msg)
    out: list[int] = []
    for b in acc:
        out.append(b)
    i = 0
    while i < size:
        shift = 8 * i
        if big:
            shift = 8 * (size - 1 - i)
        out.append((v >> shift) & 255)
        i += 1
    return bytes(out)


def _ail_struct_bool(acc: bytes, v: bool) -> bytes:
    out: list[int] = []
    for b in acc:
        out.append(b)
    if v:
        out.append(1)
    else:
        out.append(0)
    return bytes(out)


def _ail_struct_char(acc: bytes, data: bytes) -> bytes:
    if len(data) != 1:
        raise _ail_struct_error("char format requires a bytes object of length 1")
    out: list[int] = []
    for b in acc:
        out.append(b)
    out.append(data[0])
    return bytes(out)


def _ail_struct_str(acc: bytes, data: bytes, size: int) -> bytes:
    out: list[int] = []
    for b in acc:
        out.append(b)
    i = 0
    while i < size:
        if i < len(data):
            out.append(data[i])
        else:
            out.append(0)
        i += 1
    return bytes(out)


def _ail_struct_check(data: bytes, base: int, total: int, mode: int) -> int:
    start = base
    if start < 0:
        start += len(data)
        if start < 0:
            raise _ail_struct_error("offset " + str(base) + " out of range for " + str(len(data)) + "-byte buffer")
    if mode == 0:
        if len(data) != total:
            raise _ail_struct_error("unpack requires a buffer of " + str(total) + " bytes")
    elif start + total > len(data):
        if base < 0:
            raise _ail_struct_error("not enough data to unpack " + str(total) + " bytes at offset " + str(base))
        raise _ail_struct_error(
            "unpack_from requires a buffer of at least " + str(start + total) + " bytes for unpacking "
            + str(total) + " bytes at offset " + str(start) + " (actual buffer size is " + str(len(data)) + ")")
    return start


def _ail_struct_get_int(data: bytes, base: int, delta: int, size: int, signed: bool, big: bool, total: int,
                        mode: int) -> int:
    start = _ail_struct_check(data, base, total, mode) + delta
    if signed and size == 8:
        # Seven low bytes first, then the sign byte, so no intermediate shift leaves int64.
        v = 0
        i = 0
        while i < 7:
            shift = 8 * i
            if big:
                shift = 8 * (7 - i)
            v = v | (data[start + i] << shift)
            i += 1
        if big:
            high = data[start]
        else:
            high = data[start + 7]
        if high >= 128:
            if high == 128:
                v = v + (-9223372036854775808)
            else:
                v = v - ((256 - high) << 56)
        else:
            v = v | (high << 56)
        return v
    v = 0
    i = 0
    while i < size:
        shift = 8 * i
        if big:
            shift = 8 * (size - 1 - i)
        v = v | (data[start + i] << shift)
        i += 1
    if signed:
        half = 1 << (8 * size - 1)
        if v >= half:
            v = v - (1 << (8 * size))
    return v


def _ail_struct_get_bool(data: bytes, base: int, delta: int, total: int, mode: int) -> bool:
    start = _ail_struct_check(data, base, total, mode) + delta
    return data[start] != 0


def _ail_struct_get_str(data: bytes, base: int, delta: int, size: int, total: int, mode: int) -> bytes:
    start = _ail_struct_check(data, base, total, mode) + delta
    out: list[int] = []
    i = 0
    while i < size:
        out.append(data[start + i])
        i += 1
    return bytes(out)


def _ail_struct_get_char(data: bytes, base: int, delta: int, total: int, mode: int) -> bytes:
    return _ail_struct_get_str(data, base, delta, 1, total, mode)
