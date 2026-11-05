MAXV: int = 9223372036854775807


def main() -> None:
    values = []
    for i in range(3):
        values.append(MAXV // 4)
    print(sum(values))
    print(sum([1, 2, 3]))
    values.append(MAXV - 1)
    print(sum(values))


main()
