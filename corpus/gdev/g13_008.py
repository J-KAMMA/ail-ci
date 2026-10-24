# task: Define a Matrix base class with a multiply method and a SquareMatrix subclass that adds a trace method, then print results for fixed matrices.
from __future__ import annotations


class Matrix:
    """A simple dense matrix of numbers stored as a list of rows."""

    def __init__(self, rows: list[list[float]]) -> None:
        if not rows or not rows[0]:
            raise ValueError("Matrix must have at least one row and one column")
        width = len(rows[0])
        if any(len(row) != width for row in rows):
            raise ValueError("All rows must have the same length")
        self.rows: list[list[float]] = [list(row) for row in rows]

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rows), len(self.rows[0])

    def multiply(self, other: Matrix) -> Matrix:
        """Return the matrix product self * other."""
        n, k = self.shape
        k2, m = other.shape
        if k != k2:
            raise ValueError(
                f"Cannot multiply matrices of shape {self.shape} and {other.shape}"
            )
        result: list[list[float]] = []
        for i in range(n):
            row: list[float] = []
            for j in range(m):
                total = 0.0
                for t in range(k):
                    total += self.rows[i][t] * other.rows[t][j]
                row.append(total)
            result.append(row)
        return Matrix(result)

    def __repr__(self) -> str:
        body = ", ".join(str(row) for row in self.rows)
        return f"Matrix([{body}])"


class SquareMatrix(Matrix):
    """A Matrix whose number of rows equals its number of columns."""

    def __init__(self, rows: list[list[float]]) -> None:
        super().__init__(rows)
        n, m = self.shape
        if n != m:
            raise ValueError(f"SquareMatrix must be square, got shape {self.shape}")

    def trace(self) -> float:
        """Return the sum of the main diagonal elements."""
        return sum(self.rows[i][i] for i in range(len(self.rows)))

    def multiply(self, other: Matrix) -> SquareMatrix:
        """Multiply by another square matrix of the same size, returning a SquareMatrix."""
        product = super().multiply(other)
        return SquareMatrix(product.rows)


def main() -> None:
    a = Matrix([[1, 2, 3], [4, 5, 6]])
    b = Matrix([[7, 8], [9, 10], [11, 12]])
    print("A =", a)
    print("B =", b)
    print("A * B =", a.multiply(b))
    print("Shape of A * B:", a.multiply(b).shape)

    s = SquareMatrix([[2, 0, 1], [1, 3, 2], [1, 1, 1]])
    t = SquareMatrix([[1, 4, 0], [0, 1, 5], [2, 0, 1]])
    print("S =", s)
    print("T =", t)
    print("S * T =", s.multiply(t))
    print("trace(S) =", s.trace())
    print("trace(T) =", t.trace())
    print("trace(S * T) =", s.multiply(t).trace())

    identity = SquareMatrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    print("S * I =", s.multiply(identity))
    print("trace(I) =", identity.trace())


if __name__ == "__main__":
    main()
