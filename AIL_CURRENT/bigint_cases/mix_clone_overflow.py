def twice(x: int) -> int:
    return x * 2


def square_sum(xs: list[int]) -> int:
    return xs[0] * xs[0] + xs[1] * xs[1]


def main():
    print(twice(4611686018427387904))
    print(square_sum([4294967296, 4294967296]))
    print(twice(-9223372036854775808))


main()
