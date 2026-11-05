class Counter:
    def __init__(self) -> None:
        self.total: int = 1

    def grow(self) -> None:
        self.total *= 2


def main() -> None:
    counter = Counter()
    for i in range(4):
        counter.grow()
    print(counter.total)
    for i in range(58):
        counter.grow()
    print(counter.total)
    counter.grow()
    print(counter.total)


main()
