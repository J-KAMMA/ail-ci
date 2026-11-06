import math
import ail_array as ta


def mat(r: int, c: int, seed0: int) -> ta.Matrix[ta.f64]:
    m = ta.zeros((r, c), ta.f64)
    seed = seed0
    for i in range(r):
        for j in range(c):
            seed = (seed * 1103515245 + 12345) % 2147483648
            m[i, j] = (seed % 2001 - 1000) / 7.0
    return m


def show(label: str, m: ta.Matrix[ta.f64]):
    r, c = m.shape
    print("matmul f64|", label, r, c, m.tobytes().hex())


def main():
    for k in [0, 1, 2, 15, 16, 17, 1023, 1024, 1025, 2049]:
        a = mat(2, k, k + 3)
        b = mat(k, 3, k + 11)
        show("k%d" % k, ta.matmul(a, b))
    show("square", ta.matmul(mat(5, 5, 1), mat(5, 5, 2)))
    show("tall", ta.matmul(mat(7, 3, 4), mat(3, 2, 5)))
    show("wide", ta.matmul(mat(1, 40, 6), mat(40, 33, 7)))
    show("empty", ta.matmul(ta.zeros((0, 4), ta.f64), mat(4, 3, 8)))
    show("empty2", ta.matmul(mat(3, 4, 9), ta.zeros((4, 0), ta.f64)))
    x = ta.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], ta.f64)
    y = ta.array([[1.0, 0.5], [2.0, 0.25], [3.0, -1.0]], ta.f64)
    c = ta.matmul(x, y)
    print("matmul f64|", c, c[1, 1], c[0])
    # specials: lane order only, inf - inf, -0.0 identity, subnormal and overflowing products
    s = ta.array([[1e16, 1.0, -1e16, 1e8, 1.0, -1e8, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]], ta.f64)
    t = ta.full((17, 1), 1.0, ta.f64)
    show("lanes", ta.matmul(s, t))
    show("infs", ta.matmul(ta.array([[math.inf, 1.0], [-0.0, -0.0]], ta.f64), ta.array([[0.0, 1.0], [1.0, -0.0]], ta.f64)))
    show("negz", ta.matmul(ta.array([[-0.0]], ta.f64), ta.array([[0.0]], ta.f64)))
    show("over", ta.matmul(ta.array([[3e38, 3e38], [1e300, 1e300]], ta.f64), ta.array([[10.0], [1.0]], ta.f64)))
    show("tiny", ta.matmul(ta.array([[1e-30, 1e-170]], ta.f64), ta.array([[1e-20], [1e-170]], ta.f64)))
    show("nan", ta.matmul(ta.array([[math.nan, 1.0]], ta.f64), ta.array([[1.0], [1.0]], ta.f64)))
    try:
        show("bad", ta.matmul(mat(2, 3, 1), mat(4, 5, 2)))
    except ValueError as e:
        print("matmul f64|", "ValueError", e)


main()
