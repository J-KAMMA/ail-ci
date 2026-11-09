# Broadcasting of 2-D arrays (job aicore1): row (c,) and (1, c), column (r, 1), outer (r, 1) x (1, c), in place, every op,
# f64 and f32, specials in the broadcast operand, and the error texts.
import math
import ail_array as ta


def mf(r: int, c: int, s: int) -> ta.Matrix[ta.f64]:
    m = ta.zeros((r, c), ta.f64)
    for i in range(r):
        for j in range(c):
            s = (1103515245 * s + 12345) % 2147483648
            m[i, j] = float(s % 2001 - 1000) / 64.0
    return m


def ms(r: int, c: int, s: int) -> ta.Matrix[ta.f32]:
    m = ta.zeros((r, c), ta.f32)
    for i in range(r):
        for j in range(c):
            s = (1103515245 * s + 12345) % 2147483648
            m[i, j] = float(s % 2001 - 1000) / 7.0
    return m


def main():
    a = mf(3, 4, 1)
    row = ta.array([1.5, -0.0, math.inf, math.nan], ta.f64)
    col = ta.array([[2.0], [0.0], [-3.25]], ta.f64)
    top = ta.array([[0.5, -1.0, 0.0, 7.0]], ta.f64)
    print("f64 + row", a + row)
    print("f64 row - M", row - a)
    print("f64 * col", a * col)
    print("f64 col / M", col / a)
    print("f64 M / col", a / col)
    print("f64 + top", a + top)
    print("f64 outer", col * top)
    print("f64 outer2", top - col)
    print("f64 max row", ta.maximum(a, row))
    print("f64 min col", ta.minimum(col, a))
    print("f64 max 1d first", ta.maximum(row, a))
    b = a.copy()
    b += row
    b *= col
    b -= top
    b /= col
    print("f64 inplace", b)
    x = ms(3, 4, 5)
    xr = ta.array([0.1, -0.0, 3.0, 1e-30], ta.f32)
    xc = ta.array([[3.0], [0.0], [-7.0]], ta.f32)
    print("f32 + row", x + xr, (x + xr).tobytes().hex())
    print("f32 row - M", xr - x)
    print("f32 / col", x / xc, (x / xc).tobytes().hex())
    print("f32 col * M", xc * x)
    print("f32 outer", xc * ta.array([[1.0, 0.1, -2.0]], ta.f32))
    print("f32 max row", ta.maximum(x, xr))
    print("f32 min 1d first", ta.minimum(xr, x))
    y = x.copy()
    y += xr
    y /= xc
    print("f32 inplace", y, y.tobytes().hex())
    for n in range(9):
        try:
            if n == 0:
                print(a + ta.zeros(3, ta.f64))
            elif n == 1:
                print(ta.zeros(5, ta.f64) - a)
            elif n == 2:
                print(a * ta.zeros((2, 1), ta.f64))
            elif n == 3:
                c = col.copy()
                c += a
                print(c)
            elif n == 4:
                print(x + ta.zeros((3, 2), ta.f32))
            elif n == 5:
                print(a + ta.zeros((1, 5), ta.f64))
            elif n == 6:
                print(ta.zeros((4, 1), ta.f64) / a)
            elif n == 7:
                d = top.copy()
                d -= col
                print(d)
            else:
                print(ta.maximum(x, ta.zeros(7, ta.f32)))
        except ValueError as e:
            print(n, "ValueError", e)


main()
