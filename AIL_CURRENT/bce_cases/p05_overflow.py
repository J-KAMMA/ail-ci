def fact(n: int) -> int:
    acc = 1
    for i in range(1, n):
        acc = acc * i
    return acc


def climb(start: int, steps: int) -> int:
    i = start
    c = 0
    while c < steps:
        i += 1
        c += 1
    return i


def squares(n: int) -> int:
    x = 3
    for _ in range(n):
        x = x * x
    return x


def idx_big(xs: list[int], k: int) -> int:
    return xs[k + 1]


def sumsq(xs: list[int]) -> int:
    t = 0
    for i in range(len(xs)):
        t += xs[i] * xs[i]
    return t


def main():
    print(fact(30))
    print(climb(9223372036854775800, 20))
    print(climb(-9223372036854775808, 3))
    print(squares(8))
    print(sumsq([3037000500, 3037000500, 1]))
    print(sumsq([9223372036854775807, 2]))
    for k in (0, 2, 9223372036854775807, -9223372036854775808, 2 ** 70):
        try:
            print(idx_big([1, 2, 3, 4], k))
        except (IndexError, OverflowError) as e:
            print(type(e).__name__, e)


main()
