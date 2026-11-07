LIMIT = 20000


def main() -> None:
    data = list(range(LIMIT))
    hits = 0
    for value in range(LIMIT):
        if value in data:
            hits += 1
    print(hits)


main()
