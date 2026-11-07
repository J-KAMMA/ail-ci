LIMIT = 6000


def main() -> None:
    left = [{"id": value} for value in range(LIMIT)]
    right = [{"id": value} for value in range(LIMIT)]
    matches = 0
    for one in left:
        for two in right:
            if one["id"] == two["id"]:
                matches += 1
    print(matches)


main()
