LIMIT = 6000


def main() -> None:
    left = [{"id": value} for value in range(LIMIT)]
    right = [{"id": value} for value in range(LIMIT)]
    by_id = {two["id"]: two for two in right}
    matches = 0
    for one in left:
        if one["id"] in by_id:
            matches += 1
    print(matches)


main()
