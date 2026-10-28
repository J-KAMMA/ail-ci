"""Little-endian integer and float access to the byte buffers `ail_ffi` passes to C (out-parameters, structs).

A C struct passed by pointer is a `bytearray` of the struct's size; its fields sit at the offsets the C compiler
gives them (`offsetof`). These helpers read and write the fields. They are plain Python with annotations, so
the same file runs under CPython and compiles to native code: copy it beside the program and `from ail_cbuf import ...`.
`@cstruct` uses the same helpers for its generated fields.

    q = bytearray(8)                  # struct { int32_t quot, rem; }
    div_out(7, 2, q)
    print(get_i32(q, 0), get_i32(q, 4))

The accessor families are `u8 i8 u16 i16 u32 i32 u64 i64 f32 f64`; `get_*` and `put_*` come in pairs. Integers
are 64 bit in AIL, so `get_i64` returns the signed value in both worlds; an unsigned 64 bit value >= 2**63 (an
address that high, a huge size_t) is out of scope. `get_f32`/`get_f64` handle zero and normal values exactly
(also infinity and NaN); `put_f32`/`put_f64` do not write subnormals, infinity or NaN. The 64 bit `put_*`
functions write the low 64 bits, like C's conversion to the field type.
"""


def get_u8(b: bytearray, at: int) -> int:
    return b[at]


def get_u16(b: bytearray, at: int) -> int:
    return b[at] | (b[at + 1] << 8)


def get_i16(b: bytearray, at: int) -> int:
    v = b[at] | (b[at + 1] << 8)
    if v >= 32768:
        v -= 65536
    return v


def get_u32(b: bytearray, at: int) -> int:
    return b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)


def get_i32(b: bytearray, at: int) -> int:
    v = b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)
    if v >= 2147483648:
        v -= 4294967296
    return v


def get_i8(b: bytearray, at: int) -> int:
    v = b[at]
    if v >= 128:
        v -= 256
    return v


def get_f32(b: bytearray, at: int) -> float:
    raw = b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)
    e = (raw >> 23) & 255
    m = raw & 8388607
    v = 0.0
    if e == 255:
        v = float("inf") if m == 0 else float("nan")
    elif e == 0:
        v = m * 2.0 ** -149
    else:
        v = (m + 8388608) * 2.0 ** (e - 150)
    if raw >= 2147483648:
        v = -v
    return v


def get_i64(b: bytearray, at: int) -> int:
    lo = b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)
    hi = b[at + 4] | (b[at + 5] << 8) | (b[at + 6] << 16) | (b[at + 7] << 24)
    if hi >= 2147483648:
        hi -= 4294967296
    return (hi << 32) | lo


def get_f64(b: bytearray, at: int) -> float:
    lo = b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24)
    hi = b[at + 4] | (b[at + 5] << 8) | (b[at + 6] << 16) | (b[at + 7] << 24)
    e = (hi >> 20) & 2047
    m = ((hi & 1048575) << 32) | lo
    v = 0.0
    if e == 2047:
        v = float("inf") if m == 0 else float("nan")
    elif e == 0:
        v = m * 2.0 ** -1074
    else:
        v = (m + 4503599627370496) * 2.0 ** (e - 1075)
    if hi >= 2147483648:
        v = -v
    return v


def put_u8(b: bytearray, at: int, v: int) -> None:
    b[at] = v & 255


def put_u16(b: bytearray, at: int, v: int) -> None:
    b[at] = v & 255
    b[at + 1] = (v >> 8) & 255


def put_i8(b: bytearray, at: int, v: int) -> None:
    b[at] = v & 255


def put_i16(b: bytearray, at: int, v: int) -> None:
    b[at] = v & 255
    b[at + 1] = (v >> 8) & 255


def put_u32(b: bytearray, at: int, v: int) -> None:
    b[at] = v & 255
    b[at + 1] = (v >> 8) & 255
    b[at + 2] = (v >> 16) & 255
    b[at + 3] = (v >> 24) & 255


def put_f32(b: bytearray, at: int, v: float) -> None:
    a = v
    sign = 0
    if a < 0.0:
        sign = 1
        a = -a
    if a == 0.0:
        put_u32(b, at, 0)
        if sign == 1:
            b[at + 3] = 128
        return
    e = 0
    while a >= 2.0:
        a = a / 2.0
        e += 1
    while a < 1.0:
        a = a * 2.0
        e -= 1
    mant = int((a - 1.0) * 8388608.0)
    raw = (sign << 31) | ((e + 127) << 23) | mant
    put_u32(b, at, raw)


def put_i32(b: bytearray, at: int, v: int) -> None:
    b[at] = v & 255
    b[at + 1] = (v >> 8) & 255
    b[at + 2] = (v >> 16) & 255
    b[at + 3] = (v >> 24) & 255


def put_i64(b: bytearray, at: int, v: int) -> None:
    put_i32(b, at, v & 4294967295)
    put_i32(b, at + 4, (v >> 32) & 4294967295)


def put_f64(b: bytearray, at: int, v: float) -> None:
    a = v
    sign = 0
    if a < 0.0:
        sign = 1
        a = -a
    if a == 0.0:
        put_i64(b, at, 0)
        if sign == 1:
            b[at + 7] = 128
        return
    e = 0
    while a >= 2.0:
        a = a / 2.0
        e += 1
    while a < 1.0:
        a = a * 2.0
        e -= 1
    mant = int((a - 1.0) * 4503599627370496.0)
    hi = (sign << 31) | ((e + 1023) << 20) | (mant >> 32)
    put_i32(b, at, mant & 4294967295)
    put_i32(b, at + 4, hi)
