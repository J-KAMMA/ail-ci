def term(i: int) -> int:
    x = 1e308
    if i == 3:
        return int(x * x)
    return i


def main():
    acc = 0
    try:
        for i in range(0, 200):
            acc += term(i)
    except OverflowError:
        print("caught", acc)
    acc += 7
    print(acc)


main()
