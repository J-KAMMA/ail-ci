import sys
from typing import Sequence


class Matrix:
    """A simple rectangular matrix of integers."""

    def __init__(self, data: Sequence[Sequence[int]]) -> None:
        rows = [list(row) for row in data]
        if rows:
            width = len(rows[0])
            if any(len(row) != width for row in rows):
                raise ValueError("all rows must have the same length")
        else:
            width = 0
        self._data: list[list[int]] = rows
        self._rows: int = len(rows)
        self._cols: int = width

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    def __add__(self, other: "Matrix") -> "Matrix":
        if not isinstance(other, Matrix):
            return NotImplemented
        if self.rows != other.rows or self.cols != other.cols:
            raise ValueError("matrix dimensions must match for addition")
        return Matrix(
            [
                [self._data[i][j] + other._data[i][j] for j in range(self.cols)]
                for i in range(self.rows)
            ]
        )

    def __mul__(self, other: "Matrix") -> "Matrix":
        if not isinstance(other, Matrix):
            return NotImplemented
        if self.cols != other.rows:
            raise ValueError("inner dimensions must match for multiplication")
        result = [[0] * other.cols for _ in range(self.rows)]
        for i in range(self.rows):
            for k in range(self.cols):
                a = self._data[i][k]
                if a == 0:
                    continue
                row_k = other._data[k]
                out_row = result[i]
                for j in range(other.cols):
                    out_row[j] += a * row_k[j]
        return Matrix(result)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Matrix):
            return NotImplemented
        return self.rows == other.rows and self._data == other._data

    def __getitem__(self, idx: int | tuple[int, int]) -> int | list[int]:
        if isinstance(idx, tuple):
            i, j = idx
            return self._data[i][j]
        return self._data[idx]

    def __repr__(self) -> str:
        return "\n".join(" ".join(str(x) for x in row) for row in self._data)


def main() -> None:
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    values = list(map(int, tokens[1:1 + n * n]))
    data = [values[i * n:(i + 1) * n] for i in range(n)]
    a = Matrix(data)

    print(a + a)
    print(a * a)
    print(a == a)


if __name__ == "__main__":
    main()
