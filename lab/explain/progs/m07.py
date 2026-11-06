# expect: Ledger.__init__=typed Ledger.add=typed Ledger.flip=general counts=general show=typed main=typed
class Ledger:
    def __init__(self) -> None:
        self.n: int = 0

    def add(self, v: int) -> None:
        self.n = self.n + v

    def flip(self) -> list[int]:
        return sorted([self.n])


def counts(n: int) -> dict[str, int]:
    d = {}
    d["n"] = n
    return d


def show(n: int) -> None:
    l = Ledger()
    l.add(n)
    d: dict[str, int] = counts(n)
    print(d["n"] + len(l.flip()))


def main() -> None:
    show(3)
    print("ok")

main()
