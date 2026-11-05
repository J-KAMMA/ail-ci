
BIG = 4611686018427387904

def f(x: int) -> int:
    if x == 3:
        return 1000 // (x - 3)
    return BIG


def main():
    vals = [0, 0, 0, 0, 0]
    acc = 0
    try:
        for i in range(0, 5):
            vals[i] = f(i)
        for i in range(0, 5):
            acc += vals[i]
    except ZeroDivisionError:
        print("caught ZeroDivisionError", acc)
    print(acc)


main()
