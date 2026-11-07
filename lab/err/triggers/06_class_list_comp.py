class P:
    def __init__(self, x: int) -> None:
        self.x = x

def make(xs: list[int]) -> list[P]:
    return [P(x) for x in xs]

print([p.x for p in make([1, 2])])
