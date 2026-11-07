LIMIT = 150000


def main() -> None:
    values = list(range(LIMIT))
    total = 0
    for _ in range(LIMIT):
        total += values.pop(0)
    print(total, len(values))


main()
