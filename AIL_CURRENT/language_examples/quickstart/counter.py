class Counter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.values: list[int] = []

    def add(self, value: int) -> None:
        self.values.append(value)

    def total(self) -> int:
        return sum(self.values)


def main() -> None:
    counter = Counter("demo")
    counter.add(3)
    counter.add(4)
    counter.add(5)
    print(counter.name, counter.total(), len(counter.values))


main()
