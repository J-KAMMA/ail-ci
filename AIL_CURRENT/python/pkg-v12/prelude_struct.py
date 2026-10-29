# -*- coding: utf-8 -*-
# prelude_struct.py -- `struct.pack` / `unpack` / `calcsize` / `unpack_from` / `pack_into` as Python source
# (stdlib5.py injects it). The formats are CPython 3.12's standard sizes, with an explicit byte-order
# prefix: '<' little, '>' big, '!' network (big), '=' native (the host is little-endian). Integer codes
# b B h H i I l L q Q, x, ?, c and s. Float codes (e f d), n N P, native alignment ('@' or no prefix)
# and the class and iterator APIs are refused at compile time.

_ail_st_codes = "x?bBhHiIlLqQcs"
_ail_st_space = " \t\n\r\x0b\x0c"


class error(Exception):
    pass


_ail_st_error_type = error


def _ail_st_little():
    return int.from_bytes(b"\x01\x00", "little") == 1


def _ail_st_error(message: str):
    raise error(message)


def _ail_st_width(code: str) -> int:
    if code == "b" or code == "B" or code == "c" or code == "x" or code == "?":
        return 1
    if code == "h" or code == "H":
        return 2
    if code == "i" or code == "I" or code == "l" or code == "L":
        return 4
    return 8


def _ail_st_signed(code: str) -> bool:
    return code == "b" or code == "h" or code == "i" or code == "l" or code == "q" or code == "n"


def _ail_st_parse(fmt: str) -> list:
    if len(fmt) == 0 or (fmt[0] != "<" and fmt[0] != ">" and fmt[0] != "=" and fmt[0] != "!"):
        _ail_st_error("a format string must start with '<', '>', '=' or '!' (native alignment is not built)")
    little = fmt[0] == "<" or (fmt[0] == "=" and _ail_st_little())
    toks = [little]
    i = 1
    while i < len(fmt):
        while i < len(fmt) and fmt[i] in _ail_st_space:
            i = i + 1
        if i >= len(fmt):
            break
        start = i
        while i < len(fmt) and fmt[i] >= "0" and fmt[i] <= "9":
            i = i + 1
        count = 1
        if i > start:
            count = int(fmt[start:i])
        if i >= len(fmt):
            _ail_st_error("bad format string")
        code = fmt[i]
        if code not in _ail_st_codes:
            _ail_st_error("format code '" + code + "' is not built; use an integer code, x, ?, c or s")
        toks.append(code)
        toks.append(count)
        i = i + 1
    return toks


def _ail_st_size(toks: list) -> int:
    total = 0
    i = 1
    while i < len(toks):
        code = toks[i]
        count = toks[i + 1]
        if code == "s":
            total = total + count
        else:
            total = total + count * _ail_st_width(code)
        i = i + 2
    return total


def _ail_st_count(toks: list) -> int:
    total = 0
    i = 1
    while i < len(toks):
        code = toks[i]
        if code == "s":
            total = total + 1
        elif code != "x":
            total = total + toks[i + 1]
        i = i + 2
    return total


def _ail_st_calcsize(fmt: str) -> int:
    return _ail_st_size(_ail_st_parse(fmt))


def _ail_st_check_int(v, code: str) -> int:
    if isinstance(v, bool):
        iv = int(v)
    elif isinstance(v, int):
        iv = v
    else:
        _ail_st_error("required argument is not an integer")
    width = _ail_st_width(code) * 8
    signed = _ail_st_signed(code)
    if signed:
        low = -(1 << (width - 1))
        high = (1 << (width - 1)) - 1
    else:
        low = 0
        high = (1 << width) - 1
    if iv < low or iv > high:
        _ail_st_error("'" + code + "' format requires " + str(low) + " <= number <= " + str(high))
    return iv


def _ail_st_pack(fmt: str, values) -> bytes:
    toks = _ail_st_parse(fmt)
    little = toks[0]
    out = bytearray()
    k = 0
    i = 1
    while i < len(toks):
        code = toks[i]
        count = toks[i + 1]
        i = i + 2
        if code == "x":
            n = 0
            while n < count:
                out.append(0)
                n = n + 1
        elif code == "s":
            if k >= len(values):
                _ail_st_error("pack expected " + str(_ail_st_count(toks)) + " items for packing (got " + str(len(values)) + ")")
            v = values[k]
            k = k + 1
            if isinstance(v, str) or (not isinstance(v, bytes) and not isinstance(v, bytearray)):
                _ail_st_error("argument for 's' must be a bytes object")
            n = 0
            while n < count:
                if n < len(v):
                    out.append(v[n])
                else:
                    out.append(0)
                n = n + 1
        else:
            n = 0
            while n < count:
                if k >= len(values):
                    _ail_st_error("pack expected " + str(_ail_st_count(toks)) + " items for packing (got " + str(len(values)) + ")")
                v = values[k]
                k = k + 1
                if code == "?":
                    if bool(v):
                        out.append(1)
                    else:
                        out.append(0)
                elif code == "c":
                    if not isinstance(v, bytes) or len(v) != 1:
                        _ail_st_error("char format requires a bytes object of length 1")
                    out.append(v[0])
                else:
                    iv = _ail_st_check_int(v, code)
                    out += iv.to_bytes(_ail_st_width(code), "little" if little else "big",
                                       signed=_ail_st_signed(code))
                n = n + 1
    if k != len(values):
        _ail_st_error("pack expected " + str(k) + " items for packing (got " + str(len(values)) + ")")
    return bytes(out)


def _ail_st_read(toks: list, data, pos: int):
    little = toks[0]
    out = []
    i = 1
    while i < len(toks):
        code = toks[i]
        count = toks[i + 1]
        i = i + 2
        if code == "x":
            pos = pos + count
        elif code == "s":
            out.append(bytes(data[pos:pos + count]))
            pos = pos + count
        else:
            n = 0
            while n < count:
                width = _ail_st_width(code)
                chunk = data[pos:pos + width]
                pos = pos + width
                if code == "?":
                    out.append(chunk[0] != 0)
                elif code == "c":
                    out.append(bytes(chunk))
                else:
                    out.append(int.from_bytes(chunk, "little" if little else "big",
                                              signed=_ail_st_signed(code)))
                n = n + 1
    return tuple(out)


def _ail_st_bytes(data):
    if not isinstance(data, bytes) and not isinstance(data, bytearray):
        raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")
    return data


def _ail_st_check_buffer(data, size: int, offset: int, what: str) -> int:
    _ail_st_bytes(data)
    start = offset
    if start < 0:
        if -start > len(data):
            _ail_st_error("offset " + str(offset) + " out of range for " + str(len(data)) + "-byte buffer")
        start = len(data) + start
        if len(data) - start < size:
            if what == "unpack_from":
                _ail_st_error("not enough data to unpack " + str(size) + " bytes at offset " + str(offset))
            _ail_st_error("no space to pack " + str(size) + " bytes at offset " + str(offset))
    elif len(data) - start < size:
        if what == "unpack_from":
            _ail_st_error("unpack_from requires a buffer of at least " + str(start + size) + " bytes for unpacking "
                          + str(size) + " bytes at offset " + str(start) + " (actual buffer size is " + str(len(data)) + ")")
        _ail_st_error("pack_into requires a buffer of at least " + str(start + size) + " bytes for packing "
                      + str(size) + " bytes at offset " + str(start) + " (actual buffer size is " + str(len(data)) + ")")
    return start


def _ail_st_unpack(fmt: str, data):
    toks = _ail_st_parse(fmt)
    size = _ail_st_size(toks)
    _ail_st_bytes(data)
    if len(data) != size:
        _ail_st_error("unpack requires a buffer of " + str(size) + " bytes")
    return _ail_st_read(toks, data, 0)


def _ail_st_unpack_from(fmt: str, data, offset: int = 0):
    toks = _ail_st_parse(fmt)
    size = _ail_st_size(toks)
    start = _ail_st_check_buffer(data, size, offset, "unpack_from")
    return _ail_st_read(toks, data, start)


def _ail_st_pack_into(fmt: str, buffer, offset: int, values) -> None:
    if not isinstance(buffer, bytearray):
        raise TypeError("argument must be read-write bytes-like object, not " + type(buffer).__name__)
    packed = _ail_st_pack(fmt, values)
    start = _ail_st_check_buffer(buffer, len(packed), offset, "pack_into")
    buffer[start:start + len(packed)] = packed
