import math
import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def fill(n: int, seed0: int) -> ta.Array[ta.f64]:
    a = ta.zeros(n, ta.f64)
    seed = seed0
    for k in range(n):
        seed = (seed * 1103515245 + 12345) % 2147483648
        a[k] = (seed % 20001 - 10000) / 3.0
    return a


def ext(cell: str, a: ta.Array[ta.f64]):
    print("min f64|", cell, ta.min(a), bits(ta.min(a)))
    print("max f64|", cell, ta.max(a), bits(ta.max(a)))
    print("argmin f64|", cell, ta.argmin(a))
    print("argmax f64|", cell, ta.argmax(a))


def main():
    for n in [0, 1, 15, 16, 17, 1023, 1024, 1025, 2049, 5000]:
        a = fill(n, n + 1)
        b = fill(n, n + 77)
        print("sum f64|", n, bits(ta.sum(a)), ta.sum(a))
        print("dot f64|", n, bits(ta.dot(a, b)), ta.dot(a, b))
    for pos in [0, 15, 16, 1023, 1024, 1025]:
        a = fill(1100, pos)
        a[pos] = math.nan
        print("sum f64|", pos, bits(ta.sum(a)))
        print("dot f64|", pos, bits(ta.dot(a, a)))
        a[pos] = math.inf
        a[1099 - pos] = -math.inf
        print("sum f64|", pos, bits(ta.sum(a)))
    z = ta.array([-0.0, -0.0], ta.f64)
    print("sum f64|", bits(ta.sum(z)), bits(ta.sum(ta.array([-0.0, 0.0], ta.f64))), bits(ta.dot(z, z)))
    print("sum f64|", bits(ta.sum(ta.array([1e308, 1e308], ta.f64))), bits(ta.sum(ta.array([3e38, 3e38], ta.f64))))
    ext("ties", ta.array([3.0, 1.0, 1.0, 5.0, 5.0], ta.f64))
    ext("zeros", ta.array([0.0, -0.0, 0.0, -0.0], ta.f64))
    ext("zeros2", ta.array([-0.0, 0.0, -0.0], ta.f64))
    ext("nan1", ta.array([1.0, math.nan, -1.0, math.nan], ta.f64))
    ext("nan0", ta.array([math.nan, 2.0], ta.f64))
    ext("infs", ta.array([math.inf, -math.inf, 1.0, -math.inf, math.inf], ta.f64))
    ext("one", ta.array([-0.0], ta.f64))
    ext("big", fill(5000, 9))
    e = ta.zeros(0, ta.f64)
    try:
        print(ta.min(e))
    except ValueError as x:
        print("min f64|", "ValueError", x)
    try:
        print(ta.argmax(e))
    except ValueError as x:
        print("argmax f64|", "ValueError", x)
    try:
        print(ta.dot(e, ta.zeros(1, ta.f64)))
    except ValueError as x:
        print("dot f64|", "ValueError", x)


main()
