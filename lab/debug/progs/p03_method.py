class Counter:
    def __init__(self, start: int) -> None:
        self.value = start

    def bump(self, by: int) -> int:
        self.value += by
        return self.value


def main() -> None:
    c = Counter(3)
    c.bump(4)
    print(c.bump(5))


main()
