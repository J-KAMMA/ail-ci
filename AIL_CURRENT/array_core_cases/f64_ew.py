import math
import ail_array as ta


def show(cell: str, a: ta.Array[ta.f64]):
    print(cell + "|", a, a.tobytes().hex())


def edges() -> ta.Array[ta.f64]:
    return ta.array([0.0, -0.0, 1.0, -1.0, 0.1, -2.5, 5e-324, 1.401298464324817e-45, 1.1754943508222875e-38, 16777217.0,
                     3.4028234663852886e+38, 1.7976931348623157e308, -1.7976931348623157e308, 1e39, math.inf, -math.inf,
                     math.nan, 0.5, 3.0, 7.0, 1e-300, 1.0000000596046448], ta.f64)


def rot(a: ta.Array[ta.f64], s: int) -> ta.Array[ta.f64]:
    n = len(a)
    b = ta.zeros(n, ta.f64)
    for k in range(n):
        b[k] = a[(k + s) % n]
    return b


def main():
    a = edges()
    for s in [0, 1, 5, 11, 16]:
        b = rot(a, s)
        show("add f64", a + b)
        show("sub f64", a - b)
        show("mul f64", a * b)
        show("div f64", a / b)
        show("minimum f64", ta.minimum(a, b))
        show("maximum f64", ta.maximum(a, b))
    # TA2: IEEE division, no exception
    z = ta.array([1.0, -1.0, 0.0, -0.0, math.nan, math.inf], ta.f64)
    show("div f64", z / ta.zeros(6, ta.f64))
    show("div f64", z / ta.full(6, -0.0, ta.f64))
    show("div f64", z / 0.0)
    show("div f64", 0.0 / z)
    for x in [0.0, -0.0, 2.0, 1e39, math.nan, -math.inf]:
        show("add f64", a + x)
        show("sub f64", x - a)
        show("mul f64", a * x)
        show("div f64", x / a)
        show("minimum f64", ta.minimum(a, x))
        show("maximum f64", ta.maximum(a, x))
    show("add f64", a + 3)
    show("mul f64", 2 * a)
    show("neg f64", -a)
    show("neg f64", -(-a))
    show("abs f64", abs(a))
    show("abs f64", abs(-a))
    p = a.copy()
    p += rot(a, 3)
    show("add f64", p)
    p -= 1.5
    show("sub f64", p)
    p *= rot(a, 7)
    show("mul f64", p)
    p /= rot(a, 2)
    show("div f64", p)
    try:
        show("add f64", a + ta.zeros(3, ta.f64))
    except ValueError as e:
        print("add f64|", "ValueError", e)
    try:
        show("minimum f64", ta.minimum(a, ta.zeros(2, ta.f64)))
    except ValueError as e:
        print("minimum f64|", "ValueError", e)
    show("add f64", ta.zeros(0, ta.f64) + ta.zeros(0, ta.f64))


main()
