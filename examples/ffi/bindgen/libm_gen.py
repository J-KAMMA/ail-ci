import math_gen_ffi


def show(x: float) -> None:
    print(repr(x),
          repr(math_gen_ffi.sin(x)),
          repr(math_gen_ffi.cos(x)),
          repr(math_gen_ffi.tan(x)),
          repr(math_gen_ffi.exp(x)),
          repr(math_gen_ffi.log(math_gen_ffi.fabs(x))),
          repr(math_gen_ffi.sqrt(math_gen_ffi.fabs(x))),
          repr(math_gen_ffi.fma(x, x, x)),
          repr(math_gen_ffi.pow(math_gen_ffi.fabs(x), 2.0)))


def main():
    show(-0.0)
    show(float("inf"))
    show(float("-inf"))
    show(float("nan"))
    show(5e-324)
    show(0.0)
    show(2.5)
    show(-27.5)


main()
