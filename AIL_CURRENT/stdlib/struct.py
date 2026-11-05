"""struct1: the standard-library `struct` module (pack, unpack, calcsize, Struct) as AIL source.

A program compiled by AIL finds this file when its own directory has no `struct.py`
(`ail_modules.py` searches the bundled `stdlib/` last), so `import struct` builds the documented
CPython 3.12 behaviour: the byte orders `<`, `>`, `!`, `=` and native `@`, a repeat count
(`"3h"`), the codes `x c b B ? h H i I l L q Q n N s p`, `pack`, `unpack`, `calcsize`,
`pack_into`, `unpack_from`, `iter_unpack`, and the `Struct` class with `.size` and `.format`.
Error texts are CPython's, including `'h' format requires -32768 <= number <= 32767`,
`unpack requires a buffer of 4 bytes`, `bad char in struct format` and
`pack expected 1 items for packing (got 2)`.

The float codes `e`, `f` and `d` are not built yet: exact IEEE-754 conversion is not in this
file, so packing or unpacking one raises
`NotImplementedError("struct: float formats are not built yet")`.

Values are AIL's int64. A `Q`/`N` value that does not fit int64 cannot be represented, so
unpacking one stops loudly (as the compiler's own int arithmetic does); packing a value that
fits is exact. `s`/`p`/`c` take bytes or bytearray; a `str` is refused with CPython's message.
"""

__all__ = ["error", "pack", "unpack", "calcsize", "pack_into", "unpack_from", "iter_unpack",
           "Struct"]

_SIZES_STD = {'x': 1, 'c': 1, 'b': 1, 'B': 1, '?': 1,
              'h': 2, 'H': 2,
              'i': 4, 'I': 4,
              'l': 4, 'L': 4,
              'q': 8, 'Q': 8,
              'f': 4, 'd': 8, 'e': 2,
              's': 1, 'p': 1}

_SIZES_NATIVE = {'x': 1, 'c': 1, 'b': 1, 'B': 1, '?': 1,
                 'h': 2, 'H': 2,
                 'i': 4, 'I': 4,
                 'l': 8, 'L': 8,
                 'q': 8, 'Q': 8,
                 'f': 4, 'd': 8, 'e': 2,
                 'n': 8, 'N': 8,
                 's': 1, 'p': 1}

_SIGNED = frozenset(('b', 'h', 'i', 'l', 'q', 'n'))
_FLOATS = frozenset(('e', 'f', 'd'))
_SPACE = " \t\n\r"


class error(Exception):
    """Raised for a bad format or an argument the format cannot hold."""

    pass


def _is_bytes(value) -> bool:
    return isinstance(value, bytes) or isinstance(value, bytearray)



def _parse(format) -> tuple:
    """(little, native, items, size, offsets) for a format string.

    `items` is a list of (code, count); `offsets` is the byte offset of each item and `size` the
    total size, with native alignment applied for `@` (the default)."""
    fmt = format
    if isinstance(fmt, bytes) or isinstance(fmt, bytearray):
        fmt = bytes(fmt).decode("ascii")
    if not isinstance(fmt, str):
        raise error("format must be str or bytes")
    little = True   # the module targets little-endian hosts (x86-64 Linux)
    native = True
    i = 0
    if len(fmt) > 0 and fmt[0] in '<>!@=':
        first = fmt[0]
        i = 1
        if first == '<':
            little = True
            native = False
        elif first == '>':
            little = False
            native = False
        elif first == '!':
            little = False
            native = False
        elif first == '=':
            native = False
    items: list = []
    while i < len(fmt):
        c = fmt[i]
        if c in _SPACE:
            i = i + 1
            continue
        if c in '<>!@=':
            raise error("bad char in struct format")
        count = 1
        digits = ""
        while i < len(fmt) and fmt[i] >= '0' and fmt[i] <= '9':
            digits = digits + fmt[i]
            i = i + 1
        if digits != "":
            count = int(digits)
        if i >= len(fmt):
            raise error("bad char in struct format")
        c = fmt[i]
        i = i + 1
        if c not in _SIZES_NATIVE:
            raise error("bad char in struct format")
        if (c == 'n' or c == 'N') and not native:
            raise error("bad char in struct format")
        items.append((c, count))
    offsets, size = _layout(native, items)
    return (little, native, items, size, offsets)


def _item_size(code: str, native: bool) -> int:
    if native:
        return _SIZES_NATIVE[code]
    return _SIZES_STD[code]


def _layout(native: bool, items) -> tuple:
    offsets: list = []
    pos = 0
    for item in items:
        code = item[0]
        count = item[1]
        if code == 'x' or code == 'c' or code == 's' or code == 'p':
            size = 1
            align = 1
        else:
            size = _item_size(code, native)
            if native:
                align = size
            else:
                align = 1
        pos = (pos + align - 1) // align * align
        offsets.append(pos)
        if code == 'x':
            pos = pos + count
        elif code == 's' or code == 'p' or code == 'c':
            pos = pos + count
        else:
            pos = pos + size * count
    return (offsets, pos)


def _range_text(code: str, native: bool) -> str:
    if code == 'b':
        return "'b' format requires -128 <= number <= 127"
    if code == 'B':
        return "'B' format requires 0 <= number <= 255"
    if code == 'h':
        return "'h' format requires -32768 <= number <= 32767"
    if code == 'H':
        return "'H' format requires 0 <= number <= 65535"
    if code == 'i':
        return "'i' format requires -2147483648 <= number <= 2147483647"
    if code == 'I':
        return "'I' format requires 0 <= number <= 4294967295"
    if code == 'q':
        return "'q' format requires -9223372036854775808 <= number <= 9223372036854775807"
    if code == 'Q':
        return "'Q' format requires 0 <= number <= 18446744073709551615"
    if code == 'l':
        if native:
            return "'l' format requires -9223372036854775808 <= number <= 9223372036854775807"
        return "'l' format requires -2147483648 <= number <= 2147483647"
    if code == 'L':
        if native:
            return "'L' format requires 0 <= number <= 18446744073709551615"
        return "'L' format requires 0 <= number <= 4294967295"
    if code == 'n':
        return "'n' format requires -9223372036854775808 <= number <= 9223372036854775807"
    return "'N' format requires 0 <= number <= 18446744073709551615"


def _check_int(code: str, value, native: bool) -> int:
    if not isinstance(value, int):
        raise error("required argument is not an integer")
    lo = 0
    hi = 0
    if code == 'b':
        lo, hi = -128, 127
    elif code == 'B':
        lo, hi = 0, 255
    elif code == 'h':
        lo, hi = -32768, 32767
    elif code == 'H':
        lo, hi = 0, 65535
    elif code == 'i':
        lo, hi = -2147483648, 2147483647
    elif code == 'I':
        lo, hi = 0, 4294967295
    elif code == 'q' or code == 'n' or (code == 'l' and native):
        lo, hi = -9223372036854775808, 9223372036854775807
    elif code == 'l':
        lo, hi = -2147483648, 2147483647
    else:
        # Q, N, L native: the upper bound is beyond int64, so a non-negative int64 always fits
        if value < 0:
            raise error(_range_text(code, native))
        return value
    if value < lo or value > hi:
        raise error(_range_text(code, native))
    return value


def _put_int(out: bytearray, pos: int, width: int, value: int, signed: bool, little: bool) -> None:
    order = "little"
    if not little:
        order = "big"
    out[pos:pos + width] = value.to_bytes(width, order, signed=signed)


def _pack_into_items(out: bytearray, items, offsets, native: bool, little: bool, values) -> None:
    expected = 0
    for item in items:
        if item[0] == 'x':
            continue
        if item[0] == 's' or item[0] == 'p':
            expected = expected + 1
        else:
            expected = expected + item[1]
    if expected != len(values):
        raise error("pack expected %d items for packing (got %d)" % (expected, len(values)))
    index = 0
    for k in range(len(items)):
        code = items[k][0]
        count = items[k][1]
        pos = offsets[k]
        if code == 'x':
            continue
        if code in _FLOATS:
            raise NotImplementedError("struct: float formats are not built yet")
        if code == '?':
            for n in range(count):
                b = 0
                if values[index]:
                    b = 1
                out[pos + n] = b
                index = index + 1
        elif code == 'c':
            for n in range(count):
                v = values[index]
                if not _is_bytes(v) or len(v) != 1:
                    raise error("char format requires a bytes object of length 1")
                out[pos + n] = v[0]
                index = index + 1
        elif code == 's':
            v = values[index]
            if not _is_bytes(v):
                raise error("argument for 's' must be a bytes object")
            raw = bytes(v)
            n = len(raw)
            if n > count:
                n = count
            for m in range(n):
                out[pos + m] = raw[m]
            index = index + 1
        elif code == 'p':
            v = values[index]
            if not _is_bytes(v):
                raise error("argument for 'p' must be a bytes object")
            raw = bytes(v)
            limit = count - 1
            if limit < 0:
                limit = 0
            n = len(raw)
            if n > limit:
                n = limit
            out[pos] = n
            for m in range(n):
                out[pos + 1 + m] = raw[m]
            index = index + 1
        else:
            width = _item_size(code, native)
            signed = code in _SIGNED
            for n in range(count):
                v = _check_int(code, values[index], native)
                _put_int(out, pos, width, v, signed, little)
                pos = pos + width
                index = index + 1


def _unpack_items(data, items, offsets, native: bool, little: bool) -> tuple:
    order = "little"
    if not little:
        order = "big"
    result: list = []
    for k in range(len(items)):
        code = items[k][0]
        count = items[k][1]
        pos = offsets[k]
        if code == 'x':
            continue
        if code in _FLOATS:
            raise NotImplementedError("struct: float formats are not built yet")
        if code == '?':
            for n in range(count):
                result.append(data[pos + n] != 0)
        elif code == 'c':
            for n in range(count):
                result.append(bytes(data[pos + n:pos + n + 1]))
        elif code == 's':
            result.append(bytes(data[pos:pos + count]))
        elif code == 'p':
            used = 0
            if count > 0:
                used = data[pos]
                if used > count - 1:
                    used = count - 1
            result.append(bytes(data[pos + 1:pos + 1 + used]))
        else:
            width = _item_size(code, native)
            signed = code in _SIGNED
            for n in range(count):
                chunk = bytes(data[pos:pos + width])
                result.append(int.from_bytes(chunk, order, signed=signed))
                pos = pos + width
    return tuple(result)


def calcsize(format) -> int:
    """calcsize(fmt) -> int: the number of bytes the format occupies."""
    return _parse(format)[3]


def pack(format, *values) -> bytes:
    """pack(fmt, v1, v2, ...) -> bytes: the values packed according to the format."""
    parsed = _parse(format)
    out = bytearray(parsed[3])
    _pack_into_items(out, parsed[2], parsed[4], parsed[1], parsed[0], values)
    return bytes(out)


def unpack(format, buffer) -> tuple:
    """unpack(fmt, buffer) -> tuple: the values the buffer holds, one item per format item."""
    parsed = _parse(format)
    data = bytes(buffer)
    if len(data) != parsed[3]:
        raise error("unpack requires a buffer of %d bytes" % parsed[3])
    return _unpack_items(data, parsed[2], parsed[4], parsed[1], parsed[0])


def pack_into(format, buffer, offset, *values) -> None:
    """pack_into(fmt, buffer, offset, v1, ...): write the values into a writable buffer."""
    if not isinstance(buffer, bytearray):
        raise TypeError("pack_into requires a writable buffer")
    parsed = _parse(format)
    size = parsed[3]
    need = offset + size
    if offset < 0 or len(buffer) < need:
        raise error("pack_into requires a buffer of at least %d bytes for packing %d bytes at "
                    "offset %d (actual buffer size is %d)"
                    % (need, size, offset, len(buffer)))
    target = bytearray(size)
    _pack_into_items(target, parsed[2], parsed[4], parsed[1], parsed[0], values)
    for i in range(size):
        buffer[offset + i] = target[i]


def unpack_from(format, buffer, offset: int = 0) -> tuple:
    """unpack_from(fmt, buffer, offset=0) -> tuple: unpack starting at offset."""
    parsed = _parse(format)
    size = parsed[3]
    need = offset + size
    if offset < 0 or len(buffer) < need:
        raise error("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes at "
                    "offset %d (actual buffer size is %d)"
                    % (need, size, offset, len(buffer)))
    data = bytes(buffer[offset:offset + size])
    return _unpack_items(data, parsed[2], parsed[4], parsed[1], parsed[0])


def _iter_records(parsed, data, size):
    i = 0
    while i + size <= len(data):
        yield _unpack_items(data[i:i + size], parsed[2], parsed[4], parsed[1], parsed[0])
        i = i + size


def iter_unpack(format, buffer):
    """iter_unpack(fmt, buffer) -> iterator of tuples, one per record."""
    parsed = _parse(format)
    size = parsed[3]
    if size == 0:
        raise error("cannot iteratively unpack with a struct of length 0")
    data = bytes(buffer)
    if len(data) % size != 0:
        raise error("iterative unpacking requires a buffer of a multiple of %d bytes" % size)
    return _iter_records(parsed, data, size)


class Struct:
    """Struct(fmt): a format parsed once, with .format and .size and the pack/unpack methods."""

    def __init__(self, format):
        parsed = _parse(format)
        self.format = format
        self._little = parsed[0]
        self._native = parsed[1]
        self._items = parsed[2]
        self._offsets = parsed[4]
        self.size = parsed[3]

    def pack(self, *values) -> bytes:
        out = bytearray(self.size)
        _pack_into_items(out, self._items, self._offsets, self._native, self._little, values)
        return bytes(out)

    def unpack(self, buffer) -> tuple:
        data = bytes(buffer)
        if len(data) != self.size:
            raise error("unpack requires a buffer of %d bytes" % self.size)
        return _unpack_items(data, self._items, self._offsets, self._native, self._little)

    def pack_into(self, buffer, offset, *values) -> None:
        if not isinstance(buffer, bytearray):
            raise TypeError("pack_into requires a writable buffer")
        need = offset + self.size
        if offset < 0 or len(buffer) < need:
            raise error("pack_into requires a buffer of at least %d bytes for packing %d bytes at "
                        "offset %d (actual buffer size is %d)"
                        % (need, self.size, offset, len(buffer)))
        target = bytearray(self.size)
        _pack_into_items(target, self._items, self._offsets, self._native, self._little, values)
        for i in range(self.size):
            buffer[offset + i] = target[i]

    def unpack_from(self, buffer, offset: int = 0) -> tuple:
        need = offset + self.size
        if offset < 0 or len(buffer) < need:
            raise error("unpack_from requires a buffer of at least %d bytes for unpacking %d bytes "
                        "at offset %d (actual buffer size is %d)"
                        % (need, self.size, offset, len(buffer)))
        data = bytes(buffer[offset:offset + self.size])
        return _unpack_items(data, self._items, self._offsets, self._native, self._little)

    def iter_unpack(self, buffer):
        return iter_unpack(self.format, buffer)
