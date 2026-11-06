
def sq(x: int) -> int:
    return x * x


def main():
    acc = 0
    for i in range(0, 10):
        acc += sq(i)
    print(acc)


main()
