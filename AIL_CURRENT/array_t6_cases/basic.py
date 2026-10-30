import ail_array as ta


def show(m: ta.Matrix[ta.f64]):
    r, c = m.shape
    print(m, len(m), r, c, m.tobytes().hex())


def main():
    a = ta.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], ta.f64)
    b = ta.array([[1.0, 0.5], [2.0, 0.25], [3.0, -1.0]], ta.f64)
    show(a)
    show(a.T)
    c = ta.matmul(a, b)
    show(c)
    z = ta.zeros((2, 3), ta.f64)
    z[1, 2] = 7.5
    z[0, 0] = -0.0
    show(z)
    z[0] = a[1]
    show(z)
    show(z + a)
    show(z * 2.0 - a)
    show(-z)
    show(abs(z - a))
    z += a
    show(z)
    z *= 0.5
    show(z)
    show(a[1:])
    show(a[::-1])
    print(a[1, -1], a[-1], a == a, a == z, a != z)
    show(ta.sqrt(a))
    show(ta.maximum(a, 3.0))
    show(ta.clip(a, 2.0, 5.0))
    print(a.copy() == a)
    f = ta.full((2, 2), 3, ta.f64)
    show(f)
    try:
        print(a[2, 0])
    except IndexError as e:
        print("IndexError", e)
    try:
        print(ta.matmul(a, a))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(a + b)
    except ValueError as e:
        print("ValueError", e)
    show(ta.matmul(ta.zeros((2, 0), ta.f64), ta.zeros((0, 3), ta.f64)))
    show(ta.zeros((0, 3), ta.f64))
    show(ta.zeros((3, 0), ta.f64))


main()
