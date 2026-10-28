"""G5b: the stdlib `struct` module for the formats the compiler lowers (structlib.py).

`structlib.py` rewrites `struct.pack`, `struct.unpack` / `unpack_from` in tuple assignments and
`struct.calcsize` with a literal format into the helpers this file supplies. Everything else is a
named compile-time refusal. The helpers here are the IEEE-754 conversions: `structlib.py` writes
the integer fields with `int.to_bytes` and reads them from the bytes itself, so only a float field
needs C to keep its exact bits.
"""
from ail_ffi import extern, c_double, c_int, c_int64



@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_double_bits")
def c_double_bits(value: c_double) -> c_int64: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_bits_double")
def c_bits_double(bits: c_int64) -> c_double: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_float_bits")
def c_float_bits(value: c_double) -> c_int: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_bits_float")
def c_bits_float(bits: c_int) -> c_double: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_float_overflow")
def c_float_overflow(value: c_double) -> c_int: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_half_bits")
def c_half_bits(value: c_double) -> c_int: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_bits_half")
def c_bits_half(bits: c_int) -> c_double: ...


@extern(lib="m", header="struct_glue.h", sources=["struct_glue.c"], symbol="ail_struct_half_overflow")
def c_half_overflow(value: c_double) -> c_int: ...


def double_bits(value: float) -> int:
    return c_double_bits(value)


def bits_double(bits: int) -> float:
    return c_bits_double(bits)


def float_bits(value: float) -> int:
    if c_float_overflow(value) != 0:
        raise OverflowError("float too large to pack with f format")
    return c_float_bits(value)


def bits_float(bits: int) -> float:
    return c_bits_float(bits)


def half_bits(value: float) -> int:
    if c_half_overflow(value) != 0:
        raise OverflowError("float too large to pack with e format")
    return c_half_bits(value)


def bits_half(bits: int) -> float:
    return c_bits_half(bits)

# `structlib.py` replaces every built call with one of the helpers above, so these stand-ins are
# only here because the merge checks that a module defines the names a program uses. A call that
# the pass refuses is left in the source, and the stand-in's empty signature then makes the compile
# fail instead of letting a half-lowered program run.
def pack() -> bytes:
    raise RuntimeError("struct.pack is lowered only for a literal format")
    return b""


def unpack() -> bytes:
    raise RuntimeError("struct.unpack is lowered only for a literal format in a tuple assignment")
    return b""


def unpack_from() -> bytes:
    raise RuntimeError("struct.unpack_from is lowered only for a literal format in a tuple assignment")
    return b""


def calcsize() -> int:
    raise RuntimeError("struct.calcsize is lowered only for a literal format")
    return 0
