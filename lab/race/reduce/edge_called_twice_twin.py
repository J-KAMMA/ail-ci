def total(n: int, base: int) -> int:
    acc = base
    for i in range(0, n):
        acc += i
    return acc


def main():
    print(total(100, 0), total(100, 1000))


main()
