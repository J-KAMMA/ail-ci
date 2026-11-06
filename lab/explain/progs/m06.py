# expect: Box.__init__=typed Box.put=typed Box.dump=general outer=general show=typed main=typed
class Box:
    def __init__(self) -> None:
        self.items: list[int] = []

    def put(self, v: int) -> None:
        self.items.append(v)

    def dump(self) -> list[int]:
        return sorted(self.items)


def outer(n: int) -> int:
    def inner(x: int) -> int:
        ys = [x, "s"]
        return x
    return inner(n)


def show(n: int) -> None:
    b = Box()
    b.put(n)
    xs: list[int] = b.dump()
    print(len(xs))


def main() -> None:
    show(outer(2))
    print("ok")

main()
