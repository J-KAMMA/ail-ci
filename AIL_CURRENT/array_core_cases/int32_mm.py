import ail_array as ta


def mat(r: int, c: int, seed0: int, span: int) -> ta.Matrix[ta.int32]:
    m = ta.zeros((r, c), ta.int32)
    seed = seed0
    for i in range(r):
        for j in range(c):
            seed = (seed * 1103515245 + 12345) % 2147483648
            m[i, j] = seed % (2 * span + 1) - span
    return m


def show(label: str, m: ta.Matrix[ta.int32]):
    r, c = m.shape
    print("matmul int32|", label, r, c, m, m.tobytes().hex())


def attempt(label: str, a: ta.Matrix[ta.int32], b: ta.Matrix[ta.int32]):
    try:
        show(label, ta.matmul(a, b))
    except OverflowError as e:
        print("matmul int32|", label, "OverflowError", e)
    except ValueError as e:
        print("matmul int32|", label, "ValueError", e)


def main():
    for k in [0, 1, 2, 15, 16, 17, 1023, 1024, 1025]:
        attempt("k%d" % k, mat(2, k, k + 3, 1000), mat(k, 3, k + 11, 1000))
    attempt("square", mat(5, 5, 1, 46340), mat(5, 5, 2, 46340))
    attempt("tall", mat(7, 3, 4, 9), mat(3, 2, 5, 9))
    attempt("wide", mat(1, 40, 6, 99), mat(40, 33, 7, 99))
    attempt("empty", ta.zeros((0, 4), ta.int32), mat(4, 3, 8, 5))
    attempt("empty2", mat(3, 4, 9, 5), ta.zeros((4, 0), ta.int32))
    x = ta.array([[1, 2, 3], [4, 5, 6]], ta.int32)
    y = ta.array([[1, 0], [2, -1], [3, 7]], ta.int32)
    c = ta.matmul(x, y)
    print("matmul int32|", c, c[1, 1], c[0], c == ta.array([[14, 19], [32, 37]], ta.int32))
    big = 2147483647
    small = -2147483648
    attempt("fits", ta.array([[big, 1]], ta.int32), ta.array([[1], [-1]], ta.int32))
    attempt("over1", ta.array([[big, 1]], ta.int32), ta.array([[1], [1]], ta.int32))
    attempt("over2", ta.array([[1, 1], [65536, 65536]], ta.int32), ta.array([[1], [32768]], ta.int32))
    # partial sums leave int64 (2**63 after two products) and come back: the exact result 0 fits
    attempt("int64 cancel", ta.array([[small, small, small, small, small], [small, small, small, small, 1]], ta.int32),
            ta.array([[small], [small], [big], [big], [2]], ta.int32))
    attempt("int64 cancel2", ta.array([[small, small, small, small]], ta.int32),
            ta.array([[small], [small], [big], [big]], ta.int32))
    attempt("over big", ta.array([[small, small, small]], ta.int32), ta.array([[small], [small], [small]], ta.int32))
    attempt("min", ta.array([[small, 0]], ta.int32), ta.array([[1], [5]], ta.int32))
    attempt("bad", mat(2, 3, 1, 5), mat(4, 5, 2, 5))


main()
