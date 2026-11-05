from dataclasses import dataclass


@dataclass
class Pair:
    a: int = 0
    b: int = 0

    def total(self) -> int:
        return self.a + self.b

    def bump(self, step: int) -> int:
        self.a = self.a + step
        return self.total()


def main() -> None:
    p = Pair(3, 4)
    p.bump(2)
    print(p.total())
    print(p.a, p.b)


main()
