def _ail_struct_tname(x):
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, bytes):
        return "bytes"
    if isinstance(x, bytearray):
        return "bytearray"
    if isinstance(x, list):
        return "list"
    if isinstance(x, dict):
        return "dict"
    if x is None:
        return "NoneType"
    return "object"


def _ail_struct_buffer(data):
    if isinstance(data, bytes):
        return bytes(data)
    if isinstance(data, bytearray):
        return bytes(data)
    raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")


def _ail_struct_raw(value, code):
    if isinstance(value, bytes) or isinstance(value, bytearray):
        return bytes(value)
    raise RuntimeError("argument for '" + code + "' must be a bytes object")


def _ail_struct_pack(ops, expected, values):
    if len(values) != expected:
        raise RuntimeError("pack expected " + str(expected) + " items for packing (got " + str(len(values)) + ")")
    out = bytearray()
    vi = 0
    oi = 0
    while oi < len(ops):
        kind = ops[oi]
        width = ops[oi + 1]
        signed = ops[oi + 2]
        big = ops[oi + 3]
        pos = ops[oi + 4]
        oi += 5
        while len(out) < pos:
            out.append(0)
        if kind == 4:
            i = 0
            while i < width:
                out.append(0)
                i += 1
            continue
        value = values[vi]
        vi += 1
        if kind == 0:
            if not isinstance(value, int):
                raise RuntimeError("required argument is not an integer")
            number = value
            if width >= 8:
                if not signed and number < 0:
                    raise RuntimeError("argument out of range")
            else:
                lo = 0
                hi = (1 << (8 * width)) - 1
                if signed:
                    lo = -(1 << (8 * width - 1))
                    hi = (1 << (8 * width - 1)) - 1
                if number < lo or number > hi:
                    raise RuntimeError("argument out of range")
                if number < 0:
                    number += 1 << (8 * width)
            i = 0
            if big:
                while i < width:
                    out.append((number >> (8 * (width - 1 - i))) & 255)
                    i += 1
            else:
                while i < width:
                    out.append(number & 255)
                    number = number >> 8
                    i += 1
        elif kind == 1:
            if value:
                out.append(1)
            else:
                out.append(0)
        elif kind == 2:
            if not (isinstance(value, bytes) or isinstance(value, bytearray)) or len(value) != 1:
                raise RuntimeError("char format requires a bytes object of length 1")
            out.append(value[0])
        elif kind == 3:
            data = _ail_struct_raw(value, "s")
            i = 0
            while i < width:
                if i < len(data):
                    out.append(data[i])
                else:
                    out.append(0)
                i += 1
        elif kind == 6:
            data = _ail_struct_raw(value, "p")
            if width > 0:
                size = len(data)
                if size > width - 1:
                    size = width - 1
                out.append(size)
                i = 0
                while i < width - 1:
                    if i < size:
                        out.append(data[i])
                    else:
                        out.append(0)
                    i += 1
    return bytes(out)


def _ail_struct_unpack_check(data, offset, size, exact):
    raw = _ail_struct_buffer(data)
    if offset < 0:
        raise RuntimeError("offset must be non-negative")
    if exact:
        if len(raw) != size:
            raise RuntimeError("unpack requires a buffer of " + str(size) + " bytes")
    elif len(raw) < offset + size:
        raise RuntimeError("unpack_from requires a buffer of at least " + str(offset + size) + " bytes for unpacking "
                           + str(size) + " bytes at offset " + str(offset) + " (actual buffer size is "
                           + str(len(raw)) + ")")


def _ail_struct_unpack_int(data, offset, pos, width, signed, big):
    raw = _ail_struct_buffer(data)
    start = offset + pos
    if width >= 8 and signed and raw[start + width - 1] >= 128:
        number = -1
        if big:
            i = 0
            while i < width:
                number = (number << 8) | raw[start + i]
                i += 1
        else:
            i = width - 1
            while i >= 0:
                number = (number << 8) | raw[start + i]
                i -= 1
        return number
    if width >= 8 and not signed and raw[start + width - 1] >= 128:
        raise RuntimeError("integer overflow")
    number = 0
    if big:
        i = 0
        while i < width:
            number = (number << 8) | raw[start + i]
            i += 1
    else:
        i = width - 1
        while i >= 0:
            number = (number << 8) | raw[start + i]
            i -= 1
    if signed and width < 8 and number >= 1 << (8 * width - 1):
        number -= 1 << (8 * width)
    return number


def _ail_struct_unpack_bool(data, offset, pos):
    return _ail_struct_buffer(data)[offset + pos] != 0


def _ail_struct_unpack_char(data, offset, pos):
    raw = _ail_struct_buffer(data)
    return bytes(raw[offset + pos:offset + pos + 1])


def _ail_struct_unpack_bytes(data, offset, pos, width):
    raw = _ail_struct_buffer(data)
    return bytes(raw[offset + pos:offset + pos + width])


def _ail_struct_unpack_pascal(data, offset, pos, width):
    raw = _ail_struct_buffer(data)
    if width == 0:
        return b""
    size = raw[offset + pos]
    if size > width - 1:
        size = width - 1
    return bytes(raw[offset + pos + 1:offset + pos + 1 + size])


def _ail_struct_pack_into(ops, expected, size, buffer, offset, values):
    if not isinstance(buffer, bytearray):
        raise TypeError("argument must be read-write bytes-like object, not " + _ail_struct_tname(buffer))
    if offset < 0:
        raise RuntimeError("offset must be non-negative")
    if offset + size > len(buffer):
        raise RuntimeError("pack_into requires a buffer of at least " + str(offset + size) + " bytes for packing "
                           + str(size) + " bytes at offset " + str(offset) + " (actual buffer size is "
                           + str(len(buffer)) + ")")
    packed = _ail_struct_pack(ops, expected, values)
    i = 0
    while i < size:
        buffer[offset + i] = packed[i]
        i += 1
