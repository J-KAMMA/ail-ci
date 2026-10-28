# prelude_struct.py -- `struct` over int.to_bytes / int.from_bytes (structlib.py injects it).
# The format string is read by the compiler, so only the field helpers below are built: every
# format that reaches a program is one of the integer, bool, char, fixed-string or pascal-string
# forms (float formats are refused by name in structlib.py).


def _ail_struct_pad(n: int) -> bytes:
    return b"\x00" * n


def _ail_struct_join(parts: list[bytes]) -> bytes:
    out = bytearray()
    for p in parts:
        out.extend(p)
    return bytes(out)


def _ail_struct_pack_int(value: int, size: int, signed: bool, order: str, low: int, high: int, code: str) -> bytes:
    if low == 0 and high == 0:
        if code == 'P':
            signed = True
        elif not signed and value < 0:
            raise ValueError("'%s' format requires 0 <= number <= 18446744073709551615" % code)
    elif value < low or value > high:
        raise ValueError("'%s' format requires %d <= number <= %d" % (code, low, high))
    return value.to_bytes(size, order, signed=signed)


def _ail_struct_pack_bool(value: bool) -> bytes:
    if value:
        return b"\x01"
    return b"\x00"


def _ail_struct_pack_char(value: bytes) -> bytes:
    if len(value) != 1:
        raise ValueError("char format requires a bytes object of length 1")
    return value


def _ail_struct_pack_s(value: bytes, size: int) -> bytes:
    if len(value) >= size:
        return value[:size]
    return value + b"\x00" * (size - len(value))


def _ail_struct_pack_p(value: bytes, size: int) -> bytes:
    if size == 0:
        return b""
    n = len(value)
    if n > size - 1:
        n = size - 1
    return bytes([n]) + value[:n] + b"\x00" * (size - 1 - n)


def _ail_struct_check(data: bytes, base: int, total: int, exact: bool) -> None:
    if exact:
        if len(data) != total:
            raise ValueError("unpack requires a buffer of %d bytes" % total)
    else:
        if base < 0:
            raise ValueError("not enough data to unpack %d bytes at offset %d" % (total, base))
        need = base + total
        if len(data) < need:
            raise ValueError("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at offset %d (actual buffer size is %d)" % (need, total, base, len(data)))


def _ail_struct_unpack_int(data: bytes, offset: int, size: int, signed: bool, order: str, base: int, total: int, exact: bool) -> int:
    _ail_struct_check(data, base, total, exact)
    return int.from_bytes(data[offset:offset + size], order, signed=signed)


def _ail_struct_unpack_bool(data: bytes, offset: int, base: int, total: int, exact: bool) -> bool:
    _ail_struct_check(data, base, total, exact)
    return data[offset] != 0


def _ail_struct_unpack_char(data: bytes, offset: int, base: int, total: int, exact: bool) -> bytes:
    _ail_struct_check(data, base, total, exact)
    return data[offset:offset + 1]


def _ail_struct_unpack_s(data: bytes, offset: int, size: int, base: int, total: int, exact: bool) -> bytes:
    _ail_struct_check(data, base, total, exact)
    return data[offset:offset + size]


def _ail_struct_unpack_p(data: bytes, offset: int, size: int, base: int, total: int, exact: bool) -> bytes:
    _ail_struct_check(data, base, total, exact)
    if size == 0:
        return b""
    n = data[offset]
    if n > size - 1:
        n = size - 1
    return data[offset + 1:offset + 1 + n]


def _ail_struct_pack_into(buffer: bytearray, offset: int, data: bytes) -> None:
    if offset < 0:
        raise ValueError("no space to pack %d bytes at offset %d" % (len(data), offset))
    if offset + len(data) > len(buffer):
        raise ValueError("pack_into requires a buffer of at least %d bytes for packing %d bytes at offset %d (actual buffer size is %d)" % (offset + len(data), len(data), offset, len(buffer)))
    i = 0
    while i < len(data):
        buffer[offset + i] = data[i]
        i += 1
