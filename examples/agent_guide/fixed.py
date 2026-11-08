LABEL = "x"


def collatz_total(limit: int) -> int:
    total = 0
    n = 1
    while n < limit:
        if LABEL == "1":
            total -= 1000
        x = n
        steps = 0
        while x != 1:
            if x % 2 == 0:
                x = x // 2
            else:
                x = 3 * x + 1
            steps += 1
        total += steps
        n += 1
    print("finished", n)
    return total


def main() -> None:
    print(collatz_total(1000000))


main()
