def calc(n: int, f: float) -> float:
    k = n + 1
    g = f * 2.0
    r = g + k
    return r


def main() -> None:
    n = 42
    f = 1.5
    print(calc(n, f))


main()
