from ail_ffi import *

link("./libwalk.a")


@extern(header="walk.h")
def walk(n: c_int32, cb: callback(c_int32, c_int32, on_error=-1)) -> c_int32: ...


def step(i: int) -> int:
    print("step", i)
    return i * i


def fail(i: int) -> int:
    print("fail", i)
    if i == 3:
        raise ValueError("stop at 3")
    return i


def main():
    print("sum", walk(4, step))
    print("empty", walk(0, step))
    try:
        print(walk(6, fail))
    except ValueError as error:
        print("caught:", error)
    print("done")


main()
