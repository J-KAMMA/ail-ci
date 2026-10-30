def total(xs: list[int], n: int) -> int:
    s = 0
    for i in range(n):
        s += xs[i]
    return s


def total2(xs: list[int], a: int, b: int) -> int:
    s = 0
    for i in range(a, b):
        s += xs[i] * 2
    return s


def main():
    xs = [3, 1, 4, 1, 5, 9, 2, 6]
    print(total(xs, len(xs)))
    print(total2(xs, 2, len(xs)))
    for n in (len(xs) + 1, len(xs) + 5):
        try:
            print(total(xs, n))
        except IndexError as e:
            print("IndexError", e)
    for a, b in ((0, 9), (3, 100), (7, 9)):
        try:
            print(total2(xs, a, b))
        except IndexError as e:
            print("IndexError", e)
    try:
        print(total2(xs, -3, 4))
    except IndexError as e:
        print("IndexError", e)


main()
