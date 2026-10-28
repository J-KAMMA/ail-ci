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


def _ail_struct_buffer(data) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")


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


def _ail_struct_pack_char(value) -> bytes:
    if not isinstance(value, bytes):
        raise ValueError("char format requires a bytes object of length 1")
    if len(value) != 1:
        raise ValueError("char format requires a bytes object of length 1")
    return value


def _ail_struct_pack_s(value, size: int) -> bytes:
    if not isinstance(value, bytes) and not isinstance(value, bytearray):
        raise ValueError("argument for 's' must be a bytes object")
    if len(value) >= size:
        return value[:size]
    return value + b"\x00" * (size - len(value))


def _ail_struct_pack_p(value, size: int) -> bytes:
    if not isinstance(value, bytes) and not isinstance(value, bytearray):
        raise ValueError("argument for 'p' must be a bytes object")
    if size == 0:
        return b""
    n = len(value)
    if n > size - 1:
        n = size - 1
    return bytes([n]) + value[:n] + b"\x00" * (size - 1 - n)


def _ail_struct_check(data: bytes, base: int, total: int, exact: bool) -> int:
    n = len(data)
    if exact:
        if n != total:
            raise ValueError("unpack requires a buffer of %d bytes" % total)
        return 0
    if base < 0:
        start = base + n
        if start + total > n:
            raise ValueError("not enough data to unpack %d bytes at offset %d" % (total, base))
        if start < 0:
            raise ValueError("offset %d out of range for %d-byte buffer" % (base, n))
        return n
    if base + total > n:
        raise ValueError("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at offset %d (actual buffer size is %d)" % (base + total, total, base, n))
    return 0


def _ail_struct_unpack_int(data, offset: int, size: int, signed: bool, order: str, base: int, total: int, exact: bool) -> int:
    data = _ail_struct_buffer(data)
    offset += _ail_struct_check(data, base, total, exact)
    return int.from_bytes(data[offset:offset + size], order, signed=signed)


def _ail_struct_unpack_bool(data, offset: int, base: int, total: int, exact: bool) -> bool:
    data = _ail_struct_buffer(data)
    offset += _ail_struct_check(data, base, total, exact)
    return data[offset] != 0


def _ail_struct_unpack_char(data, offset: int, base: int, total: int, exact: bool) -> bytes:
    data = _ail_struct_buffer(data)
    offset += _ail_struct_check(data, base, total, exact)
    return data[offset:offset + 1]


def _ail_struct_unpack_s(data, offset: int, size: int, base: int, total: int, exact: bool) -> bytes:
    data = _ail_struct_buffer(data)
    offset += _ail_struct_check(data, base, total, exact)
    return data[offset:offset + size]


def _ail_struct_unpack_p(data, offset: int, size: int, base: int, total: int, exact: bool) -> bytes:
    data = _ail_struct_buffer(data)
    offset += _ail_struct_check(data, base, total, exact)
    if size == 0:
        return b""
    n = data[offset]
    if n > size - 1:
        n = size - 1
    return data[offset + 1:offset + 1 + n]


def _ail_struct_pack_into(buffer, offset: int, data: bytes) -> None:
    if not isinstance(buffer, bytearray):
        raise TypeError("argument must be read-write bytes-like object, not " + type(buffer).__name__)
    n = len(buffer)
    start = offset
    if offset < 0:
        start = offset + n
        if start + len(data) > n:
            raise ValueError("no space to pack %d bytes at offset %d" % (len(data), offset))
        if start < 0:
            raise ValueError("offset %d out of range for %d-byte buffer" % (offset, n))
    elif offset + len(data) > n:
        raise ValueError("pack_into requires a buffer of at least %d bytes for packing %d bytes at offset %d (actual buffer size is %d)" % (offset + len(data), len(data), offset, n))
    i = 0
    while i < len(data):
        buffer[start + i] = data[i]
        i += 1
