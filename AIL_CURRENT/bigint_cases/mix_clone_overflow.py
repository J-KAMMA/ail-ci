def twice(x: int) -> int:
    return x * 2


def square_sum(xs: list[int]) -> int:
    return xs[0] * xs[0] + xs[1] * xs[1]


def risky(xs: list[int], i: int) -> int:
    return xs[i] + xs[i - 1]


def rec(n: int, xs: list[int]) -> int:
    if n <= 0:
        return xs[0] * xs[0]
    return rec(n - 1, xs) + 1


def main():
    print(twice(4611686018427387904))
    print(square_sum([4294967296, 4294967296]))
    print(twice(-9223372036854775808))
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([1, 2, 3], 1))
    xs = [4294967296]
    print(rec(3, xs))
    s = 0
    for i in range(1000):
        s = (s + rec(70, xs)) % 1000000007
    print(s)
    try:
        print(risky([1], 1))
    except IndexError as e:
        print("IndexError", str(e))


main()
