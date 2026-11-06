def total(n: int) -> int:
    acc = 0
    for i in range(n):
        if i % 3 == 0:
            acc += i
        else:
            acc -= 1
    k = 0
    while k < n:
        k += 2
    return acc + k


def main() -> None:
    print(total(10))
    print(total(25))


main()
