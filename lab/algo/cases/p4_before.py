LIMIT = 12000


def main() -> None:
    values = list(range(LIMIT))
    total = 0
    for _ in range(LIMIT):
        total += sum(values)
    print(total)


main()
