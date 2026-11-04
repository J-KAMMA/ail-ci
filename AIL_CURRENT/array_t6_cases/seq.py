import ail_array as ta


def make(r: int, c: int, seed: int) -> ta.Matrix[ta.f64]:
    m = ta.zeros((r, c), ta.f64)
    s = seed
    for i in range(r):
        for j in range(c):
            s = (s * 1103515245 + 12345) % 2147483648
            m[i, j] = (s % 2001 - 1000) / 1000.0
    return m


def mlp(x: ta.Matrix[ta.f64], w1: ta.Matrix[ta.f64], b1: ta.Matrix[ta.f64], w2: ta.Matrix[ta.f64]) -> ta.Matrix[ta.f64]:
    h = ta.matmul(x, w1)
    h = ta.maximum(h + b1, 0.0)
    return ta.matmul(h, w2)


def main():
    x = make(4, 8, 1)
    w1 = make(8, 16, 2)
    b1 = make(4, 16, 3)
    w2 = make(16, 3, 4)
    y = mlp(x, w1, b1, w2)
    print(y, y.tobytes().hex())
    z = ta.matmul(ta.matmul(x, w1), ta.matmul(w1.T, x.T))
    print(z.tobytes().hex())
    t = x.T
    t[0, 0] = 99.0
    print(x[0, 0], t[0, 0], len(t), t.copy() == t, x == t)
    rows = ta.zeros((3, 8), ta.f64)
    for i in range(3):
        rows[i] = x[i]
    print(rows)
    rows[2] = ta.full(8, 2.5, ta.f64)
    print(rows[2:], rows[:1], rows[::2], rows[-1])


main()
