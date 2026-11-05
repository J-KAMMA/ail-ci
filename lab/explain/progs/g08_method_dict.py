# expect: Counter.__init__=typed Counter.snapshot=general Counter.get=typed main=general
class Counter:
    def __init__(self, start: int) -> None:
        self.n: int = start

    def snapshot(self) -> dict[str, int]:
        d = {}
        d["n"] = self.n
        return d

    def get(self) -> int:
        return self.n


def main() -> None:
    c = Counter(4)
    print(c.get())
    print(c.snapshot())


main()
