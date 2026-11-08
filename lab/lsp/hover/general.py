def find(d: dict[int, int], k: int) -> int | None:
    return d.get(k)


def main() -> None:
    picked = find({1: 2}, 1)
    print(picked)


main()
