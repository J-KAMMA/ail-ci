def lanes(d: list[float], e: list[float]) -> float:
    n = len(d)
    nb = (n + 1023) // 1024
    acc = 0.0
    for b in range(nb):
        s = b * 1024
        t = s + 1024
        if t > n:
            t = n
        l0 = -0.0
        l1 = -0.0
        full = s + ((t - s) // 2) * 2
        k = s
        while k < full:
            l0 = l0 + d[k + 0] * e[k + 0]
            l1 = l1 + d[k + 1] * e[k + 1]
            k += 2
        while k < t:
            l0 = l0 + d[k] * e[k]
            k += 1
        acc = acc + (l0 + l1)
    return acc


def main():
    for n in (1, 2, 3, 1023, 1024, 1025, 3000):
        d: list[float] = []
        e: list[float] = []
        for i in range(n):
            d.append(float(i % 7) * 0.5)
            e.append(float(i % 5) - 1.5)
        print(n, lanes(d, e))
    try:
        a: list[float] = [1.0] * 2050
        b: list[float] = [2.0] * 2049
        print(lanes(a, b))
    except IndexError as ex:
        print("IndexError", ex)


main()
