from ail.types import BigInt


class Counter:
    total: BigInt = 0

    def __init__(self) -> None:
        self.total = 0

    def bump(self, amount: int) -> None:
        self.total = self.total + amount


c = Counter()
i = 0
while i < 1000:
    c.bump(1)
    i = i + 1
big: BigInt = 2 ** 70
c.total = c.total + big
print(c.total)
