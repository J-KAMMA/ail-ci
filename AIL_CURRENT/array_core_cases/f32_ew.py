import math
import ail_array as ta


def show(cell: str, a: ta.Array[ta.f32]):
    print(cell + "|", a, a.tobytes().hex())


def edges() -> ta.Array[ta.f32]:
    return ta.array([0.0, -0.0, 1.0, -1.0, 0.1, -2.5, 5e-324, 1.401298464324817e-45, 1.1754943508222875e-38, 16777217.0,
                     3.4028234663852886e+38, 1.7976931348623157e308, -1.7976931348623157e308, 1e39, math.inf, -math.inf,
                     math.nan, 0.5, 3.0, 7.0, 1e-300, 1.0000000596046448], ta.f32)


def rot(a: ta.Array[ta.f32], s: int) -> ta.Array[ta.f32]:
    n = len(a)
    b = ta.zeros(n, ta.f32)
    for k in range(n):
        b[k] = a[(k + s) % n]
    return b


def main():
    a = edges()
    for s in [0, 1, 5, 11, 16]:
        b = rot(a, s)
        show("add f32", a + b)
        show("sub f32", a - b)
        show("mul f32", a * b)
        show("div f32", a / b)
        show("minimum f32", ta.minimum(a, b))
        show("maximum f32", ta.maximum(a, b))
    # TA2: IEEE division, no exception
    z = ta.array([1.0, -1.0, 0.0, -0.0, math.nan, math.inf], ta.f32)
    show("div f32", z / ta.zeros(6, ta.f32))
    show("div f32", z / ta.full(6, -0.0, ta.f32))
    show("div f32", z / 0.0)
    show("div f32", 0.0 / z)
    for x in [0.0, -0.0, 2.0, 1e39, math.nan, -math.inf]:
        show("add f32", a + x)
        show("sub f32", x - a)
        show("mul f32", a * x)
        show("div f32", x / a)
        show("minimum f32", ta.minimum(a, x))
        show("maximum f32", ta.maximum(a, x))
    show("add f32", a + 3)
    show("mul f32", 2 * a)
    show("neg f32", -a)
    show("neg f32", -(-a))
    show("abs f32", abs(a))
    show("abs f32", abs(-a))
    p = a.copy()
    p += rot(a, 3)
    show("add f32", p)
    p -= 1.5
    show("sub f32", p)
    p *= rot(a, 7)
    show("mul f32", p)
    p /= rot(a, 2)
    show("div f32", p)
    try:
        show("add f32", a + ta.zeros(3, ta.f32))
    except ValueError as e:
        print("add f32|", "ValueError", e)
    try:
        show("minimum f32", ta.minimum(a, ta.zeros(2, ta.f32)))
    except ValueError as e:
        print("minimum f32|", "ValueError", e)
    show("add f32", ta.zeros(0, ta.f32) + ta.zeros(0, ta.f32))


main()
