def collatz(n: int) -> int:
    value = n if n > 1 else 1
    steps = n - n
    while value != 1:
        if value % 2 == 0:
            value = value // 2
        else:
            value = 3 * value + 1
        steps += 1
    return steps


def main() -> None:
    total = collatz(1) - 1
    for i in range(1, 20):
        total += collatz(i)
        if i % 7 == 0:
            continue
        if i > 15:
            break
    print(total)
    for a in range(3):
        for b in range(3):
            total += a * b
    print(total)


main()
