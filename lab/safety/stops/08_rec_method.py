class Walker:
    def __init__(self, start: int) -> None:
        self.value = start

    def step(self, n: int) -> int:
        self.value = n
        return self.step(n + 1)


walker = Walker(0)
print("prefix", walker.value)
print("start", walker.step(0))
print("unreachable", 1)
