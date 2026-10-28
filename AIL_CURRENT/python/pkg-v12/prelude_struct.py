# struct.pack / unpack / unpack_from / calcsize for literal formats (structlib.py).
# Integer, bool, char, string and padding codes in every byte order. Float codes are
# refused at build time by structlib.py, so this code never sees one.


def _ail_struct_info(ch, order):
    if ch == 'x':
        return [1, 1, False, 'x', 'pad']
    if ch == 'c':
        return [1, 1, False, 'c', 'char']
    if ch == 'b':
        return [1, 1, True, 'int', 'b']
    if ch == 'B':
        return [1, 1, False, 'int', 'B']
    if ch == '?':
        return [1, 1, False, 'bool', 'bool']
    if ch == 'h':
        return [2, 2, True, 'int', 'h']
    if ch == 'H':
        return [2, 2, False, 'int', 'H']
    if ch == 'i':
        return [4, 4, True, 'int', 'i']
    if ch == 'I':
        return [4, 4, False, 'int', 'I']
    if ch == 'l':
        if order == '@':
            return [8, 8, True, 'int', 'l']
        return [4, 4, True, 'int', 'l']
    if ch == 'L':
        if order == '@':
            return [8, 8, False, 'int', 'L']
        return [4, 4, False, 'int', 'L']
    if ch == 'q':
        return [8, 8, True, 'int', 'q']
    if ch == 'Q':
        return [8, 8, False, 'int', 'Q']
    if ch == 'P':
        return [8, 8, False, 'int', 'P']
    if ch == 'n':
        return [8, 8, True, 'int', 'n']
    if ch == 'N':
        return [8, 8, False, 'int', 'N']
    if ch == 's':
        return [1, 1, False, 's', 'char']
    if ch == 'p':
        return [1, 1, False, 'p', 'pascal']
    raise ValueError("bad char in struct format")


def _ail_struct_layout(fmt):
    if len(fmt) > 0 and fmt[0] in '@=<>!':
        order = fmt[0]
        i = 1
    else:
        order = '@'
        i = 0
    fields = []
    pos = 0
    n = len(fmt)
    while i < n:
        ch = fmt[i]
        if ch == ' ' or ch == '\t' or ch == '\n' or ch == '\r':
            i += 1
            continue
        count = 1
        if ch >= '0' and ch <= '9':
            j = i
            while j < n and fmt[j] >= '0' and fmt[j] <= '9':
                j += 1
            if j >= n:
                raise ValueError("bad char in struct format")
            count = int(fmt[i:j])
            ch = fmt[j]
            i = j + 1
        else:
            i += 1
        info = _ail_struct_info(ch, order)
        size = info[0]
        align = info[1]
        signed = info[2]
        kind = info[3]
        name = info[4]
        if kind == 'x':
            fields.append(['x', count, pos, count, False, name])
            pos += count
            continue
        if kind == 's' or kind == 'p':
            fields.append([kind, count, pos, count, False, name])
            pos += count
            continue
        k = 0
        while k <= count:
            if order == '@' and align > 1:
                rest = pos % align
                if rest:
                    pos += align - rest
            if k < count:
                fields.append([kind, 1, pos, size, signed, name])
                pos += size
            k += 1
    return [order, fields, pos]


def _ail_struct_little(order):
    if order == '>' or order == '!':
        return False
    if order == '<':
        return True
    return int.from_bytes(b'\x01\x00', 'little') == 1


def _ail_struct_count(fields):
    total = 0
    for field in fields:
        if field[0] != 'x':
            total += 1
    return total


def _ail_struct_pack(fmt, values):
    order, fields, size = _ail_struct_layout(fmt)
    out = bytearray(size)
    little = _ail_struct_little(order)
    want = _ail_struct_count(fields)
    if want != len(values):
        raise ValueError("pack expected %d items for packing (got %d)" % (want, len(values)))
    vi = 0
    for field in fields:
        kind = field[0]
        count = field[1]
        off = field[2]
        width = field[3]
        signed = field[4]
        name = field[5]
        if kind == 'x':
            continue
        value = values[vi]
        vi += 1
        if kind == 'int':
            if not isinstance(value, int):
                raise ValueError("required argument is not an integer")
            if signed:
                low = -(1 << (width * 8 - 1))
                high = (1 << (width * 8 - 1)) - 1
            else:
                low = 0
                high = (1 << (width * 8)) - 1
            if value < low or value > high:
                if signed:
                    raise ValueError("'%s' format requires %d <= number <= %d" % (name, low, high))
                raise ValueError("'%s' format requires 0 <= number <= %d" % (name, high))
            raw = int(value).to_bytes(width, 'little' if little else 'big', signed=signed)
            k = 0
            while k < width:
                out[off + k] = raw[k]
                k += 1
        elif kind == 'bool':
            out[off] = 1 if value else 0
        elif kind == 'c':
            if not isinstance(value, bytes) or len(value) != 1:
                raise ValueError("char format requires a bytes object of length 1")
            out[off] = value[0]
        elif kind == 's':
            if not isinstance(value, (bytes, bytearray)):
                raise ValueError("argument for 's' must be a bytes object")
            k = 0
            while k < count and k < len(value):
                out[off + k] = value[k]
                k += 1
            while k < count:
                out[off + k] = 0
                k += 1
        else:
            if not isinstance(value, (bytes, bytearray)):
                raise ValueError("argument for 'p' must be a bytes object")
            used = len(value)
            if used > count - 1:
                used = count - 1
            if used < 0:
                used = 0
            if count > 0:
                out[off] = used
            k = 0
            while k < used:
                out[off + 1 + k] = value[k]
                k += 1
    return bytes(out)


def _ail_struct_values(fields, data, base):
    order = fields[0]
    little = _ail_struct_little(order)
    out = []
    for field in fields[1]:
        kind = field[0]
        count = field[1]
        off = base + field[2]
        width = field[3]
        signed = field[4]
        if kind == 'x':
            continue
        if kind == 's':
            out.append(bytes(data[off:off + count]))
            continue
        if kind == 'p':
            used = 0
            if count > 0:
                used = data[off]
                if used > count - 1:
                    used = count - 1
            out.append(bytes(data[off + 1:off + 1 + used]))
            continue
        if kind == 'c':
            out.append(bytes(data[off:off + 1]))
            continue
        if kind == 'bool':
            out.append(data[off] != 0)
            continue
        out.append(int.from_bytes(data[off:off + width], 'little' if little else 'big', signed=signed))
    return tuple(out)


def _ail_struct_unpack(fmt, data):
    order, fields, size = _ail_struct_layout(fmt)
    if len(data) != size:
        raise ValueError("unpack requires a buffer of %d bytes" % size)
    return _ail_struct_values([order, fields], data, 0)


def _ail_struct_unpack_from(fmt, data, offset):
    if not isinstance(offset, int):
        try:
            has_index = hasattr(offset, "__index__")
        except Exception:
            has_index = False
        if has_index:
            offset = int(offset)
            if not isinstance(offset, int):
                raise TypeError("__index__ returned non-int (type %s)" % type(offset).__name__)
        else:
            raise TypeError("'%s' object cannot be interpreted as an integer" % type(offset).__name__)
    order, fields, size = _ail_struct_layout(fmt)
    length = len(data)
    if offset < 0:
        start = offset
        if offset + length < 0:
            raise ValueError("offset %d out of range for %d-byte buffer" % (offset, length))
        offset = offset + length
        if offset + size > length:
            raise ValueError("not enough data to unpack %d bytes at offset %d" % (size, start))
    elif offset + size > length:
        raise ValueError("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at "
                         "offset %d (actual buffer size is %d)" % (offset + size, size, offset, length))
    return _ail_struct_values([order, fields], data, offset)
