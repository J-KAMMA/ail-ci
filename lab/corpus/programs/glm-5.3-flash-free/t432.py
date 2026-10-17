import sys


class Matrix:
    def __init__(self, data: list[list[int]]) -> None:
        if data and any(len(row) != len(data[0]) for row in data):
            raise ValueError("all rows must have the same length")
        self.data = data
        self.rows = len(data)
        self.cols = len(data[0]) if data else 0

    def __add__(self, other: "Matrix") -> "Matrix":
        if (self.rows, self.cols) != (other.rows, other.cols):
            raise ValueError("dimension mismatch for addition")
        return Matrix(
            [[a + b for a, b in zip(r1, r2)] for r1, r2 in zip(self.data, other.data)]
        )

    def __mul__(self, other: "Matrix") -> "Matrix":
        if self.cols != other.rows:
            raise ValueError("dimension mismatch for multiplication")
        other_cols = list(zip(*other.data))
        return Matrix(
            [
                [sum(a * b for a, b in zip(row, col)) for col in other_cols]
                for row in self.data
            ]
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Matrix):
            return NotImplemented
        return self.data == other.data

    def __repr__(self) -> str:
        return "\n".join(" ".join(str(v) for v in row) for row in self.data)

    def __getitem__(self, index: tuple[int, int]) -> int:
        i, j = index
        return self.data[i][j]


def main() -> None:
    tokens = sys.stdin.read().split()
    n = int(tokens[0])
    flat = [int(tok) for tok in tokens[1 : 1 + n * n]]
    a = Matrix([flat[r * n : (r + 1) * n] for r in range(n)])
    print(a + a)
    if a.rows == a.cols:
        print(a * a)
    print(a == a)


if __name__ == "__main__":
    main()
