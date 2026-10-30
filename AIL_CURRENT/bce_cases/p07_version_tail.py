def dot2(d: list[float], e: list[float]) -> float:
    n = len(d)
    l0 = -0.0
    l1 = -0.0
    nf = n // 2
    for q in range(nf):
        l0 = l0 + d[q * 2] * e[q * 2]
        l1 = l1 + d[q * 2 + 1] * e[q * 2 + 1]
    rem = n - nf * 2
    if rem > 0:
        l0 = l0 + d[n - 1] * e[n - 1]
    return l0 + l1


def blocks(d: list[float], e: list[float], w: int) -> float:
    n = len(d)
    t = 0.0
    k = 0
    while k + w <= n:
        a = 0.0
        for j in range(w):
            a = a + d[k + j] * e[k + j]
        t = t + a
        k += w
    return t


def main():
    for n in (0, 1, 2, 3, 8, 9):
        d = [float(i) + 0.25 for i in range(n)]
        e = [float(i) * 0.5 - 1.0 for i in range(n)]
        print(n, dot2(d, e))
    d = [float(i) + 0.25 for i in range(9)]
    for m in (0, 4, 8):
        try:
            print("short e", m, dot2(d, [1.5] * m))
        except IndexError as ex:
            print("IndexError", m, ex)
    for w in (1, 2, 4, 5):
        try:
            print("blocks", w, blocks(d, [2.0] * 9, w))
        except IndexError as ex:
            print("IndexError", w, ex)
    try:
        print(blocks(d, [2.0] * 5, 4))
    except IndexError as ex:
        print("IndexError", ex)


main()
