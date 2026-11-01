# task: Compute the LU decomposition without pivoting of a hard-coded 3x3 matrix and print the L and U matrices.
from fractions import Fraction


def lu_decompose(a: list[list[Fraction]]) -> tuple[list[list[Fraction]], list[list[Fraction]]]:
    """Return (L, U) with A = L * U, L unit lower triangular (Doolittle), no pivoting."""
    n = len(a)
    lower = [[Fraction(1) if i == j else Fraction(0) for j in range(n)] for i in range(n)]
    upper = [[Fraction(0) for _ in range(n)] for _ in range(n)]

    for k in range(n):
        # Row k of U
        for j in range(k, n):
            s = sum(lower[k][p] * upper[p][j] for p in range(k))
            upper[k][j] = a[k][j] - s

        if upper[k][k] == 0:
            raise ValueError(f"Zero pivot encountered at position {k}; LU without pivoting fails.")

        # Column k of L
        for i in range(k + 1, n):
            s = sum(lower[i][p] * upper[p][k] for p in range(k))
            lower[i][k] = (a[i][k] - s) / upper[k][k]

    return lower, upper


def format_matrix(m: list[list[Fraction]]) -> list[str]:
    cells = [[str(x) for x in row] for row in m]
    width = max(len(c) for row in cells for c in row)
    return ["[ " + "  ".join(c.rjust(width) for c in row) + " ]" for row in cells]


def main() -> None:
    raw = [
        [4, 3, 2],
        [6, 3, 1],
        [2, 5, 7],
    ]
    matrix = [[Fraction(x) for x in row] for row in raw]

    lower, upper = lu_decompose(matrix)

    print("A =")
    for line in format_matrix(matrix):
        print(line)
    print()
    print("L =")
    for line in format_matrix(lower):
        print(line)
    print()
    print("U =")
    for line in format_matrix(upper):
        print(line)


if __name__ == "__main__":
    main()
