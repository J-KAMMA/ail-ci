def lanes(d: list[float], n: int) -> float:
    k = 0
    acc = 0.0
    while k < n:
        acc = acc + d[k] * d[k + 15]
        k += 16
    return acc


def lanes2(d: list[float]) -> float:
    n = len(d)
    full = (n // 16) * 16
    k = 0
    acc = 0.0
    while k < full:
        acc = acc + d[k + 0] + d[k + 15]
        k += 16
    return acc


def bigstart(d: list[float]) -> int:
    k = 9223372036854775807 - 20
    c = 0
    while k < 9223372036854775807 + 40:
        c += 1
        k += 16
    return k + c


def main():
    d = [float(i) * 0.5 for i in range(70)]
    print(lanes2(d))
    for n in (16, 33, 48, 49, 64, 65):
        try:
            print(n, lanes(d, n))
        except IndexError as e:
            print(n, "IndexError", e)
    print(bigstart(d))
    try:
        print(lanes(d[:20], 17))
    except IndexError as e:
        print("IndexError", e)


main()
