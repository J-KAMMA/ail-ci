def squares(n: int) -> list[int]:
    out = [i * i for i in range(n) if i % 2 == 1]
    return out


def main() -> None:
    xs = squares(9)
    total = sum(xs)
    print(xs, total)


main()
