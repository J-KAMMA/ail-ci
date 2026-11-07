LIMIT = 20000


def main() -> None:
    data = list(range(LIMIT))
    members = set(data)
    hits = 0
    for value in range(LIMIT):
        if value in members:
            hits += 1
    print(hits)


main()
