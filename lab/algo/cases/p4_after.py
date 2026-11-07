LIMIT = 12000


def main() -> None:
    values = list(range(LIMIT))
    total = sum(values) * LIMIT
    print(total)


main()
