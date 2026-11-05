# expect: Store.__init__=typed Store.put=typed Store.as_dict=general tail=general show=typed main=typed
class Store:
    def __init__(self) -> None:
        self.n: int = 0

    def put(self, n: int) -> None:
        self.n = n

    def as_dict(self) -> dict[str, int]:
        d = {}
        d["n"] = self.n
        return d


def tail(xs: list[int]) -> list[int]:
    ys: list[int] = xs[1:]
    return ys


def show(xs: list[int]) -> None:
    s = Store()
    s.put(xs[0])
    d: dict[str, int] = s.as_dict()
    print(d["n"] + len(tail(xs)))


def main() -> None:
    show([5, 6])
    print("ok")

main()
