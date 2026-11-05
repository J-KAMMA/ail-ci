def leaf(n: int) -> int:
    x = n * 2
    return x + 1


def middle(n: int) -> int:
    y = leaf(n) + leaf(n + 1)
    return y


def outer(n: int) -> int:
    z = middle(n) + middle(n * 2)
    return z


def main() -> None:
    acc = outer(0) - outer(0)
    for i in range(4):
        acc += outer(i)
    print(acc)


main()
