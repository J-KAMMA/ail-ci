from helper import label, scale


def total(rows: list[int]) -> int:
    acc = scale(0, 0)
    for row in rows:
        acc += scale(row, 4)
    return acc


def main() -> None:
    print(total([0, 1, 2]))
    print(label(24))


main()
