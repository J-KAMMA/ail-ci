# task: Implement a dataclass Matrix2x2 supporting __add__ and __mul__ and print the results of a few operations.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Matrix2x2:
    a: int
    b: int
    c: int
    d: int

    def __add__(self, other: object) -> Matrix2x2:
        if not isinstance(other, Matrix2x2):
            return NotImplemented
        return Matrix2x2(
            self.a + other.a,
            self.b + other.b,
            self.c + other.c,
            self.d + other.d,
        )

    def __mul__(self, other: object) -> Matrix2x2:
        if isinstance(other, Matrix2x2):
            return Matrix2x2(
                self.a * other.a + self.b * other.c,
                self.a * other.b + self.b * other.d,
                self.c * other.a + self.d * other.c,
                self.c * other.b + self.d * other.d,
            )
        if isinstance(other, int):
            return Matrix2x2(
                self.a * other,
                self.b * other,
                self.c * other,
                self.d * other,
            )
        return NotImplemented

    def __rmul__(self, other: object) -> Matrix2x2:
        if isinstance(other, int):
            return self * other
        return NotImplemented

    def __str__(self) -> str:
        return f"[[{self.a}, {self.b}], [{self.c}, {self.d}]]"


def main() -> None:
    m1 = Matrix2x2(1, 2, 3, 4)
    m2 = Matrix2x2(5, 6, 7, 8)
    identity = Matrix2x2(1, 0, 0, 1)

    print("m1 =", m1)
    print("m2 =", m2)
    print("m1 + m2 =", m1 + m2)
    print("m1 * m2 =", m1 * m2)
    print("m2 * m1 =", m2 * m1)
    print("m1 * identity =", m1 * identity)
    print("3 * m1 =", 3 * m1)
    print("m2 * -2 =", m2 * -2)
    print("m1 == m1 * identity:", m1 == m1 * identity)
    print("repr:", repr(m1 + m2))


if __name__ == "__main__":
    main()
