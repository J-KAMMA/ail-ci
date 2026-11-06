BIG = 4611686018427387904

def term(i: int) -> int:
    if i == 6:
        return 1000 // (i - 6)
    if i >= 2:
        return BIG
    return 0


def main():
    acc = 0
    for i in par_range(0, 8):
        acc += term(i)
    print(acc)


main()
