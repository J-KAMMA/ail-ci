class error(Exception):
    pass


_STRUCT_SIZES = [1, 1, 1, 1, 1, 2, 2, 4, 4, 4, 4, 8, 1, 1]
_STRUCT_CODES = "xcbB?hHiIlLqsp"
_STRUCT_NAMES = ["pad", "char", "byte", "ubyte", "bool", "short", "ushort", "int", "uint",
                 "long", "ulong", "longlong", "char[]", "pascal"]


def _ail_struct_code(code: str) -> int:
    i = 0
    while i < len(_STRUCT_CODES):
        if _STRUCT_CODES[i] == code:
            return i
        i += 1
    return -1


def _ail_struct_plan(fmt):
    if isinstance(fmt, bytes):
        fmt = fmt.decode()
    if not isinstance(fmt, str):
        raise error("struct format must be a string or bytes")
    n = len(fmt)
    big = 1
    i = 0
    if n > 0:
        first = fmt[0]
        if first == "<":
            big = 0
            i = 1
        elif first == ">" or first == "!":
            big = 1
            i = 1
        elif first == "=":
            big = 0
            i = 1
        elif first == " " or first == "\t" or first == "\n" or first == "\r" or first == "\v" or first == "\f":
            i = 0
            while i < n and (fmt[i] == " " or fmt[i] == "\t" or fmt[i] == "\n" or fmt[i] == "\r"
                             or fmt[i] == "\v" or fmt[i] == "\f"):
                i += 1
            if i < n:
                raise error("bad char in struct format")
        else:
            raise error("native byte order is not built; write '<', '>', '=' or '!' before the format")
    plan = [big, 0, 0]
    size = 0
    while i < n:
        while i < n and fmt[i] in " \t\n\r\v\f":
            i += 1
        if i >= n:
            break
        count = 0
        digits = 0
        while i < n and fmt[i] >= "0" and fmt[i] <= "9":
            count = count * 10 + (ord(fmt[i]) - 48)
            digits += 1
            i += 1
        if i >= n:
            raise error("repeat count given without format specifier")
        code = fmt[i]
        i += 1
        code_id = _ail_struct_code(code)
        if code_id < 0:
            if code == "@":
                raise error("native byte order is not built; write '<', '>', '=' or '!' before the format")
            if code == "Q" or code == "N":
                raise error("struct code '%s' is not built (an unsigned 64-bit value can leave int64)" % code)
            if code == "n":
                raise error("struct code 'n' is not built (it only exists in native byte order)")
            if code == "P":
                raise error("struct code 'P' is not built (it only exists in native byte order)")
            if code == "e" or code == "f" or code == "d":
                raise error("struct code '%s' is not built (float packing is not built)" % code)
            raise error("bad char in struct format")
        if digits == 0:
            count = 1
        if code_id == 13 and count == 0:
            raise error("struct code 'p' with a zero repeat is not built")
        if count == 0 and code_id != 12 and code_id != 13:
            continue
        item_size = _STRUCT_SIZES[code_id] * count
        plan.append(size)
        plan.append(code_id)
        plan.append(count)
        plan[2] = plan[2] + 1
        size = size + item_size
    plan[1] = size
    return plan


def _ail_struct_expected(plan) -> int:
    total = 0
    n = plan[2]
    i = 0
    while i < n:
        code = plan[4 + 3 * i]
        count = plan[5 + 3 * i]
        if code == 12 or code == 13:
            total += 1
        elif code != 0:
            total += count
        i += 1
    return total


def _ail_struct_bytes(value, what: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    raise error("argument for '%s' must be a bytes object" % what)


def _ail_struct_pack(fmt, *values):
    plan = _ail_struct_plan(fmt)
    big = plan[0]
    size = plan[1]
    n = plan[2]
    expected = _ail_struct_expected(plan)
    if len(values) != expected:
        raise error("pack expected %d items for packing (got %d)" % (expected, len(values)))
    out = bytearray(size)
    at = 0
    i = 0
    while i < n:
        offset = plan[3 + 3 * i]
        code = plan[4 + 3 * i]
        count = plan[5 + 3 * i]
        if code == 0:
            i += 1
            continue
        if code == 12 or code == 13:
            if at >= len(values):
                raise error("pack expected %d items for packing (got %d)" % (_ail_struct_expected(plan), len(values)))
            value = values[at]
            at += 1
            if code == 12:
                data = _ail_struct_bytes(value, "s")
                j = 0
                while j < count and j < len(data):
                    out[offset + j] = data[j]
                    j += 1
            else:
                data = _ail_struct_bytes(value, "p")
                room = count - 1
                if room < 0:
                    room = 0
                used = len(data)
                if used > room:
                    used = room
                if count > 0:
                    out[offset] = used
                    j = 0
                    while j < used:
                        out[offset + 1 + j] = data[j]
                        j += 1
            i += 1
            continue
        j = 0
        while j < count:
            if at >= len(values):
                raise error("pack expected %d items for packing (got %d)" % (_ail_struct_expected(plan), len(values)))
            value = values[at]
            at += 1
            if code == 1:
                if not isinstance(value, bytes) or len(value) != 1:
                    raise error("char format requires a bytes object of length 1")
                out[offset + j] = value[0]
            elif code == 4:
                b = 0
                if bool(value):
                    b = 1
                out[offset + j] = b
            else:
                width = _STRUCT_SIZES[code]
                signed = code == 2 or code == 5 or code == 7 or code == 9 or code == 11
                name = _STRUCT_CODES[code]
                if not isinstance(value, int):
                    raise error("required argument is not an integer")
                if signed:
                    limit = 1 << (width * 8 - 1)
                    low = -limit
                    high = limit - 1
                    if value < low or value > high:
                        raise error("'%s' format requires %d <= number <= %d" % (name, low, high))
                else:
                    high = (1 << (width * 8)) - 1
                    if value < 0 or value > high:
                        raise error("'%s' format requires 0 <= number <= %d" % (name, high))
                order = "big"
                if big == 0:
                    order = "little"
                data = value.to_bytes(width, order, signed=signed)
                k = 0
                while k < width:
                    out[offset + j * width + k] = data[k]
                    k += 1
            j += 1
        i += 1
    return bytes(out)


def _ail_struct_unpack_list(fmt, data):
    plan = _ail_struct_plan(fmt)
    big = plan[0]
    size = plan[1]
    n = plan[2]
    if isinstance(data, bytes):
        pass
    elif isinstance(data, bytearray):
        pass
    else:
        raise TypeError("a bytes-like object is required, not '%s'" % type(data).__name__)
    if len(data) != size:
        raise error("unpack requires a buffer of %d bytes" % size)
    out = []
    i = 0
    order = "big"
    if big == 0:
        order = "little"
    while i < n:
        offset = plan[3 + 3 * i]
        code = plan[4 + 3 * i]
        count = plan[5 + 3 * i]
        if code == 0:
            i += 1
            continue
        if code == 12:
            out.append(bytes(data[offset:offset + count]))
        elif code == 13:
            if count <= 0:
                out.append(b"")
            else:
                used = data[offset]
                room = count - 1
                if used > room:
                    used = room
                out.append(bytes(data[offset + 1:offset + 1 + used]))
        elif code == 1:
            j = 0
            while j < count:
                out.append(bytes(data[offset + j:offset + j + 1]))
                j += 1
        elif code == 4:
            j = 0
            while j < count:
                out.append(data[offset + j] != 0)
                j += 1
        else:
            width = _STRUCT_SIZES[code]
            signed = code == 2 or code == 5 or code == 7 or code == 9 or code == 11
            j = 0
            while j < count:
                start = offset + j * width
                out.append(int.from_bytes(bytes(data[start:start + width]), order, signed=signed))
                j += 1
        i += 1
    return out


def _ail_struct_calcsize(fmt) -> int:
    return _ail_struct_plan(fmt)[1]
