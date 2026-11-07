LIMIT = 60000


def main() -> None:
    values = []
    for value in range(LIMIT):
        values = values + [value]
    print(len(values), sum(range(LIMIT)) == sum(values))


main()
