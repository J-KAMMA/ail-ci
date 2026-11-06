"""Implements (a subset of) Sun XDR -- eXternal Data Representation.

See: RFC 1014

This is CPython 3.12's Lib/xdrlib.py as AIL source.  Every class, method, signature and error
text is kept.  What the compiler refuses is rewritten:

* `io.BytesIO` becomes a list of `bytes` chunks joined in `get_buffer()`;
* the `@raise_conversion_error` decorator (only `@staticmethod` and `@lru_cache` decorators are
  built) becomes explicit type and range checks in each packing method, raising
  `ConversionError` with CPython's `struct.pack` text (`"'L' format requires 0 <= number <=
  4294967295"`, `"required argument is not an integer"`, `"required argument is not a float"`);
  `pack_uhyper` turns the `TypeError` from a non-integer argument into `ConversionError` with
  CPython's shift text, so a wrong type stops loudly instead of being coerced by `math`;
* `struct` is not a built module, so ints use `int.to_bytes`/`int.from_bytes` and floats are
  encoded/decoded from IEEE-754 fields with exactly representable power-of-two arithmetic;
* the `0x10000000000000000` constant in `unpack_hyper` (2**64, beyond int64) becomes a
  two's-complement magnitude computation that stays inside int64.

`unpack_uhyper` returns CPython's value when it fits int64; a value of 2**63 or more stops loudly
with `OverflowError`, because AIL ints are signed 64-bit.  `pack_uhyper` of any int64 value,
including 2**63 - 1, is exact.

CPython 3.12 prints a DeprecationWarning for `import xdrlib`; this module does not, and the lab
programs compare stdout and the exit status only.
"""

import math

__all__ = ["Error", "Packer", "Unpacker", "ConversionError"]

_UINT_MAX = 4294967295
_INT_MIN = -2147483648
_INT_MAX = 2147483647
_TWO52 = 4503599627370496.0


class Error(Exception):
    """Exception class for this module. Use:

    except xdrlib.Error as var:
        # var has the Error instance for the exception

    Public ivars:
        msg -- contains the message
    """

    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return repr(self.msg)

    def __str__(self):
        return str(self.msg)


class ConversionError(Error):
    pass


def _uint_bytes(x: int) -> bytes:
    if not isinstance(x, int):
        raise ConversionError("required argument is not an integer")
    if x < 0 or x > _UINT_MAX:
        raise ConversionError("'L' format requires 0 <= number <= 4294967295")
    return int(x).to_bytes(4, "big")


def _int_bytes(x: int) -> bytes:
    if not isinstance(x, int):
        raise ConversionError("required argument is not an integer")
    if x < _INT_MIN or x > _INT_MAX:
        raise ConversionError("'l' format requires -2147483648 <= number <= 2147483647")
    return int(x).to_bytes(4, "big", signed=True)


def _pow2(n: int) -> float:
    r = 1.0
    i = 0
    if n >= 0:
        while i < n:
            r = r * 2.0
            i = i + 1
    else:
        while i < -n:
            r = r / 2.0
            i = i + 1
    return r


def _split(x: float):
    """Return (sign, e, n) with x = n * 2**e exactly.

    A finite nonzero double is a normal (n in [2**52, 2**53), e >= -1074) or a subnormal
    (n < 2**52, e = -1074).  A zero is (sign, 0, 0); an infinity is (sign, 9999, 0) and a
    nan is (sign, 9999, 1)."""
    sign = 0
    if math.copysign(1.0, x) < 0.0:
        sign = 1
    a = math.fabs(x)
    if a == 0.0:
        return sign, 0, 0
    if math.isnan(a):
        return sign, 9999, 1
    if math.isinf(a):
        return sign, 9999, 0
    e = 0
    m = a
    while m >= 2.0:
        m = m / 2.0
        e = e + 1
    while m < 1.0 and e > -1022:
        m = m * 2.0
        e = e - 1
    if m < 1.0:
        return sign, -1074, int(m * _TWO52)
    return sign, e - 52, int((m - 1.0) * _TWO52) + (1 << 52)


def _double_bytes(x: float) -> bytes:
    if not isinstance(x, float) and not isinstance(x, int):
        raise ConversionError("required argument is not a float")
    sign, e, n = _split(x)
    if e == 9999:
        hi = (sign << 31) | (2047 << 20)
        if n != 0:
            hi = hi | (1 << 19)
        return hi.to_bytes(4, "big") + b"\0\0\0\0"
    if n == 0:
        return (sign << 31).to_bytes(4, "big") + b"\0\0\0\0"
    if n < (1 << 52):
        hi = (sign << 31) | (n >> 32)
        lo = n & _UINT_MAX
        return hi.to_bytes(4, "big") + lo.to_bytes(4, "big")
    frac = n - (1 << 52)
    hi = (sign << 31) | ((e + 1075) << 20) | (frac >> 32)
    lo = frac & _UINT_MAX
    return hi.to_bytes(4, "big") + lo.to_bytes(4, "big")


def _round_shift(n: int, shift: int) -> int:
    """Round n / 2**shift to nearest, ties to even."""
    if shift <= 0:
        return n << (-shift)
    if shift > 63:
        return 0
    q = n >> shift
    rem = n - (q << shift)
    half = 1 << (shift - 1)
    if rem > half:
        return q + 1
    if rem == half and (q & 1) != 0:
        return q + 1
    return q


def _float_bytes(x: float) -> bytes:
    if not isinstance(x, float) and not isinstance(x, int):
        raise ConversionError("required argument is not a float")
    sign, e, n = _split(x)
    if e == 9999:
        if n != 0:
            return ((sign << 31) | (255 << 23) | (1 << 22)).to_bytes(4, "big")
        return ((sign << 31) | (255 << 23)).to_bytes(4, "big")
    if n == 0:
        return (sign << 31).to_bytes(4, "big")
    nb = 0
    t = n
    while t > 0:
        nb = nb + 1
        t = t >> 1
    exp = nb - 1 + e
    if exp > 127:
        raise OverflowError("float too large to pack with f format")
    if exp < -126:
        f = _round_shift(n, -(e + 149))
        if f >= (1 << 23):
            return ((sign << 31) | (1 << 23)).to_bytes(4, "big")
        return ((sign << 31) | f).to_bytes(4, "big")
    sig = _round_shift(n, nb - 24)
    if sig >= (1 << 24):
        sig = sig >> 1
        exp = exp + 1
        if exp > 127:
            raise OverflowError("float too large to pack with f format")
    return ((sign << 31) | ((exp + 127) << 23) | (sig - (1 << 23))).to_bytes(4, "big")


class Packer:
    """Pack various data representations into a buffer."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.__buf = []

    def get_buffer(self):
        return b"".join(self.__buf)

    def get_buf(self):
        return self.get_buffer()

    def pack_uint(self, x):
        self.__buf.append(_uint_bytes(x))

    def pack_int(self, x):
        self.__buf.append(_int_bytes(x))

    def pack_enum(self, x):
        self.pack_int(x)

    def pack_bool(self, x):
        if x:
            self.__buf.append(b"\0\0\0\1")
        else:
            self.__buf.append(b"\0\0\0\0")

    def pack_uhyper(self, x):
        try:
            hi = x >> 32 & _UINT_MAX
            lo = x & _UINT_MAX
        except TypeError as e:
            raise ConversionError(str(e))
        self.pack_uint(hi)
        self.pack_uint(lo)

    def pack_hyper(self, x):
        self.pack_uhyper(x)

    def pack_float(self, x):
        self.__buf.append(_float_bytes(x))

    def pack_double(self, x):
        self.__buf.append(_double_bytes(x))

    def pack_fstring(self, n, s):
        if n < 0:
            raise ValueError("fstring size must be nonnegative")
        data = s[:n]
        n = ((n + 3) // 4) * 4
        data = data + (n - len(data)) * b"\0"
        self.__buf.append(data)

    def pack_fopaque(self, n, s):
        self.pack_fstring(n, s)

    def pack_string(self, s):
        n = len(s)
        self.pack_uint(n)
        self.pack_fstring(n, s)

    def pack_opaque(self, s):
        self.pack_string(s)

    def pack_bytes(self, s):
        self.pack_string(s)

    def pack_list(self, items, pack_item):
        for item in items:
            self.pack_uint(1)
            pack_item(item)
        self.pack_uint(0)

    def pack_farray(self, n, items, pack_item):
        if len(items) != n:
            raise ValueError("wrong array size")
        for item in items:
            pack_item(item)

    def pack_array(self, items, pack_item):
        n = len(items)
        self.pack_uint(n)
        self.pack_farray(n, items, pack_item)


class Unpacker:
    """Unpacks various data representations from the given buffer."""

    def __init__(self, data):
        self.reset(data)

    def reset(self, data):
        self.__buf = data
        self.__pos = 0

    def get_position(self):
        return self.__pos

    def set_position(self, position):
        self.__pos = position

    def get_buffer(self):
        return self.__buf

    def done(self):
        if self.__pos < len(self.__buf):
            raise Error("unextracted data remains")

    def unpack_uint(self):
        i = self.__pos
        self.__pos = j = i + 4
        data = self.__buf[i:j]
        if len(data) < 4:
            raise EOFError
        return int.from_bytes(data, "big")

    def unpack_int(self):
        i = self.__pos
        self.__pos = j = i + 4
        data = self.__buf[i:j]
        if len(data) < 4:
            raise EOFError
        return int.from_bytes(data, "big", signed=True)

    def unpack_enum(self):
        return self.unpack_int()

    def unpack_bool(self):
        return bool(self.unpack_int())

    def unpack_uhyper(self):
        hi = self.unpack_uint()
        lo = self.unpack_uint()
        return int(hi) << 32 | lo

    def unpack_hyper(self):
        hi = self.unpack_uint()
        lo = self.unpack_uint()
        if hi & 0x80000000:
            magnitude = ((~hi & 0x7fffffff) << 32) | (~lo & _UINT_MAX)
            return -magnitude - 1
        return (hi << 32) | lo

    def unpack_float(self):
        i = self.__pos
        self.__pos = j = i + 4
        data = self.__buf[i:j]
        if len(data) < 4:
            raise EOFError
        bits = int.from_bytes(data, "big")
        sign = 1.0
        if (bits >> 31) != 0:
            sign = -1.0
        exp = (bits >> 23) & 255
        frac = bits & 0x7fffff
        if exp == 255:
            if frac != 0:
                return math.nan
            return sign * math.inf
        if exp == 0:
            return sign * (frac * _pow2(-149))
        return sign * ((frac + 8388608) * _pow2(exp - 150))

    def unpack_double(self):
        i = self.__pos
        self.__pos = j = i + 8
        data = self.__buf[i:j]
        if len(data) < 8:
            raise EOFError
        hi = int.from_bytes(data[0:4], "big")
        lo = int.from_bytes(data[4:8], "big")
        sign = 1.0
        if (hi >> 31) != 0:
            sign = -1.0
        exp = (hi >> 20) & 2047
        frac = ((hi & 0xfffff) << 32) | lo
        if exp == 2047:
            if frac != 0:
                return math.nan
            return sign * math.inf
        if exp == 0:
            return sign * (frac * _pow2(-1074))
        return sign * ((frac + _TWO52) * _pow2(exp - 1075))

    def unpack_fstring(self, n):
        if n < 0:
            raise ValueError("fstring size must be nonnegative")
        i = self.__pos
        j = i + (n + 3) // 4 * 4
        if j > len(self.__buf):
            raise EOFError
        self.__pos = j
        return self.__buf[i:i + n]

    def unpack_fopaque(self, n):
        return self.unpack_fstring(n)

    def unpack_string(self):
        n = self.unpack_uint()
        return self.unpack_fstring(n)

    def unpack_opaque(self):
        return self.unpack_string()

    def unpack_bytes(self):
        return self.unpack_string()

    def unpack_list(self, unpack_item):
        result = []
        while True:
            x = self.unpack_uint()
            if x == 0:
                break
            if x != 1:
                raise ConversionError("0 or 1 expected, got %r" % (x,))
            result.append(unpack_item())
        return result

    def unpack_farray(self, n, unpack_item):
        result = []
        for i in range(n):
            result.append(unpack_item())
        return result

    def unpack_array(self, unpack_item):
        n = self.unpack_uint()
        return self.unpack_farray(n, unpack_item)
