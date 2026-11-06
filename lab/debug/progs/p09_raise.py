def pick(xs: list[int], i: int) -> int:
    v = xs[i]
    return v


def main() -> None:
    data = [1, 2, 3]
    print(pick(data, 1))
    print(pick(data, 9))


main()
