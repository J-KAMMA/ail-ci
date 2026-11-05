# expect: Vault.__init__=typed Vault.store=typed Vault.report=general outer=general evens=general show=typed main=typed
class Vault:
    def __init__(self) -> None:
        self.items: list[int] = []

    def store(self, v: int) -> None:
        self.items.append(v)

    def report(self) -> list[int]:
        xs = [self.items[0], "s"]
        return self.items


def outer(n: int) -> int:
    def inner(x: int) -> int:
        ys = [x, "s"]
        return x
    return inner(n)


def evens(n: int) -> list[int]:
    out: list[int] = []
    for i in range(n):
        out.append(i)
        yield i
    return out


def show(n: int) -> None:
    v = Vault()
    v.store(n)
    xs: list[int] = v.report()
    print(len(xs))


def main() -> None:
    show(outer(2))
    print("ok")

main()
