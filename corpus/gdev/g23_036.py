# task: Find the adjugate of a hard-coded 3x3 matrix and verify that A times adjugate(A) equals det(A) times the identity, printing the result.
from typing import Sequence

Matrix = list[list[int]]


def det2(m: Sequence[Sequence[int]]) -> int:
    """Determinant of a 2x2 matrix."""
    return m[0][0] * m[1][1] - m[0][1] * m[1][0]


def minor(m: Sequence[Sequence[int]], row: int, col: int) -> Matrix:
    """Return the submatrix obtained by deleting the given row and column."""
    return [
        [m[r][c] for c in range(len(m[r])) if c != col]
        for r in range(len(m))
        if r != row
    ]


def det3(m: Sequence[Sequence[int]]) -> int:
    """Determinant of a 3x3 matrix by cofactor expansion along the first row."""
    total = 0
    for j in range(3):
        sign = 1 if j % 2 == 0 else -1
        total += sign * m[0][j] * det2(minor(m, 0, j))
    return total


def cofactor_matrix(m: Sequence[Sequence[int]]) -> Matrix:
    """Matrix of cofactors C[i][j] = (-1)^(i+j) * det(minor(i, j))."""
    result: Matrix = []
    for i in range(3):
        row: list[int] = []
        for j in range(3):
            sign = 1 if (i + j) % 2 == 0 else -1
            row.append(sign * det2(minor(m, i, j)))
        result.append(row)
    return result


def transpose(m: Sequence[Sequence[int]]) -> Matrix:
    """Return the transpose of a matrix."""
    return [[m[r][c] for r in range(len(m))] for c in range(len(m[0]))]


def adjugate(m: Sequence[Sequence[int]]) -> Matrix:
    """Adjugate (classical adjoint): transpose of the cofactor matrix."""
    return transpose(cofactor_matrix(m))


def matmul(a: Sequence[Sequence[int]], b: Sequence[Sequence[int]]) -> Matrix:
    """Multiply two matrices with exact integer arithmetic."""
    rows = len(a)
    inner = len(b)
    cols = len(b[0])
    return [
        [sum(a[i][k] * b[k][j] for k in range(inner)) for j in range(cols)]
        for i in range(rows)
    ]


def identity(n: int) -> Matrix:
    """Return the n x n identity matrix."""
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def scale(s: int, m: Sequence[Sequence[int]]) -> Matrix:
    """Multiply every entry of a matrix by a scalar."""
    return [[s * x for x in row] for row in m]


def format_matrix(name: str, m: Sequence[Sequence[int]]) -> str:
    """Format a matrix as aligned text lines."""
    width = max(len(str(x)) for row in m for x in row)
    lines = [f"{name} ="]
    for row in m:
        lines.append("  [ " + "  ".join(f"{x:>{width}}" for x in row) + " ]")
    return "\n".join(lines)


def main() -> None:
    A: Matrix = [
        [2, -3, 1],
        [2, 0, -1],
        [1, 4, 5],
    ]

    d = det3(A)
    adj = adjugate(A)
    product = matmul(A, adj)
    expected = scale(d, identity(3))
    ok = product == expected

    print(format_matrix("A", A))
    print()
    print(f"det(A) = {d}")
    print()
    print(format_matrix("adj(A)", adj))
    print()
    print(format_matrix("A * adj(A)", product))
    print()
    print(format_matrix("det(A) * I", expected))
    print()
    print(f"A * adj(A) == det(A) * I: {ok}")


if __name__ == "__main__":
    main()
