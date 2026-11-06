BIG = 4611686018427387904

def term(i: int) -> int:
    if i == 1:
        return 1000 // (i - 1)
    if i >= 3:
        return BIG
    return 0


def main():
    acc = 0
    for i in range(0, 8):
        acc += term(i)
    print(acc)


main()
