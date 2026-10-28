# -*- coding: utf-8 -*-
# prelude_struct.py -- `struct` over the standard byte orders as Python source (structlib.py injects it).
#
# Plain Python in the subset the compiler builds, and a module CPython imports as it stands, so the tests
# compare it with the struct module directly. structlib.py refuses, by name, the native byte order ('@' or
# no prefix), the float codes (f, d, e), the pascal-string code (p) and every other function or attribute of
# the module; what is left is pack, unpack, unpack_from, pack_into, calcsize and error over the integer,
# char, string, pad and bool codes with the '<', '>', '=', '!' byte orders.
#
# The one declared difference is the language's 64-bit int: unpacking a 'Q' (or a 'q' below -2**63) whose
# value leaves the signed 64-bit range stops with "integer overflow", as every int in the language does.


class error(Exception):
    pass


def _ail_struct_typename(value):
    return type(value).__name__


def _ail_struct_codes(fmt):
    """(big_endian, codes, counts, total size) for a format; structlib.py has validated the characters."""
    n = len(fmt)
    if n == 0:
        raise error("bad char in struct format")
    first = fmt[0]
    if first == '<' or first == '=':
        big = False
    elif first == '>' or first == '!':
        big = True
    else:
        raise error("native byte order is not built")
    codes = []
    counts = []
    i = 1
    count = 1
    have = False
    total = 0
    while i < n:
        ch = fmt[i]
        if ch == ' ' or ch == '\t' or ch == '\n' or ch == '\r' or ch == '\v' or ch == '\f':
            if have:
                raise error("bad char in struct format")
            i = i + 1
            continue
        if ch >= '0' and ch <= '9':
            if have:
                count = count * 10 + ord(ch) - 48
            else:
                count = ord(ch) - 48
                have = True
            if count > 2147483647:
                raise error("total struct size too long")
            i = i + 1
            continue
        if not have:
            count = 1
        have = False
        if ch == 'x' or ch == 'c' or ch == 's' or ch == 'b' or ch == 'B' or ch == '?':
            size = count
        elif ch == 'h' or ch == 'H':
            size = count * 2
        elif ch == 'i' or ch == 'I' or ch == 'l' or ch == 'L':
            size = count * 4
        elif ch == 'q' or ch == 'Q':
            size = count * 8
        else:
            raise error("bad char in struct format")
        total = total + size
        if total > 2147483647:
            raise error("total struct size too long")
        codes.append(ch)
        counts.append(count)
        i = i + 1
    return (big, codes, counts, total)


def _ail_struct_items(codes, counts):
    """How many values a format takes."""
    total = 0
    i = 0
    while i < len(codes):
        ch = codes[i]
        if ch == 'x':
            total = total + 0
        elif ch == 's':
            total = total + 1
        else:
            total = total + counts[i]
        i = i + 1
    return total


def _ail_struct_buffer(value):
    if isinstance(value, bytes) or isinstance(value, bytearray):
        return value
    raise TypeError("a bytes-like object is required, not '" + _ail_struct_typename(value) + "'")


def _ail_struct_writable(value):
    if isinstance(value, bytearray):
        return value
    raise TypeError("argument must be read-write bytes-like object, not " + _ail_struct_typename(value))


def _ail_struct_index(value):
    if isinstance(value, bool):
        if value:
            return 1
        return 0
    if isinstance(value, int):
        return value
    raise TypeError("'" + _ail_struct_typename(value) + "' object cannot be interpreted as an integer")


def _ail_struct_width(ch):
    if ch == 'b' or ch == 'B':
        return 1
    if ch == 'h' or ch == 'H':
        return 2
    if ch == 'i' or ch == 'I' or ch == 'l' or ch == 'L':
        return 4
    return 8


def _ail_struct_signed(ch):
    return ch == 'b' or ch == 'h' or ch == 'i' or ch == 'l' or ch == 'q'


def _ail_struct_put(out, pos, value, width, signed, big, code):
    if signed:
        if width == 8:
            if value < -9223372036854775807 - 1 or value > 9223372036854775807:
                raise error("'" + code + "' format requires -9223372036854775808 <= number <= 9223372036854775807")
        else:
            lo = -(1 << (8 * width - 1))
            hi = (1 << (8 * width - 1)) - 1
            if value < lo or value > hi:
                raise error("'" + code + "' format requires " + str(lo) + " <= number <= " + str(hi))
    else:
        if value < 0:
            if width == 8:
                raise error("'" + code + "' format requires 0 <= number <= 18446744073709551615")
            hi = (1 << (8 * width)) - 1
            raise error("'" + code + "' format requires 0 <= number <= " + str(hi))
        if width < 8:
            hi = (1 << (8 * width)) - 1
            if value > hi:
                raise error("'" + code + "' format requires 0 <= number <= " + str(hi))
    i = 0
    while i < width:
        if big:
            out[pos + width - 1 - i] = (value >> (8 * i)) & 255
        else:
            out[pos + i] = (value >> (8 * i)) & 255
        i = i + 1


def _ail_struct_get(data, pos, width, signed, big):
    if big:
        top = data[pos]
        v = top
        if signed and top >= 128:
            v = top - 256
        i = 1
        while i < width:
            v = v * 256 + data[pos + i]
            i = i + 1
        return v
    top = data[pos + width - 1]
    v = top
    if signed and top >= 128:
        v = top - 256
    i = width - 2
    while i >= 0:
        v = v * 256 + data[pos + i]
        i = i - 1
    return v


def _ail_struct_unpack_values(data, start, big, codes, counts):
    out = []
    pos = start
    i = 0
    while i < len(codes):
        ch = codes[i]
        c = counts[i]
        if ch == 'x':
            pos = pos + c
        elif ch == 's':
            out.append(bytes(data[pos:pos + c]))
            pos = pos + c
        elif ch == 'c':
            j = 0
            while j < c:
                out.append(bytes(data[pos:pos + 1]))
                pos = pos + 1
                j = j + 1
        elif ch == '?':
            j = 0
            while j < c:
                if data[pos] != 0:
                    out.append(True)
                else:
                    out.append(False)
                pos = pos + 1
                j = j + 1
        else:
            width = _ail_struct_width(ch)
            signed = _ail_struct_signed(ch)
            j = 0
            while j < c:
                out.append(_ail_struct_get(data, pos, width, signed, big))
                pos = pos + width
                j = j + 1
        i = i + 1
    return out


def _ail_struct_check_items(kind, codes, counts, values):
    need = _ail_struct_items(codes, counts)
    if len(values) != need:
        raise error(kind + " expected " + str(need) + " items for packing (got " + str(len(values)) + ")")
    return need


def _ail_struct_pack_values(big, codes, counts, total, values):
    _ail_struct_check_items("pack", codes, counts, values)
    out = bytearray(total)
    pos = 0
    k = 0
    i = 0
    while i < len(codes):
        ch = codes[i]
        c = counts[i]
        if ch == 'x':
            pos = pos + c
        elif ch == 's':
            v = values[k]
            if not isinstance(v, bytes) and not isinstance(v, bytearray):
                raise error("argument for 's' must be a bytes object")
            j = 0
            while j < c:
                if j < len(v):
                    out[pos + j] = v[j]
                j = j + 1
            pos = pos + c
            k = k + 1
        elif ch == 'c':
            j = 0
            while j < c:
                v = values[k]
                if not isinstance(v, bytes) or len(v) != 1:
                    raise error("char format requires a bytes object of length 1")
                out[pos + j] = v[0]
                k = k + 1
                j = j + 1
            pos = pos + c
        elif ch == '?':
            j = 0
            while j < c:
                v = values[k]
                if v:
                    out[pos + j] = 1
                k = k + 1
                j = j + 1
            pos = pos + c
        else:
            width = _ail_struct_width(ch)
            signed = _ail_struct_signed(ch)
            j = 0
            while j < c:
                v = values[k]
                if isinstance(v, bool):
                    if v:
                        v = 1
                    else:
                        v = 0
                elif not isinstance(v, int):
                    raise error("required argument is not an integer")
                _ail_struct_put(out, pos, v, width, signed, big, ch)
                pos = pos + width
                k = k + 1
                j = j + 1
        i = i + 1
    return bytes(out)


def _ail_struct_pack(fmt, values):
    big, codes, counts, total = _ail_struct_codes(fmt)
    return _ail_struct_pack_values(big, codes, counts, total, values)


def _ail_struct_unpack(fmt, data):
    big, codes, counts, total = _ail_struct_codes(fmt)
    buf = _ail_struct_buffer(data)
    if len(buf) != total:
        raise error("unpack requires a buffer of " + str(total) + " bytes")
    return tuple(_ail_struct_unpack_values(buf, 0, big, codes, counts))


def _ail_struct_unpack_from(fmt, data, offset):
    big, codes, counts, total = _ail_struct_codes(fmt)
    buf = _ail_struct_buffer(data)
    off = _ail_struct_index(offset)
    n = len(buf)
    start = off
    if off < 0:
        if off + total > 0:
            raise error("not enough data to unpack " + str(total) + " bytes at offset " + str(off))
        start = n + off
        if start < 0:
            raise error("offset " + str(off) + " out of range for " + str(n) + "-byte buffer")
    if start + total > n:
        raise error("unpack_from requires a buffer of at least " + str(start + total) + " bytes for unpacking " +
                    str(total) + " bytes at offset " + str(off) + " (actual buffer size is " + str(n) + ")")
    return tuple(_ail_struct_unpack_values(buf, start, big, codes, counts))


def _ail_struct_pack_into(fmt, target, offset, values):
    big, codes, counts, total = _ail_struct_codes(fmt)
    _ail_struct_check_items("pack_into", codes, counts, values)
    buf = _ail_struct_writable(target)
    off = _ail_struct_index(offset)
    n = len(buf)
    start = off
    if off < 0:
        if off + total > 0:
            raise error("no space to pack " + str(total) + " bytes at offset " + str(off))
        start = n + off
        if start < 0:
            raise error("offset " + str(off) + " out of range for " + str(n) + "-byte buffer")
    if start + total > n:
        raise error("pack_into requires a buffer of at least " + str(start + total) + " bytes for packing " +
                    str(total) + " bytes at offset " + str(off) + " (actual buffer size is " + str(n) + ")")
    packed = _ail_struct_pack_values(big, codes, counts, total, values)
    i = 0
    while i < total:
        buf[start + i] = packed[i]
        i = i + 1
    return None


def _ail_struct_calcsize(fmt):
    big, codes, counts, total = _ail_struct_codes(fmt)
    return total
