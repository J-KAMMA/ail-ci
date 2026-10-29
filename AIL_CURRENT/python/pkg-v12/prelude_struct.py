# -*- coding: utf-8 -*-
# prelude_struct.py -- `struct` pack / unpack / unpack_from / calcsize as Python source (structlib.py injects it).
#
# Plain Python in the subset the general path builds, and a module CPython imports as it stands. Only the
# explicit byte-order prefixes '<', '>' and '!' (normalised by structlib.py) are accepted here; native
# alignment is refused at compile time, so the layout is the standard one. Floats ('e', 'f', 'd'), Pascal
# strings ('p') and the native-only codes ('n', 'N', 'P') are refused at compile time too. Values are
# Python ints here, so an unsigned 64-bit value keeps its exact value when read from a buffer.


class error(Exception):
    pass


def _ail_struct_fields(fmt):
    order = "little"
    body = fmt
    if fmt[:1] == ">":
        order = "big"
        body = fmt[1:]
    elif fmt[:1] == "<":
        order = "little"
        body = fmt[1:]
    fields = []
    i = 0
    while i < len(body):
        j = i
        while j < len(body) and body[j].isdigit():
            j += 1
        count = int(body[i:j]) if j > i else 1
        if j >= len(body):
            raise error("bad char in struct format")
        code = body[j]
        if code == "x":
            fields.append(("x", count, count, False))
        elif code == "c":
            fields.append(("c", count, 1, False))
        elif code == "s":
            fields.append(("s", 1, count, False))
        elif code == "?":
            fields.append(("?", count, 1, False))
        elif code == "b":
            fields.append((code, count, 1, True))
        elif code == "B":
            fields.append((code, count, 1, False))
        elif code == "h":
            fields.append((code, count, 2, True))
        elif code == "H":
            fields.append((code, count, 2, False))
        elif code == "i":
            fields.append((code, count, 4, True))
        elif code == "I":
            fields.append((code, count, 4, False))
        elif code == "l":
            fields.append((code, count, 4, True))
        elif code == "L":
            fields.append((code, count, 4, False))
        elif code == "q":
            fields.append((code, count, 8, True))
        elif code == "Q":
            fields.append((code, count, 8, False))
        else:
            raise error("bad char in struct format")
        i = j + 1
    return order, fields


def _ail_struct_size(fields):
    total = 0
    for code, count, size, signed in fields:
        if code == "s" or code == "x":
            total += size
        else:
            total += count * size
    return total


def _ail_struct_expected(fields):
    total = 0
    for code, count, size, signed in fields:
        if code == "s":
            total += 1
        elif code != "x":
            total += count
    return total


def _ail_struct_pack(fmt, *values):
    order, fields = _ail_struct_fields(fmt)
    expected = _ail_struct_expected(fields)
    if len(values) != expected:
        raise error("pack expected %d items for packing (got %d)" % (expected, len(values)))
    out = []
    index = 0
    for code, count, size, signed in fields:
        if code == "x":
            out.append(b"\x00" * count)
            continue
        if code == "s":
            value = values[index]
            index += 1
            if not isinstance(value, (bytes, bytearray)):
                raise error("argument for 's' must be a bytes object")
            data = bytes(value)
            if len(data) < size:
                data = data + b"\x00" * (size - len(data))
            out.append(data[:size])
            continue
        for _ in range(count):
            value = values[index]
            index += 1
            if code == "c":
                if not isinstance(value, bytes) or len(value) != 1:
                    raise error("char format requires a bytes object of length 1")
                out.append(value)
            elif code == "?":
                out.append(b"\x01" if value else b"\x00")
            else:
                if not isinstance(value, int):
                    raise error("required argument is not an integer")
                try:
                    out.append(value.to_bytes(size, order, signed=signed))
                except OverflowError:
                    if signed:
                        low = -(1 << (8 * size - 1))
                        high = (1 << (8 * size - 1)) - 1
                        raise error("'%s' format requires %d <= number <= %d" % (code, low, high))
                    high = (1 << (8 * size)) - 1
                    raise error("'%s' format requires 0 <= number <= %d" % (code, high))
    return b"".join(out)


def _ail_struct_read(fields, order, data, base):
    out = []
    offset = base
    for code, count, size, signed in fields:
        if code == "x":
            offset += count
        elif code == "s":
            out.append(bytes(data[offset:offset + size]))
            offset += size
        elif code == "c":
            for _ in range(count):
                out.append(bytes(data[offset:offset + 1]))
                offset += 1
        elif code == "?":
            for _ in range(count):
                out.append(data[offset] != 0)
                offset += 1
        else:
            for _ in range(count):
                out.append(int.from_bytes(data[offset:offset + size], order, signed=signed))
                offset += size
    return tuple(out)


def _ail_struct_unpack(fmt, data):
    order, fields = _ail_struct_fields(fmt)
    size = _ail_struct_size(fields)
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("a bytes-like object is required, not '%s'" % type(data).__name__)
    if len(data) != size:
        raise error("unpack requires a buffer of %d bytes" % size)
    return _ail_struct_read(fields, order, data, 0)


def _ail_struct_unpack_from(fmt, data, offset=0):
    order, fields = _ail_struct_fields(fmt)
    size = _ail_struct_size(fields)
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("a bytes-like object is required, not '%s'" % type(data).__name__)
    if not isinstance(offset, int):
        raise TypeError("'%s' object cannot be interpreted as an integer" % type(offset).__name__)
    if offset < 0:
        if offset < -len(data) and offset <= -size:
            raise error("offset %d out of range for %d-byte buffer" % (offset, len(data)))
        if offset + len(data) < 0 or offset + len(data) + size > len(data):
            raise error("not enough data to unpack %d bytes at offset %d" % (size, offset))
        offset += len(data)
    if len(data) < offset + size:
        raise error("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at offset %d "
                    "(actual buffer size is %d)" % (offset + size, size, offset, len(data)))
    return _ail_struct_read(fields, order, data, offset)


def _ail_struct_calcsize(fmt):
    order, fields = _ail_struct_fields(fmt)
    return _ail_struct_size(fields)
