import ail_array as ta


def bits(x: float) -> str:
    return ta.array([x], ta.f64).tobytes().hex()


def fill(x: ta.Matrix[ta.f64], seed: int):
    r, c = x.shape
    s = seed
    for i in range(r):
        for j in range(c):
            s = (s * 1103515245 + 12345) % 2147483648
            x[i, j] = (s % 20001 - 10000) / 7.0


def column(b: ta.Matrix[ta.f64], j: int) -> ta.Array[ta.f64]:
    k, n = b.shape
    col = ta.zeros(k, ta.f64)
    for t in range(k):
        col[t] = b[t, j]
    return col


def one(m: int, k: int, n: int, seed: int):
    a = ta.zeros((m, k), ta.f64)
    b = ta.zeros((k, n), ta.f64)
    fill(a, seed)
    fill(b, seed + 99)
    c = ta.matmul(a, b)
    r, q = c.shape
    ok = True
    for i in range(m):
        for j in range(n):
            if bits(c[i, j]) != bits(ta.dot(a[i], column(b, j))):
                ok = False
    print(m, k, n, r, q, ok, c.tobytes().hex())


def main():
    shapes = [(1, 1, 1), (1, 5, 1), (1, 15, 1), (1, 16, 1), (1, 17, 1), (3, 1, 2), (2, 1, 1), (1, 1, 4), (2, 15, 3), (2, 16, 3),
              (2, 17, 3), (3, 31, 2), (3, 32, 2), (3, 33, 2), (1, 1023, 1), (1, 1024, 1), (1, 1025, 1), (2, 1023, 2),
              (2, 1024, 2), (2, 1025, 2), (3, 2047, 1), (3, 2048, 1), (3, 2049, 2), (1, 3072, 2), (1, 3073, 1),
              (4, 3, 5), (5, 4, 3), (7, 33, 2), (2, 0, 3), (0, 3, 2), (3, 2, 0), (0, 0, 0), (0, 5, 0), (3, 0, 0),
              (9, 9, 9), (17, 5, 18), (6, 100, 70)]
    seed = 7
    for sh in shapes:
        one(sh[0], sh[1], sh[2], seed)
        seed += 13


main()
