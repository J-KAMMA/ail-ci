# prelude_struct.py -- struct for the integer, bool, char, string and padding formats.
# Plain Python: it also runs under CPython, which is how the tests compare it with the real module.

_STRUCT_WS = " \t\n\r\v\f"
_STRUCT_CHARS = "xcbB?hHiIlLqQnNspP"

class error(Exception):
    pass


def _ail_struct_prefix(fmt: str) -> str:
    if len(fmt) == 0:
        return "@"
    p = fmt[0]
    if p == "<" or p == ">" or p == "=" or p == "!" or p == "@":
        return p
    return "@"


def _ail_struct_parts(fmt: str) -> list[str]:
    prefix = _ail_struct_prefix(fmt)
    start = 0
    if len(fmt) > 0 and (fmt[0] == "<" or fmt[0] == ">" or fmt[0] == "=" or fmt[0] == "!" or fmt[0] == "@"):
        start = 1
    parts: list[str] = [prefix]
    num = ""
    i = start
    while i < len(fmt):
        ch = fmt[i]
        if ch in _STRUCT_WS:
            if num != "":
                raise error("bad char in struct format")
            i += 1
            continue
        if ch >= "0" and ch <= "9":
            num = num + ch
            i += 1
            continue
        if ch in _STRUCT_CHARS:
            if (ch == "n" or ch == "N" or ch == "P") and prefix != "@":
                raise error("bad char in struct format")
            n = 1
            if num != "":
                n = int(num)
            parts.append(str(n) + ch)
            num = ""
            i += 1
            continue
        raise error("bad char in struct format")
    if num != "":
        raise error("repeat count given without format specifier")
    return parts


def _ail_struct_count(tok: str) -> int:
    if len(tok) == 1:
        return 1
    return int(tok[:-1])


def _ail_struct_char(tok: str) -> str:
    return tok[-1]


def _ail_struct_size(prefix: str, ch: str) -> int:
    if ch == "x" or ch == "c" or ch == "b" or ch == "B" or ch == "?" or ch == "s" or ch == "p":
        return 1
    if ch == "h" or ch == "H":
        return 2
    if ch == "i" or ch == "I":
        return 4
    if ch == "l" or ch == "L":
        if prefix == "@":
            return 8
        return 4
    if ch == "q" or ch == "Q" or ch == "n" or ch == "N" or ch == "P":
        return 8
    raise error("bad char in struct format")


def _ail_struct_padding(pos: int, align: int) -> int:
    if align <= 1:
        return 0
    return (align - pos % align) % align


def _ail_struct_order(fmt: str) -> str:
    p = _ail_struct_prefix(fmt)
    if p == ">" or p == "!":
        return "big"
    return "little"


def _ail_struct_total(fmt: str) -> int:
    parts = _ail_struct_parts(fmt)
    prefix = parts[0]
    pos = 0
    i = 1
    while i < len(parts):
        tok = parts[i]
        ch = _ail_struct_char(tok)
        n = _ail_struct_count(tok)
        if ch == "s" or ch == "p":
            pos += n
        elif ch == "x":
            pos += n
        else:
            size = _ail_struct_size(prefix, ch)
            if n == 0:
                if prefix == "@":
                    pos += _ail_struct_padding(pos, size)
            else:
                k = 0
                while k < n:
                    if prefix == "@":
                        pos += _ail_struct_padding(pos, size)
                    pos += size
                    k += 1
        i += 1
    return pos


def _ail_struct_value_meta(fmt: str, idx: int) -> list[str]:
    parts = _ail_struct_parts(fmt)
    prefix = parts[0]
    pos = 0
    vi = 0
    i = 1
    while i < len(parts):
        tok = parts[i]
        ch = _ail_struct_char(tok)
        n = _ail_struct_count(tok)
        if ch == "s" or ch == "p":
            if vi == idx:
                return [str(pos), str(n), ch]
            vi += 1
            pos += n
        elif ch == "x":
            pos += n
        else:
            size = _ail_struct_size(prefix, ch)
            if n == 0:
                if prefix == "@":
                    pos += _ail_struct_padding(pos, size)
            else:
                k = 0
                while k < n:
                    if prefix == "@":
                        pos += _ail_struct_padding(pos, size)
                    if vi == idx:
                        return [str(pos), str(size), ch]
                    vi += 1
                    pos += size
                    k += 1
        i += 1
    return ["0", "0", "x"]


def _ail_struct_zeros(n: int) -> bytes:
    if n <= 0:
        return b""
    out = bytearray(n)
    return bytes(out)


def _ail_struct_prev_end(fmt: str, idx: int) -> int:
    if idx <= 0:
        return 0
    meta = _ail_struct_value_meta(fmt, idx - 1)
    return int(meta[0]) + int(meta[1])


def _ail_struct_gap(fmt: str, idx: int) -> int:
    meta = _ail_struct_value_meta(fmt, idx)
    return int(meta[0]) - _ail_struct_prev_end(fmt, idx)


def _ail_struct_check_int(ch: str, size: int, value) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) or isinstance(value, str) or value is None:
        raise error("required argument is not an integer")
    v = int(value)
    if ch == "b":
        if v < -128 or v > 127:
            raise error("'b' format requires -128 <= number <= 127")
    elif ch == "B":
        if v < 0 or v > 255:
            raise error("'B' format requires 0 <= number <= 255")
    elif ch == "h":
        if v < -32768 or v > 32767:
            raise error("'h' format requires -32768 <= number <= 32767")
    elif ch == "H":
        if v < 0 or v > 65535:
            raise error("'H' format requires 0 <= number <= 65535")
    elif ch == "i":
        if v < -2147483648 or v > 2147483647:
            raise error("'i' format requires -2147483648 <= number <= 2147483647")
    elif ch == "I":
        if v < 0 or v > 4294967295:
            raise error("'I' format requires 0 <= number <= 4294967295")
    elif ch == "l":
        if size == 8:
            if v < -9223372036854775808 or v > 9223372036854775807:
                raise error("'l' format requires -9223372036854775808 <= number <= 9223372036854775807")
        elif v < -2147483648 or v > 2147483647:
            raise error("'l' format requires -2147483648 <= number <= 2147483647")
    elif ch == "L":
        if size == 8:
            if v < 0 or v > 9223372036854775807:
                raise error("'L' format requires 0 <= number <= 18446744073709551615")
        elif v < 0 or v > 4294967295:
            raise error("'L' format requires 0 <= number <= 4294967295")
    elif ch == "q" or ch == "n":
        if v < -9223372036854775808 or v > 9223372036854775807:
            raise error("'" + ch + "' format requires -9223372036854775808 <= number <= 9223372036854775807")
    elif ch == "Q" or ch == "N" or ch == "P":
        if v < 0 or v > 9223372036854775807:
            raise error("'" + ch + "' format requires 0 <= number <= 18446744073709551615")
    return v


def _ail_struct_encode_int(fmt: str, ch: str, size: int, value) -> bytes:
    v = _ail_struct_check_int(ch, size, value)
    order = _ail_struct_order(fmt)
    out = bytearray(size)
    x = v
    i = 0
    while i < size:
        if order == "big":
            out[size - 1 - i] = x & 255
        else:
            out[i] = x & 255
        x = x >> 8
        i += 1
    return bytes(out)


def _ail_struct_pack_int(fmt: str, idx: int, value) -> bytes:
    meta = _ail_struct_value_meta(fmt, idx)
    size = int(meta[1])
    ch = meta[2]
    return _ail_struct_zeros(_ail_struct_gap(fmt, idx)) + _ail_struct_encode_int(fmt, ch, size, value)


def _ail_struct_pack_bool(fmt: str, idx: int, value) -> bytes:
    gap = _ail_struct_zeros(_ail_struct_gap(fmt, idx))
    if value:
        return gap + b"\x01"
    return gap + b"\x00"


def _ail_struct_pack_bytes(fmt: str, idx: int, value) -> bytes:
    meta = _ail_struct_value_meta(fmt, idx)
    size = int(meta[1])
    ch = meta[2]
    gap = _ail_struct_zeros(_ail_struct_gap(fmt, idx))
    if ch == "c":
        if not isinstance(value, bytes):
            raise error("char format requires a bytes object of length 1")
        if len(value) != 1:
            raise error("char format requires a bytes object of length 1")
        return gap + value
    if not isinstance(value, bytes) and not isinstance(value, bytearray):
        raise error("argument for '" + ch + "' must be a bytes object")
    if ch == "s":
        take = len(value)
        if take > size:
            take = size
        return gap + bytes(value[:take]) + _ail_struct_zeros(size - take)
    if size == 0:
        return gap
    take = len(value)
    if take > size - 1:
        take = size - 1
    if take > 255:
        take = 255
    length = bytes([take])
    return gap + length + bytes(value[:take]) + _ail_struct_zeros(size - 1 - take)


def _ail_struct_pack_join(fmt: str, chunks: list[bytes]) -> bytes:
    out = b""
    i = 0
    while i < len(chunks):
        out = out + chunks[i]
        i += 1
    total = _ail_struct_total(fmt)
    if len(out) < total:
        out = out + _ail_struct_zeros(total - len(out))
    return out


def _ail_struct_require_buffer(data) -> None:
    if not (isinstance(data, bytes) or isinstance(data, bytearray)):
        raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")


def _ail_struct_require_write_buffer(buf) -> None:
    if not isinstance(buf, bytearray):
        name = type(buf).__name__
        if buf is None:
            name = "None"
        raise TypeError("argument must be read-write bytes-like object, not " + name)


def _ail_struct_check(fmt: str, data) -> None:
    _ail_struct_require_buffer(data)
    total = _ail_struct_total(fmt)
    if len(data) != total:
        raise error("unpack requires a buffer of " + str(total) + " bytes")


def _ail_struct_adjust(fmt: str, buf, offset: int, pack: bool) -> int:
    total = _ail_struct_total(fmt)
    n = len(buf)
    if offset < 0:
        if offset < -n and offset <= -total:
            raise error("offset " + str(offset) + " out of range for " + str(n) + "-byte buffer")
        adjusted = offset + n
        if adjusted + total > n:
            if pack:
                raise error("no space to pack " + str(total) + " bytes at offset " + str(offset))
            raise error("not enough data to unpack " + str(total) + " bytes at offset " + str(offset))
        return adjusted
    if offset + total > n:
        if pack:
            raise error("pack_into requires a buffer of at least " + str(offset + total) + " bytes for packing "
                        + str(total) + " bytes at offset " + str(offset) + " (actual buffer size is " + str(n) + ")")
        raise error("unpack_from requires a buffer of at least " + str(offset + total) + " bytes for unpacking "
                    + str(total) + " bytes at offset " + str(offset) + " (actual buffer size is " + str(n) + ")")
    return offset


def _ail_struct_check_from(fmt: str, data, offset: int) -> int:
    _ail_struct_require_buffer(data)
    return _ail_struct_adjust(fmt, data, offset, False)


def _ail_struct_check_into(fmt: str, buf, offset: int) -> int:
    _ail_struct_require_write_buffer(buf)
    offset = _ail_struct_adjust(fmt, buf, offset, True)
    total = _ail_struct_total(fmt)
    p = offset
    end = offset + total
    while p < end:
        buf[p] = 0
        p += 1
    return offset


def _ail_struct_decode_int(fmt: str, ch: str, size: int, chunk) -> int:
    if size == 0:
        return 0
    order = _ail_struct_order(fmt)
    if ch in "bhilqn":
        if order == "big":
            first = chunk[0]
        else:
            first = chunk[size - 1]
        if first >= 128:
            v = first - 256
        else:
            v = first
        i = 1
        while i < size:
            if order == "big":
                b = chunk[i]
            else:
                b = chunk[size - 1 - i]
            v = v * 256 + b
            i += 1
        return v
    v = 0
    i = 0
    while i < size:
        if order == "big":
            b = chunk[i]
        else:
            b = chunk[size - 1 - i]
        if v > 36028797018963967:
            raise error("unsigned 64-bit value is outside this language's int64")
        v = v * 256 + b
        i += 1
    return v


def _ail_struct_unpack_int(fmt: str, idx: int, data) -> int:
    meta = _ail_struct_value_meta(fmt, idx)
    start = int(meta[0])
    size = int(meta[1])
    ch = meta[2]
    return _ail_struct_decode_int(fmt, ch, size, data[start:start + size])


def _ail_struct_unpack_int_at(fmt: str, idx: int, data, offset: int) -> int:
    meta = _ail_struct_value_meta(fmt, idx)
    start = offset + int(meta[0])
    size = int(meta[1])
    ch = meta[2]
    return _ail_struct_decode_int(fmt, ch, size, data[start:start + size])


def _ail_struct_unpack_bool(fmt: str, idx: int, data) -> bool:
    meta = _ail_struct_value_meta(fmt, idx)
    start = int(meta[0])
    return data[start] != 0


def _ail_struct_unpack_bool_at(fmt: str, idx: int, data, offset: int) -> bool:
    meta = _ail_struct_value_meta(fmt, idx)
    start = offset + int(meta[0])
    return data[start] != 0


def _ail_struct_unpack_bytes(fmt: str, idx: int, data) -> bytes:
    meta = _ail_struct_value_meta(fmt, idx)
    start = int(meta[0])
    size = int(meta[1])
    ch = meta[2]
    if ch == "s" or ch == "c":
        return bytes(data[start:start + size])
    if size == 0:
        return b""
    n = data[start]
    if n > size - 1:
        n = size - 1
    return bytes(data[start + 1:start + 1 + n])


def _ail_struct_unpack_bytes_at(fmt: str, idx: int, data, offset: int) -> bytes:
    meta = _ail_struct_value_meta(fmt, idx)
    start = offset + int(meta[0])
    size = int(meta[1])
    ch = meta[2]
    if ch == "s" or ch == "c":
        return bytes(data[start:start + size])
    if size == 0:
        return b""
    n = data[start]
    if n > size - 1:
        n = size - 1
    return bytes(data[start + 1:start + 1 + n])


def _ail_struct_store_item(buf, fmt: str, idx: int, offset: int, chunk: bytes) -> None:
    p = offset + _ail_struct_prev_end(fmt, idx)
    i = 0
    while i < len(chunk):
        buf[p] = chunk[i]
        p += 1
        i += 1
