from __future__ import annotations

import sys
from typing import Iterator


class Matrix:
    def __init__(self, rows: list[list[int]]) -> None:
        if not rows or any(len(row) != len(rows) for row in rows):
            raise ValueError("matrix must be non-empty and square-shaped rows")
        self.rows = [list(row) for row in rows]
        self.n = len(self.rows)

    def __add__(self, other: Matrix) -> Matrix:
        if self.n != other.n:
            raise ValueError("dimension mismatch for addition")
        result = [
            [self.rows[i][j] + other.rows[i][j] for j in range(self.n)]
            for i in range(self.n)
        ]
        return Matrix(result)

    def __mul__(self, other: Matrix) -> Matrix:
        if self.n != other.n:
            raise ValueError("dimension mismatch for multiplication")
        n = self.n
        result = [[0] * n for _ in range(n)]
        for i in range(n):
            for k in range(n):
                a = self.rows[i][k]
                if a == 0:
                    continue
                for j in range(n):
                    result[i][j] += a * other.rows[k][j]
        return Matrix(result)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Matrix):
            return NotImplemented
        return self.n == other.n and self.rows == other.rows

    def __repr__(self) -> str:
        return "\n".join(" ".join(str(value) for value in row) for row in self.rows)

    def __getitem__(self, index: int) -> list[int]:
        return self.rows[index]


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    it: Iterator[str] = iter(data)
    n = int(next(it))
    rows = [[int(next(it)) for _ in range(n)] for _ in range(n)]
    a = Matrix(rows)

    print(a + a)
    print()
    print(a * a)
    print()
    print(a == a)


if __name__ == "__main__":
    main()
