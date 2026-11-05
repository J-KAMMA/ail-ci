class Counter:
    def __init__(self) -> None:
        self.total: int = 1

    def double(self) -> None:
        self.total *= 2

    def add_self(self) -> None:
        self.total += self.total


def main() -> None:
    counter = Counter()
    for i in range(4):
        counter.double()
    print(counter.total)
    for i in range(58):
        counter.double()
    print(counter.total)
    for i in range(1):
        counter.add_self()
    print(counter.total)


main()
