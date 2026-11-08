def helper() -> None:
    x = 1 / 2
    print(x)


def outer() -> None:
    def helper() -> None:
        x = not 1
        print(x)
    helper()


helper()
outer()
