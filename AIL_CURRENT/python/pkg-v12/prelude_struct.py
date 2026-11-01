# -*- coding: utf-8 -*-
# prelude_struct.py -- `struct` packing / unpacking as Python source (structlib.py injects what a program uses).
# The format parser follows CPython's _struct: native (the default and '@'), standard ('=', '<', '>', '!') sizes,
# whitespace, repeat counts, native alignment, and the error texts CPython raises. Floats are turned into their
# IEEE 754 bits with integer arithmetic (there is no struct to call underneath).
import math


class error(Exception):
    pass


def _ail_struct_tname(x) -> str:
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
    if isinstance(x, tuple):
        return "tuple"
    if isinstance(x, dict):
        return "dict"
    if x is None:
        return "NoneType"
    return "object"


def _ail_struct_rw_tname(x) -> str:
    if x is None:
        return "None"
    return type(x).__name__


# ---- the format ---------------------------------------------------------------------------------------------------
_STRUCT_NATIVE = {"b": (1, 1, "i"), "B": (1, 1, "i"), "?": (1, 1, "?"), "h": (2, 2, "i"), "H": (2, 2, "i"),
                  "i": (4, 4, "i"), "I": (4, 4, "i"), "l": (8, 8, "i"), "L": (8, 8, "i"),
                  "q": (8, 8, "i"), "Q": (8, 8, "i"), "n": (8, 8, "i"), "N": (8, 8, "i"), "P": (8, 8, "i"),
                  "e": (2, 2, "f"), "f": (4, 4, "f"), "d": (8, 8, "f")}
_STRUCT_STANDARD = {"b": (1, 1, "i"), "B": (1, 1, "i"), "?": (1, 1, "?"), "h": (2, 1, "i"), "H": (2, 1, "i"),
                    "i": (4, 1, "i"), "I": (4, 1, "i"), "l": (4, 1, "i"), "L": (4, 1, "i"),
                    "q": (8, 1, "i"), "Q": (8, 1, "i"), "e": (2, 1, "f"), "f": (4, 1, "f"), "d": (8, 1, "f")}
_STRUCT_WHITE = " \t\r\n\v\f"
_STRUCT_MAX = 9223372036854775807


def _ail_struct_bad() -> None:
    raise error("bad char in struct format")


def _ail_struct_format_text(fmt):
    if isinstance(fmt, bytes):
        s = ""
        for ch in fmt:
            s = s + chr(ch)
        fmt = s
    if not isinstance(fmt, str):
        raise TypeError("Struct() argument 1 must be a str or bytes object, not " + _ail_struct_tname(fmt))
    if "\x00" in fmt:
        raise error("embedded null character")
    return fmt


def _ail_struct_parse(fmt):
    """(items, size): items are (code, count, unit, offset)."""
    fmt = _ail_struct_format_text(fmt)
    order = "@"
    if len(fmt) > 0 and fmt[0] in "<>=!@":
        order = fmt[0]
        fmt = fmt[1:]
    native = order == "@" or order == "="
    table = _STRUCT_NATIVE if order == "@" else _STRUCT_STANDARD
    items = []
    offset = 0
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch in _STRUCT_WHITE:
            i = i + 1
            continue
        count = 1
        if ch >= "0" and ch <= "9":
            j = i
            while j < len(fmt) and fmt[j] >= "0" and fmt[j] <= "9":
                j = j + 1
            digits = fmt[i:j]
            first = 0
            while first < len(digits) and digits[first] == "0":
                first = first + 1
            significant = digits[first:]
            if len(significant) > 19 or (len(significant) == 19 and significant > "9223372036854775807"):
                raise error("total struct size too long")
            if significant == "":
                count = 0
            else:
                count = int(significant)
            i = j
            if i >= len(fmt):
                raise error("repeat count given without format specifier")
            ch = fmt[i]
        i = i + 1
        if ch == "x":
            if count > _STRUCT_MAX - offset:
                raise error("total struct size too long")
            items.append(("x", count, 1, offset))
            offset = offset + count
            continue
        if ch == "s" or ch == "p":
            if count > _STRUCT_MAX - offset:
                raise error("total struct size too long")
            items.append((ch, count, count, offset))
            offset = offset + count
            continue
        if ch == "c":
            if count > _STRUCT_MAX - offset:
                raise error("total struct size too long")
            items.append(("c", count, 1, offset))
            offset = offset + count
            continue
        if ch not in table:
            _ail_struct_bad()
        unit = table[ch][0]
        align = table[ch][1] if order == "@" else 1
        if align > 1 and offset % align != 0:
            pad = align - offset % align
            if pad > _STRUCT_MAX - offset:
                raise error("total struct size too long")
            offset = offset + pad
        if count > (_STRUCT_MAX - offset) // unit:
            raise error("total struct size too long")
        items.append((ch, count, unit, offset))
        offset = offset + unit * count
    return items, offset


def _ail_struct_count(items) -> int:
    total = 0
    for code, count, unit, offset in items:
        if code == "x":
            continue
        if code == "s" or code == "p":
            total = total + 1
        else:
            total = total + count
    return total


# ---- float bits ----------------------------------------------------------------------------------------------------
def _ail_struct_bits64(x: float):
    if x != x:
        sign = 0
        if _ail_struct_signbit(x):
            sign = 1
        return [sign * 2147483648 + 2146959360, 0]
    sign = 0
    y = x
    if _ail_struct_signbit(y):
        sign = 1
        y = 0.0 - y
    top = sign * 2147483648
    if y == 0.0:
        return [top, 0]
    if y == _ail_struct_inf():
        return [top + 2146435072, 0]
    if y < 2.2250738585072014e-308:
        s = int((y * 4.4989137945431964e+161) * 4.4989137945431964e+161)
        return [top + s // 4294967296, s % 4294967296]
    e = 0
    m = y
    if m >= 2.0:
        if m >= 1.3407807929942597e+154:
            m = m * 7.458340731200207e-155
            e = e + 512
        if m >= 1.157920892373162e+77:
            m = m * 8.636168555094445e-78
            e = e + 256
        if m >= 3.402823669209385e+38:
            m = m * 2.938735877055719e-39
            e = e + 128
        if m >= 1.8446744073709552e+19:
            m = m * 5.421010862427522e-20
            e = e + 64
        if m >= 4294967296.0:
            m = m * 2.3283064365386963e-10
            e = e + 32
        if m >= 65536.0:
            m = m * 1.52587890625e-05
            e = e + 16
        if m >= 256.0:
            m = m * 0.00390625
            e = e + 8
        if m >= 16.0:
            m = m * 0.0625
            e = e + 4
        if m >= 4.0:
            m = m * 0.25
            e = e + 2
        if m >= 2.0:
            m = m * 0.5
            e = e + 1
    elif m < 1.0:
        if m * 1.3407807929942597e+154 < 1.0:
            m = m * 1.3407807929942597e+154
            e = e - 512
        if m * 1.157920892373162e+77 < 1.0:
            m = m * 1.157920892373162e+77
            e = e - 256
        if m * 3.402823669209385e+38 < 1.0:
            m = m * 3.402823669209385e+38
            e = e - 128
        if m * 1.8446744073709552e+19 < 1.0:
            m = m * 1.8446744073709552e+19
            e = e - 64
        if m * 4294967296.0 < 1.0:
            m = m * 4294967296.0
            e = e - 32
        if m * 65536.0 < 1.0:
            m = m * 65536.0
            e = e - 16
        if m * 256.0 < 1.0:
            m = m * 256.0
            e = e - 8
        if m * 16.0 < 1.0:
            m = m * 16.0
            e = e - 4
        if m * 4.0 < 1.0:
            m = m * 4.0
            e = e - 2
        if m * 2.0 < 1.0:
            m = m * 2.0
            e = e - 1
        m = m * 2.0
        e = e - 1
    s = int((m - 1.0) * 4503599627370496.0)
    return [top + (e + 1023) * 1048576 + s // 4294967296, s % 4294967296]


def _ail_struct_signbit(x: float) -> bool:
    return math.copysign(1.0, x) < 0.0


def _ail_struct_inf() -> float:
    return math.inf


def _ail_struct_nan() -> float:
    return math.nan


def _ail_struct_scale(m: float, ex: int) -> float:
    r = m
    k = ex
    if k >= 0:
        if k >= 512:
            r = r * 1.3407807929942597e+154
            k = k - 512
        if k >= 256:
            r = r * 1.157920892373162e+77
            k = k - 256
        if k >= 128:
            r = r * 3.402823669209385e+38
            k = k - 128
        if k >= 64:
            r = r * 1.8446744073709552e+19
            k = k - 64
        if k >= 32:
            r = r * 4294967296.0
            k = k - 32
        if k >= 16:
            r = r * 65536.0
            k = k - 16
        if k >= 8:
            r = r * 256.0
            k = k - 8
        if k >= 4:
            r = r * 16.0
            k = k - 4
        if k >= 2:
            r = r * 4.0
            k = k - 2
        if k >= 1:
            r = r * 2.0
    else:
        k = 0 - k
        while k >= 512:
            r = r * 7.458340731200207e-155
            k = k - 512
        while k >= 256:
            r = r * 8.636168555094445e-78
            k = k - 256
        while k >= 128:
            r = r * 2.938735877055719e-39
            k = k - 128
        while k >= 64:
            r = r * 5.421010862427522e-20
            k = k - 64
        while k >= 32:
            r = r * 2.3283064365386963e-10
            k = k - 32
        while k >= 16:
            r = r * 1.52587890625e-05
            k = k - 16
        while k >= 8:
            r = r * 0.00390625
            k = k - 8
        while k >= 4:
            r = r * 0.0625
            k = k - 4
        while k >= 2:
            r = r * 0.25
            k = k - 2
        while k >= 1:
            r = r * 0.5
            k = k - 1
    return r


def _ail_struct_round_shift(v: int, shift: int) -> int:
    if shift <= 0:
        return v << (0 - shift)
    q = v >> shift
    rem = v & ((1 << shift) - 1)
    half = 1 << (shift - 1)
    if rem > half or (rem == half and q % 2 == 1):
        q = q + 1
    return q


def _ail_struct_f32_bits(x: float, overflow_inf: bool = False) -> int:
    hi, lo = _ail_struct_bits64(x)
    sign = hi >> 31
    exp = (hi >> 20) % 2048
    mant = ((hi % 1048576) << 32) + lo
    if exp == 2047:
        if mant != 0:
            return sign * 2147483648 + 2143289344
        return sign * 2147483648 + 2139095040
    if exp == 0:
        return sign * 2147483648
    m = 4503599627370496 + mant
    e = exp - 1023
    if e < -126:
        shift = 0 - 97 - e
        if shift > 53:
            return sign * 2147483648
        k = _ail_struct_round_shift(m, shift)
        if k >= 8388608:
            return sign * 2147483648 + 8388608
        return sign * 2147483648 + k
    k = _ail_struct_round_shift(m, 29)
    if k >= 16777216:
        k = k >> 1
        e = e + 1
    if e > 127:
        if overflow_inf:
            return sign * 2147483648 + 2139095040
        raise OverflowError("float too large to pack with f format")
    return sign * 2147483648 + (e + 127) * 8388608 + (k % 8388608)


def _ail_struct_f16_bits(x: float) -> int:
    hi, lo = _ail_struct_bits64(x)
    sign = hi >> 31
    exp = (hi >> 20) % 2048
    mant = ((hi % 1048576) << 32) + lo
    if exp == 2047:
        if mant != 0:
            return sign * 32768 + 32256
        return sign * 32768 + 31744
    if exp == 0:
        return sign * 32768
    m = 4503599627370496 + mant
    e = exp - 1023
    if e < -14:
        shift = 28 - e
        if shift > 53:
            return sign * 32768
        k = _ail_struct_round_shift(m, shift)
        if k >= 1024:
            return sign * 32768 + 1024
        return sign * 32768 + k
    k = _ail_struct_round_shift(m, 42)
    if k >= 2048:
        k = k >> 1
        e = e + 1
    if e > 15:
        raise OverflowError("float too large to pack with e format")
    return sign * 32768 + (e + 15) * 1024 + (k % 1024)


def _ail_struct_from_f32(bits: int) -> float:
    sign = bits >> 31
    exp = (bits >> 23) % 256
    mant = bits % 8388608
    if exp == 255:
        if mant == 0:
            r = _ail_struct_inf()
        else:
            r = _ail_struct_nan()
    elif exp == 0:
        r = _ail_struct_scale(float(mant), -149)
    else:
        r = _ail_struct_scale(1.0 + float(mant) * 1.1920928955078125e-07, exp - 127)
    if sign:
        r = math.copysign(r, -1.0)
    return r


def _ail_struct_from_f16(bits: int) -> float:
    sign = bits >> 15
    exp = (bits >> 10) % 32
    mant = bits % 1024
    if exp == 31:
        if mant == 0:
            r = _ail_struct_inf()
        else:
            r = _ail_struct_nan()
    elif exp == 0:
        r = _ail_struct_scale(float(mant), -24)
    else:
        r = _ail_struct_scale(1.0 + float(mant) * 0.0009765625, exp - 15)
    if sign:
        r = math.copysign(r, -1.0)
    return r


# ---- pack ----------------------------------------------------------------------------------------------------------
def _ail_struct_int_range(code: str, bits: int, signed: bool) -> None:
    if signed:
        if bits == 64:
            raise error("'" + code + "' format requires -9223372036854775808 <= number <= 9223372036854775807")
        raise error("'" + code + "' format requires " + str(0 - (1 << (bits - 1))) + " <= number <= "
                    + str((1 << (bits - 1)) - 1))
    if bits == 64:
        raise error("'" + code + "' format requires 0 <= number <= 18446744073709551615")
    raise error("'" + code + "' format requires 0 <= number <= " + str((1 << bits) - 1))


def _ail_struct_put_int(out, off: int, size: int, value: int, signed: bool, big: bool, code: str) -> None:
    bits = size * 8
    if signed:
        if bits == 64:
            if value < -9223372036854775807 - 1 or value > 9223372036854775807:
                _ail_struct_int_range(code, bits, True)
        elif value < 0 - (1 << (bits - 1)) or value > (1 << (bits - 1)) - 1:
            _ail_struct_int_range(code, bits, True)
    elif value < 0:
        _ail_struct_int_range(code, bits, False)
    elif bits < 64 and value > (1 << bits) - 1:
        _ail_struct_int_range(code, bits, False)
    k = 0
    while k < size:
        if big:
            exponent = size - 1 - k
        else:
            exponent = k
        out[off + k] = (value // (256 ** exponent)) % 256
        k = k + 1


def _ail_struct_put_float(out, off: int, size: int, value: float, code: str, big: bool) -> None:
    if code == "d":
        hi, lo = _ail_struct_bits64(value)
        if big:
            out[off] = hi // 16777216
            out[off + 1] = (hi // 65536) % 256
            out[off + 2] = (hi // 256) % 256
            out[off + 3] = hi % 256
            out[off + 4] = lo // 16777216
            out[off + 5] = (lo // 65536) % 256
            out[off + 6] = (lo // 256) % 256
            out[off + 7] = lo % 256
        else:
            out[off] = lo % 256
            out[off + 1] = (lo // 256) % 256
            out[off + 2] = (lo // 65536) % 256
            out[off + 3] = lo // 16777216
            out[off + 4] = hi % 256
            out[off + 5] = (hi // 256) % 256
            out[off + 6] = (hi // 65536) % 256
            out[off + 7] = hi // 16777216
    elif code == "f":
        bits = _ail_struct_f32_bits(value, _NATIVE_MODE[-1])
        k = 0
        while k < 4:
            if big:
                out[off + k] = (bits >> (8 * (3 - k))) % 256
            else:
                out[off + k] = (bits >> (8 * k)) % 256
            k = k + 1
    else:
        bits = _ail_struct_f16_bits(value)
        if big:
            out[off] = bits // 256
            out[off + 1] = bits % 256
        else:
            out[off] = bits % 256
            out[off + 1] = bits // 256


def _ail_struct_bytes(v, code: str):
    if not isinstance(v, bytes) and not isinstance(v, bytearray):
        raise error("argument for '" + code + "' must be a bytes object")
    return v


def _ail_struct_check_count(items, values, what: str) -> None:
    need = _ail_struct_count(items)
    if len(values) != need:
        raise error(what + " expected " + str(need) + " items for packing (got " + str(len(values)) + ")")


def _ail_struct_pack_items(items, size: int, values, what: str = "pack") -> bytes:
    _ail_struct_check_count(items, values, what)
    out = bytearray(size)
    k = 0
    for code, count, unit, offset in items:
        if code == "x":
            continue
        if code == "s" or code == "p":
            v = values[k]
            k = k + 1
            v = _ail_struct_bytes(v, code)
            if code == "p":
                n = len(v)
                if n > count - 1:
                    n = count - 1
                if count > 0:
                    out[offset] = n
                j = 0
                while j < n:
                    out[offset + 1 + j] = v[j]
                    j = j + 1
            else:
                n = len(v)
                if n > count:
                    n = count
                j = 0
                while j < n:
                    out[offset + j] = v[j]
                    j = j + 1
            continue
        j = 0
        while j < count:
            v = values[k]
            k = k + 1
            pos = offset + unit * j
            if code == "c":
                if not isinstance(v, bytes) or len(v) != 1:
                    raise error("char format requires a bytes object of length 1")
                out[pos] = v[0]
            elif code == "?":
                if v:
                    out[pos] = 1
                else:
                    out[pos] = 0
            elif code == "e" or code == "f" or code == "d":
                if not isinstance(v, int) and not isinstance(v, float):
                    raise error("required argument is not a float")
                _ail_struct_put_float(out, pos, unit, float(v), code, _ail_struct_big(items))
            else:
                if not isinstance(v, int):
                    raise error("required argument is not an integer")
                signed = code == "b" or code == "h" or code == "i" or code == "l" or code == "q" or code == "n"
                _ail_struct_put_int(out, pos, unit, int(v), signed, _ail_struct_big(items), code)
            j = j + 1
    return bytes(out)


_BIG = [False]
_NATIVE_MODE = [False]


def _ail_struct_big(items) -> bool:
    return _BIG[-1]


def _ail_struct_set_big(items, big: bool) -> None:
    _BIG[-1] = big


def _ail_struct_pack_with(big: bool, fmt, values) -> bytes:
    items, size = _ail_struct_parse(fmt)
    _ail_struct_set_big(items, big)
    return _ail_struct_pack_items(items, size, values)


# ---- unpack --------------------------------------------------------------------------------------------------------
def _ail_struct_get_int(data, off: int, size: int, signed: bool, big: bool) -> int:
    if size == 8 and signed:
        lower = 0
        if big:
            lower = (data[off] % 128) * 72057594037927936
            k = 1
            while k < 8:
                lower = lower + data[off + k] * (256 ** (7 - k))
                k = k + 1
            negative = data[off] >= 128
        else:
            lower = data[off] + data[off + 1] * 256 + data[off + 2] * 65536 + data[off + 3] * 16777216
            lower = lower + data[off + 4] * 4294967296 + data[off + 5] * 1099511627776
            lower = lower + data[off + 6] * 281474976710656 + (data[off + 7] % 128) * 72057594037927936
            negative = data[off + 7] >= 128
        if negative:
            return lower - 9223372036854775807 - 1
        return lower
    v = 0
    k = 0
    while k < size:
        if big:
            v = v * 256 + data[off + k]
        else:
            v = v + data[off + k] * (1 << (8 * k))
        k = k + 1
    if signed and v >= 1 << (size * 8 - 1):
        v = v - (1 << (size * 8))
    if not signed and size == 8 and v < 0:
        raise OverflowError("unsigned 64-bit value does not fit in int64")
    return v


def _ail_struct_get_float(data, off: int, size: int, code: str, big: bool) -> float:
    if code == "d":
        if big:
            hi = data[off] * 16777216 + data[off + 1] * 65536 + data[off + 2] * 256 + data[off + 3]
            lo = data[off + 4] * 16777216 + data[off + 5] * 65536 + data[off + 6] * 256 + data[off + 7]
        else:
            lo = data[off] + data[off + 1] * 256 + data[off + 2] * 65536 + data[off + 3] * 16777216
            hi = data[off + 4] + data[off + 5] * 256 + data[off + 6] * 65536 + data[off + 7] * 16777216
        return _ail_struct_from_bits64(hi, lo)
    if code == "f":
        bits = _ail_struct_get_int(data, off, 4, False, big)
        return _ail_struct_from_f32(bits)
    bits = _ail_struct_get_int(data, off, 2, False, big)
    return _ail_struct_from_f16(bits)


def _ail_struct_from_bits64(hi: int, lo: int) -> float:
    sign = hi >> 31
    exp = (hi >> 20) % 2048
    mant = (hi % 1048576) * 4294967296 + lo
    if exp == 2047:
        if mant == 0:
            r = _ail_struct_inf()
        else:
            r = _ail_struct_nan()
    elif exp == 0:
        r = _ail_struct_scale(float(mant), -1074)
    else:
        r = _ail_struct_scale(1.0 + float(mant) * 2.220446049250313e-16, exp - 1023)
    if sign:
        r = math.copysign(r, -1.0)
    return r


def _ail_struct_unpack_items(items, size: int, data, start: int):
    out = []
    for code, count, unit, offset in items:
        pos = start + offset
        if code == "x":
            continue
        if code == "s":
            out.append(bytes(data[pos:pos + count]))
            continue
        if code == "p":
            if count == 0:
                raise error("Negative size passed to PyBytes_FromStringAndSize")
            n = data[pos]
            if n > count - 1:
                n = count - 1
            out.append(bytes(data[pos + 1:pos + 1 + n]))
            continue
        j = 0
        while j < count:
            p = pos + unit * j
            if code == "c":
                out.append(bytes(data[p:p + 1]))
            elif code == "?":
                out.append(data[p] != 0)
            elif code == "e" or code == "f" or code == "d":
                out.append(_ail_struct_get_float(data, p, unit, code, _ail_struct_big(items)))
            else:
                signed = code == "b" or code == "h" or code == "i" or code == "l" or code == "q" or code == "n"
                out.append(_ail_struct_get_int(data, p, unit, signed, _ail_struct_big(items)))
            j = j + 1
    return tuple(out)


def _ail_struct_is_buffer(data) -> bool:
    return isinstance(data, bytes) or isinstance(data, bytearray)


def _ail_struct_is_array(buffer) -> bool:
    return type(buffer).__name__ == "_AilArray"


def _ail_struct_is_rw_buffer(buffer) -> bool:
    return isinstance(buffer, bytearray) or _ail_struct_is_array(buffer)


def _ail_struct_buffer_len(buffer) -> int:
    if _ail_struct_is_array(buffer):
        return len(buffer) * buffer.itemsize
    return len(buffer)


def _ail_struct_array_bytes(buffer) -> bytearray:
    tc = buffer.typecode
    size = buffer.itemsize
    n = len(buffer)
    out = bytearray(n * size)
    p = 0
    i = 0
    if tc == "d":
        while i < n:
            _ail_struct_put_float(out, p, 8, buffer.data[i], "d", False)
            p = p + 8
            i = i + 1
        return out
    signed = tc == "b" or tc == "h" or tc == "i" or tc == "l" or tc == "q"
    while i < n:
        _ail_struct_put_int(out, p, size, buffer.data[i], signed, False, tc)
        p = p + size
        i = i + 1
    return out


def _ail_struct_array_set(buffer, raw) -> None:
    tc = buffer.typecode
    size = buffer.itemsize
    n = len(buffer)
    p = 0
    i = 0
    if tc == "d":
        doubles = []
        while i < n:
            doubles.append(_ail_struct_get_float(raw, p, 8, "d", False))
            p = p + 8
            i = i + 1
        buffer.data = doubles
        return
    signed = tc == "b" or tc == "h" or tc == "i" or tc == "l" or tc == "q"
    ints = []
    while i < n:
        ints.append(_ail_struct_get_int(raw, p, size, signed, False))
        p = p + size
        i = i + 1
    buffer.data = ints


def _ail_struct_store(buffer, offset: int, packed) -> None:
    if not _ail_struct_is_array(buffer):
        k = 0
        while k < len(packed):
            buffer[offset + k] = packed[k]
            k = k + 1
        return
    raw = _ail_struct_array_bytes(buffer)
    k = 0
    while k < len(packed):
        raw[offset + k] = packed[k]
        k = k + 1
    _ail_struct_array_set(buffer, raw)


def _ail_struct_pack_values(fmt, values) -> bytes:
    items, size = _ail_struct_parse(fmt)
    _ail_struct_set_big(items, _ail_struct_big_of(fmt))
    _NATIVE_MODE[-1] = _ail_struct_native_of(fmt)
    return _ail_struct_pack_items(items, size, values)


def _ail_struct_pack(*args):
    return _ail_struct_pack_values(args[0], args[1:])


def _ail_struct_expand(*parts):
    out = []
    for part in parts:
        for item in part:
            out.append(item)
    return out


def _ail_struct_pack_seq(fmt, values) -> bytes:
    return _ail_struct_pack_values(fmt, values)




def _ail_struct_unpack(fmt, data):
    items, size = _ail_struct_parse(fmt)
    if not _ail_struct_is_buffer(data):
        raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")
    if len(data) != size:
        raise error("unpack requires a buffer of " + str(size) + " bytes")
    _ail_struct_set_big(items, _ail_struct_big_of(fmt))
    return _ail_struct_unpack_items(items, size, data, 0)


def _ail_struct_big_of(fmt) -> bool:
    fmt = _ail_struct_format_text(fmt)
    if len(fmt) > 0 and (fmt[0] == ">" or fmt[0] == "!"):
        return True
    return False


def _ail_struct_native_of(fmt) -> bool:
    fmt = _ail_struct_format_text(fmt)
    if len(fmt) == 0:
        return True
    return fmt[0] not in "<>=!"


def _ail_struct_calcsize(fmt) -> int:
    items, size = _ail_struct_parse(fmt)
    return size


def _ail_struct_unpack_from(fmt, data, offset: int = 0):
    items, size = _ail_struct_parse(fmt)
    if not _ail_struct_is_buffer(data):
        raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")
    if offset < 0:
        original = offset
        offset = offset + len(data)
        if offset < 0:
            raise error("offset " + str(original) + " out of range for " + str(len(data)) + "-byte buffer")
        if offset + size > len(data):
            raise error("not enough data to unpack " + str(size) + " bytes at offset "
                                  + str(original))
    elif offset + size > len(data):
        raise error("unpack_from requires a buffer of at least " + str(offset + size)
                              + " bytes for unpacking " + str(size) + " bytes at offset " + str(offset)
                              + " (actual buffer size is " + str(len(data)) + ")")
    _ail_struct_set_big(items, _ail_struct_big_of(fmt))
    return _ail_struct_unpack_items(items, size, data, offset)


def _ail_struct_pack_into_values(fmt, buffer, offset: int, values) -> None:
    items, size = _ail_struct_parse(fmt)
    _ail_struct_check_count(items, values, "pack_into")
    if not _ail_struct_is_rw_buffer(buffer):
        raise TypeError("argument must be read-write bytes-like object, not " + _ail_struct_rw_tname(buffer))
    total = _ail_struct_buffer_len(buffer)
    if offset < 0:
        original = offset
        offset = offset + total
        if offset < 0:
            raise error("offset " + str(original) + " out of range for " + str(total) + "-byte buffer")
        if offset + size > total:
            raise error("no space to pack " + str(size) + " bytes at offset " + str(original))
    elif offset + size > total:
        raise error("pack_into requires a buffer of at least " + str(offset + size)
                    + " bytes for packing " + str(size) + " bytes at offset " + str(offset)
                    + " (actual buffer size is " + str(total) + ")")
    _ail_struct_set_big(items, _ail_struct_big_of(fmt))
    _NATIVE_MODE[-1] = _ail_struct_native_of(fmt)
    packed = _ail_struct_pack_items(items, size, values, "pack_into")
    _ail_struct_store(buffer, offset, packed)


def _ail_struct_pack_into(*args):
    _ail_struct_pack_into_values(args[0], args[1], args[2], args[3:])


def _ail_struct_pack_into_seq(fmt, buffer, offset: int, values) -> None:
    _ail_struct_pack_into_values(fmt, buffer, offset, values)




def _ail_struct_iter_unpack(fmt, data):
    items, size = _ail_struct_parse(fmt)
    if not _ail_struct_is_buffer(data):
        raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")
    if size == 0:
        raise error("cannot iteratively unpack with a struct of length 0")
    if len(data) % size != 0:
        raise error("iterative unpacking requires a buffer of a multiple of " + str(size) + " bytes")
    _ail_struct_set_big(items, _ail_struct_big_of(fmt))
    out = []
    offset = 0
    while offset < len(data):
        out.append(_ail_struct_unpack_items(items, size, data, offset))
        offset = offset + size
    return out


class _AilStruct:
    def __init__(self, format):
        items, size = _ail_struct_parse(format)
        self.format = _ail_struct_format_text(format)
        self.size = size
        self._items = items
        self._big = _ail_struct_big_of(self.format)
        self._native = _ail_struct_native_of(self.format)

    def pack(self, *values) -> bytes:
        _ail_struct_set_big(self._items, self._big)
        _NATIVE_MODE[-1] = self._native
        return _ail_struct_pack_items(self._items, self.size, values)

    def unpack(self, data):
        if not _ail_struct_is_buffer(data):
            raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")
        if len(data) != self.size:
            raise error("unpack requires a buffer of " + str(self.size) + " bytes")
        _ail_struct_set_big(self._items, self._big)
        return _ail_struct_unpack_items(self._items, self.size, data, 0)

    def pack_into(self, buffer, offset: int, *values) -> None:
        _ail_struct_check_count(self._items, values, "pack_into")
        if not _ail_struct_is_rw_buffer(buffer):
            raise TypeError("argument must be read-write bytes-like object, not " + _ail_struct_rw_tname(buffer))
        total = _ail_struct_buffer_len(buffer)
        if offset < 0:
            original = offset
            offset = offset + total
            if offset < 0:
                raise error("offset " + str(original) + " out of range for " + str(total) + "-byte buffer")
            if offset + self.size > total:
                raise error("no space to pack " + str(self.size) + " bytes at offset " + str(original))
        elif offset + self.size > total:
            raise error("pack_into requires a buffer of at least " + str(offset + self.size)
                                  + " bytes for packing " + str(self.size) + " bytes at offset " + str(offset)
                                  + " (actual buffer size is " + str(total) + ")")
        _ail_struct_set_big(self._items, self._big)
        _NATIVE_MODE[-1] = self._native
        packed = _ail_struct_pack_items(self._items, self.size, values, "pack_into")
        _ail_struct_store(buffer, offset, packed)

    def unpack_from(self, data, offset: int = 0):
        if not _ail_struct_is_buffer(data):
            raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")
        if offset < 0:
            original = offset
            offset = offset + len(data)
            if offset < 0:
                raise error("offset " + str(original) + " out of range for " + str(len(data)) + "-byte buffer")
            if offset + self.size > len(data):
                raise error("not enough data to unpack " + str(self.size) + " bytes at offset "
                                      + str(original))
        elif offset + self.size > len(data):
            raise error("unpack_from requires a buffer of at least " + str(offset + self.size)
                                  + " bytes for unpacking " + str(self.size) + " bytes at offset " + str(offset)
                                  + " (actual buffer size is " + str(len(data)) + ")")
        _ail_struct_set_big(self._items, self._big)
        return _ail_struct_unpack_items(self._items, self.size, data, offset)

    def iter_unpack(self, data):
        if not _ail_struct_is_buffer(data):
            raise TypeError("a bytes-like object is required, not '" + _ail_struct_tname(data) + "'")
        if self.size == 0:
            raise error("cannot iteratively unpack with a struct of length 0")
        if len(data) % self.size != 0:
            raise error("iterative unpacking requires a buffer of a multiple of " + str(self.size) + " bytes")
        _ail_struct_set_big(self._items, self._big)
        out = []
        offset = 0
        while offset < len(data):
            out.append(_ail_struct_unpack_items(self._items, self.size, data, offset))
            offset = offset + self.size
        return out
