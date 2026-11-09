def term(i: int) -> int:
    if i == 3:
        return 1 // (i - 3)
    return i * 2


def main():
    acc = 0
    for i in range(0, 200):
        acc += term(i)
    print(acc)


main()
