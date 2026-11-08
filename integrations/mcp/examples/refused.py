def countdown(limit: int) -> int:
    total = 0
    n = 0
    while n < limit:
        total += n
        n += 1
    else:
        print("done", n)
    return total


def main() -> None:
    print(countdown(5))


main()
