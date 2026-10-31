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


def mk(n: int, v: float, step: float) -> list[float]:
    out: list[float] = []
    for i in range(n):
        out.append(v + float(i) * step)
    return out


def main():
    for n in (1, 2, 3, 8, 9):
        print(n, dot2(mk(n, 0.25, 1.0), mk(n, -1.0, 0.5)))
    d = mk(9, 0.25, 1.0)
    for m in (1, 4, 8):
        try:
            print("short e", m, dot2(d, mk(m, 1.5, 0.0)))
        except IndexError as ex:
            print("IndexError", m, ex)
    for w in (1, 2, 4, 5):
        try:
            print("blocks", w, blocks(d, mk(9, 2.0, 0.0), w))
        except IndexError as ex:
            print("IndexError", w, ex)
    try:
        print(blocks(d, mk(5, 2.0, 0.0), 4))
    except IndexError as ex:
        print("IndexError", ex)


main()
