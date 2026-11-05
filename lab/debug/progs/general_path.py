def find(d: dict[int, int], k: int) -> int | None:
    return d.get(k)


def main() -> None:
    print(find({1: 2}, 1))
    xs = [1, 2, 3]
    i = 5
    print(xs[i])


main()
