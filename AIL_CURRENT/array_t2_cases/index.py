import ail_array as ta


def main():
    a = ta.array([10.0, 20.0, 30.0, 40.0, 50.0], ta.f64)
    n = len(a)
    for i in range(-n - 2, n + 2):
        try:
            print(i, a[i])
        except IndexError as exc:
            print(i, "IndexError", exc)
    for i in range(-n - 2, n + 2):
        try:
            a[i] = i * 1.5
        except IndexError as exc:
            print(i, "IndexError", exc)
    print(a)
    # slices: every combination of a few bounds and steps
    starts = [-9, -5, -2, 0, 1, 3, 5, 8]
    stops = [-9, -5, -1, 0, 2, 5, 8]
    steps = [1, 2, 3, -1, -2, -4, 7, -7]
    count = 0
    for st in starts:
        for sp in stops:
            for sd in steps:
                s = a[st:sp:sd]
                count += len(s)
                print(st, sp, sd, s)
    print(count)
    print(a[:], a[::], a[2:], a[:2], a[::2], a[::-1], a[-2:], a[:-2], a[1:-1], a[3:1], a[1::-1], a[:0:-1])
    try:
        zero = 0
        print(a[::zero])
    except ValueError as exc:
        print("ValueError", exc)
    # slice assignment
    b = ta.zeros(6, ta.f64)
    b[1:4] = ta.array([1.0, 2.0, 3.0], ta.f64)
    print(b)
    b[::2] = ta.array([7.0, 8.0, 9.0], ta.f64)
    print(b)
    b[::-2] = ta.array([-1.0, -2.0, -3.0], ta.f64)
    print(b)
    b[:] = b[::-1]
    print(b)
    b[0:3] = b[3:6]
    print(b)
    b[2:2] = ta.zeros(0, ta.f64)
    try:
        b[0:2] = ta.zeros(3, ta.f64)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        b[::2] = ta.zeros(2, ta.f64)
    except ValueError as exc:
        print("ValueError", exc)
    print(b)
    # swap and augmented element assignment
    b[0], b[5] = b[5], b[0]
    print(b)
    b[1] += 10
    b[2] -= 0.5
    b[3] *= 2
    b[-1] /= 4
    print(b)
    # copies and aliases
    c = a[:]
    c[0] = -1.0
    print(a[0], c[0])
    d = a
    d[0] = -2.0
    print(a[0], d[0], a is d, a is c)
    e = a.copy()
    e[1] = 99.0
    print(a[1], e[1])
    # iteration, list, len
    total = 0.0
    for v in a:
        total += v
    print(total, len(a), list(a), a.tolist(), [x * 2 for x in a], sum(a), min(a), max(a))
    for i, v in enumerate(a):
        print(i, v, end=';')
    print()
    for x, y in zip(a, c):
        print(x - y, end=';')
    print()
    # equality
    print(a == c, a == a, a != c, a == a.copy(), ta.zeros(0, ta.f64) == ta.zeros(0, ta.f64))
    nan = float("nan")
    nn = ta.array([nan], ta.f64)
    print(nn == nn, nn != nn, nn == nn.copy())
    print(ta.array([0.0], ta.f64) == ta.array([-0.0], ta.f64))
    # repr / str / f-string
    print(str(a), repr(a), f"{a}|{a!r}|{a!s}", [len(a)])
    print(ta.zeros(0, ta.f64), ta.zeros(0, ta.int32))
    # lengths
    try:
        ta.zeros(-1, ta.f64)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        ta.full(-2, 1.0, ta.f64)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        ta.arange(-3, ta.int32)
    except ValueError as exc:
        print("ValueError", exc)
    # bytes
    f = ta.frombytes(bytes([0, 0, 0, 0, 0, 0, 240, 63, 0, 0, 0, 0, 0, 0, 0, 128]), ta.f64)
    print(f, f.tobytes().hex())
    try:
        ta.frombytes(bytes([1, 2, 3]), ta.f64)
    except ValueError as exc:
        print("ValueError", exc)
    g = ta.frombytes(bytes([0, 0, 0, 0, 0, 0, 248, 127, 0, 0, 0, 0, 0, 0, 240, 127, 0, 0, 0, 0, 0, 0, 240, 255, 1, 0, 0, 0, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255, 239, 127]), ta.f64)
    print(g, g.tobytes().hex())
    # sizes
    big = ta.zeros(100000, ta.f64)
    for i in range(len(big)):
        big[i] = i * 0.5
    print(big[99999], big[-1], len(big[::7]), big[5:99000:991][3], ta.sum(big))
    ii = ta.arange(100000, ta.int32)
    print(ta.sum(ii), ta.dot(ii, ii), ii[-1], len(ii[1::3]))


main()
