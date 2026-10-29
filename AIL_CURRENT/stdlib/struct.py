"""A small `struct` for AIL: pack, unpack, unpack_from, calcsize and error.

Formats use CPython 3.12's sizes for this host (little-endian x86-64): the standard
sizes for `= < > !`, native sizes and alignment for `@`. Integer and string codes,
`c`, `?`, `x`, `s`, `p`, `e f d`, and `P` in native mode are built. A format may be a
`str` or `bytes`; any other type raises CPython's `TypeError`. Unpacking needs a bytes
or bytearray buffer and raises CPython's `TypeError` for anything else. `iter_unpack`,
`pack_into`, the buffer protocol and NaN payload bits (the sign is kept, the payload is
canonicalized; see DIFFERENCES) are not built.
"""
import math

_NATIVE_ONLY = "P n N"


class error(Exception):
    pass


def _bad(msg: str) -> None:
    raise error(msg)


def _format_text(fmt: str) -> str:
    if isinstance(fmt, str):
        return fmt
    if isinstance(fmt, bytes):
        return fmt.decode("latin-1")
    name = type(fmt).__name__
    if (isinstance(fmt, bytearray) or isinstance(fmt, list) or isinstance(fmt, dict)
            or isinstance(fmt, set)):
        raise TypeError("unhashable type: '%s'" % name)
    raise TypeError("Struct() argument 1 must be a str or bytes object, not %s" % name)


def _buffer_bytes(buffer) -> bytes:
    if isinstance(buffer, bytes):
        return buffer
    if isinstance(buffer, bytearray):
        return bytes(buffer)
    raise TypeError("a bytes-like object is required, not '%s'" % type(buffer).__name__)


def _slots(fmt: str) -> list:
    fmt = _format_text(fmt)
    if "\x00" in fmt:
        _bad("embedded null character")
    if not fmt:
        return []
    native = True
    order = "@"
    first = fmt[0]
    if first in "@=<>!":
        native = first == "@"
        order = first
        fmt = fmt[1:]
    out = []
    i = 0
    n = len(fmt)
    while i < n:
        ch = fmt[i]
        if ch in " \t\n\r\v\f":
            i += 1
            continue
        count = 1
        j = i
        while j < n and fmt[j].isdigit():
            j += 1
        if j > i:
            count = int(fmt[i:j])
            if count < 0:
                _bad("repeat count is negative")
            i = j
            if i >= n:
                _bad("repeat count given without format specifier")
            ch = fmt[i]
        if ch not in "xcbB?hHiIlLqQnNefdspP":
            _bad("bad char in struct format")
        if not native and ch in _NATIVE_ONLY:
            _bad("bad char in struct format")
        if ch == "s" or ch == "p" or ch == "x":
            size = 1
        else:
            size = _size(ch, native)
        if ch == "s" or ch == "p" or ch == "x":
            out.append((ch, count, 1))
        else:
            out.append((ch, count, size))
        i += 1
    return out


def _size(ch: str, native: bool) -> int:
    if ch in "xcbB?":
        return 1
    if ch == "h" or ch == "H" or ch == "e":
        return 2
    if ch == "i" or ch == "I" or ch == "f":
        return 4
    if ch == "l" or ch == "L":
        return 8 if native else 4
    if ch == "q" or ch == "Q" or ch == "d":
        return 8
    if ch == "n" or ch == "N" or ch == "P":
        return 8
    if ch == "s" or ch == "p":
        return 1
    _bad("bad char in struct format")
    return 0


def _layout(fmt: str) -> list:
    fmt = _format_text(fmt)
    slots = _slots(fmt)
    if not fmt:
        return []
    native = fmt[0] == "@" or (fmt[0] not in "@=<>!")
    out = []
    off = 0
    for ch, count, size in slots:
        if native and ch not in "xsp" and size > 1:
            rem = off % size
            if rem:
                off += size - rem
        each = size * count
        out.append((ch, count, size, off, each))
        off += each
    return out


def calcsize(fmt: str) -> int:
    out = 0
    for ch, count, size, off, each in _layout(fmt):
        out = off + each
    return out


def _order(fmt: str) -> tuple:
    fmt = _format_text(fmt)
    if not fmt:
        return "little", True
    first = fmt[0]
    if first == "!" or first == ">":
        return "big", False
    return "little", first == "@" or first not in "@=<>!"


def _int_bytes(value: int, size: int, signed: bool, order: str) -> bytes:
    return int(value).to_bytes(size, order, signed=signed)


def _normalise(ax: float) -> tuple:
    e = 0
    while ax >= 2.0:
        ax = ax / 2.0
        e += 1
    while ax < 1.0:
        ax = ax * 2.0
        e -= 1
    return ax, e


def _scale(ax: float, n: int) -> float:
    while n > 0:
        ax = ax * 2.0
        n -= 1
    return ax


def _float_bits(x: float, size: int, checked: bool = True) -> int:
    negative = math.copysign(1.0, x) < 0.0
    if size == 8:
        bits = 11
        bias = 1023
        mantbits = 52
    elif size == 4:
        bits = 8
        bias = 127
        mantbits = 23
    else:
        bits = 5
        bias = 15
        mantbits = 10
    sign = (1 if negative else 0) << (bits + mantbits)
    if math.isnan(x):
        return sign + ((1 << bits) - 1) * (1 << mantbits) + (1 << (mantbits - 1))
    if math.isinf(x):
        return sign + ((1 << bits) - 1) * (1 << mantbits)
    ax = abs(x)
    if ax == 0.0:
        return sign
    m, e = _normalise(ax)
    exp = e
    if exp >= 1 - bias:
        scaled = m * math.pow(2.0, mantbits)
        low = int(scaled)
        frac = scaled - low
        if frac > 0.5 or (frac == 0.5 and low % 2 == 1):
            low += 1
        if low >= (1 << (mantbits + 1)):
            low = low // 2
            exp += 1
        mant = low - (1 << mantbits)
        if exp >= bias + 1:
            if size == 2:
                raise OverflowError("float too large to pack with e format")
            if size == 4 and checked:
                raise OverflowError("float too large to pack with f format")
            return sign + ((1 << bits) - 1) * (1 << mantbits)
        return sign + (exp + bias) * (1 << mantbits) + mant
    scaled = _scale(ax, bias - 1 + mantbits)
    low = int(scaled)
    frac = scaled - low
    if frac > 0.5 or (frac == 0.5 and low % 2 == 1):
        low += 1
    if low >= (1 << mantbits):
        return sign + (1 << mantbits)
    return sign + low


def _bits_float(bits: int, size: int) -> float:
    if size == 8:
        bits_n = 11
        bias = 1023
        mantbits = 52
    elif size == 4:
        bits_n = 8
        bias = 127
        mantbits = 23
    else:
        bits_n = 5
        bias = 15
        mantbits = 10
    signbit = 1 << (bits_n + mantbits)
    negative = (bits & signbit) != 0
    exp = (bits >> mantbits) & ((1 << bits_n) - 1)
    mant = bits & ((1 << mantbits) - 1)
    if exp == (1 << bits_n) - 1:
        value = math.inf if mant == 0 else math.nan
    elif exp == 0:
        value = mant * math.pow(2.0, 1 - bias - mantbits)
    else:
        value = (mant + (1 << mantbits)) * math.pow(2.0, exp - bias - mantbits)
    return -value if negative else value


def pack(fmt: str, *values) -> bytes:
    order, native = _order(fmt)
    out = bytearray()
    k = 0
    total = len(values)
    slots = _layout(fmt)
    need = 0
    for ch, count, size, off, each in slots:
        if ch != "x":
            need += count if ch not in "sp" else 1
    if total != need:
        _bad("pack expected %d items for packing (got %d)" % (need, total))
    for ch, count, size, off, each in slots:
        if len(out) < off:
            out.extend(bytes(off - len(out)))
        if ch == "x":
            out.extend(bytes(each))
            continue
        if ch == "s":
            if k >= total:
                _bad("pack expected more items for packing")
            item = values[k]
            k += 1
            if not (isinstance(item, bytes) or isinstance(item, bytearray)):
                _bad("argument for 's' must be a bytes object")
            data = bytes(item)
            if len(data) > count:
                data = data[:count]
            out.extend(data)
            if len(data) < count:
                out.extend(bytes(count - len(data)))
            continue
        if ch == "p":
            if k >= total:
                _bad("pack expected more items for packing")
            item = values[k]
            k += 1
            if not (isinstance(item, bytes) or isinstance(item, bytearray)):
                _bad("argument for 'p' must be a bytes object")
            if count == 0:
                continue
            data = bytes(item)
            if len(data) > count - 1:
                data = data[:count - 1]
            out.append(len(data))
            out.extend(data)
            if len(data) < count - 1:
                out.extend(bytes(count - 1 - len(data)))
            continue
        for _ in range(count):
            if k >= total:
                _bad("pack expected more items for packing")
            item = values[k]
            k += 1
            if ch == "c":
                if not isinstance(item, bytes) or len(item) != 1:
                    _bad("char format requires a bytes object of length 1")
                out.extend(item)
            elif ch == "?":
                out.append(1 if item else 0)
            elif ch in "efd":
                if isinstance(item, str) or isinstance(item, bytes) or isinstance(item, bytearray):
                    _bad("required argument is not a float")
                value = float(item)
                if ch == "e":
                    out.extend(_float_bits(value, 2).to_bytes(2, order))
                elif ch == "f":
                    out.extend(_float_bits(value, 4, not native).to_bytes(4, order))
                else:
                    out.extend(_float_bits(value, 8).to_bytes(8, order))
            else:
                if not isinstance(item, int):
                    _bad("required argument is not an integer")
                value = int(item)
                signed = ch in "bhilqn"
                bits = size * 8
                if signed:
                    low = -(1 << (bits - 1))
                    high = (1 << (bits - 1)) - 1
                else:
                    low = 0
                    high = (1 << bits) - 1
                if value < low or value > high:
                    _bad("'%s' format requires %d <= number <= %d" % (ch, low, high))
                out.extend(_int_bytes(value, size, signed, order))
    return bytes(out)


def unpack_from(fmt: str, buffer, offset: int = 0) -> tuple:
    fmt = _format_text(fmt)
    total = calcsize(fmt)
    order, native = _order(fmt)
    data = _buffer_bytes(buffer)
    out = []
    original = offset
    if offset < 0:
        offset = len(data) + offset
        if offset < 0:
            _bad("offset %d out of range for %d-byte buffer" % (original, len(data)))
        if offset + total > len(data):
            _bad("not enough data to unpack %d bytes at offset %d" % (total, original))
    elif offset + total > len(data):
        _bad("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at offset %d (actual buffer size is %d)"
             % (offset + total, total, offset, len(data)))
    for ch, count, size, off, each in _layout(fmt):
        start = offset + off
        if ch == "x":
            continue
        if ch == "s":
            out.append(data[start:start + count])
            continue
        if ch == "p":
            if count == 0:
                out.append(b"")
                continue
            used = data[start]
            if used > count - 1:
                used = count - 1
            out.append(data[start + 1:start + 1 + used])
            continue
        for j in range(count):
            p = start + j * size
            raw = data[p:p + size]
            if ch == "c":
                out.append(raw)
            elif ch == "?":
                out.append(raw[0] != 0)
            elif ch == "e":
                out.append(_bits_float(int.from_bytes(raw, order), 2))
            elif ch == "f":
                out.append(_bits_float(int.from_bytes(raw, order), 4))
            elif ch == "d":
                out.append(_bits_float(int.from_bytes(raw, order), 8))
            else:
                signed = ch in "bhilqn"
                out.append(int.from_bytes(raw, order, signed=signed))
    return tuple(out)


def unpack(fmt: str, buffer) -> tuple:
    need = calcsize(fmt)
    data = _buffer_bytes(buffer)
    if len(data) != need:
        _bad("unpack requires a buffer of %d bytes" % need)
    return unpack_from(fmt, data, 0)
