# expect: Chain.__init__=typed Chain.grow=general outer=general show=typed main=typed
class Chain:
    def __init__(self) -> None:
        self.n: int = 0

    def grow(self) -> int:
        ys = [self.n, "s"]
        return self.n


def outer(n: int) -> int:
    def inner(x: int) -> int:
        ys = [x, "s"]
        return x
    return inner(n)


def show(n: int) -> None:
    c = Chain()
    print(c.grow() + outer(n))


def main() -> None:
    show(2)
    print("ok")

main()
