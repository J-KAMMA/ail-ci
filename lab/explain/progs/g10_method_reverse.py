# expect: Bag.__init__=typed Bag.add=typed Bag.size=typed Bag.dump=general main=typed
class Bag:
    def __init__(self) -> None:
        self.items: list[int] = []

    def add(self, v: int) -> None:
        self.items.append(v)

    def size(self) -> int:
        return len(self.items)

    def dump(self) -> list[int]:
        return sorted(self.items)


def main() -> None:
    b = Bag()
    b.add(2)
    print(b.size())
    print(b.dump())


main()
