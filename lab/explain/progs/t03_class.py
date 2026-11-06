# expect: Counter.__init__=typed Counter.add=typed Counter.get=typed main=typed
class Counter:
    def __init__(self, start: int) -> None:
        self.n: int = start

    def add(self, v: int) -> None:
        self.n = self.n + v

    def get(self) -> int:
        return self.n


def main() -> None:
    c = Counter(2)
    c.add(3)
    print(c.get())


main()
