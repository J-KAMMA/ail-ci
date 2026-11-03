from ail_ffi import *

link("m")

@extern(header="math.h", symbol="cbrt")
def c_cbrt(x: c_double) -> c_double: ...

@extern(header="math.h", symbol="hypot")
def c_hypot(x: c_double, y: c_double) -> c_double: ...

@extern(header="math.h", symbol="fma")
def c_fma(x: c_double, y: c_double, z: c_double) -> c_double: ...

@extern(header="math.h", symbol="frexp")
def c_frexp(x: c_double, e: ptr(c_int)) -> c_double: ...


def read_i32(b: bytearray) -> int:
    v = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
    if v >= 2147483648:
        v -= 4294967296
    return v


def show(x: float) -> None:
    e = bytearray(4)
    m = c_frexp(x, e)
    print(repr(x), repr(c_cbrt(x)), repr(c_hypot(x, 1.0)),
          repr(c_fma(x, x, x)), repr(m), read_i32(e))


def main():
    show(-0.0)
    show(float("inf"))
    show(5e-324)
    show(0.0)
    show(8.0)
    show(-27.5)


main()
